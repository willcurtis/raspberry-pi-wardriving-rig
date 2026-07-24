import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    "wardriver_client",
    Path(__file__).parents[1] / "desktop/client.py",
)
desktop = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(desktop)


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.payload


class DesktopTests(unittest.TestCase):
    def test_normalize_url_adds_default_scheme(self):
        self.assertEqual(
            desktop.normalize_url("wardriver.local:8080"),
            "http://wardriver.local:8080",
        )

    def test_normalize_url_removes_path(self):
        self.assertEqual(
            desktop.normalize_url("https://pi.example/control?x=1"),
            "https://pi.example",
        )

    def test_normalize_url_rejects_unsupported_scheme(self):
        with self.assertRaises(desktop.ControllerError):
            desktop.normalize_url("ftp://wardriver.local")

    def test_format_size(self):
        self.assertEqual(desktop.format_size(500), "500 B")
        self.assertEqual(desktop.format_size(1536), "1.5 KB")

    def test_client_uses_session_token_for_actions(self):
        client = desktop.WardriverClient(
            "wardriver.local:8080", "wardrive", "secret"
        )
        with patch.object(
            desktop.urllib.request,
            "urlopen",
            side_effect=[
                FakeResponse({"csrf_token": "control-token"}),
                FakeResponse({"message": "Kismet started"}),
            ],
        ) as urlopen:
            client.open_session()
            message = client.action("/api/kismet/start")
        self.assertEqual(message, "Kismet started")
        action_request = urlopen.call_args_list[1].args[0]
        self.assertEqual(action_request.method, "POST")
        self.assertEqual(action_request.get_header("X-csrf-token"), "control-token")
        self.assertTrue(action_request.get_header("Authorization").startswith("Basic "))


if __name__ == "__main__":
    unittest.main()
