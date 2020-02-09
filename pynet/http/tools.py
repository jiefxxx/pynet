import http
import mimetypes
import re

import magic


def get_mimetype(path):
    mime = magic.Magic().from_file(path)
    if mime == "text/plain":
        mime = mimetypes.guess_type(path)[0]
    return mime


def chunk(path, seek, size=1024 * 5):
    with open(path, "rb") as f:
        f.seek(seek)
        ret = f.read(size)
    return seek + len(ret), ret


def chunks(path, seek=0, chunk_size=65500):
    with open(path, "rb") as f:
        if seek > 0:
            f.seek(seek)
        while True:
            data = f.read(chunk_size)
            if not data:
                break
            yield data


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


HTTP_CONNECTION_ABORT = -1
HTTP_CONNECTION_CONTINUE = 0
HTTP_CONNECTION_UPGRADE = 1


def log_response(log_fct, addr, response, handler=None):
    code = response.header.code
    if handler:
        log_fct("["+str(code) + "] "+http_code_to_string(code)+" "+
                str(addr)+" "+str(handler.header.query)+" "+str(handler.header.url))
    else:
        log_fct("["+str(code)+"] "+http_code_to_string(code)+" "+str(addr))