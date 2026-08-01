#!/usr/bin/env python3
"""Upload pending Kismet WiGLE CSV exports, marking successful files."""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import secrets
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_URL = "https://api.wigle.net/api/v2/file/upload"


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


def multipart_file(path: Path) -> tuple[bytes, str]:
    boundary = "----wardrive-" + secrets.token_hex(16)
    mime = mimetypes.guess_type(path.name)[0] or "text/csv"
    head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode()
    body = head + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    return body, boundary


def upload(path: Path, api_name: str, api_token: str, url: str, retries: int = 3) -> None:
    body, boundary = multipart_file(path)
    auth = base64.b64encode(f"{api_name}:{api_token}".encode()).decode()
    request = urllib.request.Request(
        url, data=body, method="POST",
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
            "User-Agent": "raspberry-pi-wardriving-rig/1.0",
        },
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                payload = json.loads(response.read().decode() or "{}")
                if not payload.get("success", True):
                    raise RuntimeError(payload.get("message", "WiGLE rejected upload"))
                return
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            if exc.code < 500 or attempt == retries - 1:
                raise RuntimeError(f"WiGLE HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == retries - 1:
                raise RuntimeError(f"WiGLE connection failed: {exc}") from exc
        time.sleep(2 ** attempt)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("/etc/wardrive/wigle.env"))
    parser.add_argument("--captures", type=Path, default=Path("/var/lib/wardrive/captures"))
    args = parser.parse_args()
    config = read_env(args.config)
    name, token = config.get("WIGLE_API_NAME"), config.get("WIGLE_API_TOKEN")
    if not name or not token:
        print("WiGLE credentials are not configured", file=sys.stderr)
        return 2
    candidates = sorted(args.captures.glob("*.wiglecsv"), key=lambda p: p.stat().st_mtime)
    pending = [p for p in candidates if not Path(str(p) + ".uploaded").exists()]
    if not pending:
        print("No pending WiGLE CSV files")
        return 0
    failures = 0
    for path in pending:
        try:
            upload(path, name, token, config.get("WIGLE_UPLOAD_URL", DEFAULT_URL))
            marker = Path(str(path) + ".uploaded")
            marker.write_text(f"uploaded={int(time.time())}\n", encoding="utf-8")
            os.chmod(marker, 0o640)
            print(f"Uploaded {path.name}")
        except (OSError, RuntimeError) as exc:
            failures += 1
            print(f"Failed {path.name}: {exc}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
