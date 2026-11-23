"""Προσωρινός λογαριασμός διαχειριστή Home Assistant για εφάπαξ υποστήριξη.

Δημιουργείται ΜΟΝΟ μετά από ρητό πάτημα κουμπιού του πελάτη, παραδίδεται
κρυπτογραφημένος (RSA-OAEP) στο Broker και σβήνεται όταν τελειώσει η συνεδρία.
Μόνο stdlib + openssl CLI. Κανένας κωδικός δεν γράφεται σε log ή δίσκο.
Μεταφορά του μοτίβου SupervisorCoreSession από το Smart Pro Tools.
"""
import base64
import hashlib
import json
import os
import secrets
import socket
import ssl
import struct
import subprocess
import tempfile
import urllib.error
import urllib.request

ACCOUNT_NAME = "Smart Pro Temporary Support"
USERNAME_PREFIX = "smartpro_guest_"
ADMIN_GROUP = "system-admin"
MARKER = "/data/ha_temp_account.json"
CONTEXT_FILE = "/tmp/smart-pro-phase-f-runtime/.ha-context.json"
TIMEOUT = 8.0
MAX_MESSAGE = 524288
ALLOWED = {"config/auth/list", "config/auth/create", "config/auth/delete",
           "config/auth_provider/homeassistant/create"}


class HAError(RuntimeError):
    """Σταθερός κωδικός αιτίας, ποτέ κωδικός πρόσβασης ή token."""


def _read_exact(sock, count):
    data = bytearray()
    while len(data) < count:
        part = sock.recv(count - len(data))
        if not part:
            raise HAError("connection_closed")
        data.extend(part)
    return bytes(data)


def _read_frame(sock):
    start = _read_exact(sock, 2)
    if start[0] & 0x70 or not (start[0] & 0x80) or start[1] & 128:
        raise HAError("frame_rejected")
    opcode = start[0] & 15
    n = start[1] & 127
    if n == 126:
        n = struct.unpack("!H", _read_exact(sock, 2))[0]
    elif n == 127:
        n = struct.unpack("!Q", _read_exact(sock, 8))[0]
    if n > MAX_MESSAGE:
        raise HAError("oversized_frame")
    return opcode, _read_exact(sock, n)


def _send_frame(sock, data, opcode=1):
    mask = os.urandom(4)
    n = len(data)
    header = bytes([0x80 | n]) if n < 126 else (b"\xfe" + struct.pack("!H", n) if n < 65536 else b"\xff" + struct.pack("!Q", n))
    sock.sendall(bytes([0x80 | opcode]) + header + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))


def _recv_json(sock):
    for _ in range(12):
        opcode, payload = _read_frame(sock)
        if opcode == 9:
            _send_frame(sock, payload, 10)
            continue
        if opcode != 1:
            raise HAError("unexpected_frame")
        try:
            msg = json.loads(payload.decode("utf-8"))
        except Exception:
            raise HAError("invalid_json")
        if not isinstance(msg, dict):
            raise HAError("invalid_message")
        return msg
    raise HAError("too_many_control_frames")


def _handshake(sock):
    key = base64.b64encode(os.urandom(16)).decode("ascii")
    accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()).decode("ascii")
    sock.sendall(("GET /core/websocket HTTP/1.1\r\nHost: supervisor\r\nConnection: Upgrade\r\nUpgrade: websocket\r\n"
                  "Sec-WebSocket-Version: 13\r\nSec-WebSocket-Key: %s\r\n\r\n" % key).encode("ascii"))
    data = bytearray()
    while b"\r\n\r\n" not in data:
        if len(data) > 8192:
            raise HAError("oversized_upgrade")
        part = sock.recv(1)
        if not part:
            raise HAError("upgrade_closed")
        data.extend(part)
    lines = data.decode("ascii", "replace").split("\r\n")
    if not lines[0].startswith("HTTP/1.1 101 "):
        raise HAError("upgrade_rejected")
    headers = {}
    for line in lines[1:]:
        name, sep, value = line.partition(":")
        if sep:
            headers[name.lower().strip()] = value.strip()
    if headers.get("sec-websocket-accept") != accept:
        raise HAError("invalid_accept")


class CoreSession:
    def __init__(self, token):
        if not isinstance(token, str) or len(token) < 16:
            raise HAError("core_auth_unavailable")
        self.token = token
        self.sock = None
        self.id = 0

    def __enter__(self):
        try:
            self.sock = socket.create_connection(("supervisor", 80), TIMEOUT)
            self.sock.settimeout(TIMEOUT)
            _handshake(self.sock)
            if _recv_json(self.sock).get("type") != "auth_required":
                raise HAError("challenge_invalid")
            _send_frame(self.sock, json.dumps({"type": "auth", "access_token": self.token}, separators=(",", ":")).encode())
            if _recv_json(self.sock).get("type") != "auth_ok":
                raise HAError("auth_denied")
            return self
        except Exception:
            self.__exit__()
            raise

    def __exit__(self, *_):
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock = None
        self.token = ""

    def command(self, command_type, **params):
        if command_type not in ALLOWED:
            raise HAError("command_not_allowed")
        self.id += 1
        _send_frame(self.sock, json.dumps({"id": self.id, "type": command_type, **params}, separators=(",", ":")).encode())
        res = _recv_json(self.sock)
        if res.get("id") != self.id or res.get("type") != "result":
            raise HAError("reply_invalid")
        if res.get("success") is not True:
            raise HAError("command_rejected")
        return res.get("result")


def _is_ours(user):
    return isinstance(user, dict) and isinstance(user.get("name"), str) and user["name"] == ACCOUNT_NAME and isinstance(user.get("id"), str) and user.get("is_owner") is False and user.get("system_generated") is False


def _write_marker(user_id):
    fd = os.open(MARKER, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump({"user_id": user_id}, f)


def _clear_marker():
    try:
        os.unlink(MARKER)
    except OSError:
        pass


# ---- Broker ---------------------------------------------------------------

def read_context():
    """Το phase-f script γράφει report_token/arch στο runtime dir· σβήνεται μαζί του."""
    try:
        with open(CONTEXT_FILE, "r", encoding="utf-8") as f:
            ctx = json.load(f)
        if all(isinstance(ctx.get(k), str) and ctx[k] for k in ("report_token", "client_version", "architecture")):
            return ctx
    except Exception:
        pass
    return None


def context_alive():
    return os.path.exists(CONTEXT_FILE)


def _broker_post(broker_validate_url, route, payload):
    url = broker_validate_url.rsplit("/session/validate", 1)[0] + "/session/execution/ha-account/" + route
    if not url.startswith("https://"):
        raise HAError("broker_not_https")
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Cache-Control": "no-store", "User-Agent": "SmartProRemoteSupportSession/ha"})
    try:
        with urllib.request.urlopen(req, timeout=20, context=ssl.create_default_context()) as resp:
            return int(resp.status), json.loads(resp.read(65536).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            return int(exc.code), json.loads(exc.read(65536).decode("utf-8"))
        except Exception:
            return int(exc.code), {}
    except Exception:
        raise HAError("broker_unreachable")


def _encrypt(public_pem, plain):
    with tempfile.TemporaryDirectory(prefix="spha") as d:
        os.chmod(d, 0o700)
        kp = os.path.join(d, "k.pem")
        with open(kp, "w") as f:
            f.write(public_pem)
        try:
            out = subprocess.run(["openssl", "pkeyutl", "-encrypt", "-pubin", "-inkey", kp, "-pkeyopt", "rsa_padding_mode:oaep"],
                                 input=plain, capture_output=True, timeout=15, check=True).stdout
        except Exception:
            raise HAError("crypto_unavailable")
    if len(out) < 128:
        raise HAError("crypto_unavailable")
    return base64.b64encode(out).decode("ascii")


def create_and_deliver(broker_url):
    """Επιστρέφει username. Αν κάτι αποτύχει ΜΕΤΑ τη δημιουργία, ο λογαριασμός σβήνεται αμέσως."""
    ctx = read_context()
    if not ctx:
        raise HAError("no_active_execution")
    base = {"report_token": ctx["report_token"], "client": "home_assistant_os",
            "client_version": ctx["client_version"], "architecture": ctx["architecture"]}
    status, data = _broker_post(broker_url, "key", base)
    pem = data.get("public_key") if status == 200 and isinstance(data, dict) else None
    if not isinstance(pem, str) or "BEGIN PUBLIC KEY" not in pem:
        raise HAError("no_public_key")
    _encrypt(pem, b"precheck")  # αν αποτύχει εδώ, ΔΕΝ δημιουργείται λογαριασμός
    token = os.environ.get("SUPERVISOR_TOKEN", "")
    username = USERNAME_PREFIX + secrets.token_hex(4)
    password = secrets.token_urlsafe(30)
    uid = None
    try:
        with CoreSession(token) as core:
            users = core.command("config/auth/list")
            if not isinstance(users, list):
                raise HAError("inventory_invalid")
            for u in users:  # αν έμεινε παλιός δικός μας, σβήνεται πρώτα
                if _is_ours(u):
                    core.command("config/auth/delete", user_id=u["id"])
            res = core.command("config/auth/create", name=ACCOUNT_NAME, group_ids=[ADMIN_GROUP], local_only=True)
            uid = res.get("user", {}).get("id") if isinstance(res, dict) else None
            if not isinstance(uid, str) or len(uid) < 16:
                raise HAError("identity_uncertain")
            _write_marker(uid)
            core.command("config/auth_provider/homeassistant/create", user_id=uid, username=username, password=password)
        cipher = _encrypt(pem, json.dumps({"u": username, "p": password}, separators=(",", ":")).encode())
        status, data = _broker_post(broker_url, "deliver", {**base, "ciphertext": cipher, "username": username})
        if status != 200 or data.get("stored") is not True:
            raise HAError("delivery_failed")
        return username
    except Exception:
        if uid:
            try:
                delete_account(uid)
            except Exception:
                pass
        raise
    finally:
        password = ""


def delete_account(user_id=None):
    """Σβήνει τον δικό μας λογαριασμό (marker ή όλους με το όνομά μας). Επιστρέφει True αν δεν έμεινε τίποτα."""
    token = os.environ.get("SUPERVISOR_TOKEN", "")
    with CoreSession(token) as core:
        users = core.command("config/auth/list")
        if not isinstance(users, list):
            raise HAError("inventory_invalid")
        for u in users:
            if _is_ours(u):
                core.command("config/auth/delete", user_id=u["id"])
        after = core.command("config/auth/list")
        if any(_is_ours(u) for u in after):
            raise HAError("delete_uncertain")
    _clear_marker()
    return True


def cleanup_leftover():
    """Στην εκκίνηση του add-on: αν έμεινε προσωρινός λογαριασμός, σβήνεται."""
    if not os.environ.get("SUPERVISOR_TOKEN"):
        return "no_token"
    try:
        delete_account()
        return "clean"
    except Exception as exc:
        return "failed:" + str(exc)[:40]
