from urllib.parse import urlparse, parse_qsl

from pynet.http.exceptions import HTTPError
from pynet.http.tools import http_parse_query, http_parse_field, http_code_to_string, create_cookie


class HTTPResponseHeader:
    def __init__(self):
        self.protocol = "HTTP/1.1"
        self.code = None
        self.fields = HTTPFields()

    def set_cookie(self, name, value, expire=None, **kwargs):
        finder = str(name)+"="+str(value)
        for field in self.fields.fields:
            if field[0] == "Set-Cookie" and field[1][:len(finder)] == finder:
                self.fields.fields.remove(field)
        self.fields.append(("Set-Cookie", create_cookie(name, value, expire, **kwargs)))

    def enable_range(self, value):
        self.fields.set("Accept-Ranges", value)

    def parse_line(self, line):
        if self.code is None:
            self.protocol, self.code, _ = http_parse_query(line)
        else:
            self.fields.append(http_parse_field(line))
            if self.fields.length() > 100:
                raise HTTPError(431)

    def __str__(self):
        ret = self.protocol + " " + str(self.code) + " " + http_code_to_string(self.code) + "\r\n"
        ret += str(self.fields)
        ret += "\r\n"
        return ret


class HTTPRequestHeader:
    def __init__(self):
        self.url = None
        self.query = None
        self.protocol = None
        self.fields = HTTPFields()

    def new(self, url, query, protocol="HTTP/1.1"):
        self.url = Url(url)
        self.query = query
        self.protocol = protocol
        return self

    def is_valid(self):
        if self.url and self.query and self.protocol:
            return True
        return False

    def keep_alive(self):
        connection = self.fields.get("Connection")
        if not connection:
            return False
        connection = connection.split(', ')
        if "keep-alive" in connection:
            return True
        return False

    def upgraded(self):
        connection = self.fields.get("Connection")
        if not connection:
            return False
        connection = connection.split(', ')
        if "Upgrade" in connection:
            return True
        return False

    def get_cookie(self, name, data_type=None):
        cookie_raw = self.fields.get("Cookie")
        if not cookie_raw:
            return
        for cookie in cookie_raw.split("; "):
            cookie = cookie.split("=")
            if cookie[0] == name:
                if data_type:
                    return data_type(cookie[1])
                return cookie[1]

    def get_websocket_upgrade(self):
        if self.upgraded() and self.fields.get("Upgrade") == "websocket":
            return self.fields.get("Sec-WebSocket-Key")

    def parse_line(self, line):
        if self.query is None:
            self.query, url, self.protocol = http_parse_query(line)
            self.url = Url(url)
        else:
            self.fields.append(http_parse_field(line))
            if self.fields.length() > 100:
                raise HTTPError(431)

    def __str__(self):
        ret = str(self.query) + " " + str(self.url) + " " + str(self.protocol) + "\r\n"
        ret += str(self.fields)
        ret += "\r\n"
        return ret


class HTTPFields:
    def __init__(self):
        self.fields = []

    def length(self):
        return len(self.fields)

    def get(self, name, default=None, data_type=None):
        for field_name, field_value in self.fields:
            if field_name == name:
                if not data_type:
                    return field_value
                else:
                    return data_type(field_value)
        return default

    def set(self, name, value):
        for i in range(0, len(self.fields)):
            if self.fields[i][0] == name:
                self.fields[i] = (name, value)
                return
        self.fields.append((name, value))

    def append(self, value):
        self.fields.append(value)

    def add_fields(self, fields):
        self.fields += fields

    def __str__(self):
        ret = ""
        for field in self.fields:
            ret += field[0] + ": " + str(field[1]) + "\r\n"
        return ret


class Url:
    def __init__(self, full_path):
        self.full = full_path
        self._parsed = urlparse(full_path)
        self.path = self._parsed.path
        self.query = parse_qsl(self._parsed.query)
        self.regex = []

    def get(self, key, default=None, data_type=None):
        for query in self.query:
            if query[0] == key:
                if data_type:
                    return data_type(query[1])
                return query[1]
        return default

    def to_sql_where(self, blacklist=None):
        if blacklist is None:
            blacklist = []
        where = {}
        for query in self.query:
            if query[0] not in blacklist:
                where[query[0]] = query[1]
                if query[1] == 'null':
                    where[query[0]] = None

        return where

    def __str__(self):
        return self.full
