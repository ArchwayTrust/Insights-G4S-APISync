"""
Azure Key Vault Integration Module
Handles retrieving secrets from Azure Key Vault using Fabric notebookutils
"""

from typing import Dict
import logging


def get_secret(vault_url: str, secret_name: str) -> str:
    """
    Retrieve a secret from Key Vault using Fabric notebookutils
    
    Args:
        vault_url: Key Vault URL (e.g., "https://your-keyvault.vault.azure.net/")
        secret_name: Name of the secret to retrieve
        
    Returns:
        Secret value as string
        
    Note:
        Uses Fabric's native notebookutils.credentials.getSecret() which handles
        authentication automatically using the workspace identity.
        Format: notebookutils.credentials.getSecret('https://<name>.vault.azure.net/', 'secret-name')
    """
    try:
        # Use Fabric's native Key Vault integration
        import notebookutils
        secret_value = notebookutils.credentials.getSecret(vault_url, secret_name)
        return secret_value
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to retrieve secret {secret_name} from {vault_url}: {str(e)}")
        raise Exception(f"Failed to retrieve secret '{secret_name}': {str(e)}")


def get_multiple_secrets(vault_url: str, secret_names: list) -> Dict[str, str]:
    """
    Retrieve multiple secrets from Key Vault
    
    Args:
        vault_url: Key Vault URL
        secret_names: List of secret names to retrieve
        
    Returns:
        Dictionary mapping secret names to their values
    """
    logger = logging.getLogger(__name__)
    secrets = {}
    for name in secret_names:
        try:
            secrets[name] = get_secret(vault_url, name)
        except Exception as e:
            logger.error(f"Failed to retrieve secret {name}: {str(e)}")
            secrets[name] = None
    return secrets


def get_api_key_from_keyvault(vault_url: str, secret_name: str) -> str:
    """
    Helper function to retrieve an API key from Key Vault
    
    Args:
        vault_url: Key Vault URL (e.g., "https://your-keyvault.vault.azure.net/")
        secret_name: Name of the secret containing the API key
        
    Returns:
        API key as string
    """
    return get_secret(vault_url, secret_name)
