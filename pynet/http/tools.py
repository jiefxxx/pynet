import datetime
import http
import io
import mimetypes
import os
import re
import shutil
from http import cookies

import magic

HTTP_CONNECTION_ABORT = -1
HTTP_CONNECTION_CONTINUE = 0
HTTP_CONNECTION_UPGRADE = 1


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