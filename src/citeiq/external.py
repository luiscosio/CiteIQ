"""External metadata clients (Crossref, OpenAlex, Unpaywall, etc.) with basic caching."""

from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

import orjson
import requests

LOGGER = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": "CiteIQ/0.1 (mailto:metadata@citeiq.local)",
}


class APICache:
    """Simple file-based cache backed by JSON blobs on disk."""

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _key_to_path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.json"

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        path = self._key_to_path(key)
        if not path.exists():
            return None
        try:
            return orjson.loads(path.read_bytes())
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Failed to read cache entry %s: %s", path, exc)
            return None

    def set(self, key: str, value: Dict[str, Any]) -> None:
        path = self._key_to_path(key)
        path.write_bytes(orjson.dumps(value))


class ExternalMetadataService:
    """Wraps remote lookups with caching and graceful fallbacks."""

    def __init__(
        self,
        cache_dir: Path,
        crossref_endpoint: str = "https://api.crossref.org",
        openalex_endpoint: str = "https://api.openalex.org",
        unpaywall_endpoint: str = "https://api.unpaywall.org",
        email: Optional[str] = None,
        per_request_pause: float = 0.2,
    ) -> None:
        self.cache = APICache(cache_dir)
        self.crossref_endpoint = crossref_endpoint.rstrip("/")
        self.openalex_endpoint = openalex_endpoint.rstrip("/")
        self.unpaywall_endpoint = unpaywall_endpoint.rstrip("/")
        self.email = email
        self.per_request_pause = per_request_pause

    def _request_json(self, url: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        cache_key = f"{url}?{orjson.dumps(params).decode('utf-8') if params else ''}"
        if cached := self.cache.get(cache_key):
            return cached
        headers = DEFAULT_HEADERS.copy()
        if self.email:
            headers["User-Agent"] = f"CiteIQ/0.1 (mailto:{self.email})"
        try:
            response = requests.get(url, params=params, headers=headers, timeout=20)
            if response.status_code == 200:
                payload = response.json()
                self.cache.set(cache_key, payload)
                time.sleep(self.per_request_pause)
                return payload
            LOGGER.warning("Non-200 response %s for %s", response.status_code, url)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Failed request %s params=%s: %s", url, params, exc)
        return None

    # Crossref methods
    def crossref_get_work(self, doi: str) -> Optional[Dict[str, Any]]:
        doi = doi.lower()
        url = f"{self.crossref_endpoint}/works/{doi}"
        return self._request_json(url)

    def crossref_search_bibliographic(self, query: str) -> Optional[Dict[str, Any]]:
        url = f"{self.crossref_endpoint}/works"
        params = {"query.bibliographic": query, "rows": 3}
        return self._request_json(url, params=params)

    # OpenAlex
    def openalex_get_work(self, identifier: str) -> Optional[Dict[str, Any]]:
        # identifier can be doi:10.1234/abc
        url = f"{self.openalex_endpoint}/works/{identifier}"
        return self._request_json(url)

    def openalex_search(self, doi: Optional[str] = None, title: Optional[str] = None) -> Optional[Dict[str, Any]]:
        url = f"{self.openalex_endpoint}/works"
        if doi:
            params = {"filter": f"doi:{doi}"}
        elif title:
            params = {"search": title, "per-page": 3}
        else:
            return None
        return self._request_json(url, params=params)

    # Unpaywall
    def unpaywall_get(self, doi: str) -> Optional[Dict[str, Any]]:
        if not self.email:
            LOGGER.debug("Skipping Unpaywall for %s due to missing email", doi)
            return None
        url = f"{self.unpaywall_endpoint}/v2/{doi}"
        params = {"email": self.email}
        return self._request_json(url, params=params)

