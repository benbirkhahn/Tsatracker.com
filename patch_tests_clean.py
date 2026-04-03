import re

with open('test_app.py', 'r') as f:
    content = f.read()

test_functions = """
    @unittest.mock.patch("app.requests.get")
    def test_fetch_dtw_rows(self, mock_get):
        import app
        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {"Name": "Evans", "WaitTime": 3},
            {"Name": "McNamara", "WaitTime": 0}
        ]
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        rows = app.fetch_dtw_rows()
        self.assertEqual(len(rows), 2)

        self.assertEqual(rows[0]["checkpoint"], "Evans Terminal")
        self.assertEqual(rows[0]["wait_minutes"], 3.0)
        self.assertEqual(rows[0]["airport_code"], "DTW")
        self.assertEqual(rows[0]["source"], "https://proxy.metroairport.com/SkyFiiTSAProxy.ashx")

        self.assertEqual(rows[1]["checkpoint"], "McNamara Terminal")
        self.assertEqual(rows[1]["wait_minutes"], 0.0)

    @unittest.mock.patch.dict("os.environ", {"IAH_API_KEY": "fake_key"})
    @unittest.mock.patch("app.requests.get")
    def test_fetch_iah_rows(self, mock_get):
        import app

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": {
                "wait_times": [
                    {"name": "Terminal A", "waitSeconds": 300, "isDisplayable": True, "lane": "General"},
                    {"name": "Terminal B", "waitSeconds": 60, "isDisplayable": False, "lane": "General"},
                    {"name": "Immigration", "waitSeconds": 1200, "isDisplayable": True, "lane": "FIS"}
                ]
            }
        }
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        rows = app.fetch_iah_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["checkpoint"], "Terminal A")
        self.assertEqual(rows[0]["wait_minutes"], 5.0)
        self.assertEqual(rows[0]["airport_code"], "IAH")
        self.assertEqual(rows[0]["source"], "https://api.houstonairports.mobi/wait-times/checkpoint/iah")

"""

class_def = "class TestNormalizeLaneType(unittest.TestCase):"
if class_def in content:
    content = content.replace(class_def, class_def + test_functions)

with open('test_app.py', 'w') as f:
    f.write(content)
