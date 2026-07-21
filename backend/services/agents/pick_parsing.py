"""Parsing and sanity-checking of model-produced trade levels.

The stock analysis agent returns free text. It has produced entry zones like
"140-150", "$140 - $150" and "140". None of those survive float(), which is why
every pick was silently discarded before.

Parsing them is only half the job. A parsed number can still be nonsense: the
model has returned an entry zone of 140-150 for a stock trading at 327. Levels
are therefore validated against a live quote and rejected when they are too far
away to be a real setup.
"""

import logging
import re
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# A pick whose entry midpoint sits further than this from the live price is
# treated as a model error rather than a trade idea.
MAX_ENTRY_DEVIATION = 0.20

_NUMBER = r"[-+]?\d[\d,]*\.?\d*"
# Hyphen, en dash and em dash all show up in model output.
_RANGE_RE = re.compile(rf"({_NUMBER})\s*[-–—]\s*({_NUMBER})")
_SINGLE_RE = re.compile(rf"({_NUMBER})")


def _to_float(raw: str) -> float:
    return float(raw.replace(",", "").strip())


def parse_price_range(value) -> Optional[Tuple[float, float]]:
    """Parse a model price level into (low, high).

    A single price parses to (p, p). Returns None when nothing usable is found.
    """
    if value is None:
        return None

    if isinstance(value, (int, float)):
        price = float(value)
        return (price, price) if price > 0 else None

    text = str(value).strip()
    if not text:
        return None

    # Strip currency symbols and thousands markers before matching.
    cleaned = text.replace("$", "").replace("₹", "").replace("USD", "").replace("INR", "")

    match = _RANGE_RE.search(cleaned)
    if match:
        try:
            low, high = _to_float(match.group(1)), _to_float(match.group(2))
        except ValueError:
            return None
        if low <= 0 or high <= 0:
            return None
        return (min(low, high), max(low, high))

    match = _SINGLE_RE.search(cleaned)
    if match:
        try:
            price = _to_float(match.group(1))
        except ValueError:
            return None
        if price <= 0:
            return None
        return (price, price)

    return None


def parse_single_price(value) -> Optional[float]:
    """Parse a single price level (target, stop). Ranges collapse to midpoint."""
    parsed = parse_price_range(value)
    if parsed is None:
        return None
    low, high = parsed
    return (low + high) / 2


def validate_against_quote(
    ticker: str,
    entry_low: float,
    entry_high: float,
    target: float,
    stop_loss: float,
    side: str,
    quote_price: float,
) -> Optional[str]:
    """Return a rejection reason, or None when the levels are usable.

    This is where a hallucinated price level is caught: the model producing
    "entry 140-150" for a stock at 327 is a model error, not a trade.
    """
    if quote_price <= 0:
        return "no live quote to validate against"

    midpoint = (entry_low + entry_high) / 2
    deviation = abs(midpoint - quote_price) / quote_price
    if deviation > MAX_ENTRY_DEVIATION:
        return (
            f"entry zone {entry_low:.2f}-{entry_high:.2f} is {deviation:.0%} from "
            f"live price {quote_price:.2f} (limit {MAX_ENTRY_DEVIATION:.0%})"
        )

    # Direction sanity: a long that targets below its stop is incoherent.
    if side == "LONG" and not (stop_loss < midpoint < target):
        return f"LONG levels incoherent: stop {stop_loss}, entry {midpoint:.2f}, target {target}"
    if side == "SHORT" and not (target < midpoint < stop_loss):
        return f"SHORT levels incoherent: target {target}, entry {midpoint:.2f}, stop {stop_loss}"

    return None
