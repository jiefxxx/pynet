import io
import json
import os

from pynet.http.header import HTTPResponseHeader
from pynet.http.tools import get_mimetype


class HTTPResponse:
    def __init__(self):
        self.header = HTTPResponseHeader()
        self.data = None
        self.data_seek = 0

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
        return self

    def text(self, code, data, content_type="text/text"):
        self.header.code = code
        self.header.fields.set("Content-type", content_type)
        self.data = io.BytesIO(data.encode())
        return self

    def json(self, code, data, readable=False):
        self.text(code, "", content_type="application/json")
        if readable:
            json.dump(data, self.data, sort_keys=True, indent=4)
        else:
            json.dump(data, self.data)
        return self

    def file(self, path):
        if not os.path.exists(path):
            return self.error(404)

        self.header.fields.set("Content-type", get_mimetype(path))
        self.header.code = 200
        self.data = open(path, "rb")
        return self

    def set_length(self, rng=None):
        self.data.seek(0, 2)
        full_size = self.data.tell()
        self.header.fields.set("Content-Length", full_size)
        if rng:
            seek = int(rng.split("=")[1][:-1])
            size = full_size - seek
            self.header.fields.set("Content-Range", "bytes "+str(seek)+"-"+str(full_size-1)+"/"+str(full_size))
            self.header.fields.set("Content-Length", size)
            self.header.code = 206
            self.data_seek = seek

    def sender(self, chunk_size):
        yield str(self.header).encode()
        if self.data:
            self.data.seek(self.data_seek)
            while True:
                data = self.data.read(chunk_size)
                if not data:
                    break
                yield data
            self.data.close()
