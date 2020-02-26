import codecs
import gzip
import io
import json
import shutil

from mako.runtime import Context

from pynet.http.header import HTTPResponseHeader
from pynet.http.tools import get_file_length


class HTTPResponse:
    def __init__(self):
        self.header = HTTPResponseHeader()
        self.data = None
        self.data_seek = 0
        self.prevent_close = False

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

    def file(self, code, data, content_type="text/text", prevent_close=False):
        self.header.code = code
        self.header.fields.set("Content-type", content_type)
        self.header.enable_range("bytes")
        self.data = data
        self.prevent_close = prevent_close
        return self

    def render(self, code, template, **kwargs):
        self.text(code, "", content_type="text/html")
        wrapper_file = codecs.getwriter('utf-8')(self.data)
        ctx = Context(wrapper_file, **kwargs)
        template.render_context(ctx)
        return self

    def json(self, code, data, readable=False):
        self.text(code, "", content_type="application/json")
        wrapper_file = codecs.getwriter('utf-8')(self.data)
        if readable:
            json.dump(data, wrapper_file, sort_keys=True, indent=4)
        else:
            json.dump(data, wrapper_file)
        return self

    def compress_gzip(self):
        if not self.data:
            return

        self.header.fields.set("Content-Encoding", "gzip")
        compressed = io.BytesIO()
        compress_wrapper = gzip.GzipFile(fileobj=compressed, mode="wb")
        self.data.seek(0)
        shutil.copyfileobj(self.data, compress_wrapper)
        self.data = compressed

    def set_length(self, rng=None):
        if not self.data:
            self.header.fields.set("Content-Length", 0)
            return

        full_size = get_file_length(self.data)
        self.header.fields.set("Content-Length", full_size)
        if rng:
            seek = int(rng.split("=")[1][:-1])
            seek_end = full_size - 1  # TODO:seek end not fully implemented
            size = seek_end - seek + 1
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
            if not self.prevent_close:
                self.data.close()
