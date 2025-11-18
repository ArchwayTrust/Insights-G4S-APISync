"""
Azure Key Vault Integration Module
Handles retrieving secrets from Azure Key Vault for API authentication
"""

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from typing import Dict
import logging


class KeyVaultClient:
    """Client for retrieving secrets from Azure Key Vault"""
    
    def __init__(self, vault_url: str):
        """
        Initialize the Key Vault client
        
        Args:
            vault_url: Key Vault URL (e.g., "https://your-keyvault.vault.azure.net/")
        """
        self.vault_url = vault_url
        self.credential = DefaultAzureCredential()
        self.client = SecretClient(vault_url=vault_url, credential=self.credential)
        self.logger = logging.getLogger(__name__)
        
    def get_secret(self, secret_name: str) -> str:
        """
        Retrieve a secret from Key Vault
        
        Args:
            secret_name: Name of the secret to retrieve
            
        Returns:
            Secret value as string
        """
        try:
            secret = self.client.get_secret(secret_name)
            self.logger.info(f"Successfully retrieved secret: {secret_name}")
            return secret.value
        except Exception as e:
            self.logger.error(f"Failed to retrieve secret {secret_name}: {str(e)}")
            raise
            
    def get_multiple_secrets(self, secret_names: list) -> Dict[str, str]:
        """
        Retrieve multiple secrets from Key Vault
        
        Args:
            secret_names: List of secret names to retrieve
            
        Returns:
            Dictionary mapping secret names to their values
        """
        secrets = {}
        for name in secret_names:
            try:
                secrets[name] = self.get_secret(name)
            except Exception as e:
                self.logger.error(f"Failed to retrieve secret {name}: {str(e)}")
                secrets[name] = None
        return secrets


def get_api_key_from_keyvault(vault_url: str, secret_name: str) -> str:
    """
    Helper function to retrieve an API key from Key Vault
    
    Args:
        vault_url: Key Vault URL
        secret_name: Name of the secret containing the API key
        
    Returns:
        API key as string
    """
    kv_client = KeyVaultClient(vault_url)
    return kv_client.get_secret(secret_name)
