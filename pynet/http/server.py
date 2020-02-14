import asyncio
import logging
import re

import pythread
from mako.lookup import TemplateLookup
from pythread.modes import ProcessMode

from pynet.http.exceptions import HTTPError, HTTPStreamEnd
from pynet.http.handler import HTTP404handler
from pynet.http.header import HTTPRequestHeader
from pynet.http.response import HTTPResponse
from pynet.http.session import HTTPSessionManager
from pynet.http.tools import HTTP_CONNECTION_CONTINUE, HTTP_CONNECTION_UPGRADE, log_response, CachedFilesManager

CHUNK_SIZE = 1024*50


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


async def get_header(reader):
    header = HTTPRequestHeader()
    while True:
        try:
            data = await asyncio.wait_for(reader.readline(), timeout=5.0)
        except asyncio.TimeoutError:
            raise HTTPError(408)
        data = data[:-2]
        if len(data) > 0:
            header.parse_line(data)
        else:
            break
    return header


async def get_data(reader, size, handler):
    while size > 0:
        if CHUNK_SIZE > size:
            data = await reader.read(size)
        else:
            data = await reader.read(CHUNK_SIZE)
        size -= len(data)
        if asyncio.iscoroutinefunction(handler.feed):
            await handler.feed(data)
        else:
            handler.feed(data)
    return True


async def send_response(writer, response):
    for data in response.sender(CHUNK_SIZE):
        writer.write(data)
        await writer.drain()


async def send_error(writer, code, server, handler=None):
    if handler:
        response = handler.response.error(code)
    else:
        response = HTTPResponse()
        response.header.fields.add_fields(server.base_fields)
    try:
        await send_response(writer, response.error(code))
    except (ConnectionResetError, BrokenPipeError):
        pass
    finally:
        return response


async def http_worker(reader, writer, server):
    addr = writer.get_extra_info('peername')
    handler = None
    stream_handler = None
    try:
        while True:
            header = await get_header(reader)
            if not header.is_valid():
                raise HTTPError(400)

            handler_construct, user_data, regex = server.router.get_route(header.url.path)
            header.url.regex = regex
            handler = handler_construct(header, user_data, addr, server)

            prepare_return = await handler.prepare()

            if prepare_return == HTTP_CONNECTION_CONTINUE:

                data_count = header.fields.get("Content-Length", 0, int)

                if not await get_data(reader, data_count, handler):
                    raise HTTPError(handler.abort_code, handler=handler)

                await handler.execute_request()
                response = await handler.prepare_response()
                log_response(logging.info, addr, response, handler)
                await send_response(writer, response)

            elif prepare_return == HTTP_CONNECTION_UPGRADE:
                response = await handler.prepare_response()
                await send_response(writer, response)
                log_response(logging.info, addr, handler.response, handler)
                stream_handler = handler.stream_handler
                await asyncio.gather(stream_sender(writer, stream_handler),
                                     stream_reader(reader, stream_handler))

            else:
                raise HTTPError(500)

            if not header.keep_alive():
                break
            handler = None

    except (ConnectionResetError, BrokenPipeError, HTTPStreamEnd):
        if stream_handler:
            stream_handler.error()

    except HTTPError as exc:
        response = await send_error(writer, exc.code, server, handler)
        log_response(logging.warning, addr, response, handler)

    except Exception as e:
        response = await send_error(writer, 500, server, handler)
        log_response(logging.exception, addr, response, handler)

    finally:
        writer.close()


class HTTPRouter:
    def __init__(self):
        self.route = []
        self.user_data = {}

    def get_route(self, path):
        for reg_path, handler, user_data in self.route:
            m = re.fullmatch(reg_path, path)
            if m is not None:
                user_data.update(self.user_data)
                regex = []
                for group in m.groups():
                    if len(group) == 0:
                        group = None
                    regex.append(group)
                return handler, user_data, regex
        return HTTP404handler, [], []

    def add_user_data(self, name, value):
        self.user_data[name] = value

    def add_route(self, reg_path, handler, user_data=None, ws=None):
        if not user_data:
            user_data = {}
        if ws is not None:
            user_data["#ws_room"] = ws
        self.route.append((reg_path, handler, user_data))


class HTTPServer():
    def __init__(self, port=8080, loop=None, template_dir="template/", cache_size=100):
        if not loop:
            loop = asyncio.get_event_loop()

        self.cached = CachedFilesManager(max_size=cache_size)
        self.router = HTTPRouter()
        self.sessionManager = HTTPSessionManager()
        self.template_lookup = TemplateLookup(directories=[template_dir],
                                              module_directory='/tmp/mako_modules')
        self.loop = loop
        self.server = None
        self.port = port
        self.base_fields = [("Server", "pynet/0.1.2")]
        pythread.create_new_mode(ProcessMode, "httpServer", size=5)

    def set_base_fields(self, base_fields):
        self.base_fields = base_fields + [("Server", "pynet/0.1.2")]

    def get_template(self, name):
        return self.template_lookup.get_template(name)

    async def root_handler(self, reader, writer):
        await http_worker(reader, writer, self)

    def start(self):
        coro = asyncio.start_server(self.root_handler, reuse_address=True, port=self.port, loop=self.loop)
        self.server = self.loop.run_until_complete(coro)
        logging.info('Serving on {}'.format(self.server.sockets[0].getsockname()))

    def run_forever(self):
        try:
            self.loop.run_forever()
        except KeyboardInterrupt:
            pass
        finally:
            self.close()

    def close(self):
        self.server.close()
        self.loop.run_until_complete(self.server.wait_closed())
        pythread.close_mode("httpServer")
