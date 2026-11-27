"""Owned, ephemeral task application with independent server-side verdicts."""

import html
import secrets
import threading
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit


class AgentFixture:
    def __init__(self):
        self.lock = threading.Lock()
        self.sessions: set[str] = set()
        self.state = {
            "record": "Original",
            "submitted": False,
            "logins": 0,
            "logouts": 0,
            "searches": 0,
            "details": 0,
            "dynamic": 0,
        }
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def reply(self, body: str, status: int = 200, headers: tuple = ()):
                payload = (
                    "<!doctype html><html><head><meta charset=utf-8><title>Agent task lab</title></head><body>"
                    + body
                    + "</body></html>"
                ).encode()
                self.send_response(status)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Cache-Control", "no-store")
                for key, value in headers:
                    self.send_header(key, value)
                self.end_headers()
                self.wfile.write(payload)

            def authenticated(self):
                cookies = SimpleCookie()
                try:
                    cookies.load(self.headers.get("Cookie", ""))
                except CookieError:
                    return False
                session = cookies.get("session")
                return session is not None and session.value in fixture.sessions

            def do_GET(self):
                path = urlsplit(self.path).path
                query = parse_qs(urlsplit(self.path).query)
                with fixture.lock:
                    if path == "/docs":
                        self.reply(
                            "<h1>Account documentation</h1><p>The renewal window is 17 days.</p><a href=/search>Search catalog</a>"
                        )
                    elif path == "/search":
                        fixture.state["searches"] += bool(query.get("q"))
                        results = (
                            '<a href="/item/widget">Widget W42</a>'
                            if query.get("q")
                            else ""
                        )
                        self.reply(
                            "<h1>Catalog</h1><form action=/search><label>Search<input name=q></label><button>Search catalog</button></form>"
                            + results
                        )
                    elif path == "/item/widget":
                        fixture.state["details"] += 1
                        self.reply(
                            "<h1>Widget W42</h1><dl><dt>SKU</dt><dd>W42</dd><dt>Price</dt><dd>42 USD</dd></dl><a href=/search>Catalog</a>"
                        )
                    elif path == "/login":
                        self.reply(
                            "<h1>Sign in</h1><form method=post action=/login><label>Username<input name=username autocomplete=username></label><label>Password<input type=password name=password autocomplete=current-password></label><button>Sign in</button></form>"
                        )
                    elif path == "/record":
                        if not self.authenticated():
                            self.reply(
                                "<h1>Login required</h1><a href=/login>Sign in</a>", 401
                            )
                        else:
                            self.reply(
                                "<h1>Protected record</h1><p>Current record: "
                                + html.escape(fixture.state["record"])
                                + "</p><form method=post action=/record><label>Record name<input name=name required></label><button>Save record</button></form><form method=post action=/logout><button>Log out</button></form>"
                            )
                    elif path == "/wizard":
                        self.reply(
                            "<h1>Plan request</h1><form method=post action=/wizard><label>Plan<select name=plan><option value=basic>Basic</option><option value=pro>Pro</option></select></label><label>Agree<input type=checkbox name=agree required></label><button>Next</button></form>"
                        )
                    elif path == "/dynamic":
                        self.reply(
                            """<h1>Dynamic recovery</h1><button onclick="document.querySelector('p').textContent='Changed content'">Change content</button><p>Original content</p><form method=post action=/dynamic><button>Confirm recovery</button></form>"""
                        )
                    else:
                        self.reply(
                            "<h1>Task lab</h1><a href=/docs>Documentation</a><a href=/login>Sign in</a><a href=/wizard>Plan request</a>"
                        )

            def do_POST(self):
                try:
                    size = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    self.reply("Invalid body", 400)
                    return
                if not 0 <= size <= 8192:
                    self.reply("Body exceeds fixture limit", 413)
                    return
                values = parse_qs(
                    self.rfile.read(size).decode("utf-8", errors="strict")
                )
                path = urlsplit(self.path).path
                with fixture.lock:
                    if path == "/login":
                        if values.get("username") != ["agent"] or values.get(
                            "password"
                        ) != ["fixture-only"]:
                            self.reply("<h1>Invalid credentials</h1>", 403)
                            return
                        sid = secrets.token_hex(24)
                        fixture.sessions.add(sid)
                        fixture.state["logins"] += 1
                        self.reply(
                            "Signed in",
                            303,
                            (
                                ("Location", "/record"),
                                (
                                    "Set-Cookie",
                                    f"session={sid}; HttpOnly; SameSite=Lax; Path=/",
                                ),
                            ),
                        )
                    elif path == "/record" and self.authenticated():
                        name = values.get("name", [""])[0].strip()
                        if not name or len(name) > 128:
                            self.reply(
                                "<h1>Validation error: record name required</h1>", 422
                            )
                            return
                        fixture.state["record"] = name
                        self.reply("Saved", 303, (("Location", "/record"),))
                    elif path == "/logout":
                        cookies = SimpleCookie(self.headers.get("Cookie", ""))
                        if cookies.get("session"):
                            fixture.sessions.discard(cookies["session"].value)
                        fixture.state["logouts"] += 1
                        self.reply(
                            "Logged out",
                            303,
                            (
                                ("Location", "/login"),
                                ("Set-Cookie", "session=; Max-Age=0; HttpOnly; Path=/"),
                            ),
                        )
                    elif path == "/wizard":
                        plan, agreed = (
                            values.get("plan", [""])[0],
                            values.get("agree") == ["on"],
                        )
                        if plan != "pro" or not agreed:
                            self.reply(
                                "<h1>Validation error</h1><p>Choose Pro and agree.</p><a href=/wizard>Try again</a>",
                                422,
                            )
                            return
                        self.reply(
                            "<h1>Confirm Pro plan</h1><form method=post action=/wizard/confirm><input type=hidden name=plan value=pro><input type=hidden name=agree value=yes><button>Submit request</button></form>"
                        )
                    elif path == "/wizard/confirm" and values == {
                        "plan": ["pro"],
                        "agree": ["yes"],
                    }:
                        fixture.state["submitted"] = True
                        self.reply("<h1>Request submitted</h1>")
                    elif path == "/dynamic":
                        fixture.state["dynamic"] += 1
                        self.reply("<h1>Recovery confirmed</h1>")
                    else:
                        self.reply("<h1>Unauthorized or invalid task request</h1>", 403)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def verdict(self, task: str, answer: str) -> bool:
        with self.lock:
            state = dict(self.state)
        if task == "documentation":
            return "17" in answer and "day" in answer.lower()
        if task == "search":
            return (
                state["searches"] > 0
                and state["details"] > 0
                and "W42" in answer
                and "42" in answer
            )
        if task == "authenticated_update":
            return (
                state["record"] == "Agent updated"
                and state["logins"] > 0
                and state["logouts"] > 0
                and not self.sessions
            )
        if task == "multistep_form":
            return state["submitted"] is True
        if task == "compare_tabs":
            return "17" in answer and "W42" in answer and "42" in answer
        if task == "stale_recovery":
            return state["dynamic"] > 0
        return False

    def receipt_state(self):
        with self.lock:
            return {**self.state, "active_logins": len(self.sessions)}
