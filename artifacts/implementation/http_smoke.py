"""HTTP acceptance checks against preview_server.py's disposable port only."""

import base64
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen


BASE = "http://127.0.0.1:8027/api"


def request(path, method="GET", data=None, expected=200, headers=None):
    if isinstance(data, dict):
        data = json.dumps(data).encode()
        headers = {"Content-Type": "application/json"}
    try:
        response = urlopen(Request(BASE + path, data=data, method=method, headers=headers or {}))
    except HTTPError as error:
        response = error
    with response:
        content = response.read()
        assert response.status == expected, (path, response.status, content)
        return json.loads(content) if content else None


# This endpoint belongs to the fixture process; never point this script at the
# normal application port, because it deliberately creates disposable records.
projects = request("/epics")
assert projects[0]["name"] == "Board acceptance"
prefix = "/projects/1"
image = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a4WQAAAAASUVORK5CYII=")
boundary = "ideadock-acceptance-boundary"
body = (
    f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="http.png"\r\n'
    "Content-Type: image/png\r\n\r\n"
).encode() + image + f"\r\n--{boundary}--\r\n".encode()
asset = request(prefix + "/assets", "POST", body, 201,
                {"Content-Type": f"multipart/form-data; boundary={boundary}"})
payload = {
    "name": "HTTP acceptance",
    "objects": [{"id": "image-a", "type": "image", "asset_key": asset["key"],
                 "x": -20, "y": 40, "width": 160, "height": 160}],
    "view": {"x": 30, "y": -40, "zoom": .75},
}
board = request(prefix + "/boards", "POST", payload, 201)
path = prefix + f'/boards/{board["id"]}'
saved = request(path, "PUT", {**payload, "revision": board["revision"]})
conflict = request(path, "PUT", {**payload, "revision": board["revision"]}, 409)
assert conflict["detail"]["latest"]["revision"] == saved["revision"]
assert conflict["detail"]["code"] == "revision_conflict"
blocked = request(prefix + f'/assets/{asset["id"]}', "DELETE", expected=409)
assert blocked["detail"]["boards"][0]["name"] == "HTTP acceptance"
copy = request(path + "/copy", "POST", {**payload, "name": "HTTP local copy"}, 201)
assert copy["objects"] == saved["objects"] and copy["id"] != saved["id"]
request("/projects/2/boards", "POST", payload, 400)
request(path, "PUT", {**payload, "revision": saved["revision"], "view": {"x": 0, "y": 0, "zoom": 0}}, 422)
request(path + f'?revision={saved["revision"]}', "DELETE", expected=204)
request(prefix + f'/boards/{copy["id"]}?revision={copy["revision"]}', "DELETE", expected=204)
request(prefix + f'/assets/{asset["id"]}', "DELETE", expected=204)
print("HTTP smoke passed: upload, save, serialized 409/latest, deletion guard, copy, isolation, validation, cleanup.")
