"""Exercise the public board workflow against an isolated running application."""
import base64
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aR1sAAAAASUVORK5CYII=")


class BoardHttpTests(unittest.TestCase):
    def test_item_board_lifecycle_over_http(self):
        with tempfile.TemporaryDirectory() as directory:
            # Override storage before importing the app in the subprocess: the
            # developer's configured database and uploads must never be touched.
            env = dict(os.environ, DATABASE_URL=f"sqlite:///{Path(directory).as_posix()}/test.db",
                       UPLOAD_DIR=str(Path(directory) / "uploads"), AUTO_BOOTSTRAP_DB="false")
            subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"],
                           cwd=ROOT, env=env, check=True, capture_output=True)
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
            with open(Path(directory) / "server.log", "w+") as log:
                # Stop Uvicorn gracefully through stdin on every platform. A
                # forced Windows termination can leave SQLite WAL files locked.
                runner = (
                    "import sys, threading, uvicorn; "
                    "from app.db import engine; "
                    f"server = uvicorn.Server(uvicorn.Config('app.main:app', host='127.0.0.1', port={port})); "
                    "threading.Thread(target=lambda: (sys.stdin.readline(), setattr(server, 'should_exit', True)), daemon=True).start(); "
                    "server.run(); engine.dispose()"
                )
                server = subprocess.Popen([sys.executable, "-c", runner], stdin=subprocess.PIPE,
                                          cwd=ROOT, env=env, stdout=log, stderr=log)
                try:
                    self.base = f"http://127.0.0.1:{port}"
                    for _ in range(100):
                        try:
                            self.request("GET", "/api/health")
                            break
                        except URLError:
                            if server.poll() is not None:
                                log.seek(0)
                                self.fail(log.read())
                            time.sleep(.1)
                    else:
                        self.fail("Isolated application did not start")
                    self.lifecycle()
                finally:
                    try:
                        server.communicate(input=b"stop\n", timeout=15)
                    except subprocess.TimeoutExpired:
                        server.kill()
                        server.communicate()

    def request(self, method, path, payload=None, *, data=None, content_type=None):
        headers = {}
        if payload is not None:
            data = json.dumps(payload).encode()
            content_type = "application/json"
        if content_type:
            headers["Content-Type"] = content_type
        with urlopen(Request(self.base + path, data=data, headers=headers, method=method), timeout=10) as response:
            body = response.read()
            return json.loads(body) if body and "application/json" in response.headers.get("Content-Type", "") else body

    def lifecycle(self):
        owner = self.request("POST", "/api/items", {"title": "Owner without Epic"})
        other = self.request("POST", "/api/items", {"title": "Other owner"})
        path = f"/api/items/{owner['id']}"
        board = self.request("POST", path + "/boards", {"name": "HTTP Inspiration"})
        self.assertEqual(board["item_id"], owner["id"])
        boundary = "IdeaDockHttpTestBoundary"
        upload = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="sample.png"\r\n'
                  'Content-Type: image/png\r\n\r\n').encode() + PNG + f"\r\n--{boundary}--\r\n".encode()
        asset = self.request("POST", path + "/board-assets", data=upload,
                             content_type=f"multipart/form-data; boundary={boundary}")
        saved = self.request("PUT", path + f"/boards/{board['id']}", {
            "name": board["name"], "revision": board["revision"], "view": board["view"],
            "objects": [{"id": "image", "type": "image", "asset_key": asset["key"],
                         "x": 10, "y": 20, "width": 100, "height": 50}]})
        self.assertEqual(self.request("GET", asset["file_url"]), PNG)
        self.request("PATCH", path, {"epic_names": ["Changed grouping"]})
        reopened = self.request("GET", path + f"/boards/{board['id']}")
        self.assertEqual(reopened["objects"], saved["objects"])
        results = self.request("GET", "/api/boards?q=http%20inspiration")
        self.assertEqual([(b["id"], b["item_id"]) for b in results], [(board["id"], owner["id"])])
        self.assertEqual(self.request("GET", f"/api/items/{other['id']}/boards"), [])
        with self.assertRaises(HTTPError) as denied:
            self.request("GET", f"/api/items/{other['id']}/boards/{board['id']}")
        self.assertEqual(denied.exception.code, 404)
        with self.assertRaises(HTTPError) as protected:
            self.request("DELETE", path + f"/board-assets/{asset['id']}")
        self.assertEqual(protected.exception.code, 409)
        self.request("DELETE", path + f"/boards/{board['id']}?revision={saved['revision']}")
        self.request("DELETE", path + f"/board-assets/{asset['id']}")
        self.assertEqual(self.request("GET", path + "/boards"), [])
        self.assertIn(b"Visual boards", self.request("GET", "/static/boards.html"))


if __name__ == "__main__":
    unittest.main()
