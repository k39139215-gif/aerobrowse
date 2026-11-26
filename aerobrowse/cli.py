"""AeroBrowse CLI. MCP stdout is reserved exclusively for protocol messages."""

import argparse
import json
from typing import Any

from aerobrowse.engine import AeroBrowser


def cmd_fetch(args: Any) -> None:
    with AeroBrowser(default_mode="fidelity" if args.js else "auto") as browser:
        result = browser.fetch(args.url, force_fidelity=args.js)
    print(json.dumps(result, ensure_ascii=False))
    if not result.get("success"):
        raise SystemExit(1)


def cmd_mcp(args: Any) -> None:
    from aerobrowse.mcp_server import run_mcp

    run_mcp()


def cmd_bench(args: Any) -> None:
    from aerobrowse.benchmark import run

    print(json.dumps(run(args.url), ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Hybrid HTTP and isolated Chromium browsing"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("fetch")
    fetch.add_argument("url")
    fetch.add_argument("--js", action="store_true")
    fetch.add_argument(
        "--markdown",
        "-m",
        action="store_true",
        help="Accepted for compatibility; JSON includes markdown",
    )
    fetch.add_argument(
        "--actions",
        "-a",
        action="store_true",
        help="Accepted for compatibility; JSON includes actions",
    )
    fetch.set_defaults(func=cmd_fetch)
    sub.add_parser("mcp").set_defaults(func=cmd_mcp)
    bench = sub.add_parser("bench")
    bench.add_argument("url")
    bench.set_defaults(func=cmd_bench)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
