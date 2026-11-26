"""CDP Fetch adapter: intercept every redirect hop rather than Playwright route chains."""

import base64
from typing import Any

from playwright.sync_api import Error as PlaywrightError

from aerobrowse.errors import AeroError


class Request:
    def __init__(self, session: Any, event: dict[str, Any]):
        self.session, self.event = session, event
        request = event["request"]
        self.url = request["url"]
        self.method = request["method"]
        self.resource_type = event.get("resourceType", "Other").lower()
        self.redirected_from = bool(event.get("redirectedRequestId"))
        self._headers = request.get("headers", {})
        self.post_data_buffer = b""
        if request.get("postDataEntries"):
            self.post_data_buffer = b"".join(
                base64.b64decode(entry["bytes"], validate=True)
                for entry in request["postDataEntries"]
            )
        elif "postData" in request:
            self.post_data_buffer = request["postData"].encode("utf-8")
        elif request.get("hasPostData"):
            # Never silently send an empty or truncated upload.
            raise AeroError(
                "UNSUPPORTED_CAPABILITY",
                "Request body is unavailable for safe brokering",
            )

    def all_headers(self) -> dict[str, str]:
        return dict(self._headers)


class Route:
    def __init__(self, session: Any, event: dict[str, Any]):
        self.session, self.request_id = session, event["requestId"]
        self.request = Request(session, event)

    def abort(self, reason: str) -> None:
        self.session.send(
            "Fetch.failRequest",
            {"requestId": self.request_id, "errorReason": "BlockedByClient"},
        )

    def fulfill(self, *, status: int, headers: dict[str, str], body: bytes) -> None:
        fields = []
        for name, value in headers.items():
            for part in value.split("\n") if name.lower() == "set-cookie" else [value]:
                fields.append({"name": name, "value": part})
        self.session.send(
            "Fetch.fulfillRequest",
            {
                "requestId": self.request_id,
                "responseCode": status,
                "responseHeaders": fields,
                "body": base64.b64encode(body).decode("ascii"),
            },
        )


def install(page: Any, broker: Any, failed: Any) -> Any:
    session = page.context.new_cdp_session(page)

    def paused(event: dict[str, Any]) -> None:
        try:
            broker(Route(session, event))
        except AeroError as exc:
            failed(exc)
            session.send(
                "Fetch.failRequest",
                {"requestId": event["requestId"], "errorReason": "BlockedByClient"},
            )
        except (ValueError, KeyError, TypeError):
            failed(
                AeroError("INVALID_REQUEST", "Browser request cannot be safely decoded")
            )
            session.send(
                "Fetch.failRequest",
                {"requestId": event["requestId"], "errorReason": "BlockedByClient"},
            )
        except PlaywrightError:
            failed(
                AeroError(
                    "BROWSER_ROUTE_CLOSED", "Browser request closed during interception"
                )
            )

    session.on("Fetch.requestPaused", paused)
    session.send(
        "Fetch.enable",
        {
            "patterns": [{"urlPattern": "*", "requestStage": "Request"}],
            "handleAuthRequests": False,
        },
    )
    return session
