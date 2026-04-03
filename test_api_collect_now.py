import unittest
from unittest.mock import patch
import os

# We need to test the flask app.
# The app logic initializes DB and starts polling if not careful.
# Let's set AUTO_START_RUNTIME=false to avoid polling.
os.environ["AUTO_START_RUNTIME"] = "false"
os.environ["ENABLE_POLLER"] = "false"

from app import app

class TestApiCollectNow(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.client.testing = True

    @patch('app.COLLECT_NOW_TOKEN', None)
    def test_unconfigured_token(self):
        """When COLLECT_NOW_TOKEN is not configured, it should return 403 Forbidden."""
        response = self.client.post("/api/collect-now")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json, {"error": "Forbidden"})

    @patch('app.COLLECT_NOW_TOKEN', "")
    def test_empty_token(self):
        """When COLLECT_NOW_TOKEN is empty, it should return 403 Forbidden."""
        response = self.client.post("/api/collect-now")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json, {"error": "Forbidden"})

    @patch('app.COLLECT_NOW_TOKEN', "secret-token")
    def test_missing_provided_token(self):
        """When COLLECT_NOW_TOKEN is configured but request lacks x-collect-token header."""
        response = self.client.post("/api/collect-now")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json, {"error": "Unauthorized"})

    @patch('app.COLLECT_NOW_TOKEN', "secret-token")
    def test_invalid_provided_token(self):
        """When COLLECT_NOW_TOKEN is configured but request has wrong token."""
        response = self.client.post("/api/collect-now", headers={"x-collect-token": "wrong-token"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json, {"error": "Unauthorized"})

    @patch('app.COLLECT_NOW_TOKEN', "secret-token")
    @patch('app.collect_once')
    def test_valid_token(self, mock_collect_once):
        """When COLLECT_NOW_TOKEN is configured and correct token is provided."""
        mock_collect_once.return_value = {"ok": [{"airport": "PHL", "rows": 10}], "errors": []}

        response = self.client.post("/api/collect-now", headers={"x-collect-token": "secret-token"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"ok": [{"airport": "PHL", "rows": 10}], "errors": []})
        mock_collect_once.assert_called_once()

if __name__ == "__main__":
    unittest.main()
