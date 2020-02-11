import inspect

import pythread

from pynet.http.data import HTTPData
from pynet.http.exceptions import HTTPError
from pynet.http.response import HTTPResponse
from pynet.http.tools import HTTP_CONNECTION_CONTINUE, HTTP_CONNECTION_UPGRADE
from pynet.http.websocket import webSocket_process_key, WebSocketClient


class HTTPHandler:
    handler_fields = []
    enable_session = False
    enable_range = False

    def __init__(self, header, args, addr, server):
        self.addr = addr
        self.user_data, self.header = args, header

        self.response = HTTPResponse()
        self.response.header.fields.add_fields(server.base_fields)
        self.response.header.fields.add_fields(self.handler_fields)

        self.server = server

        self.session = None
        self.data = None
        self.stream_handler = None

        if self.enable_session:
            self.session = self.server.sessionManager.get_session(self.header.get_cookie("sessionId"), addr[0])
            self.response.header.set_cookie("sessionId", self.session.uid, expire=self.session.expire, httponly=True)

        if self.enable_range:
            self.response.header.enable_range("bytes")

    def html_render(self, template_name, **kwargs):
        template = self.server.get_template(template_name)
        self.response.render(200, template, **kwargs)

    def upgrade(self, stream_handler):
        self.stream_handler = stream_handler

    def get_webSocket_room(self):
        return self.user_data.get("#ws_room")

    async def prepare(self):
        key = self.header.get_websocket_upgrade()
        if key and self.get_webSocket_room():
            key = webSocket_process_key(key)
            self.upgrade(WebSocketClient(self.header, self.get_webSocket_room(), self.addr, self.server))
            self.response.upgrade_websocket(key)
            return HTTP_CONNECTION_UPGRADE

        content_length = self.header.fields.get("Content-Length", 0, int)
        if content_length > 0:
            self.data = HTTPData(content_length)
        return HTTP_CONNECTION_CONTINUE

    async def prepare_response(self):
        if self.enable_range:
            self.response.set_length(self.header.fields.get("Range"))
        else:
            self.response.set_length()

        return self.response

    def feed(self, data_chunk):
        self.data.feed(data_chunk)

    def get_query_fct(self):
        if self.header.query == "GET":
            return self.GET

        elif self.header.query == "PUT":
            return self.PUT

        elif self.header.query == "DELETE":
            return self.DELETE

        elif self.header.query == "POST":
            return self.POST

    async def execute_request(self):
        fct = self.get_query_fct()
        if fct:
            if inspect.iscoroutinefunction(fct):
                await fct(self.header.url)
            else:
                await pythread.get_mode("httpServer").process(fct, self.header.url).async_wait()

        else:
            raise HTTPError(405)

    def GET(self, url):
        raise HTTPError(405)

    def PUT(self, url):
        raise HTTPError(405)

    def DELETE(self, url):
        raise HTTPError(405)

    def POST(self, url):
        raise HTTPError(405, handler=self)


class HTTP404handler(HTTPHandler):
    async def prepare(self):
        raise HTTPError(404)