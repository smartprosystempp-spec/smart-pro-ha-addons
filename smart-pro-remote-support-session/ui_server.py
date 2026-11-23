#!/usr/bin/env python3
import html
import json
import os
import re
import secrets
import signal
import ssl
import subprocess
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

VERSION = "0.9.9"
PORT = 8099
OPTIONS_PATH = "/data/options.json"
PHASE_SCRIPT = "/opt/smart-pro/phase-f-ui-0.9.9.sh"
DEFAULT_BROKER_URL = "https://smart-pro-system.gr/wp-json/smart-pro-remote/v1/session/validate"
INGRESS_PROXY_IP = "172.30.32.2"
CODE_RE = re.compile(r"^SP-[A-Z0-9]{4}-[A-Z0-9]{4}$")
CSRF_TOKEN = secrets.token_urlsafe(32)
FLOW_TTL = 300
STATE_LOCK = threading.Lock()
FLOWS = {}
ACTIVE_FLOW = None
ACTIVE_PROCESS = None
SHUTTING_DOWN = False

def load_broker_url():
    try:
        with open(OPTIONS_PATH, "r", encoding="utf-8") as f:
            options = json.load(f)
        url = str(options.get("broker_url") or DEFAULT_BROKER_URL).strip()
    except Exception:
        url = DEFAULT_BROKER_URL
    return url if url.startswith("https://") else None

def normalize_code(raw):
    return re.sub(r"[^A-Z0-9-]", "", (raw or "").upper().strip())

def broker_validate(code):
    broker_url = load_broker_url()
    if not broker_url:
        return False, "configuration", "Η ασφαλής υπηρεσία επικύρωσης δεν είναι διαθέσιμη.", None
    payload = json.dumps({"code": code,"client": "home_assistant_os","client_version": VERSION,"request_bootstrap_ticket": False}).encode("utf-8")
    req = urllib.request.Request(broker_url,data=payload,method="POST",headers={"Content-Type":"application/json","User-Agent":f"SmartProRemoteSupport/{VERSION}","Cache-Control":"no-store"})
    try:
        with urllib.request.urlopen(req, timeout=20, context=ssl.create_default_context()) as resp:
            status=int(resp.status); body=resp.read(128*1024)
    except urllib.error.HTTPError as exc:
        status=int(exc.code); body=exc.read(128*1024)
    except Exception:
        return False,"network","Δεν ήταν δυνατή η ασφαλής επικοινωνία με το Smart Pro System.",None
    try: data=json.loads(body.decode("utf-8"))
    except Exception: return False,"unexpected","Η υπηρεσία επέστρεψε μη αναμενόμενη απάντηση.",None
    if status==200 and data.get("valid") is True:
        raw_contract=data.get("support_contract") if isinstance(data,dict) else None
        contract={"kind":"unknown","duration_minutes":0,"duration_source":"none","production_runtime_enabled":False,"qa_runtime_seconds":60,"startup_grace_seconds":0,"max_runtime_seconds":60}
        if isinstance(raw_contract,dict):
            try: duration=int(raw_contract.get("duration_minutes") or 0)
            except Exception: duration=0
            try: qa_seconds=int(raw_contract.get("qa_runtime_seconds") or 60)
            except Exception: qa_seconds=60
            try: startup_grace=int(raw_contract.get("startup_grace_seconds") or 0)
            except Exception: startup_grace=0
            try: max_runtime=int(raw_contract.get("max_runtime_seconds") or 60)
            except Exception: max_runtime=60
            production=bool(raw_contract.get("production_runtime_enabled") is True)
            if duration not in (0,30,60,90): duration=0
            if qa_seconds != 60: qa_seconds=60
            expected_max=(duration*60+60) if production and duration in (30,60,90) else 60
            if production and startup_grace != 60: production=False
            if max_runtime != expected_max: production=False; max_runtime=60; startup_grace=0
            if not production: duration=0 if str(raw_contract.get("duration_source") or "none") != "paid_guest_case" else duration
            contract={
                "kind":str(raw_contract.get("kind") or "unknown")[:40],
                "duration_minutes":duration,
                "duration_source":str(raw_contract.get("duration_source") or "none")[:40],
                "production_runtime_enabled":production,
                "qa_runtime_seconds":qa_seconds,
                "startup_grace_seconds":startup_grace if production else 0,
                "max_runtime_seconds":max_runtime if production else 60,
            }
        return True,"valid","Ο κωδικός είναι έγκυρος και η συνεδρία είναι έτοιμη.",contract
    reason=str((data.get("data") or {}).get("reason") or data.get("reason") or "unknown") if isinstance(data,dict) else "unknown"
    messages={"invalid":"Ο κωδικός δεν είναι έγκυρος. Ελέγξτε τον και δοκιμάστε ξανά.","revoked":"Ο κωδικός έχει ανακληθεί και δεν μπορεί να χρησιμοποιηθεί.","expired":"Ο κωδικός έχει λήξει. Χρειάζεται νέος κωδικός υποστήριξης.","inactive":"Η συγκεκριμένη συνεδρία δεν είναι διαθέσιμη.","rate_limited":"Έγιναν πολλές προσπάθειες. Περιμένετε λίγο πριν δοκιμάσετε ξανά."}
    return False,reason,messages.get(reason,"Ο κωδικός δεν έγινε αποδεκτός από την ασφαλή υπηρεσία."),None

def clean_flows():
    now=time.time()
    with STATE_LOCK:
        stale=[fid for fid,f in FLOWS.items() if f.get("state")=="validated" and now-f.get("created",now)>FLOW_TTL]
        for fid in stale:
            FLOWS[fid]["code"]=""; del FLOWS[fid]

def new_validated_flow(code,contract=None):
    clean_flows(); flow_id=secrets.token_urlsafe(32)
    safe_contract=contract if isinstance(contract,dict) else {"kind":"unknown","duration_minutes":0,"duration_source":"none","production_runtime_enabled":False,"qa_runtime_seconds":60,"startup_grace_seconds":0,"max_runtime_seconds":60}
    with STATE_LOCK: FLOWS[flow_id]={"state":"validated","code":code,"created":time.time(),"message":"Ο κωδικός επιβεβαιώθηκε.","support_contract":safe_contract}
    return flow_id

def get_flow_snapshot(flow_id):
    clean_flows()
    with STATE_LOCK:
        f=FLOWS.get(flow_id)
        return None if not f else {k:v for k,v in f.items() if k!="code"}

def get_active_flow_snapshot():
    """Return the current running UI flow without requiring a browser query token.

    This is intentionally limited to the in-memory ACTIVE_FLOW already owned by this
    add-on process. It never restores or reuses the one-time support code and never
    starts a new execution.
    """
    clean_flows()
    with STATE_LOCK:
        flow_id=ACTIVE_FLOW
        f=FLOWS.get(flow_id) if flow_id else None
        if not f or f.get("state") != "running":
            return None,None
        return flow_id,{k:v for k,v in f.items() if k!="code"}

def run_phase_f(flow_id, code):
    global ACTIVE_FLOW, ACTIVE_PROCESS
    success=False; saw_failure=False
    try:
        proc=subprocess.Popen([PHASE_SCRIPT],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1,start_new_session=True,env={**os.environ,"SMART_PRO_UI_BRIDGE":"1"})
        with STATE_LOCK: ACTIVE_PROCESS=proc
        proc.stdin.write(code+"\n"); proc.stdin.flush(); proc.stdin.close(); code=""
        for line in proc.stdout:
            line=line.rstrip("\n"); print(line,flush=True)
            if "CONTROLLED EXECUTION PHASE F: ΟΛΟΚΛΗΡΩΘΗΚΕ" in line: success=True
            if line.startswith("ΣΦΑΛΜΑ:"): saw_failure=True
            if line.startswith("ΕΠΙΤΥΧΙΑ: Το MeshAgent ξεκίνησε ως ephemeral foreground"):
                with STATE_LOCK:
                    f0=FLOWS.get(flow_id)
                    if f0: f0["agent_up"]=True; f0["agent_started"]=time.time()-3
        rc=proc.wait()
        with STATE_LOCK:
            f=FLOWS.get(flow_id)
            if f:
                f["ended"]=time.time()
                if success and rc==0 and not saw_failure:
                    f["state"]="completed"; f["message"]="Η προσωρινή ασφαλής σύνδεση ολοκληρώθηκε και τερματίστηκε καθαρά."
                else:
                    f["state"]="failed"; f["message"]="Η ασφαλής σύνδεση δεν ολοκληρώθηκε και σταμάτησε με ασφάλεια."
    except Exception:
        print("CUSTOMER UI BRIDGE: execution worker failure — χωρίς καταγραφή code.",flush=True)
        with STATE_LOCK:
            f=FLOWS.get(flow_id)
            if f: f.update(state="failed",ended=time.time(),message="Η διαδικασία σταμάτησε με ασφάλεια πριν ολοκληρωθεί.")
    finally:
        code=""
        with STATE_LOCK: ACTIVE_PROCESS=None; ACTIVE_FLOW=None

def start_flow(flow_id):
    global ACTIVE_FLOW
    clean_flows()
    with STATE_LOCK:
        f=FLOWS.get(flow_id)
        if not f or f.get("state")!="validated": return False,"Η επιβεβαιωμένη συνεδρία δεν είναι πλέον διαθέσιμη. Ελέγξτε ξανά τον κωδικό."
        if ACTIVE_FLOW is not None: return False,"Υπάρχει ήδη προσωρινή συνεδρία σε εξέλιξη."
        code=f.pop("code","")
        if not CODE_RE.fullmatch(code): return False,"Ο προσωρινός κωδικός δεν είναι πλέον διαθέσιμος. Ελέγξτε ξανά τον κωδικό."
        f.update(state="running",started=time.time(),message="Προετοιμάζεται η ασφαλής σύνδεση."); ACTIVE_FLOW=flow_id
    threading.Thread(target=run_phase_f,args=(flow_id,code),daemon=True).start(); return True,"started"

RUNTIME_MAX_FILE="/tmp/smart-pro-phase-f-runtime/.runtime-max-seconds"

def minutes_left(flow):
    """Εκτίμηση λεπτών που απομένουν. Διαβάζει μόνο το ήδη υπάρχον runtime όριο (ενημερώνεται και από εγκεκριμένη παράταση)."""
    try:
        started=float(flow.get("agent_started") or 0)
        if not started: return None
        max_s=int(open(RUNTIME_MAX_FILE).read().strip())
        contract=flow.get("support_contract") if isinstance(flow.get("support_contract"),dict) else {}
        try: grace=int(contract.get("startup_grace_seconds") or 0)
        except Exception: grace=0
        rem=started+max_s-time.time()
        if rem>grace>0: rem-=grace
        return max(0,int(rem))
    except Exception:
        return None

def styles():
    return '''<style>
:root{--bg:#07111f;--panel:#111e31;--panel2:#0d192a;--line:#29405e;--text:#f5f8fd;--muted:#a9bfd8;--accent:#65c7f7;--accent2:#89dcff;--success:#42d39d;--successbg:#0e322c;--warn:#f6c85f;--warnbg:#372d0b;--error:#ff8e8e;--errorbg:#3a1d24}
*{box-sizing:border-box}body{margin:0;min-height:100vh;background:var(--bg);color:var(--text);font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;display:flex;align-items:center;justify-content:center;padding:28px}.shell{width:min(760px,100%);background:var(--panel);border:1px solid var(--line);border-radius:24px;padding:34px;box-shadow:0 24px 80px rgba(0,0,0,.28)}.eyebrow{font-size:12px;letter-spacing:.16em;color:var(--accent);font-weight:800}h1{font-size:clamp(32px,5vw,48px);line-height:1.05;margin:10px 0 12px}.lead{color:var(--muted);font-size:17px;line-height:1.6;margin:0 0 28px}.card{background:var(--panel2);border:1px solid var(--line);border-radius:18px;padding:22px}label{display:block;font-weight:800;margin-bottom:9px}.hint{color:var(--muted);font-size:14px;line-height:1.5;margin:0 0 15px}input[type=text]{width:100%;border:1px solid #395372;border-radius:13px;background:#081424;color:#fff;font-size:21px;letter-spacing:.08em;padding:15px 16px;outline:none;text-transform:uppercase}input:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(101,199,247,.14)}button{margin-top:14px;border:0;border-radius:13px;padding:14px 18px;background:var(--accent);color:#06111d;font-size:16px;font-weight:900;cursor:pointer;width:100%}button:hover{background:var(--accent2)}.notice{margin:0 0 18px;border-radius:15px;padding:16px 18px;display:flex;gap:5px;flex-direction:column;line-height:1.45}.success{border:1px solid #329b7e;background:var(--successbg)}.warn{border:1px solid #967719;background:var(--warnbg)}.error{border:1px solid #a84f5f;background:var(--errorbg);color:#ffe6e9}.ready{margin:18px 0;border-top:1px solid var(--line);padding-top:18px;display:flex;gap:12px;align-items:flex-start}.ready p{margin:5px 0 0;color:var(--muted);line-height:1.5}.dot{width:12px;height:12px;border-radius:50%;background:var(--success);margin-top:5px;box-shadow:0 0 0 5px rgba(66,211,157,.12)}.pulse{animation:pulse 1.5s infinite}@keyframes pulse{50%{opacity:.35}}.security{margin-top:18px;color:var(--muted);font-size:13px;line-height:1.55}.security strong{color:var(--text)}.version{margin-top:24px;color:#7691b1;font-size:12px;text-align:center}@media(max-width:560px){body{padding:12px}.shell{padding:24px 18px;border-radius:18px}}
.notice.info{background:var(--panel2);border:1px solid var(--line)}.notice.todo{background:var(--warnbg);border:2px solid var(--warn)}.step{font-size:13px;font-weight:800;color:var(--accent);letter-spacing:.06em;margin:0 0 8px}
</style>'''

def wrap(content,refresh=None):
    refresh_tag=f'<meta http-equiv="refresh" content="3;url=?flow={html.escape(refresh)}">' if refresh else ''
    return f'''<!doctype html><html lang="el"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="dark light">{refresh_tag}<title>Smart Pro Remote Support</title>{styles()}</head><body><main class="shell"><div class="eyebrow">SMART PRO REMOTE SUPPORT</div><h1>Προσωρινή τεχνική υποστήριξη</h1>{content}<div class="version">Smart Pro System · Προσωρινή Υποστήριξη · v{VERSION}</div></main></body></html>'''.encode("utf-8")

def entry_page(status=None,message=None):
    notice=f'<div class="notice error"><strong>Δεν ολοκληρώθηκε η επιβεβαίωση.</strong><span>{html.escape(message or "")}</span></div>' if status=='error' else ''
    content=f'''<p class="step">ΒΗΜΑ 1 ΑΠΟ 2</p><p class="lead">Εισαγάγετε τον προσωρινό κωδικό που δημιουργήθηκε από τον ασφαλή σύνδεσμο της συγκεκριμένης συνεδρίας σας.</p>{notice}<section class="card"><form method="post" action=""><input type="hidden" name="csrf" value="{html.escape(CSRF_TOKEN)}"><input type="hidden" name="action" value="validate"><label for="support_code">Κωδικός υποστήριξης</label><p class="hint">Μορφή: <strong>SP-XXXX-XXXX</strong>. Ο κωδικός ελέγχεται με ασφαλή σύνδεση.</p><input id="support_code" name="support_code" type="text" inputmode="text" autocomplete="one-time-code" autocapitalize="characters" spellcheck="false" maxlength="12" placeholder="SP-XXXX-XXXX" pattern="SP-[A-Za-z0-9]{{4}}-[A-Za-z0-9]{{4}}" required><button type="submit">Έλεγχος κωδικού</button></form></section><p class="security"><strong>Ασφάλεια:</strong> ο κωδικός δεν αποθηκεύεται πουθενά στο σύστημά σας. Μετά τον έλεγχο, η σύνδεση ξεκινά μόνο όταν πατήσετε εσείς το κουμπί «Έναρξη ασφαλούς σύνδεσης».</p>'''
    return wrap(content)

def validated_page(flow_id):
    flow=get_flow_snapshot(flow_id) or {}
    contract=flow.get("support_contract") if isinstance(flow.get("support_contract"),dict) else {}
    raw_duration=contract.get("duration_minutes") or 0
    try: duration=int(raw_duration)
    except Exception: duration=0
    production=bool(contract.get("production_runtime_enabled") is True)
    if duration in (30,60,90) and production:
        duration_block=f'<div class="notice info"><strong>Διάρκεια υποστήριξης: {duration} λεπτά</strong><span>Η διάρκεια μετράει από τη στιγμή που θα πατήσετε «Έναρξη ασφαλούς σύνδεσης».</span></div>'
    else:
        duration_block='<div class="notice warn"><strong>Δοκιμαστική συνεδρία</strong><span>Δεν υπάρχει συνδεδεμένη διάρκεια 30/60/90. Η δοκιμή κλείνει μετά από 60 δευτερόλεπτα.</span></div>'
    content=f'''<p class="step">ΒΗΜΑ 2 ΑΠΟ 2</p><p class="lead">Ο κωδικός είναι σωστός. Απομένει ένα βήμα.</p><div class="notice todo"><strong>Η σύνδεση δεν έχει ξεκινήσει ακόμα.</strong><span>Πατήστε το κουμπί «Έναρξη ασφαλούς σύνδεσης» παρακάτω. Μπορεί να περάσουν μερικά δευτερόλεπτα μέχρι να συνδεθεί ο τεχνικός.</span></div>{duration_block}<section class="card"><form method="post" action=""><input type="hidden" name="csrf" value="{html.escape(CSRF_TOKEN)}"><input type="hidden" name="action" value="start"><input type="hidden" name="flow" value="{html.escape(flow_id)}"><button type="submit">Έναρξη ασφαλούς σύνδεσης</button></form></section><p class="security"><strong>Προσωρινή πρόσβαση:</strong> δεν εγκαθίσταται τίποτα μόνιμα. Η σύνδεση κλείνει αυτόματα όταν τελειώσει η διάρκεια.</p>'''
    return wrap(content)

def status_page(flow_id,flow):
    state=flow.get('state') if flow else None
    if state=='running':
        left=minutes_left(flow) if flow.get("agent_up") else None
        if flow.get("agent_up"):
            if left is None: time_txt="Ο χρόνος υποστήριξης μετράει από τη στιγμή που ξεκίνησε η σύνδεση."
            elif left<60: time_txt="Απομένει λιγότερο από 1 λεπτό."
            else: time_txt=f"Απομένουν περίπου {(left+59)//60} λεπτά."
            body=f'''<p class="lead">Η σύνδεση είναι ενεργή.</p><div class="notice success"><strong>Ο τεχνικός μπορεί να συνδεθεί τώρα.</strong><span>Παραμείνετε διαθέσιμοι. Μην κλείσετε το πρόσθετο: αν το σταματήσετε, η σύνδεση τερματίζεται αμέσως.</span></div><div class="notice info"><strong>Χρόνος υποστήριξης</strong><span>{time_txt}</span></div><div class="ready"><span class="dot pulse"></span><div><strong>Η προσωρινή συνεδρία είναι ενεργή</strong><p>Η σελίδα ενημερώνεται αυτόματα. Αν χρειαστεί λίγος επιπλέον χρόνος, ο τεχνικός μπορεί να προτείνει παράταση και θα την εγκρίνετε από τον ασφαλή σύνδεσμο του email σας.</p></div></div>'''
        else:
            body='''<p class="lead">Η σύνδεση ξεκινά.</p><div class="notice warn"><strong>Η σύνδεση προετοιμάζεται.</strong><span>Περιμένετε λίγα δευτερόλεπτα και μην κλείσετε το πρόσθετο.</span></div>'''
        return wrap(body,flow_id)
    if state=='completed':
        return wrap(f'''<p class="lead">Η προσωρινή συνεδρία ολοκληρώθηκε.</p><div class="notice success"><strong>Η υποστήριξη τερματίστηκε με ασφάλεια.</strong><span>Η σύνδεση έκλεισε και δεν έχει μείνει τίποτα ενεργό στο σύστημά σας.</span></div><p class="security">Μπορείτε να κλείσετε το πρόσθετο.</p>''')
    if state=='failed':
        return wrap(f'''<p class="lead">Η ασφαλής σύνδεση δεν ολοκληρώθηκε.</p><div class="notice error"><strong>Η σύνδεση σταμάτησε με ασφάλεια.</strong><span>Δεν έγινε καμία αλλαγή στο σύστημά σας.</span></div><p class="security">Δεν γίνεται αυτόματη νέα προσπάθεια. Επικοινωνήστε μαζί μας για να σας βοηθήσουμε να ξεκινήσετε ξανά.</p>''')
    return entry_page('error','Η σελίδα έληξε. Εισαγάγετε ξανά τον κωδικό.')

class Handler(BaseHTTPRequestHandler):
    server_version="SmartProIngress"; sys_version=""
    def log_message(self,fmt,*args): return
    def allowed_source(self):
        if os.environ.get("SMART_PRO_DEV_ALLOW_LOCAL")=="1" and self.client_address[0] in {"127.0.0.1","::1"}: return True
        return self.client_address[0]==INGRESS_PROXY_IP
    def security_headers(self):
        for k,v in [("Content-Type","text/html; charset=utf-8"),("Cache-Control","no-store, private, max-age=0"),("Pragma","no-cache"),("X-Content-Type-Options","nosniff"),("X-Frame-Options","SAMEORIGIN"),("Referrer-Policy","no-referrer"),("Content-Security-Policy","default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'self'; base-uri 'none'")]: self.send_header(k,v)
    def respond(self,body,status=200):
        self.send_response(status); self.security_headers(); self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        if not self.allowed_source(): self.respond(b"Forbidden",403); return
        flow_id=(parse_qs(urlparse(self.path).query).get('flow') or [''])[0]
        if flow_id:
            self.respond(status_page(flow_id,get_flow_snapshot(flow_id))); return
        active_flow_id,active_flow=get_active_flow_snapshot()
        if active_flow_id and active_flow:
            self.respond(status_page(active_flow_id,active_flow)); return
        self.respond(entry_page())
    def do_POST(self):
        if not self.allowed_source(): self.respond(b"Forbidden",403); return
        try: length=int(self.headers.get("Content-Length","0"))
        except ValueError: length=0
        if length<=0 or length>8192: self.respond(entry_page('error','Μη έγκυρο αίτημα.'),400); return
        form=parse_qs(self.rfile.read(length).decode("utf-8","replace"),keep_blank_values=True)
        csrf=(form.get('csrf') or [''])[0]
        if not secrets.compare_digest(csrf,CSRF_TOKEN): self.respond(entry_page('error','Η σελίδα έληξε. Ανοίξτε ξανά το Smart Pro Support και δοκιμάστε ξανά.'),403); return
        action=(form.get('action') or [''])[0]
        if action=='validate':
            code=normalize_code((form.get('support_code') or [''])[0])
            if not CODE_RE.fullmatch(code): self.respond(entry_page('error','Ο κωδικός πρέπει να έχει μορφή SP-XXXX-XXXX.'),400); return
            ok,reason,message,contract=broker_validate(code)
            if ok:
                flow_id=new_validated_flow(code,contract); code=""
                print("CUSTOMER UI: προσωρινός κωδικός επικυρώθηκε — κρατείται μόνο σε βραχύβια μνήμη μέχρι ρητό Start.",flush=True)
                self.respond(validated_page(flow_id)); return
            code=""; print(f"CUSTOMER UI: validation απορρίφθηκε με ασφαλή κατηγορία={reason} — χωρίς καταγραφή code.",flush=True); self.respond(entry_page('error',message)); return
        if action=='start':
            flow_id=(form.get('flow') or [''])[0]
            if not re.fullmatch(r'[A-Za-z0-9_-]{30,80}',flow_id): self.respond(entry_page('error','Μη έγκυρη προσωρινή UI συνεδρία.'),400); return
            ok,message=start_flow(flow_id)
            if not ok: self.respond(entry_page('error',message)); return
            print("CUSTOMER UI BRIDGE: δόθηκε ρητή εντολή Start — ο code παραδίδεται στο Phase F core μόνο μέσω private stdin pipe.",flush=True)
            self.respond(status_page(flow_id,get_flow_snapshot(flow_id))); return
        self.respond(entry_page('error','Μη υποστηριζόμενη ενέργεια.'),400)

def terminate_child():
    with STATE_LOCK: proc=ACTIVE_PROCESS
    if proc and proc.poll() is None:
        try: os.killpg(proc.pid,signal.SIGTERM)
        except Exception: pass
        try: proc.wait(timeout=4)
        except Exception:
            try: os.killpg(proc.pid,signal.SIGKILL)
            except Exception: pass

def shutdown_handler(signum,frame):
    global SHUTTING_DOWN
    if SHUTTING_DOWN: return
    SHUTTING_DOWN=True; print("CUSTOMER UI BRIDGE: shutdown — τερματισμός τυχόν ενεργού Phase F child.",flush=True); terminate_child(); raise KeyboardInterrupt

if __name__=='__main__':
    signal.signal(signal.SIGTERM,shutdown_handler); signal.signal(signal.SIGINT,shutdown_handler)
    print(f"Smart Pro Remote Support {VERSION}: Ingress UI listening on internal port {PORT}.",flush=True)
    server=ThreadingHTTPServer(("0.0.0.0",PORT),Handler); server.daemon_threads=True
    try: server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt: pass
    finally: terminate_child(); server.server_close()
