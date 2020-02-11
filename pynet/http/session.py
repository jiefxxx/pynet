import time
import uuid


class HTTPSession:
    def __init__(self, addr, expire):
        self.uid = uuid.uuid4().hex
        self.addr = addr
        self.data = {}
        self.last_time = time.time()
        self.expire = expire

    def has_expire(self):
        return self.last_time+self.expire < time.time()

    def prolong(self):
        self.last_time = time.time()


class HTTPSessionManager:
    def __init__(self, expire=60):
        self.sessions = []
        self.expire = expire

    def get_session(self, uid, addr):
        if not uid:
            return self.new_session(addr)
        for session in self.sessions:
            if session.has_expire():
                self.sessions.remove(session)
            elif session.uid == uid:
                if session.addr == addr:
                    session.prolong()
                    return session
                self.sessions.remove(session)
        return self.new_session(addr)

    def new_session(self, addr):
        session = HTTPSession(addr, self.expire)
        self.sessions.append(session)
        return session

