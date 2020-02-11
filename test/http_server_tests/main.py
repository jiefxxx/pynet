import asyncio
import logging
import time

import pythread

from pynet.http.handler import HTTPHandler
from pynet.http.server import HTTPServer
from pynet.http.websocket import WebSocketRoom

logging.basicConfig(level=logging.DEBUG)


class ScriptsRoom(WebSocketRoom):
    def __init__(self, name=None):
        WebSocketRoom.__init__(self, name)
        self.last_time = time.time()

    def on_message(self, client, message):
        print(type(self).__name__, client.addr, message)

    def notify(self):
        self.send("testing")


class MainHandler(HTTPHandler):
    handler_fields = [("Access-Control-Allow-Origin", "*")]
    enable_session = True

    async def GET(self, url):
        # raise HTTPError(404)
        print("test1", self.header.get_cookie("test1", int))
        self.response.header.set_cookie("test1", 42, expire=5, httponly=True)

        print("test2", self.session.data.get("test2"))
        self.session.data["test2"] = 43

        self.response.file("/home/jief/workspace/pynet/test/http_server_tests/main.html")


class FileHandler(HTTPHandler):
    async def GET(self, url):
        self.user_data["notify"].notify()
        self.response.file("/home/jief/workspace/pynet/test/http_server_tests/js/"+url.regex[0])


class TestHandler(HTTPHandler):
    async def GET(self, url):
        self.response.text(200, "test_string", content_type="text/html")


class TestJsonHandler(HTTPHandler):
    async def GET(self, url):
        self.response.json(200, {"test": {"name": "json", "value": 42}})


scripts_room = ScriptsRoom()

loop = asyncio.get_event_loop()
http_server = HTTPServer(loop)
http_server.add_user_data("notify", scripts_room)
http_server.add_route("/", MainHandler,  ws=scripts_room)
http_server.add_route("/js/(.*)", FileHandler)
http_server.add_route("/test", TestHandler)
http_server.add_route("/json", TestJsonHandler)
http_server.initialize(8080)

try:
    loop.run_forever()
except KeyboardInterrupt:
    pass

http_server.close()
loop.close()
pythread.close_all_mode()