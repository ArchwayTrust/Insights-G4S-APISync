"""
G4S API Client Module for PySpark/Fabric
Handles API authentication and data retrieval from Go4Schools API
"""

import requests
import time
from typing import List, Dict, Optional, Any
from urllib.parse import urlencode
import json


class G4SApiClient:
    """Client for interacting with the Go4Schools API"""
    
    def __init__(self, api_key: str, base_url: str = "https://api.go4schools.com"):
        """
        Initialize the G4S API client
        
        Args:
            api_key: Bearer token for API authentication
            base_url: Base URL for the API (default: https://api.go4schools.com)
        """
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
    def _make_request(
        self, 
        endpoint: str, 
        params: Dict[str, Any], 
        cursor: Optional[int] = None,
        timeout: int = 600,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Make a GET request to the API with retry logic
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            cursor: Pagination cursor
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            
        Returns:
            JSON response as dictionary
        """
        if cursor is not None:
            params['cursor'] = cursor
            
        url = f"{self.base_url}{endpoint}"
        
        for attempt in range(max_retries):
            try:
                response = requests.get(
                    url,
                    headers=self.headers,
                    params=params,
                    timeout=timeout
                )
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:  # Rate limit
                    wait_time = int(response.headers.get('Retry-After', 60))
                    time.sleep(wait_time)
                    continue
                else:
                    raise Exception(
                        f"API request failed with status {response.status_code}: "
                        f"{response.text}"
                    )
                    
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                else:
                    raise Exception(f"API request failed after {max_retries} attempts: {str(e)}")
                    
        raise Exception(f"API request failed after {max_retries} attempts")
    
    def fetch_all_data(
        self, 
        endpoint: str,
        academic_year: str,
        year_group: Optional[str] = None,
        report_id: Optional[str] = None,
        date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch all data from a paginated endpoint
        
        Args:
            endpoint: API endpoint path (e.g., "/customer/v1/academic-years/{academicYear}/students")
            academic_year: Academic year code (e.g., "2324")
            year_group: Optional year group filter
            report_id: Optional report ID
            date: Optional date filter in YYYY-MM-DD format
            
        Returns:
            List of all records from paginated API
        """
        # Replace {academicYear} placeholder
        endpoint = endpoint.replace("{academicYear}", academic_year)
        
        if date:
            endpoint = endpoint.replace("{date}", date)
        
        params = {}
        if year_group:
            params['yearGroup'] = year_group
        if report_id:
            params['reportId'] = report_id
        if date and '{date}' not in endpoint:
            params['date'] = date
            
        all_data = []
        cursor = None
        has_more = True
        
        while has_more:
            response = self._make_request(endpoint, params, cursor)
            
            # Extract data from response - the key varies by endpoint
            # Common keys: students, groups, teachers, etc.
            data_key = None
            for key in response.keys():
                if isinstance(response[key], list):
                    data_key = key
                    break
                    
            if data_key:
                all_data.extend(response[data_key])
            
            has_more = response.get('has_more', False)
            cursor = response.get('cursor')
            
        return all_data
    
    def fetch_data_with_metadata(
        self, 
        endpoint: str,
        academic_year: str,
        academy_code: str,
        year_group: Optional[str] = None,
        report_id: Optional[str] = None,
        date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetch all data and return with metadata for tracking
        
        Args:
            endpoint: API endpoint path
            academic_year: Academic year code
            academy_code: Academy identifier
            year_group: Optional year group filter
            report_id: Optional report ID
            date: Optional date filter
            
        Returns:
            Dictionary with 'data', 'endpoint', 'academic_year', 'academy_code', and 'fetched_at'
        """
        from datetime import datetime
        
        data = self.fetch_all_data(endpoint, academic_year, year_group, report_id, date)
        
        return {
            'endpoint': endpoint,
            'academic_year': academic_year,
            'academy_code': academy_code,
            'data': data,
            'fetched_at': datetime.utcnow().isoformat(),
            'record_count': len(data)
        }
