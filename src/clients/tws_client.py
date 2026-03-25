"""TWS client abstraction — wraps ib_insync connection lifecycle."""

from __future__ import annotations

import logging

from src.config.settings import get_settings

logger = logging.getLogger("gap_vwap_bot.tws")


class TWSClient:
    """Thin wrapper around ib_insync.IB for the gap-down VWAP reclaim bot."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        client_id: int | None = None,
    ):
        settings = get_settings()
        self.host = host or settings.ibkr_host
        self.port = port or settings.ibkr_port
        self.client_id = client_id or settings.ibkr_client_id
        self._ib: object | None = None

    def connect(self) -> None:
        from ib_insync import IB

        self._ib = IB()
        logger.info(f"Connecting to TWS at {self.host}:{self.port} (clientId={self.client_id})")
        self._ib.connect(self.host, self.port, clientId=self.client_id, timeout=15)
        self._ib.reqMarketDataType(3)
        logger.info("TWS connection established (delayed data enabled as fallback)")

    def disconnect(self) -> None:
        if self._ib:
            try:
                self._ib.disconnect()
                logger.info("TWS disconnected")
            except Exception:
                pass
            self._ib = None

    @property
    def ib(self):
        if self._ib is None:
            raise RuntimeError("TWS client not connected. Call connect() first.")
        return self._ib

    @property
    def is_connected(self) -> bool:
        return self._ib is not None and self._ib.isConnected()

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.disconnect()
