"""Ordered, fail-closed requirements for registered study protocols."""


def require(condition: bool, message: str) -> None:
    """Reject the first unmet requirement without collecting later failures."""
    if not condition:
        raise ValueError(message)
