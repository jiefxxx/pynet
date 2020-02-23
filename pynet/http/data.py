import io
import json
import os
import uuid
from tempfile import NamedTemporaryFile

from pynet.http.exceptions import HTTPError
from pynet.http.header import HTTPFields
from pynet.http.tools import get_mimetype, get_file_length


class HTTPData:
    def __init__(self, size):
        self.size = size
        self.current_size = 0

        if self.size > 100 * 1024:
            self.data_stream = NamedTemporaryFile(mode="w+b")
        else:
            self.data_stream = io.BytesIO()

    def io_size(self):
        if isinstance(self.data_stream, io.BytesIO):
            return self.data_stream.getbuffer().nbytes
        else:
            return os.stat(self.data_stream.name).st_size

    def completed(self):
        return self.io_size() == self.size

    def feed(self, data):
        if self.io_size()+len(data) > self.size:
            raise HTTPError(413)
        self.data_stream.write(data)

        if self.completed():
            self.seek()

    def close(self):
        self.data_stream.close()

    def __str__(self):
        return "HTTPData(size=" + str(os.fstat(self.data_stream.fileno()).st_size) + "/" + \
               str(self.size) + \
               ", completed=" + str(self.completed()) + ")"

    def read(self, size=-1):
        return self.data_stream.read(size)

    def seek(self, n=0):
        self.data_stream.seek(n)

    def json(self):
        return json.loads(self.read())


class HTTPMultipartSender:
    def __init__(self):
        self.list = []
        self.boundary = "----pynet-------------------"+str(uuid.uuid4())

    def add(self, name, value, file=False, content_type=None):
        field = HTTPFields()
        if file:
            field.set("Content-Disposition", 'form-data; name="' + name + '"; filename="'+os.path.basename(value)+'"')
            field.set("Content-Type", get_mimetype(value))
            data = open(value, "rb")
        else:
            field.set("Content-Disposition", 'form-data; name="'+name+'"')
            if content_type:
                field.set("Content-Type", content_type)
            data = io.BytesIO(value)
        self.list.append((field, data))

    def get_content_type(self):
        return "multipart/form-data; boundary="+self.boundary

    def get_size(self):
        tot_size = 0
        for field, data in self.list:
            tot_size += len("--"+self.boundary+"\r\n")
            tot_size += len(str(field)+"\r\n")
            tot_size += get_file_length(data)
            tot_size += len("\r\n")
        tot_size += len("--"+self.boundary+"--")
        return tot_size

    def read_chunk(self, chunk_size):
        for field, bin_file in self.list:
            yield ("--" + self.boundary + "\r\n").encode()
            yield str(field).encode()+"\r\n".encode()
            bin_file.seek(0)
            while True:
                data = bin_file.read(chunk_size)
                if not data:
                    yield "\r\n".encode()
                    break
                yield data

        yield ("--" + self.boundary + "--").encode()