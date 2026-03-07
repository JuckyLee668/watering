"""Public WeChat callback diagnostics.

Usage:
    python scripts/check_public_wechat.py
    python scripts/check_public_wechat.py --url https://water.xi-han.top/wechat/callback
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from typing import List, Tuple
from urllib.parse import urlparse

import requests


def _print(title: str, ok: bool, detail: str) -> None:
    flag = "PASS" if ok else "FAIL"
    print(f"[{flag}] {title}: {detail}")


def _resolve_records(host: str) -> Tuple[List[str], List[str]]:
    try:
        output = subprocess.check_output(
            ["nslookup", host],
            stderr=subprocess.STDOUT,
            text=True,
            timeout=6,
        )
    except Exception:
        return [], []

    server_ip = None
    values: List[str] = []
    for raw in output.splitlines():
        line = raw.strip()
        if not line.lower().startswith("address:"):
            continue
        val = line.split(":", 1)[1].strip()
        if server_ip is None:
            server_ip = val
            continue
        if val == server_ip:
            continue
        values.append(val)

    a_records: List[str] = []
    aaaa_records: List[str] = []
    for val in sorted(set(values)):
        if ":" in val:
            aaaa_records.append(val)
        elif all(c.isdigit() or c == "." for c in val):
            a_records.append(val)
    return a_records, aaaa_records


def _check_https(url: str) -> Tuple[bool, str]:
    try:
        resp = requests.get(url, timeout=8)
        return True, f"HTTP {resp.status_code}, body='{resp.text[:120]}'"
    except Exception as exc:  # pragma: no cover - external network behavior
        return False, str(exc)


def _check_local_callback() -> Tuple[bool, str]:
    try:
        resp = requests.get("http://127.0.0.1:8000/wechat/callback", timeout=4)
        return resp.status_code == 200, f"HTTP {resp.status_code}, body='{resp.text[:80]}'"
    except Exception as exc:  # pragma: no cover - environment-dependent
        return False, str(exc)


def _check_cloudflared() -> Tuple[bool, str]:
    try:
        output = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-Process | Where-Object { $_.ProcessName -like '*cloudflared*' } | Select-Object -First 1 -ExpandProperty ProcessName",
            ],
            stderr=subprocess.STDOUT,
            text=True,
            timeout=5,
        )
        ok = bool(output.strip())
        return ok, (output.strip() if ok else "cloudflared process not found")
    except Exception as exc:  # pragma: no cover - platform-dependent
        return False, str(exc)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="https://water.xi-han.top/wechat/callback")
    args = parser.parse_args()

    parsed = urlparse(args.url)
    host = parsed.hostname or ""
    if not host:
        print("[FAIL] invalid --url")
        return 1

    a_records, aaaa_records = _resolve_records(host)
    _print("dns-a", len(a_records) > 0, ", ".join(a_records) if a_records else "no A record")
    _print("dns-aaaa", len(aaaa_records) > 0, ", ".join(aaaa_records) if aaaa_records else "no AAAA record")
    _print(
        "dns-ipv4-ready",
        len(a_records) > 0,
        "Provide at least one A record (IPv4). AAAA-only may break callback reachability.",
    )

    ok_https, detail_https = _check_https(args.url)
    _print("https-callback", ok_https, detail_https)

    ok_local, detail_local = _check_local_callback()
    _print("local-app-callback", ok_local, detail_local)

    ok_cf, detail_cf = _check_cloudflared()
    _print("cloudflared-process", ok_cf, detail_cf)

    if not ok_https:
        print(
            "\nSuggestions:\n"
            "1) Turn on Cloudflare proxy for the DNS record (orange cloud), avoid AAAA-only.\n"
            "2) Ensure cloudflared tunnel is online and ingress points to http://127.0.0.1:8000.\n"
            "3) Run app in stable mode (without --reload).\n"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
