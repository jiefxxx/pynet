import json
import os

from pynet.http.header import HTTPResponseHeader
from pynet.http.tools import get_mimetype


class HTTPResponse:
    def __init__(self):
        self.header = HTTPResponseHeader()
        self.data = None
        self.data_type = None

    def upgrade_connection(self, name):
        self.header.fields.set("Connection", "Upgrade")
        self.header.fields.set("Upgrade", name)

    def upgrade_websocket(self, key):
        self.upgrade_connection("websocket")
        self.header.fields.set("Sec-WebSocket-Accept", key.decode())
        self.header.code = 101
        return self

    def error(self, code):
        self.header.code = code
        self.data_type = None
        self.data = b""
        return self

    def text(self, code, data, content_type="text/text"):
        self.header.code = code
        self.header.fields.set("Content-Length", str(len(data)))
        self.header.fields.set("Content-type", content_type)
        if type(data) is str:
            self.data = data.encode()
        else:
            self.data = data
        self.data_type = None
        return self

    def json(self, code, data):
        self.text(code, json.dumps(data, sort_keys=True, indent=4), content_type="application/json")
        return self

    def file(self, path, rng=None):
        if not os.path.exists(path):
            return self.error(404)

        self.header.fields.set("Accept-Ranges", "bytes")
        self.header.fields.set("Content-type", get_mimetype(path))
        seek = 0
        if rng is not None:
            seek = int(rng.split("=")[1][:-1])
        seek_end = os.path.getsize(path) - 1  # TODO:seek end not fully implemented
        full_size = os.path.getsize(path)
        size = seek_end - seek + 1
        if seek >= 0 and rng is not None:
            self.header.fields.set("Content-Range", "bytes " + str(seek) + "-" + str(seek_end) + "/" + str(full_size))
            self.header.fields.set("Content-Length", size)
            self.header.code = 206
        else:
            self.header.fields.set("Content-Length", full_size)
            self.header.code = 200
        self.data = {"path": path, "seek": seek, "seek_end": seek_end}
        self.data_type = "file"
        return self

    def sender(self, chunk_size):
        yield str(self.header).encode()
        if self.data and not self.data_type and len(self.data) > 0:
            current = 0
            while True:
                if len(self.data[current:]) < chunk_size:
                    yield self.data[current:]
                    break
                else:
                    yield self.data[current:current+chunk_size]
                    current += chunk_size
        elif self.data and self.data_type == "file":
            with open(self.data["path"], "rb") as f:
                if self.data["seek"] > 0:
                    f.seek(self.data["seek"])
                while True:
                    data = f.read(chunk_size)
                    if not data:
                        break
                    yield data