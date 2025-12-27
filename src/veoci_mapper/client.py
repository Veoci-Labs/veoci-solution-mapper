"""Veoci API client with Bearer token authentication."""

from typing import Any

import httpx


class VeociClientError(Exception):
    """Base exception for Veoci client errors."""
    pass


class AuthenticationError(VeociClientError):
    """Raised when authentication fails (401/403)."""
    pass


class NotFoundError(VeociClientError):
    """Raised when resource is not found (404)."""
    pass


class VeociClient:
    """
    Async HTTP client for Veoci V2 API.

    Usage:
        async with VeociClient(token="pat_xxx") as client:
            forms = await client.get("/forms", params={"containerId": "room-123"})
    """

    def __init__(
        self,
        token: str,
        base_url: str = "https://veoci.com",
    ):
        self.token = token
        self.base_url = base_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def __aenter__(self) -> "VeociClient":
        self._client = httpx.AsyncClient(
            base_url=f"{self.base_url}/api/v2",
            headers=self._headers,
            timeout=30.0,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _handle_response(self, response: httpx.Response) -> Any:
        """Handle response and raise appropriate errors."""
        if response.status_code == 401:
            raise AuthenticationError("Invalid or expired token")
        if response.status_code == 403:
            raise AuthenticationError("Access denied - check token permissions")
        if response.status_code == 404:
            raise NotFoundError(f"Resource not found: {response.url}")

        response.raise_for_status()

        if response.headers.get("content-type", "").startswith("application/json"):
            return response.json()
        return response.text

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Make GET request to Veoci API."""
        if not self._client:
            raise VeociClientError("Client not initialized. Use 'async with' context manager.")

        response = await self._client.get(path, params=params)
        return self._handle_response(response)

    async def post(self, path: str, json: dict[str, Any] | None = None) -> Any:
        """Make POST request to Veoci API."""
        if not self._client:
            raise VeociClientError("Client not initialized. Use 'async with' context manager.")

        response = await self._client.post(path, json=json)
        return self._handle_response(response)
