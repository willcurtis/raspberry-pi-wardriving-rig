"""Standard-library client helpers for the Wardriver control API."""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from datetime import datetime
from urllib.parse import urlparse, urlunparse


class ControllerError(RuntimeError):
    """A connection, authentication, or appliance API error."""


def normalize_url(value: str) -> str:
    value = value.strip()
    if not value:
        raise ControllerError("Enter the Wardriver address.")
    if "://" not in value:
        value = "http://" + value
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ControllerError("Use an HTTP or HTTPS address, such as wardriver.local:8080.")
    return urlunparse((parsed.scheme, parsed.netloc, "", "", "", "")).rstrip("/")


def format_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def format_time(value: str) -> str:
    try:
        return datetime.fromisoformat(value).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return value or "—"


class WardriverClient:
    """Authenticated client for the Wardriver control API."""

    def __init__(self, base_url: str, username: str, password: str, timeout: int = 10):
        self.base_url = normalize_url(base_url)
        self.timeout = timeout
        credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
        self.authorization = f"Basic {credentials}"
        self.csrf_token = ""

    def _request(self, path: str, method: str = "GET") -> dict[str, object]:
        headers = {
            "Accept": "application/json",
            "Authorization": self.authorization,
            "User-Agent": "WardriverDesktop/1.0",
        }
        if method != "GET":
            if not self.csrf_token:
                self.open_session()
            headers["X-CSRF-Token"] = self.csrf_token
        request = urllib.request.Request(
            self.base_url + path,
            data=b"" if method != "GET" else None,
            method=method,
            headers=headers,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            try:
                payload = json.loads(exc.read().decode("utf-8"))
                detail = payload.get("error", str(exc))
            except (json.JSONDecodeError, UnicodeDecodeError):
                detail = str(exc)
            if exc.code == 401:
                detail = "Authentication failed. Check the dashboard username and password."
            raise ControllerError(detail) from exc
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            raise ControllerError(f"Could not reach {self.base_url}: {reason}") from exc
        except TimeoutError as exc:
            raise ControllerError(f"Connection to {self.base_url} timed out.") from exc
        try:
            result = json.loads(body)
        except json.JSONDecodeError as exc:
            raise ControllerError("The appliance returned an invalid response.") from exc
        if not isinstance(result, dict):
            raise ControllerError("The appliance returned an unexpected response.")
        return result

    def open_session(self) -> None:
        payload = self._request("/api/session")
        token = payload.get("csrf_token")
        if not isinstance(token, str) or not token:
            raise ControllerError("The appliance did not provide a control token.")
        self.csrf_token = token

    def connect(self) -> tuple[dict[str, object], list[dict[str, object]]]:
        self.open_session()
        return self.status(), self.files()

    def status(self) -> dict[str, object]:
        return self._request("/api/status")

    def files(self) -> list[dict[str, object]]:
        payload = self._request("/api/files")
        files = payload.get("files", [])
        if not isinstance(files, list):
            raise ControllerError("The appliance returned an invalid file list.")
        return [item for item in files if isinstance(item, dict)]

    def action(self, path: str) -> str:
        payload = self._request(path, method="POST")
        return str(payload.get("message", "Action completed"))

