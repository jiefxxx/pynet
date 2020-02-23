import io
import ssl

from pynet.http.header import HTTPRequestHeader, HTTPResponseHeader
from pynet.http.tools import create_connection, split_request, get_header, get_data


class HTTPClient:
    def __init__(self):
        pass

    async def request(self, request, url, data=None):
        scheme, host, url = split_request(url)
        header = HTTPRequestHeader().new(url, request)
        reader, writer = await create_connection(host, http_type=scheme)
        header.fields.set("Content-Length", 0)
        header.fields.set("Host", host)
        header.fields.set("Connection", "close")
        if data:
            header.fields.set("Content-Length", data.get_size())
            header.fields.set("Content-Type", data.get_content_type())

        writer.write(str(header).encode())
        await writer.drain()
        if data:
            for chunk in data.read_chunk(5*1024):
                writer.write(chunk)
                await writer.drain()

        header = await get_header(reader, HTTPResponseHeader)

        data = io.BytesIO()
        await get_data(reader, data, header.fields.get("Content-Length", default=None, data_type=int))
        data.seek(0)

        writer.close()
        try:
            await writer.wait_closed()
        except ssl.SSLError:
            pass

        return header, data

    async def get(self, url):
        return await self.request('GET', url)

    async def post(self, url, data):
        return await self.request("POST", url, data=data)