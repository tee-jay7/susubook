"""Arkesel SMS gateway — layer 4 (Infrastructure).

Arkesel is a Ghanaian messaging provider, chosen so the delivery path stays
local to the users the system serves.

Uses `urllib` from the standard library rather than adding an HTTP dependency
for a single POST. One fewer package to pin (TD-12) and to keep patched.

The endpoint and payload follow Arkesel's v2 SMS API. Both the URL and the
sender ID are configurable, so a change at the provider is a configuration
change rather than a code change — and `SMS_API_URL` allows pointing at a
sandbox.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

log = logging.getLogger(__name__)

DEFAULT_ENDPOINT = "https://sms.arkesel.com/api/v2/sms/send"
TIMEOUT_SECONDS = 8


class ArkeselSmsGateway:
    """Posts one message. Returns success; never raises."""

    def __init__(
        self,
        api_key: str,
        *,
        sender_id: str = "SusuBook",
        endpoint: str = DEFAULT_ENDPOINT,
        timeout: int = TIMEOUT_SECONDS,
    ) -> None:
        self._api_key = api_key
        self._sender_id = sender_id
        self._endpoint = endpoint
        self._timeout = timeout

    def send(self, *, to: str, message: str) -> bool:
        payload = json.dumps(
            {
                "sender": self._sender_id,
                "message": message,
                "recipients": [to],
            }
        ).encode()

        request = urllib.request.Request(
            self._endpoint,
            data=payload,
            headers={
                "api-key": self._api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                body = response.read().decode("utf-8", "replace")
                if 200 <= response.status < 300:
                    log.info("sms accepted by gateway for %s", to)
                    return True
                # The API key must never reach a log line.
                log.error(
                    "sms gateway rejected message for %s: HTTP %s %s",
                    to, response.status, body[:200],
                )
                return False
        except urllib.error.HTTPError as exc:
            log.error("sms gateway HTTP %s for %s", exc.code, to)
        except urllib.error.URLError as exc:
            log.error("sms gateway unreachable for %s: %s", to, exc.reason)
        except Exception:  # noqa: BLE001 — a notification must never break a flow
            log.exception("sms gateway unexpected failure for %s", to)
        return False
