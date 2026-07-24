import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location("wardrive_server", Path(__file__).parents[1] / "app/server.py")
server = importlib.util.module_from_spec(SPEC)
with patch.dict("os.environ", {"WARDRIVE_WEB_CONFIG": "/dev/null"}):
    SPEC.loader.exec_module(server)


class ServerTests(unittest.TestCase):
    def test_password_verification(self):
        import hashlib
        salt = bytes.fromhex("00" * 16)
        expected = hashlib.pbkdf2_hmac("sha256", b"correct", salt, 1000).hex()
        encoded = f"1000${salt.hex()}${expected}"
        self.assertTrue(server.verify_password("correct", encoded))
        self.assertFalse(server.verify_password("wrong", encoded))

    def test_read_env(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.env"
            path.write_text("# comment\nA=one\nTOKEN=a=b\n")
            self.assertEqual(server.read_env(path), {"A": "one", "TOKEN": "a=b"})

    def test_capture_status_marks_uploaded(self):
        with tempfile.TemporaryDirectory() as directory:
            old = server.CAPTURE_DIR
            try:
                server.CAPTURE_DIR = Path(directory)
                csv = server.CAPTURE_DIR / "one.wiglecsv"
                csv.write_text("data")
                self.assertEqual(server.capture_status()["pending_uploads"], 1)
                Path(str(csv) + ".uploaded").write_text("ok")
                self.assertEqual(server.capture_status()["pending_uploads"], 0)
            finally:
                server.CAPTURE_DIR = old


if __name__ == "__main__":
    unittest.main()

