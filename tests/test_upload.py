import importlib.util
import tempfile
import unittest
from pathlib import Path


SPEC = importlib.util.spec_from_file_location("wigle_upload", Path(__file__).parents[1] / "scripts/upload_wigle.py")
upload = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(upload)


class UploadTests(unittest.TestCase):
    def test_multipart_contains_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.wiglecsv"
            path.write_bytes(b"header,data\n")
            body, boundary = upload.multipart_file(path)
            self.assertIn(path.name.encode(), body)
            self.assertIn(b"header,data", body)
            self.assertIn(boundary.encode(), body)

    def test_read_env_preserves_equals(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "wigle.env"
            path.write_text("WIGLE_API_TOKEN=a=b=c\n")
            self.assertEqual(upload.read_env(path)["WIGLE_API_TOKEN"], "a=b=c")


if __name__ == "__main__":
    unittest.main()
