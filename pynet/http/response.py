import json
import os
import time

import magic

from pynet.http.header import HTTPFields
from pynet.http.tools import http_code_to_string, chunk, HTTP_CONNECTION_UPGRADE


class HTTPResponse:
    def __init__(self, request_header, connection):
        self.request_header = request_header
        self.connection = connection
        self.proto = "HTTP/1.1"
        self.code = 404
        self.fields = HTTPFields()
        self.fields.set("Server", "Python-test/0.02")

    def __str__(self):
        ret = self.proto + " " + str(self.code) + " " + http_code_to_string(self.code) + "\r\n"
        ret += str(self.fields)
        ret += "\r\n"
        return ret

    def upgrade(self, name):
        self.fields.set("Connection", "Upgrade")
        self.fields.set("Upgrade", name)

    def upgrade_webSocket(self, key):
        self.upgrade("websocket")
        self.fields.set("Sec-WebSocket-Accept", key.decode())
        self.send_text(101, "")
        return HTTP_CONNECTION_UPGRADE

    def send_text(self, code, data=None, content_type="text/text"):
        self.code = code
        if data is not None:
            self.fields.set("Content-Length", str(len(data)))
            self.fields.set("Content-type", content_type)
            self.fields.set("Access-Control-Allow-Origin", "*")
        else:
            data = ''
        self.connection.send(str(self).encode() + data.encode())

    def send_json(self, code, data=None):
        if not data:
            data = {}
        dump = json.dumps(data, sort_keys=True, indent=4)
        self.send_text(code, dump, content_type="application/json")

    def send_header(self, code):
        self.code = code
        self.connection.send(str(self).encode())

    def send_data(self, data):
        if type(data) is str:
            data = data.encode()
        return self.connection.send(data, chunk_size=0)

    def send_error(self, code):
        self.fields.set("Content-Length", str(0))
        self.send_header(code)
        self.send_data("")

    def send_file(self, path):
        r = self.request_header.fields.get("Range")
        self.fields.set("Content-type", magic.Magic(mime=True).from_file(path))
        seek = 0
        if r is not None:
            seek = int(r.split("=")[1][:-1])
        seek_end = os.path.getsize(path) - 1  # TODO:seek end not fully implemented
        full_size = os.path.getsize(path)
        size = seek_end - seek + 1

        if seek >= 0 and r is not None:
            self.fields.set("Accept-Ranges", "bytes")
            self.fields.set("Content-Range", "bytes " + str(seek) + "-" + str(seek_end) + "/" + str(full_size))
            self.fields.set("Content-length", size)
            self.send_header(206)
        else:
            self.fields.set("Accept-Ranges", "bytes")
            self.fields.set("Content-length", os.path.getsize(path))
            self.send_header(200)

        print(path, seek, seek_end, size)
        while True:
            seek, data = chunk(path, seek)
            while True:
                if not self.connection.is_alive():
                    break
                if self.send_data(data):
                    break
                time.sleep(0.05)

            if seek >= full_size or not self.connection.is_alive():
                break
