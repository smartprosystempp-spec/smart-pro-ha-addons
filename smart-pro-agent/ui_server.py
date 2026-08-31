#!/usr/bin/env python3
import html
import json
import os
import re
import secrets
import ssl
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSION = os.environ.get("SMART_PRO_VERSION", "2.0.1")
ARCH = os.environ.get("SMART_PRO_ARCH", "").strip().lower()
PORT = 8098
OPTIONS_FILE = "/data/options.json"
IDENTITY_FILE = "/data/managed_identity.json"
DEFAULT_BROKER_BASE_URL = "https://smart-pro-system.gr/wp-json/smart-pro-remote/v1/managed"
CLIENT_ID = "smart_pro_managed_support"
HEARTBEAT_SECONDS = 60
CSRF_TOKEN = secrets.token_urlsafe(32)
STATE_LOCK = threading.RLock()
STATE = {
    "identity": None,
    "status": "unpaired",
    "last_heartbeat": None,
    "last_error": None,
    "heartbeat_interval": HEARTBEAT_SECONDS,
}


def safe_broker_base_url():
    url = DEFAULT_BROKER_BASE_URL
    try:
        with open(OPTIONS_FILE, "r", encoding="utf-8") as handle:
            options = json.load(handle)
        candidate = str(options.get("broker_base_url") or "").strip().rstrip("/")
        if candidate:
            url = candidate
    except (OSError, ValueError, TypeError):
        pass
    if not url.startswith("https://"):
        return None
    return url.rstrip("/")


def normalize_pairing_code(value):
    normalized = re.sub(r"[^A-Z0-9]", "", str(value or "").upper())
    if not re.fullmatch(r"SPM[A-HJ-NP-Z2-9]{16}", normalized):
        return None
    return "SPM-{}-{}-{}-{}".format(
        normalized[3:7], normalized[7:11], normalized[11:15], normalized[15:19]
    )


def load_identity():
    try:
        with open(IDENTITY_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError, TypeError):
        return None
    node_id = str(data.get("node_id") or "")
    node_secret = str(data.get("node_secret") or "")
    installation_ref = str(data.get("installation_ref") or "")
    if not re.fullmatch(r"SPMN-[A-F0-9]{32}", node_id):
        return None
    if not re.fullmatch(r"SPMS-[A-Za-z0-9_-]{43}", node_secret):
        return None
    if not installation_ref:
        return None
    return {
        "node_id": node_id,
        "node_secret": node_secret,
        "installation_ref": installation_ref[:100],
        "paired_at": str(data.get("paired_at") or ""),
    }


def persist_identity(identity):
    os.makedirs("/data", mode=0o700, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix="managed_identity.", dir="/data", text=True)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(identity, handle, ensure_ascii=False, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, IDENTITY_FILE)
        os.chmod(IDENTITY_FILE, 0o600)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def broker_post(endpoint, payload, timeout=15):
    base = safe_broker_base_url()
    if not base:
        raise RuntimeError("Η διεύθυνση της ασφαλούς υπηρεσίας δεν είναι έγκυρη.")
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        base + endpoint,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": f"SmartProManagedSupport/{VERSION}",
        },
        method="POST",
    )
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            raw = response.read(131072)
            return response.status, json.loads(raw.decode("utf-8")) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read(131072)
        content_type = str(exc.headers.get("Content-Type") or "unknown").split(";", 1)[0].strip().lower()
        print(f"[managed] Broker {endpoint}: HTTP {exc.code}, Content-Type={content_type}", flush=True)
        try:
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except (ValueError, UnicodeDecodeError):
            data = {}
        if isinstance(data, dict) and data.get("message"):
            message = str(data.get("message"))
        else:
            message = f"Η ασφαλής υπηρεσία απέρριψε το αίτημα (HTTP {exc.code}, {content_type})."
        raise RuntimeError(message) from exc
    except (urllib.error.URLError, TimeoutError, ssl.SSLError) as exc:
        raise RuntimeError("Δεν ήταν δυνατή η ασφαλής επικοινωνία με το Smart Pro System.") from exc


def do_pair(code):
    if ARCH not in ("aarch64", "amd64"):
        raise RuntimeError("Η αρχιτεκτονική αυτής της εγκατάστασης δεν υποστηρίζεται ακόμη.")
    status, data = broker_post(
        "/pair",
        {
            "pairing_code": code,
            "client": CLIENT_ID,
            "client_version": VERSION,
            "architecture": ARCH,
        },
    )
    if status != 201 or not data.get("success"):
        raise RuntimeError("Το pairing δεν ολοκληρώθηκε.")
    if data.get("remote_access") is not False or data.get("execution") is not False or data.get("meshcentral") is not False:
        raise RuntimeError("Η απάντηση παραβίασε το Managed Foundation security boundary.")
    identity = {
        "node_id": str(data.get("node_id") or ""),
        "node_secret": str(data.get("node_secret") or ""),
        "installation_ref": str(data.get("installation_ref") or "")[:100],
        "paired_at": str(data.get("paired_at") or ""),
    }
    if not re.fullmatch(r"SPMN-[A-F0-9]{32}", identity["node_id"]):
        raise RuntimeError("Η υπηρεσία επέστρεψε μη έγκυρη managed identity.")
    if not re.fullmatch(r"SPMS-[A-Za-z0-9_-]{43}", identity["node_secret"]):
        raise RuntimeError("Η υπηρεσία επέστρεψε μη έγκυρο managed credential.")
    if not identity["installation_ref"]:
        raise RuntimeError("Η υπηρεσία δεν επέστρεψε αναφορά εγκατάστασης.")
    persist_identity(identity)
    with STATE_LOCK:
        STATE["identity"] = identity
        STATE["status"] = "paired"
        STATE["last_error"] = None
    return identity


def heartbeat_once():
    with STATE_LOCK:
        identity = STATE.get("identity")
    if not identity:
        return
    try:
        status, data = broker_post(
            "/heartbeat",
            {
                "node_id": identity["node_id"],
                "node_secret": identity["node_secret"],
                "client_version": VERSION,
                "architecture": ARCH,
            },
        )
        if status != 200 or not data.get("success"):
            raise RuntimeError("Το heartbeat δεν επιβεβαιώθηκε.")
        if data.get("remote_access") is not False or data.get("execution") is not False or data.get("meshcentral") is not False:
            raise RuntimeError("Η απάντηση παραβίασε το Managed Foundation security boundary.")
        interval = int(data.get("heartbeat_interval_seconds") or HEARTBEAT_SECONDS)
        interval = max(30, min(300, interval))
        with STATE_LOCK:
            STATE["status"] = "ready"
            STATE["last_heartbeat"] = str(data.get("last_seen_at") or "")
            STATE["last_error"] = None
            STATE["heartbeat_interval"] = interval
    except RuntimeError as exc:
        with STATE_LOCK:
            STATE["status"] = "connection_error"
            STATE["last_error"] = str(exc)


def heartbeat_loop():
    time.sleep(3)
    while True:
        with STATE_LOCK:
            identity = STATE.get("identity")
            interval = int(STATE.get("heartbeat_interval") or HEARTBEAT_SECONDS)
        if identity:
            heartbeat_once()
        time.sleep(max(30, min(300, interval)))


def snapshot():
    with STATE_LOCK:
        identity = STATE.get("identity")
        return {
            "identity": dict(identity) if identity else None,
            "status": STATE.get("status"),
            "last_heartbeat": STATE.get("last_heartbeat"),
            "last_error": STATE.get("last_error"),
        }


def esc(value):
    return html.escape(str(value or ""), quote=True)


def render_page(message=None, error=None):
    state = snapshot()
    identity = state["identity"]
    status = state["status"]
    if not identity:
        badge = '<span class="badge neutral"><span></span>Δεν έχει γίνει σύνδεση</span>'
        body = f'''
          <section class="card hero">
            <div class="eyebrow">SMART PRO MANAGED SUPPORT</div>
            <h1>Σύνδεση με το Smart Pro System</h1>
            <p class="lead">Χρησιμοποιήστε τον προσωρινό κωδικό pairing που σας δόθηκε από το Smart Pro Support. Ο κωδικός χρησιμοποιείται μία φορά και δεν αποθηκεύεται από την εφαρμογή.</p>
            <form method="post" action="pair" autocomplete="off">
              <input type="hidden" name="csrf" value="{esc(CSRF_TOKEN)}">
              <label for="pairing_code">Κωδικός pairing</label>
              <input id="pairing_code" name="pairing_code" type="text" inputmode="text" maxlength="32" placeholder="SPM-XXXX-XXXX-XXXX-XXXX" required autocapitalize="characters" spellcheck="false">
              <button type="submit">Σύνδεση εγκατάστασης</button>
            </form>
            <div class="note"><strong>Ασφάλεια:</strong> Σε αυτή τη φάση ενεργοποιούνται μόνο η ταυτοποίηση της εγκατάστασης και το ασφαλές heartbeat. Δεν ενεργοποιείται απομακρυσμένη πρόσβαση.</div>
          </section>'''
    else:
        if status == "ready":
            badge = '<span class="badge ok"><span></span>Έτοιμο για υποστήριξη</span>'
            status_title = "Η εγκατάσταση είναι συνδεδεμένη"
            status_text = "Το Smart Pro System αναγνωρίζει με ασφάλεια αυτή την εγκατάσταση. Δεν υπάρχει ενεργή απομακρυσμένη συνεδρία."
        elif status == "connection_error":
            badge = '<span class="badge warn"><span></span>Έλεγχος σύνδεσης</span>'
            status_title = "Δεν επιβεβαιώθηκε το τελευταίο heartbeat"
            status_text = "Η εφαρμογή θα προσπαθήσει ξανά αυτόματα. Η απομακρυσμένη πρόσβαση παραμένει ανενεργή."
        else:
            badge = '<span class="badge info"><span></span>Ολοκλήρωση σύνδεσης</span>'
            status_title = "Το pairing ολοκληρώθηκε"
            status_text = "Γίνεται η πρώτη ασφαλής επιβεβαίωση της εγκατάστασης με το Smart Pro System."
        last_seen = esc(state.get("last_heartbeat") or "Αναμονή πρώτου heartbeat")
        error_html = f'<div class="inline-warning">{esc(state.get("last_error"))}</div>' if state.get("last_error") else ""
        body = f'''
          <section class="card hero">
            <div class="eyebrow">SMART PRO MANAGED SUPPORT</div>
            <h1>{esc(status_title)}</h1>
            <p class="lead">{esc(status_text)}</p>
            <div class="facts">
              <div><span>Εγκατάσταση</span><strong>{esc(identity.get("installation_ref"))}</strong></div>
              <div><span>Κατάσταση υποστήριξης</span><strong>Δεν υπάρχει ενεργή συνεδρία</strong></div>
              <div><span>Τελευταία επιβεβαίωση</span><strong>{last_seen}</strong></div>
            </div>
            {error_html}
            <div class="note"><strong>Τρέχον στάδιο 2.0.0:</strong> Η εφαρμογή δεν κατεβάζει και δεν εκτελεί MeshAgent και δεν παρέχει remote access. Το επόμενο στάδιο θα ενεργοποιηθεί μόνο μετά από ξεχωριστό QA.</div>
          </section>'''
    notices = ""
    if message:
        notices += f'<div class="notice success">{esc(message)}</div>'
    if error:
        notices += f'<div class="notice error">{esc(error)}</div>'
    return f'''<!doctype html>
<html lang="el"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Cache-Control" content="no-store"><title>Smart Pro Support</title>
<style>
:root{{--bg:#0b1118;--card:#121b25;--line:#263444;--text:#f3f7fb;--muted:#a9b7c6;--blue:#4db4e6;--green:#69d58c;--amber:#f0b84b;--red:#ff7070;}}
*{{box-sizing:border-box}}body{{margin:0;background:linear-gradient(180deg,#0b1118,#0d151e);color:var(--text);font:15px/1.55 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;min-height:100vh}}
.shell{{max-width:980px;margin:0 auto;padding:30px 20px 56px}}header{{display:flex;align-items:center;justify-content:space-between;gap:18px;margin-bottom:20px}}.brand{{font-weight:760;font-size:20px;letter-spacing:.1px}}.sub{{color:var(--muted);font-size:13px;margin-top:2px}}
.badge{{display:inline-flex;align-items:center;gap:8px;padding:8px 12px;border:1px solid var(--line);border-radius:999px;background:#101923;color:#d9e4ee;font-size:13px;white-space:nowrap}}.badge span{{width:9px;height:9px;border-radius:50%;background:#7c8b99;box-shadow:0 0 0 4px rgba(124,139,153,.09)}}.badge.ok span{{background:var(--green)}}.badge.warn span{{background:var(--amber)}}.badge.info span{{background:var(--blue)}}
.card{{background:rgba(18,27,37,.97);border:1px solid var(--line);border-radius:18px;box-shadow:0 18px 42px rgba(0,0,0,.2)}}.hero{{padding:34px}}.eyebrow{{font-size:12px;font-weight:800;letter-spacing:.12em;color:var(--blue);margin-bottom:10px}}h1{{font-size:30px;line-height:1.15;margin:0 0 12px}}.lead{{color:#c4d0db;max-width:760px;margin:0 0 28px}}
form{{max-width:620px}}label{{display:block;font-weight:700;margin:0 0 8px}}input{{width:100%;padding:14px 15px;border-radius:11px;border:1px solid #34475b;background:#0d151e;color:#fff;font-size:16px;letter-spacing:.06em;outline:none}}input:focus{{border-color:var(--blue);box-shadow:0 0 0 3px rgba(77,180,230,.14)}}button{{margin-top:14px;border:0;border-radius:11px;background:#2f9fd2;color:#071018;font-weight:800;padding:13px 18px;font-size:15px;cursor:pointer}}
.note{{margin-top:24px;padding:15px 17px;border:1px solid #2c3c4c;border-radius:12px;background:#0e1720;color:#b8c6d3}}.notice{{margin:0 0 15px;padding:13px 16px;border-radius:12px;border:1px solid var(--line)}}.notice.success{{background:rgba(105,213,140,.08);border-color:rgba(105,213,140,.35)}}.notice.error,.inline-warning{{background:rgba(255,112,112,.08);border:1px solid rgba(255,112,112,.35);color:#ffd0d0}}.inline-warning{{padding:12px 14px;border-radius:10px;margin-top:18px}}
.facts{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:24px 0}}.facts div{{border:1px solid var(--line);border-radius:12px;background:#0f1821;padding:15px}}.facts span{{display:block;color:var(--muted);font-size:12px;margin-bottom:5px}}.facts strong{{display:block;font-size:14px;overflow-wrap:anywhere}}footer{{margin-top:16px;color:#718295;font-size:12px;text-align:center}}
@media(max-width:700px){{header{{align-items:flex-start;flex-direction:column}}.hero{{padding:24px 20px}}h1{{font-size:25px}}.facts{{grid-template-columns:1fr}}}}
</style></head><body><div class="shell"><header><div><div class="brand">Smart Pro System</div><div class="sub">Ασφαλής απομακρυσμένη υποστήριξη</div></div>{badge}</header>{notices}{body}<footer>Managed Support Foundation · έκδοση {esc(VERSION)}</footer></div></body></html>'''


class Handler(BaseHTTPRequestHandler):
    server_version = "SmartProManagedUI"

    def log_message(self, fmt, *args):
        return

    def send_html(self, page, status=200):
        body = page.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, private")
        self.send_header("Pragma", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path.rstrip("/")
        if path.endswith("/health") or path == "/health":
            payload = json.dumps({"ok": True, "version": VERSION, "paired": bool(snapshot()["identity"])}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)
            return
        self.send_html(render_page())

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path.rstrip("/")
        length = min(int(self.headers.get("Content-Length", "0") or 0), 8192)
        raw = self.rfile.read(length).decode("utf-8", "replace")
        form = urllib.parse.parse_qs(raw, keep_blank_values=True)
        csrf = str((form.get("csrf") or [""])[0])
        if not secrets.compare_digest(csrf, CSRF_TOKEN):
            self.send_html(render_page(error="Η φόρμα έληξε. Ανανεώστε τη σελίδα και δοκιμάστε ξανά."), 403)
            return
        if path.endswith("/pair") or path == "/pair":
            if snapshot()["identity"]:
                self.send_html(render_page(error="Η εγκατάσταση είναι ήδη συνδεδεμένη."), 409)
                return
            code = normalize_pairing_code((form.get("pairing_code") or [""])[0])
            if not code:
                self.send_html(render_page(error="Ο κωδικός pairing δεν έχει έγκυρη μορφή."), 400)
                return
            try:
                identity = do_pair(code)
                heartbeat_once()
                self.send_html(render_page(message=f"Η εγκατάσταση {identity['installation_ref']} συνδέθηκε με επιτυχία."))
            except RuntimeError as exc:
                self.send_html(render_page(error=str(exc)), 400)
            return
        self.send_html(render_page(error="Μη διαθέσιμη ενέργεια."), 404)


if __name__ == "__main__":
    identity = load_identity()
    with STATE_LOCK:
        STATE["identity"] = identity
        STATE["status"] = "paired" if identity else "unpaired"
    threading.Thread(target=heartbeat_loop, name="smart-pro-heartbeat", daemon=True).start()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    server.daemon_threads = True
    server.serve_forever()
