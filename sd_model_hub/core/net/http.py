"""A shared httpx client that follows the network settings."""

import threading

import httpx

from sd_model_hub.core.settings import SettingsService
from sd_model_hub.version import VERSION


class HttpClientProvider:
    """Hands out one ``httpx.Client``, rebuilt when the proxy or timeout changes."""

    def __init__(self, settings: SettingsService, transport: httpx.BaseTransport | None = None) -> None:
        self._settings = settings
        self._transport = transport
        self._lock = threading.Lock()
        self._client: httpx.Client | None = None
        self._key: tuple[str | None, float] | None = None

    def get(self) -> httpx.Client:
        net = self._settings.settings.network
        key = (net.proxy, net.timeout)
        with self._lock:
            if self._client is None or key != self._key:
                # A replaced client is not closed here: running jobs may still hold it.
                self._client = httpx.Client(
                    proxy=net.proxy or None,
                    timeout=httpx.Timeout(net.timeout, connect=min(net.timeout, 15.0)),
                    follow_redirects=True,
                    headers={"User-Agent": f"sd-model-hub/{VERSION}"},
                    transport=self._transport,
                )
                self._key = key
            return self._client

    def close(self) -> None:
        with self._lock:
            if self._client is not None:
                self._client.close()
                self._client = None
