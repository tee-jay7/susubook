"""QR client cards (FR-39) — layer 4.

The QR encodes a URL containing the client's opaque public reference and
nothing else: no name, phone, balance or rate. A photographed card therefore
discloses no personal data (NFR-06, Act 843) and confers no capability
(BR-R15) -- reaching the URL still requires an authenticated collector to
whom that client is assigned.

Rendered as inline SVG rather than a PNG so it scales to any print size with
no image pipeline and no external request.
"""

from __future__ import annotations

from uuid import UUID

import segno


def collection_url(base_url: str, public_ref: UUID) -> str:
    return f"{base_url.rstrip('/')}/c/{public_ref}"


def qr_svg(base_url: str, public_ref: UUID, *, scale: int = 5) -> str:
    """Inline SVG for the client's collection URL.

    Error correction 'M' (~15% recoverable) is a deliberate middle setting:
    these cards live in market stalls and will be creased and dirtied, but a
    higher level would enlarge the symbol and reduce the printable size.
    """
    qr = segno.make(collection_url(base_url, public_ref), error="m")
    return qr.svg_inline(scale=scale, dark="#0d2d38", light=None)
