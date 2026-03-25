"""Paper-trading guard. Prevents any order submission on live accounts."""

PAPER_PORTS = (4002,)


class LiveTradingBlocked(RuntimeError):
    """Raised when an order is attempted on a non-paper-trading connection."""
    pass


def assert_paper_trading(ib) -> None:
    """Hard check that we're connected to a paper trading port."""
    port = ib.client.port
    if port not in PAPER_PORTS:
        raise LiveTradingBlocked(
            f"BLOCKED: Connected to port {port}, which is NOT a paper trading port. "
            f"Only ports {PAPER_PORTS} are allowed for order submission. "
            f"Refusing to place any orders."
        )
