
class HTTPError(Exception):
    def __init__(self, code, handler=None):
        Exception.__init__(self, "HTTPError: "+str(code))
        self.code = code
        self.handler = handler


class HTTPStreamEnd(Exception):
    def __init__(self):
        Exception.__init__(self, "Close HTTPStream")
