from typing import Any

import requests
from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError


class DifyfsProvider(ToolProvider):

    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        try:
            endpoint = credentials["service_api_endpoint"].rstrip("/")
            api_key = credentials["api_key"]
            resp = requests.get(
                f"{endpoint}/datasets",
                headers={"Authorization": f"Bearer {api_key}"},
                params={"page": 1, "limit": 1},
                timeout=10,
            )
            if resp.status_code == 401:
                raise ValueError("Invalid API key")
            if resp.status_code != 200:
                raise ValueError(f"API returned {resp.status_code}: {resp.text[:200]}")
            data = resp.json()
            if "data" not in data:
                raise ValueError("Unexpected response format from Dify API")
        except requests.exceptions.ConnectionError:
            raise ToolProviderCredentialValidationError(
                f"Cannot connect to {credentials.get('service_api_endpoint')}. Check endpoint."
            )
        except ValueError as e:
            raise ToolProviderCredentialValidationError(str(e))
        except Exception as e:
            raise ToolProviderCredentialValidationError(str(e))
