import asyncio
import re

import janus
from pythread import threaded, create_new_mode
from pythread.modes import ProcessMode

from pynet.http.handler import HTTP404Handler
from pynet.http.header import HTTPHeader
from pynet.http.tools import HTTP_CONNECTION_ABORT, HTTP_CONNECTION_CONTINUE, HTTP_CONNECTION_UPGRADE

CHUNK_SIZE = 1024*5


async def feed_stream_reader(reader, stream_reader):
    try:
        prev_data = b''
        while True:
            data = await reader.read(CHUNK_SIZE)
            if len(data) == 0:
                break
            prev_data = stream_reader.feed(prev_data + data)
        return True
    except (ConnectionResetError, BrokenPipeError):
        stream_reader.error()
        return False


async def get_header(reader):
    try:
        header = HTTPHeader()
        while True:
            data = await reader.readline()
            data = data[:-2]
            if len(data) > 0:
                header.parse_line(data)
            else:
                break
        return header
    except (ConnectionResetError, BrokenPipeError):
        return None


async def feed_data(reader, size, handler):
    try:

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

    except (ConnectionResetError, BrokenPipeError):
        return False


class HTTPConnection:
    def __init__(self, server, writer, reader, loop):
        self.queue = janus.Queue(maxsize=100, loop=loop)
        self.server, self.writer, self.reader = server, writer, reader
        self.alive = True
        self.stream_reader = None

    def is_alive(self):
        return self.alive

    def send(self, data, chunk_size=None):
        if chunk_size is None:
            chunk_size = CHUNK_SIZE
        if chunk_size > 0:
            while len(data) > chunk_size:
                self.queue.sync_q.put(data[:chunk_size])
                data = data[chunk_size:]
            self.queue.sync_q.put(data)
        else:
            if not self.queue.sync_q.full():
                self.queue.sync_q.put(data)
                return True
            else:
                return False

    def get_handler(self, header):
        handler, args = self.server.get_route(header.url.path)
        return handler(header, self, args)

    def close(self):
        if self.alive:
            self.queue.sync_q.put(None)

    async def async_close(self):
        if self.alive:
            await self.queue.async_q.put(None)

    def kill(self):
        if self.stream_reader:
            self.stream_reader.error()
        self.alive = False
        self.writer.close()

    @threaded("httpServer")
    def execute(self, handler):
        handler.execute_request()

    async def sender(self):
        try:

            while True:
                data = await self.queue.async_q.get()
                if data is None:
                    self.kill()
                    return
                self.writer.write(data)
                await self.writer.drain()

        except (ConnectionResetError, BrokenPipeError):
            self.kill()

    async def receiver(self):
        header = await get_header(self.reader)
        if header is None or not header.is_valid():
            self.kill()
            return

        handler = self.get_handler(header)

        if asyncio.iscoroutinefunction(handler.prepare):
            prepare_return = await handler.prepare()
        else:
            prepare_return = handler.prepare()

        if prepare_return == HTTP_CONNECTION_ABORT:
            return await self.async_close()

        elif prepare_return == HTTP_CONNECTION_CONTINUE:
            data_count = int(header.fields.get("Content-Length", default='0'))
            if not await feed_data(self.reader, data_count, handler):
                return self.kill()

            await self.execute(handler).async_wait()

            return await self.async_close()

        elif prepare_return == HTTP_CONNECTION_UPGRADE:
            self.stream_reader = handler.upgraded_streamReader
            if not await feed_stream_reader(self.reader, self.stream_reader):
                self.kill()

            return await self.async_close()

        return await self.async_close()


class HTTPRouter:
    def __init__(self):
        self.route = []
        self.user_data = {}

    def get_route(self, path):
        for reg_path, handler, user_data in self.route:
            m = re.fullmatch(reg_path, path)
            if m is not None:
                user_data.update(self.user_data)
                args = []
                for group in m.groups():
                    if len(group) == 0:
                        group = None
                    args.append(group)
                user_data["#regex_data"] = tuple(args)
                return handler, user_data
        return HTTP404Handler, {"#regex_data": ()}

    def add_user_data(self, name, value):
        self.user_data[name] = value

    def add_route(self, reg_path, handler, user_data=None, ws=None):
        if not user_data:
            user_data = {}
        if ws is not None:
            user_data["#ws_room"] = ws
        self.route.append((reg_path, handler, user_data))


class HTTPServer(HTTPRouter):
    def __init__(self, loop):
        HTTPRouter.__init__(self)
        self.loop = loop
        self.server = None
        create_new_mode(ProcessMode, "httpServer", size=5)

    async def root_handler(self, reader, writer):
        connection = HTTPConnection(self, writer, reader, self.loop)
        await asyncio.gather(connection.sender(), connection.receiver())

    def initialize(self, port=4242):
        coro = asyncio.start_server(self.root_handler, reuse_address=True, port=port, loop=self.loop)
        self.server = self.loop.run_until_complete(coro)
        print('Serving on {}'.format(self.server.sockets[0].getsockname()))

    def close(self):
        self.server.close()
        self.loop.run_until_complete(self.server.wait_closed())
