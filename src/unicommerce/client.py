"""
Unicommerce REST API client.

Handles OAuth2 auth, token refresh, request retry, facility discovery,
and pagination for the Unicommerce API.
"""
import time
import logging
import requests
from config.settings import (
    UC_BASE_URL, UC_USERNAME, UC_PASSWORD, UC_TENANT,
    UC_TOKEN_EXPIRY_BUFFER, UC_FACILITIES_FALLBACK,
)

logger = logging.getLogger(__name__)

# Gentle throttle between paginated calls (seconds)
PAGE_DELAY = 0.5


class UnicommerceError(Exception):
    """Raised when UC API returns an error response."""
    def __init__(self, message, errors=None):
        super().__init__(message)
        self.errors = errors or []


class UnicommerceClient:
    """REST client for the Unicommerce API."""

    def __init__(self, tenant=None, username=None, password=None):
        self.tenant = tenant or UC_TENANT
        self.base_url = f"https://{self.tenant}.unicommerce.com"
        self.username = username or UC_USERNAME
        self.password = password or UC_PASSWORD
        self.access_token = None
        self.refresh_token = None
        self.token_expiry = 0
        self.facilities = None
        self._session = requests.Session()

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def authenticate(self):
        """Obtain access token via OAuth2 password grant."""
        url = f"{self.base_url}/oauth/token"
        params = {
            "grant_type": "password",
            "client_id": "my-trusted-client",
            "username": self.username,
            "password": self.password,
        }
        logger.info("Authenticating with Unicommerce as %s", self.username)
        resp = self._session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        self.access_token = data["access_token"]
        self.refresh_token = data.get("refresh_token")
        self.token_expiry = time.time() + data.get("expires_in", 43200)
        logger.info("Authenticated. Token expires in %ds", data.get("expires_in", 0))

    def _ensure_token(self):
        """Refresh token if expired or close to expiry."""
        if self.access_token and time.time() < self.token_expiry - UC_TOKEN_EXPIRY_BUFFER:
            return
        if self.refresh_token:
            try:
                self._refresh_auth()
                return
            except Exception:
                logger.warning("Token refresh failed, re-authenticating")
        self.authenticate()

    def _refresh_auth(self):
        """Refresh access token using refresh_token grant."""
        url = f"{self.base_url}/oauth/token"
        params = {
            "grant_type": "refresh_token",
            "client_id": "my-trusted-client",
            "refresh_token": self.refresh_token,
        }
        resp = self._session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        self.access_token = data["access_token"]
        self.refresh_token = data.get("refresh_token", self.refresh_token)
        self.token_expiry = time.time() + data.get("expires_in", 43200)
        logger.info("Token refreshed. Expires in %ds", data.get("expires_in", 0))

    # ------------------------------------------------------------------
    # Request helper
    # ------------------------------------------------------------------

    def _request(self, method, path, json=None, facility=None, retries=3, timeout=60):
        """
        Send a request to the UC API with retry, backoff, and 401 re-auth.

        Args:
            method: HTTP method (GET, POST)
            path: API path (e.g. /services/rest/v1/...)
            json: Request body
            facility: Facility code for Facility header
            retries: Number of retries on failure
            timeout: Request timeout in seconds

        Returns:
            Parsed JSON response dict
        """
        self._ensure_token()
        url = f"{self.base_url}{path}"

        for attempt in range(retries):
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            }
            if facility:
                headers["Facility"] = facility

            start = time.time()
            try:
                resp = self._session.request(
                    method, url, json=json, headers=headers, timeout=timeout
                )
            except requests.exceptions.RequestException as e:
                logger.warning("Request failed (attempt %d/%d): %s %s — %s",
                               attempt + 1, retries, method, path, e)
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise

            elapsed = time.time() - start
            logger.debug("%s %s → %d (%.1fs)", method, path, resp.status_code, elapsed)

            if resp.status_code == 401:
                logger.warning("401 Unauthorized, re-authenticating (attempt %d/%d)",
                               attempt + 1, retries)
                self.authenticate()
                continue

            if resp.status_code == 429:
                wait = 2 ** attempt
                logger.warning("429 Rate limited, waiting %ds (attempt %d/%d)",
                               wait, attempt + 1, retries)
                time.sleep(wait)
                continue

            resp.raise_for_status()
            data = resp.json()

            # Check UC error envelope
            if isinstance(data, dict) and data.get("successful") is False:
                errors = data.get("errors", [])
                msg = data.get("message", "Unknown UC API error")
                error_details = "; ".join(
                    f"{e.get('code', '?')}: {e.get('description', e.get('message', ''))}"
                    for e in errors
                )
                raise UnicommerceError(f"{msg} — {error_details}", errors=errors)

            return data

        raise UnicommerceError(f"UC API failed after {retries} retries: {method} {path}")

    # ------------------------------------------------------------------
    # Facility discovery
    # ------------------------------------------------------------------

    def discover_facilities(self):
        """
        Discover active facility codes.

        Falls back to UC_FACILITIES env var if the API endpoint is unavailable.
        Also stores discovered facilities in the DB (if db_conn provided).
        """
        try:
            data = self._request("GET", "/services/rest/v1/logistics/facility/get")
            facilities_data = data.get("facilities", data.get("elements", []))
            if facilities_data:
                self.facilities = [
                    f.get("code") or f.get("facilityCode")
                    for f in facilities_data
                    if f.get("enabled", True)
                ]
                if self.facilities:
                    logger.info("Discovered %d facilities: %s",
                                len(self.facilities), self.facilities)
                    return self.facilities
        except Exception as e:
            logger.warning("Facility discovery failed (%s), using fallback", e)

        self.facilities = list(UC_FACILITIES_FALLBACK)
        logger.info("Using fallback facilities: %s", self.facilities)
        return self.facilities

    def store_facilities(self, db_conn):
        """Persist discovered facilities to the DB."""
        if not self.facilities:
            return
        with db_conn.cursor() as cur:
            for code in self.facilities:
                cur.execute("""
                    INSERT INTO facilities (code, is_active, last_seen_at)
                    VALUES (%s, TRUE, NOW())
                    ON CONFLICT (code) DO UPDATE
                    SET is_active = TRUE, last_seen_at = NOW()
                """, (code,))
        db_conn.commit()

    # ------------------------------------------------------------------
    # Pagination helper
    # ------------------------------------------------------------------

    def paginate(self, path, body, facility=None, page_size=100,
                 elements_key="elements"):
        """
        Yield all elements across paginated results.

        Args:
            path: API endpoint path
            body: Request body (pageNumber/pageSize added automatically)
            facility: Facility header
            page_size: Items per page
            elements_key: Key in response containing the results list
        """
        page = 1
        total_yielded = 0
        while True:
            body_with_page = {**body, "pageNumber": page, "pageSize": page_size}
            data = self._request("POST", path, json=body_with_page, facility=facility)
            elements = data.get(elements_key, [])
            if not elements:
                break
            yield from elements
            total_yielded += len(elements)
            if len(elements) < page_size:
                break
            page += 1
            time.sleep(PAGE_DELAY)
        logger.debug("Paginated %s: %d total elements across %d pages",
                      path, total_yielded, page)

    # ------------------------------------------------------------------
    # Convenience: iterate GRN codes from list endpoint
    # ------------------------------------------------------------------

    def iter_grn_codes(self, body, facility=None):
        """Yield GRN codes from the getInflowReceipts list endpoint."""
        data = self._request(
            "POST",
            "/services/rest/v1/purchase/inflowReceipt/getInflowReceipts",
            json=body,
            facility=facility,
        )
        receipts = data.get("inflowReceipts", [])
        for receipt in receipts:
            code = receipt.get("code") or receipt.get("inflowReceiptCode")
            if code:
                yield code
