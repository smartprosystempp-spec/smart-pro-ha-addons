#!/usr/bin/env python3
"""Smart Pro Remote Support — τοπικός proxy προς το Home Assistant (0.12.0).

Γιατί υπάρχει: ο MeshCentral relay ανοίγει ένα tunnel ανά αίτημα και φτάνει στη συσκευή
μόνο στο 127.0.0.1:80 του add-on. Ο proxy δέχεται εκεί και προωθεί στο Home Assistant.
Δύο κρίσιμες ιδιότητες:
  1. Keep-alive: μετά από κάθε απάντηση το tunnel μένει ελεύθερο. Αν δεν υπάρχει ελεύθερο
     tunnel, ο relay χάνει το πρώτο μήνυμα του browser στο WebSocket (το auth του HA frontend).
  2. Αφαιρεί forwarding headers (X-Forwarded-*), γιατί το Home Assistant τα απορρίπτει με 400
     όταν δεν έχει ρυθμιστεί reverse proxy, και το sec-websocket-extensions.

Ξεκινά μόνο μετά από ρητή συγκατάθεση του πελάτη και σταματά όταν τελειώσει η συνεδρία.
Ακούει ΜΟΝΟ στο 127.0.0.1 μέσα στο container. Δεν καταγράφει διαδρομές, headers ή περιεχόμενο.
"""
import http.client
import http.server
import os
import socket
import threading
import time

DROP = {"x-forwarded-for", "x-forwarded-proto", "x-forwarded-host", "x-forwarded-port",
        "x-forwarded-server", "x-real-ip", "forwarded", "via", "x-original-forwarded-for",
        "sec-websocket-extensions"}
HOP = {"connection", "keep-alive", "proxy-connection", "transfer-encoding", "te", "trailer", "upgrade"}
DEFAULT_UPSTREAMS = [("172.30.32.1", 80), ("homeassistant", 80), ("homeassistant", 8123), ("172.30.32.1", 8123)]


def _parse_upstreams(text):
    out = []
    for part in (text or "").split(","):
        part = part.strip()
        if not part:
            continue
        host, _, port = part.rpartition(":")
        try:
            out.append((host, int(port)))
        except Exception:
            continue
    return out


def _probe(addr, timeout=3):
    """True αν στη διεύθυνση απαντά HTTP server."""
    try:
        s = socket.create_connection(addr, timeout)
    except Exception:
        return False
    try:
        s.settimeout(timeout)
        s.sendall(b"GET / HTTP/1.1\r\nHost: homeassistant\r\nConnection: close\r\n\r\n")
        return s.recv(16).startswith(b"HTTP/")
    except Exception:
        return False
    finally:
        try:
            s.close()
        except Exception:
            pass


def _pipe(a, b, stats, key):
    try:
        while True:
            d = a.recv(65536)
            if not d:
                break
            stats[key] = stats.get(key, 0) + len(d)
            b.sendall(d)
    except Exception:
        pass
    finally:
        for s in (a, b):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                s.close()
            except Exception:
                pass


class _Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def _read_body(self):
        te = (self.headers.get("Transfer-Encoding") or "").lower()
        if "chunked" in te:
            body = b""
            while True:
                line = self.rfile.readline(65537).strip()
                try:
                    size = int(line.split(b";")[0], 16)
                except Exception:
                    raise ValueError("bad chunk")
                if size == 0:
                    while True:  # trailers
                        t = self.rfile.readline(65537)
                        if t in (b"\r\n", b"\n", b""):
                            break
                    break
                body += self.rfile.read(size)
                self.rfile.readline(3)
            return body
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n > 0 else None

    def _websocket(self, hdrs):
        srv = self.server
        try:
            up = socket.create_connection(srv.upstream, 8)
        except Exception:
            self.send_error(502)
            self.close_connection = True
            return
        up.settimeout(None)
        head = "%s %s HTTP/1.1\r\n" % (self.command, self.path) + "".join("%s: %s\r\n" % kv for kv in hdrs) + "\r\n"
        up.sendall(head.encode("latin-1"))
        cl = self.connection
        cl.settimeout(None)
        for s in (up, cl):
            try:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            except Exception:
                pass
        with srv.lock:
            srv.stats["ws"] = srv.stats.get("ws", 0) + 1
        t = threading.Thread(target=_pipe, args=(up, cl, srv.stats, "ws_down"), daemon=True)
        t.start()
        _pipe(cl, up, srv.stats, "ws_up")
        self.close_connection = True

    def handle_any(self):
        srv = self.server
        hdrs = [(k, v) for k, v in self.headers.items() if k.lower() not in DROP]
        if "websocket" in (self.headers.get("Upgrade") or "").lower():
            self._websocket(hdrs)
            return
        try:
            body = self._read_body()
        except Exception:
            self.send_error(400)
            self.close_connection = True
            return
        fwd = {k: v for k, v in hdrs if k.lower() not in HOP and k.lower() not in ("content-length",)}
        fwd["Connection"] = "close"
        if body is not None:
            fwd["Content-Length"] = str(len(body))
        cn = None
        try:
            cn = http.client.HTTPConnection(srv.upstream[0], srv.upstream[1], timeout=30)
            cn.request(self.command, self.path, body=body, headers=fwd)
            r = cn.getresponse()
        except Exception:
            self.send_error(502)
            self.close_connection = True
            if cn:
                cn.close()
            return
        try:
            clen = r.getheader("Content-Length")
            bodyless = self.command == "HEAD" or r.status in (204, 304) or 100 <= r.status < 200
            self.send_response(r.status, r.reason)
            for k, v in r.getheaders():
                if k.lower() in HOP or k.lower() == "content-length":
                    continue
                self.send_header(k, v)
            if clen is not None and (self.command == "HEAD" or not bodyless):
                self.send_header("Content-Length", clen)
            keep = bodyless or clen is not None
            if not keep:
                self.send_header("Connection", "close")
                self.close_connection = True
            self.end_headers()
            if not bodyless:
                while True:
                    chunk = r.read(65536)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    if not keep:
                        self.wfile.flush()
            with srv.lock:
                srv.stats["http"] = srv.stats.get("http", 0) + 1
        except Exception:
            self.close_connection = True
        finally:
            try:
                cn.close()
            except Exception:
                pass

    do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = do_OPTIONS = do_HEAD = handle_any


class _Server(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 64


class HALocalProxy:
    def __init__(self, listen=None, upstreams=None):
        env_listen = os.environ.get("HP_LISTEN")
        if listen is None:
            if env_listen:
                host, _, port = env_listen.rpartition(":")
                listen = (host, int(port))
            else:
                listen = ("127.0.0.1", 80)
        self.listen = listen
        env_up = _parse_upstreams(os.environ.get("HP_UPSTREAMS"))
        self.upstreams = upstreams or env_up or list(DEFAULT_UPSTREAMS)
        self._server = None
        self._thread = None
        self._lock = threading.Lock()

    @property
    def running(self):
        return self._server is not None

    def start(self):
        """Επιστρέφει (ok, μήνυμα). Idempotent."""
        with self._lock:
            if self._server is not None:
                return True, "ήδη ενεργός"
            upstream = None
            for cand in self.upstreams:
                if _probe(cand):
                    upstream = cand
                    break
            if upstream is None:
                return False, "δεν βρέθηκε το Home Assistant"
            try:
                srv = _Server(self.listen, _Handler)
            except Exception as exc:
                return False, "δεν ανοίγει η τοπική θύρα (%s)" % exc.__class__.__name__
            srv.upstream = upstream
            srv.stats = {}
            srv.lock = threading.Lock()
            srv.started = time.time()
            t = threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.5}, daemon=True)
            t.start()
            self._server, self._thread = srv, t
            return True, "%s:%s" % upstream

    def stop(self):
        with self._lock:
            srv, self._server = self._server, None
        if srv is None:
            return None
        try:
            srv.shutdown()
        except Exception:
            pass
        try:
            srv.server_close()
        except Exception:
            pass
        st = dict(getattr(srv, "stats", {}))
        st["seconds"] = int(time.time() - getattr(srv, "started", time.time()))
        return st
