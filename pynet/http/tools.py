import asyncio
import datetime
import http
import io
import mimetypes
import os
import re
import shutil
import ssl
from http import cookies

import magic

from pynet.http import CHUNK_SIZE
from pynet.http.exceptions import HTTPStreamEnd, HTTPError


def get_file_length(file):
    file.seek(0, 2)
    return file.tell()


def format_cookie_date(delta):
    time_format = "%a, %d %b %Y %H:%M:%S %Z"
    return "%s" % ((datetime.datetime.now() + datetime.timedelta(minutes=delta)).strftime(time_format))


def create_cookie(name, value, expire=None, **kwargs):
    cookie = cookies.SimpleCookie()
    cookie[name] = value
    if expire:
        cookie[name]["expires"] = format_cookie_date(expire)
    for kwarg in kwargs:
        cookie[name][kwarg] = kwargs[kwarg]
    return cookie.output()[12:]


def get_mimetype(path):
    mime = magic.Magic().from_file(path)
    if mime == "text/plain":
        mime = mimetypes.guess_type(path)[0]
    return mime


def http_code_to_string(code):
    for el in http.HTTPStatus:
        if el.value == code:
            return el.phrase
    return ""


def http_parse_query(line):
    match = re.match(r"(.*) (.*) (.*)", line.decode())
    if match is not None:
        return match.group(1), match.group(2), match.group(3)
    else:
        raise Exception("Invalid Request", str(line))


def http_parse_field(line):
    match = re.match(r"(.*): (.*)", line.decode())
    if match is not None:
        return match.group(1), match.group(2)
    else:
        raise Exception("Invalid format field:", str(line))


def create_static_file(path):
    data = io.BytesIO()
    with open(path, "rb") as f:
        shutil.copyfileobj(f, data)
    return path, data, get_mimetype(path), os.path.getmtime(path)


class CachedFilesManager:
    def __init__(self, max_size=100):
        self.iobytes_list = []
        self.size = 0
        self.max_size = max_size

    def get(self, path):
        for data in self.iobytes_list:
            if data[0] == path:
                if data[3] < os.path.getmtime(path):
                    self.iobytes_list.remove(data)
                    self.size -= get_file_length(data[1])
                    break
                return data
        size = os.path.getsize(path)
        if size > self.max_size*1024*1024:
            return path, open(path, "rb"), get_mimetype(path), os.path.getmtime(path)
        data = create_static_file(path)
        self.size += size
        self.iobytes_list.append(data)
        while self.size > self.max_size*1024*1024:
            old_data = self.iobytes_list.pop(0)
            self.size -= old_data[4]
        return data


def log_response(log_fct, addr, response, handler=None):
    code = response.header.code
    if handler:
        log_fct("["+str(code) + "] "+http_code_to_string(code)+" "+
                str(addr)+" "+str(handler.header.query)+" "+str(handler.header.url))
    else:
        log_fct("["+str(code)+"] "+http_code_to_string(code)+" "+str(addr))


async def create_connection(host, port=80, http_type="http"):
    port = port
    sslctx = None

    if ":" in host:
        split_host = host.split(":")
        host = split_host[0]
        port = int(split_host[1])

    if http_type == "https":
        paths = ssl.get_default_verify_paths()
        sslctx = ssl.SSLContext()
        sslctx.verify_mode = ssl.CERT_REQUIRED
        sslctx.check_hostname = True
        sslctx.load_verify_locations(paths.cafile)
        port = 443
    return await asyncio.open_connection(ssl=sslctx, host=host, port=port)


def split_request(url):
    if url.startswith("http://"):
        return url[0:4], url[7:].split("/", 1)[0], "/"+url[7:].split("/", 1)[1]
    elif url.startswith("https://"):
        return url[0:5], url[8:].split("/", 1)[0], "/"+url[8:].split("/", 1)[1]
    else:
        return "http", url.split("/", 1)[0], "/"+url.split("/", 1)[1]


async def stream_reader(reader, stream_handler):
    prev_data = b''
    while True:
        data = await reader.read(CHUNK_SIZE)
        if len(data) == 0:
            raise HTTPStreamEnd()
        prev_data = stream_handler.feed(prev_data + data)


async def stream_sender(writer, stream_handler):
    while True:
        data = await stream_handler.queue.async_q.get()
        if data is None:
            raise HTTPStreamEnd()
        writer.write(data)
        await writer.drain()


async def get_header(reader, header_type, timeout=None):
    header = header_type()
    while True:
        try:
            if timeout:
                data = await asyncio.wait_for(reader.readline(), timeout=timeout)
            else:
                data = await reader.readline()
        except asyncio.TimeoutError:
            raise HTTPError(408)
        data = data[:-2]
        if len(data) > 0:
            header.parse_line(data)
        else:
            break
    return header


async def get_data(reader, handler, size=None):
    while not size and size > 0:
        if size and CHUNK_SIZE > size:
            data = await reader.read(size)
        else:
            data = await reader.read(CHUNK_SIZE)
        if size:
            size -= len(data)
        if not size and len(data) == 0:
            break
        if asyncio.iscoroutinefunction(handler.write):
            await handler.write(data)
        else:
            handler.write(data)