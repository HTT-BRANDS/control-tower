#!/usr/bin/env python3
"""Wait for an HTTP endpoint to become ready with deterministic retries."""

from __future__ import annotations

import argparse
import sys
import time

import httpx


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="URL to poll")
    parser.add_argument("--timeout", type=float, default=30.0, help="Total timeout in seconds")
    parser.add_argument("--interval", type=float, default=1.0, help="Poll interval in seconds")
    parser.add_argument(
        "--expect-status",
        type=int,
        default=200,
        help="Expected HTTP status code",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    deadline = time.monotonic() + args.timeout
    last_error = "no response received"

    while time.monotonic() < deadline:
        try:
            response = httpx.get(args.url, timeout=min(args.interval, 5.0))
            if response.status_code == args.expect_status:
                print(f"ready: {args.url} -> {response.status_code}")
                return 0
            last_error = f"unexpected status {response.status_code}"
        except httpx.HTTPError as exc:
            last_error = str(exc)
        time.sleep(args.interval)

    print(f"timeout waiting for {args.url}: {last_error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
