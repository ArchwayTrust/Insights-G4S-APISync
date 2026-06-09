using System;
using System.Collections.Generic;
using System.Linq;
using System.Net.Http;
using RestSharp;
using Newtonsoft.Json;
using System.Web;
using System.Threading;
using System.Threading.Tasks;

namespace G4SApiSync.Client
{
    class APIRequest<EndPoint, DTO> : IAPIRequest<EndPoint, DTO>
        where EndPoint : IEndPoint<DTO>
    {
        private string pResource;
        private string pBearer;
        private string pAcYear;
        private string pYearGroup;
        private string pReportId;
        private string pDate;
        private RestClient pClient;

        // Resilience tuning for transient API failures (timeouts, 5xx, 429).
        // Retries are applied per page inside ReturnedJSON, so a late-page failure does not refetch earlier pages.
        private const int MaxRetries = 3;                 // attempts after the first try (4 total)
        private const int BaseDelayMs = 2000;             // exponential backoff base: ~2s, 4s, 8s (+ jitter)
        private const int MaxRetryAfterSeconds = 60;      // cap on an honoured Retry-After header

        // HTTP status codes worth retrying. Everything else (401/403/404, etc.) fails fast.
        private static readonly HashSet<int> TransientStatusCodes = new() { 408, 429, 500, 502, 503, 504 };

        public APIRequest(RestClient client, string EndPointURL, string Bearer, string DataSet, string YearGroup = null, string ReportId = null, DateTime? Date = null)
        {
            pResource = EndPointURL;
            pBearer = Bearer;
            pAcYear = DataSet;
            pYearGroup = YearGroup;
            pReportId = ReportId;

            if (Date != null)
            {
                pDate = Date.Value.ToString("yyyy-MM-dd");
            }
            else 
            {
                pDate = null;
            };

            pClient = client;
        }

        public string ReturnedJSON(int? cursor)
        {
            //Use RestSharp to query G4S API
            string fullResource;

            if (cursor == null)
            {
                fullResource = pResource;
            }
            else
            {
                fullResource = pResource + "?cursor=" + HttpUtility.UrlEncode(cursor.ToString());
            }

            var request = new RestRequest(fullResource, Method.Get);
            request.Timeout = TimeSpan.FromMilliseconds(600000);
            request.AddHeader("Authorization", "Bearer " + pBearer);
            request.AddParameter("academicYear", pAcYear);

            if (pYearGroup != null)
            {
                request.AddParameter("yearGroup", pYearGroup);
            }

            if (pReportId != null)
            {
                request.AddParameter("reportId", pReportId);
            }

            if (pDate != null)
            {
                request.AddParameter("date", pDate);
            }

            RestResponse response = GetWithRetry(request);

            string content = response.Content; // Returned JSON as string.
            return content;
        }

        // Performs the GET with bounded retries for transient failures. Transient transport
        // exceptions (timeouts, connection resets) and transient HTTP status codes are retried
        // with exponential backoff + jitter; permanent errors throw immediately, as before.
        private RestResponse GetWithRetry(RestRequest request)
        {
            int attempt = 0;

            while (true)
            {
                attempt++;

                try
                {
                    RestResponse response = pClient.Get(request);
                    int status = (int)response.StatusCode;

                    if (status == 200)
                    {
                        return response;
                    }

                    // Transient HTTP status (5xx, 429, 408): back off and retry if budget remains.
                    if (TransientStatusCodes.Contains(status) && attempt <= MaxRetries)
                    {
                        Thread.Sleep(RetryDelayMs(attempt, response));
                        continue;
                    }

                    // Permanent error, or transient but out of retries: fail as the original code did.
                    throw new APICallException(status + " - " + response.StatusDescription);
                }
                catch (Exception ex) when (IsTransientException(ex) && attempt <= MaxRetries)
                {
                    // Transient transport failure (timeout / connection reset): back off and retry.
                    Thread.Sleep(RetryDelayMs(attempt, null));
                }
            }
        }

        // Backoff for the next attempt. Honours Retry-After on a 429 when present, otherwise
        // uses exponential backoff (BaseDelayMs * 2^(attempt-1)) plus up to 1s of jitter.
        private static int RetryDelayMs(int attempt, RestResponse response)
        {
            if (response != null && (int)response.StatusCode == 429)
            {
                var retryAfter = response.Headers?
                    .FirstOrDefault(h => string.Equals(h.Name, "Retry-After", StringComparison.OrdinalIgnoreCase));

                if (retryAfter?.Value != null
                    && int.TryParse(retryAfter.Value.ToString(), out int seconds)
                    && seconds > 0)
                {
                    return Math.Min(seconds, MaxRetryAfterSeconds) * 1000;
                }
            }

            int backoff = BaseDelayMs * (int)Math.Pow(2, attempt - 1);
            return backoff + Random.Shared.Next(0, 1000);
        }

        // True for transport-level failures that are worth retrying. APICallException (a non-200
        // HTTP status we raised ourselves) is intentionally NOT transient here.
        private static bool IsTransientException(Exception ex)
        {
            return ex is HttpRequestException
                || ex is TaskCanceledException
                || ex is TimeoutException
                || ex is OperationCanceledException
                || (ex.InnerException != null && IsTransientException(ex.InnerException));
        }

        public List<DTO> ToList()
        {
            List<DTO> listToReturn = new List<DTO>();
            string JSONContent;

            JSONContent = ReturnedJSON(null);

            try
            {
                EndPoint obj = JsonConvert.DeserializeObject<EndPoint>(JSONContent);
                listToReturn.AddRange(obj.DTOs);

                while (obj.HasMore)
                {
                    int? cursor = obj.Cursor;
                    JSONContent = ReturnedJSON(cursor);
                    obj = JsonConvert.DeserializeObject<EndPoint>(JSONContent);
                    listToReturn.AddRange(obj.DTOs);
                }

            }

            // Only fall back on a JSON *shape* mismatch (envelope -> bare list -> single object).
            // Transport/API failures (APICallException, timeouts) must propagate so the endpoint
            // records the real error instead of silently returning stale/partial data.
            catch (JsonException)
            {
                try
                {
                    List<DTO> obj = JsonConvert.DeserializeObject<List<DTO>>(JSONContent);
                    listToReturn = obj;
                }
                catch (JsonException)
                {
                    DTO obj = JsonConvert.DeserializeObject<DTO>(JSONContent);
                    listToReturn.Add(obj);
                }

            }

            Thread.Sleep(200);
            return listToReturn;

        }
    }
}
