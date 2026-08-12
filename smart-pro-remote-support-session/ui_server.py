#!/usr/bin/env python3
import html
import json
import os
import re
import secrets
import ssl
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

VERSION = "0.8.0"
PORT = 8099
OPTIONS_PATH = "/data/options.json"
DEFAULT_BROKER_URL = "https://smart-pro-system.gr/wp-json/smart-pro-remote/v1/session/validate"
INGRESS_PROXY_IP = "172.30.32.2"
CODE_RE = re.compile(r"^SP-[A-Z0-9]{4}-[A-Z0-9]{4}$")
CSRF_TOKEN = secrets.token_urlsafe(32)


def load_broker_url():
    try:
        with open(OPTIONS_PATH, "r", encoding="utf-8") as f:
            options = json.load(f)
        url = str(options.get("broker_url") or DEFAULT_BROKER_URL).strip()
    except Exception:
        url = DEFAULT_BROKER_URL
    if not url.startswith("https://"):
        return None
    return url


def normalize_code(raw):
    value = (raw or "").upper().strip()
    value = re.sub(r"[^A-Z0-9-]", "", value)
    return value


def broker_validate(code):
    broker_url = load_broker_url()
    if not broker_url:
        return False, "configuration", "Η ασφαλής υπηρεσία επικύρωσης δεν είναι διαθέσιμη."

    payload = json.dumps({
        "code": code,
        "client": "home_assistant_os",
        "client_version": VERSION,
        "request_bootstrap_ticket": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        broker_url,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": f"SmartProRemoteSupport/{VERSION}",
            "Cache-Control": "no-store",
        },
    )

    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=20, context=context) as resp:
            status = int(resp.status)
            body = resp.read(128 * 1024)
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        body = exc.read(128 * 1024)
    except Exception:
        return False, "network", "Δεν ήταν δυνατή η ασφαλής επικοινωνία με το Smart Pro System."

    try:
        data = json.loads(body.decode("utf-8"))
    except Exception:
        return False, "unexpected", "Η υπηρεσία επέστρεψε μη αναμενόμενη απάντηση."

    if status == 200 and data.get("valid") is True:
        return True, "valid", "Ο κωδικός είναι έγκυρος και η συνεδρία είναι έτοιμη."

    reason = "unknown"
    if isinstance(data, dict):
        reason = str((data.get("data") or {}).get("reason") or data.get("reason") or "unknown")

    messages = {
        "invalid": "Ο κωδικός δεν είναι έγκυρος. Ελέγξτε τον και δοκιμάστε ξανά.",
        "revoked": "Ο κωδικός έχει ανακληθεί και δεν μπορεί να χρησιμοποιηθεί.",
        "expired": "Ο κωδικός έχει λήξει. Χρειάζεται νέος κωδικός υποστήριξης.",
        "inactive": "Η συγκεκριμένη συνεδρία δεν είναι διαθέσιμη.",
        "rate_limited": "Έγιναν πολλές προσπάθειες. Περιμένετε λίγο πριν δοκιμάσετε ξανά.",
    }
    return False, reason, messages.get(reason, "Ο κωδικός δεν έγινε αποδεκτός από την ασφαλή υπηρεσία.")


def page(status=None, message=None):
    ok = status == "success"
    problem = status == "error"
    status_block = ""
    if ok:
        status_block = f'''<div class="notice success"><strong>Ο κωδικός επιβεβαιώθηκε.</strong><span>{html.escape(message or '')}</span></div>
        <div class="ready"><span class="dot"></span><div><strong>Έτοιμο για το επόμενο βήμα</strong><p>Η έκδοση 0.8.0 σταματά εδώ. Δεν έχει ξεκινήσει απομακρυσμένη πρόσβαση και δεν εκτελείται MeshAgent.</p></div></div>'''
    elif problem:
        status_block = f'<div class="notice error"><strong>Δεν ολοκληρώθηκε η επιβεβαίωση.</strong><span>{html.escape(message or "")}</span></div>'

    return f'''<!doctype html>
<html lang="el">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark light">
<title>Smart Pro Remote Support</title>
<style>
:root{{--bg:#07111f;--panel:#111e31;--panel2:#0d192a;--line:#29405e;--text:#f5f8fd;--muted:#a9bfd8;--accent:#65c7f7;--accent2:#89dcff;--success:#1f9d73;--successbg:#0e322c;--error:#ff8e8e;--errorbg:#3a1d24}}
*{{box-sizing:border-box}}body{{margin:0;min-height:100vh;background:var(--bg);color:var(--text);font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;display:flex;align-items:center;justify-content:center;padding:28px}}
.shell{{width:min(760px,100%);background:var(--panel);border:1px solid var(--line);border-radius:24px;padding:34px;box-shadow:0 24px 80px rgba(0,0,0,.28)}}
.eyebrow{{font-size:12px;letter-spacing:.16em;color:var(--accent);font-weight:800}}h1{{font-size:clamp(32px,5vw,48px);line-height:1.05;margin:10px 0 12px}}.lead{{color:var(--muted);font-size:17px;line-height:1.6;margin:0 0 28px}}
.card{{background:var(--panel2);border:1px solid var(--line);border-radius:18px;padding:22px}}label{{display:block;font-weight:800;margin-bottom:9px}}.hint{{color:var(--muted);font-size:14px;line-height:1.5;margin:0 0 15px}}
input{{width:100%;border:1px solid #395372;border-radius:13px;background:#081424;color:#fff;font-size:21px;letter-spacing:.08em;padding:15px 16px;outline:none;text-transform:uppercase}}input:focus{{border-color:var(--accent);box-shadow:0 0 0 3px rgba(101,199,247,.14)}}
button{{margin-top:14px;border:0;border-radius:13px;padding:14px 18px;background:var(--accent);color:#06111d;font-size:16px;font-weight:900;cursor:pointer;width:100%}}button:hover{{background:var(--accent2)}}
.notice{{margin:0 0 18px;border-radius:15px;padding:16px 18px;display:flex;gap:5px;flex-direction:column;line-height:1.45}}.notice.success{{border:1px solid #329b7e;background:var(--successbg)}}.notice.error{{border:1px solid #a84f5f;background:var(--errorbg);color:#ffe6e9}}
.ready{{margin-top:18px;border-top:1px solid var(--line);padding-top:18px;display:flex;gap:12px;align-items:flex-start}}.ready p{{margin:5px 0 0;color:var(--muted);line-height:1.5}}.dot{{width:12px;height:12px;border-radius:50%;background:#42d39d;margin-top:5px;box-shadow:0 0 0 5px rgba(66,211,157,.12)}}
.security{{margin-top:18px;color:var(--muted);font-size:13px;line-height:1.55}}.security strong{{color:var(--text)}}.version{{margin-top:24px;color:#7691b1;font-size:12px;text-align:center}}
@media(max-width:560px){{body{{padding:12px}}.shell{{padding:24px 18px;border-radius:18px}}}}
</style>
</head>
<body>
<main class="shell">
<div class="eyebrow">SMART PRO REMOTE SUPPORT</div>
<h1>Προσωρινή τεχνική υποστήριξη</h1>
<p class="lead">Εισαγάγετε τον προσωρινό κωδικό που δημιουργήθηκε για τη συγκεκριμένη συνεδρία σας.</p>
{status_block}
<section class="card">
<form method="post" action="">
<input type="hidden" name="csrf" value="{html.escape(CSRF_TOKEN)}">
<label for="support_code">Κωδικός υποστήριξης</label>
<p class="hint">Μορφή: <strong>SP-XXXX-XXXX</strong>. Ο κωδικός ελέγχεται μέσω ασφαλούς HTTPS σύνδεσης.</p>
<input id="support_code" name="support_code" type="text" inputmode="text" autocomplete="one-time-code" autocapitalize="characters" spellcheck="false" maxlength="12" placeholder="SP-XXXX-XXXX" pattern="SP-[A-Za-z0-9]{{4}}-[A-Za-z0-9]{{4}}" required>
<button type="submit">Έλεγχος κωδικού</button>
</form>
</section>
<p class="security"><strong>Ασφάλεια:</strong> ο κωδικός δεν αποθηκεύεται από αυτή τη νέα UI ροή και δεν καταγράφεται στα logs. Η επιβεβαίωση από μόνη της δεν ξεκινά απομακρυσμένη πρόσβαση.</p>
<div class="version">Customer Code Entry Foundation · v{VERSION}</div>
</main>
</body>
</html>'''.encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server_version = "SmartProIngress"
    sys_version = ""

    def log_message(self, fmt, *args):
        return

    def allowed_source(self):
        if os.environ.get("SMART_PRO_DEV_ALLOW_LOCAL") == "1" and self.client_address[0] in {"127.0.0.1", "::1"}:
            return True
        return self.client_address[0] == INGRESS_PROXY_IP

    def security_headers(self):
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store, private, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'self'; base-uri 'none'")

    def respond(self, body, status=200):
        self.send_response(status)
        self.security_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.allowed_source():
            self.respond(b"Forbidden", 403)
            return
        self.respond(page())

    def do_POST(self):
        if not self.allowed_source():
            self.respond(b"Forbidden", 403)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > 8192:
            self.respond(page("error", "Μη έγκυρο αίτημα."), 400)
            return
        raw = self.rfile.read(length).decode("utf-8", "replace")
        form = parse_qs(raw, keep_blank_values=True)
        csrf = (form.get("csrf") or [""])[0]
        if not secrets.compare_digest(csrf, CSRF_TOKEN):
            self.respond(page("error", "Η σελίδα έληξε. Ανοίξτε ξανά το Smart Pro Support και δοκιμάστε ξανά."), 403)
            return
        code = normalize_code((form.get("support_code") or [""])[0])
        if not CODE_RE.fullmatch(code):
            self.respond(page("error", "Ο κωδικός πρέπει να έχει μορφή SP-XXXX-XXXX."), 400)
            return
        ok, reason, message = broker_validate(code)
        code = ""
        if ok:
            print("CUSTOMER UI: προσωρινός κωδικός επικυρώθηκε επιτυχώς — χωρίς αποθήκευση code και χωρίς remote execution.", flush=True)
            self.respond(page("success", message), 200)
        else:
            print(f"CUSTOMER UI: validation απορρίφθηκε με ασφαλή κατηγορία={reason} — χωρίς καταγραφή code.", flush=True)
            self.respond(page("error", message), 200)


if __name__ == "__main__":
    print(f"Smart Pro Remote Support {VERSION}: Ingress UI listening on internal port {PORT}.", flush=True)
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    server.daemon_threads = True
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
