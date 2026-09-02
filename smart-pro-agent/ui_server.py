#!/usr/bin/env python3
import base64
import hashlib
import html
import json
import os
import re
import secrets
import ssl
import subprocess
import shutil
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSION = os.environ.get("SMART_PRO_VERSION", "2.5.2")
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
    "last_installation_ref": None,
    "heartbeat_interval": HEARTBEAT_SECONDS,
    "bootstrap_status": "not_checked",
    "bootstrap_checked_at": None,
    "bootstrap_error": None,
    "bootstrap_source_hint": None,
    "settings_status": "not_checked",
    "settings_checked_at": None,
    "settings_error": None,
    "settings_sha_hint": None,
    "settings_bytes": None,
    "agent_status": "not_checked",
    "agent_checked_at": None,
    "agent_error": None,
    "agent_sha_hint": None,
    "agent_bytes": None,
    "support_session": None,
    "support_session_error": None,
    "execution_status": "idle",
    "execution_error": None,
    "execution_started_at": None,
    "execution_ended_at": None,
    "execution_result": None,
}


class BrokerError(RuntimeError):
    def __init__(self, message, http_status=None, content_type=None, error_code=None):
        super().__init__(message)
        self.http_status = http_status
        self.content_type = content_type
        self.error_code = error_code


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


def invalidate_local_identity(status, message):
    with STATE_LOCK:
        identity = STATE.get("identity")
        installation_ref = str((identity or {}).get("installation_ref") or STATE.get("last_installation_ref") or "")
    try:
        os.unlink(IDENTITY_FILE)
    except FileNotFoundError:
        pass
    except OSError as exc:
        print(f"[managed] Local credential cleanup failed: {type(exc).__name__}", flush=True)
        raise RuntimeError("Δεν ήταν δυνατή η ασφαλής κατάργηση της τοπικής ταυτότητας.") from exc
    with STATE_LOCK:
        STATE["identity"] = None
        STATE["status"] = status
        STATE["last_error"] = message
        STATE["last_installation_ref"] = installation_ref[:100] if installation_ref else None
        STATE["heartbeat_interval"] = HEARTBEAT_SECONDS
        STATE["bootstrap_status"] = "not_checked"
        STATE["bootstrap_checked_at"] = None
        STATE["bootstrap_error"] = None
        STATE["bootstrap_source_hint"] = None
        STATE["settings_status"] = "not_checked"
        STATE["settings_checked_at"] = None
        STATE["settings_error"] = None
        STATE["settings_sha_hint"] = None
        STATE["settings_bytes"] = None
        STATE["agent_status"] = "not_checked"
        STATE["agent_checked_at"] = None
        STATE["agent_error"] = None
        STATE["agent_sha_hint"] = None
        STATE["agent_bytes"] = None
        STATE["support_session"] = None
        STATE["support_session_error"] = None
        STATE["execution_status"] = "idle"
        STATE["execution_error"] = None
        STATE["execution_started_at"] = None
        STATE["execution_ended_at"] = None
        STATE["execution_result"] = None
    print(f"[managed] Local managed identity cleared: state={status}", flush=True)


def broker_post(endpoint, payload, timeout=15):
    base = safe_broker_base_url()
    if not base:
        raise BrokerError("Η διεύθυνση της ασφαλούς υπηρεσίας δεν είναι έγκυρη.")
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
            try:
                data = json.loads(raw.decode("utf-8")) if raw else {}
            except (ValueError, UnicodeDecodeError) as exc:
                raise BrokerError("Η ασφαλής υπηρεσία επέστρεψε μη έγκυρη απάντηση.") from exc
            return response.status, data
    except urllib.error.HTTPError as exc:
        raw = exc.read(131072)
        content_type = str(exc.headers.get("Content-Type") or "unknown").split(";", 1)[0].strip().lower()
        print(f"[managed] Broker {endpoint}: HTTP {exc.code}, Content-Type={content_type}", flush=True)
        try:
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except (ValueError, UnicodeDecodeError):
            data = {}
        error_code = str(data.get("code") or "") if isinstance(data, dict) else ""
        if isinstance(data, dict) and data.get("message"):
            message = str(data.get("message"))
        else:
            message = f"Η ασφαλής υπηρεσία απέρριψε το αίτημα (HTTP {exc.code}, {content_type})."
        raise BrokerError(
            message,
            http_status=exc.code,
            content_type=content_type,
            error_code=error_code or None,
        ) from exc
    except (urllib.error.URLError, TimeoutError, ssl.SSLError) as exc:
        raise BrokerError("Δεν ήταν δυνατή η ασφαλής επικοινωνία με το Smart Pro System.") from exc


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
        STATE["last_installation_ref"] = None
        STATE["bootstrap_status"] = "not_checked"
        STATE["bootstrap_checked_at"] = None
        STATE["bootstrap_error"] = None
        STATE["bootstrap_source_hint"] = None
        STATE["settings_status"] = "not_checked"
        STATE["settings_checked_at"] = None
        STATE["settings_error"] = None
        STATE["settings_sha_hint"] = None
        STATE["settings_bytes"] = None
        STATE["agent_status"] = "not_checked"
        STATE["agent_checked_at"] = None
        STATE["agent_error"] = None
        STATE["agent_sha_hint"] = None
        STATE["agent_bytes"] = None
        STATE["support_session"] = None
        STATE["support_session_error"] = None
        STATE["execution_status"] = "idle"
        STATE["execution_error"] = None
        STATE["execution_started_at"] = None
        STATE["execution_ended_at"] = None
        STATE["execution_result"] = None
    return identity


def bootstrap_authorization_check():
    with STATE_LOCK:
        identity = STATE.get("identity")
    if not identity:
        raise RuntimeError("Η εγκατάσταση δεν είναι συνδεδεμένη.")
    if ARCH not in ("aarch64", "amd64"):
        raise RuntimeError("Η αρχιτεκτονική αυτής της εγκατάστασης δεν υποστηρίζεται ακόμη.")

    try:
        status, data = broker_post(
            "/bootstrap/request",
            {
                "node_id": identity["node_id"],
                "node_secret": identity["node_secret"],
                "client_version": VERSION,
                "architecture": ARCH,
            },
        )
        if status != 201 or not data.get("success"):
            raise RuntimeError("Δεν εκδόθηκε ασφαλές bootstrap authorization.")
        if data.get("msh_delivery") is not False or data.get("agent_delivery") is not False or data.get("execution") is not False or data.get("remote_access") is not False:
            raise RuntimeError("Η απάντηση παραβίασε το authorization-only security boundary.")
        ticket = str(data.get("bootstrap_ticket") or "")
        if not re.fullmatch(r"SPMB-[A-Za-z0-9_-]{43}", ticket):
            raise RuntimeError("Η υπηρεσία επέστρεψε μη έγκυρο bootstrap authorization ticket.")

        status2, data2 = broker_post(
            "/bootstrap/consume",
            {
                "bootstrap_ticket": ticket,
                "node_id": identity["node_id"],
                "node_secret": identity["node_secret"],
                "client_version": VERSION,
                "architecture": ARCH,
            },
        )
        ticket = None
        if status2 != 200 or not data2.get("success") or data2.get("authorized") is not True:
            raise RuntimeError("Το ασφαλές bootstrap authorization δεν καταναλώθηκε.")
        if data2.get("msh_delivery") is not False or data2.get("agent_delivery") is not False or data2.get("execution") is not False or data2.get("remote_access") is not False:
            raise RuntimeError("Η απάντηση παραβίασε το authorization-only security boundary.")
        hint = str(data2.get("source_fingerprint_hint") or "")
        if hint and not re.fullmatch(r"[a-fA-F0-9]{12}", hint):
            raise RuntimeError("Η υπηρεσία επέστρεψε μη έγκυρο source fingerprint hint.")
        checked_at = str(data2.get("consumed_at") or "")
        with STATE_LOCK:
            STATE["bootstrap_status"] = "authorized"
            STATE["bootstrap_checked_at"] = checked_at
            STATE["bootstrap_error"] = None
            STATE["bootstrap_source_hint"] = hint.lower() if hint else None
        return checked_at
    except BrokerError as exc:
        if exc.error_code == "sprsb_managed_node_revoked":
            invalidate_local_identity(
                "revoked",
                "Η σύνδεση με το Smart Pro System έχει ανακληθεί. Απαιτείται νέος κωδικός pairing για επανασύνδεση.",
            )
        elif exc.error_code in ("sprsb_managed_node_auth_failed", "sprsb_managed_node_inactive"):
            invalidate_local_identity(
                "reauthorization_required",
                "Η αποθηκευμένη σύνδεση δεν είναι πλέον έγκυρη. Απαιτείται νέος κωδικός pairing.",
            )
        else:
            with STATE_LOCK:
                STATE["bootstrap_status"] = "error"
                STATE["bootstrap_error"] = str(exc)
        raise RuntimeError(str(exc)) from exc
    except RuntimeError as exc:
        with STATE_LOCK:
            STATE["bootstrap_status"] = "error"
            STATE["bootstrap_error"] = str(exc)
        raise



def parse_msh_bytes(raw):
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise RuntimeError("Το αρχείο ρυθμίσεων δεν είναι έγκυρο κείμενο.") from exc
    out = {}
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = line.strip()
        if not line or "=" not in line:
            continue
        key, value = [part.strip() for part in line.split("=", 1)]
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", key):
            out[key] = value
    return out


def verify_msh_and_discard(raw, expected_sha256, expected_bytes, expected_agent_label):
    if not isinstance(raw, (bytes, bytearray)):
        raise RuntimeError("Το αρχείο ρυθμίσεων δεν έχει έγκυρη μορφή.")
    if len(raw) < 20 or len(raw) > 262144 or len(raw) != int(expected_bytes):
        raise RuntimeError("Το αρχείο ρυθμίσεων έχει μη αναμενόμενο μέγεθος.")
    actual_sha = hashlib.sha256(raw).hexdigest()
    if not secrets.compare_digest(actual_sha, str(expected_sha256).lower()):
        raise RuntimeError("Ο έλεγχος ακεραιότητας του αρχείου ρυθμίσεων απέτυχε.")

    parsed = parse_msh_bytes(raw)
    for required in ("MeshName", "MeshType", "MeshID", "ServerID", "MeshServer"):
        if not parsed.get(required):
            raise RuntimeError("Το αρχείο ρυθμίσεων δεν περιέχει όλα τα απαιτούμενα πεδία.")
    if not str(parsed.get("MeshServer") or "").lower().startswith("wss://"):
        raise RuntimeError("Η διεύθυνση της απομακρυσμένης υπηρεσίας δεν είναι ασφαλής.")
    if expected_agent_label:
        if not re.fullmatch(r"SPMNG-[A-F0-9]{16}", expected_agent_label):
            raise RuntimeError("Η υπηρεσία επέστρεψε μη έγκυρη ταυτότητα managed node.")
        if not secrets.compare_digest(str(parsed.get("agentName") or ""), expected_agent_label):
            raise RuntimeError("Το αρχείο ρυθμίσεων δεν αντιστοιχεί σε αυτή την εγκατάσταση.")

    temp_path = None
    try:
        fd, temp_path = tempfile.mkstemp(prefix="smart_pro_managed_", suffix=".msh", dir="/tmp")
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        with open(temp_path, "rb") as handle:
            disk_raw = handle.read(262145)
        if len(disk_raw) != len(raw) or not secrets.compare_digest(hashlib.sha256(disk_raw).hexdigest(), actual_sha):
            raise RuntimeError("Η τοπική επαλήθευση του προσωρινού αρχείου απέτυχε.")
    finally:
        if temp_path:
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                pass
            except OSError as exc:
                raise RuntimeError("Δεν ήταν δυνατή η ασφαλής διαγραφή του προσωρινού αρχείου ρυθμίσεων.") from exc
    return actual_sha


def secure_settings_delivery_check():
    with STATE_LOCK:
        identity = STATE.get("identity")
    if not identity:
        raise RuntimeError("Η εγκατάσταση δεν είναι συνδεδεμένη.")
    if ARCH not in ("aarch64", "amd64"):
        raise RuntimeError("Η αρχιτεκτονική αυτής της εγκατάστασης δεν υποστηρίζεται ακόμη.")

    try:
        # Fresh authorization is mandatory immediately before settings delivery.
        bootstrap_authorization_check()
        with STATE_LOCK:
            identity = STATE.get("identity")
        if not identity:
            raise RuntimeError("Η εγκατάσταση χρειάζεται νέα σύνδεση.")

        status, data = broker_post(
            "/msh/request",
            {
                "node_id": identity["node_id"],
                "node_secret": identity["node_secret"],
                "client_version": VERSION,
                "architecture": ARCH,
            },
        )
        if status != 201 or not data.get("success") or data.get("msh_delivery_authorized") is not True:
            raise RuntimeError("Δεν εγκρίθηκε η ασφαλής λήψη ρυθμίσεων.")
        if data.get("msh_delivered") is not False or data.get("agent_delivery") is not False or data.get("execution") is not False or data.get("remote_access") is not False:
            raise RuntimeError("Η απάντηση παραβίασε το όριο ασφαλείας της τρέχουσας έκδοσης.")
        ticket = str(data.get("msh_ticket") or "")
        if not re.fullmatch(r"SPMD-[A-Za-z0-9_-]{43}", ticket):
            raise RuntimeError("Η υπηρεσία επέστρεψε μη έγκυρο ticket λήψης.")
        expected_sha = str(data.get("expected_sha256") or "").lower()
        expected_bytes = int(data.get("expected_bytes") or 0)
        agent_label = str(data.get("agent_label") or "")
        if not re.fullmatch(r"[a-f0-9]{64}", expected_sha) or expected_bytes < 20 or expected_bytes > 262144:
            raise RuntimeError("Η υπηρεσία επέστρεψε μη έγκυρα στοιχεία ελέγχου.")

        status2, data2 = broker_post(
            "/msh/consume",
            {
                "msh_ticket": ticket,
                "node_id": identity["node_id"],
                "node_secret": identity["node_secret"],
                "client_version": VERSION,
                "architecture": ARCH,
            },
        )
        ticket = None
        if status2 != 200 or not data2.get("success") or data2.get("msh_delivery") is not True:
            raise RuntimeError("Η ασφαλής λήψη ρυθμίσεων δεν ολοκληρώθηκε.")
        if data2.get("agent_delivery") is not False or data2.get("execution") is not False or data2.get("remote_access") is not False:
            raise RuntimeError("Η απάντηση παραβίασε το όριο ασφαλείας της τρέχουσας έκδοσης.")
        msh = data2.get("msh")
        if not isinstance(msh, dict) or msh.get("encoding") != "base64":
            raise RuntimeError("Η υπηρεσία επέστρεψε μη έγκυρο αρχείο ρυθμίσεων.")
        delivered_sha = str(msh.get("sha256") or "").lower()
        delivered_bytes = int(msh.get("bytes") or 0)
        delivered_label = str(msh.get("agent_label") or "")
        if not secrets.compare_digest(delivered_sha, expected_sha) or delivered_bytes != expected_bytes or not secrets.compare_digest(delivered_label, agent_label):
            raise RuntimeError("Τα στοιχεία του αρχείου άλλαξαν μεταξύ έγκρισης και λήψης.")
        try:
            raw = base64.b64decode(str(msh.get("data") or ""), validate=True)
        except Exception as exc:
            raise RuntimeError("Το αρχείο ρυθμίσεων δεν αποκωδικοποιήθηκε σωστά.") from exc
        actual_sha = verify_msh_and_discard(raw, expected_sha, expected_bytes, agent_label)
        checked_at = str(data2.get("consumed_at") or "")
        with STATE_LOCK:
            STATE["settings_status"] = "verified"
            STATE["settings_checked_at"] = checked_at
            STATE["settings_error"] = None
            STATE["settings_sha_hint"] = actual_sha[:12]
            STATE["settings_bytes"] = expected_bytes
        print(f"[managed] Secure managed settings verified and discarded: bytes={expected_bytes}, sha256={actual_sha[:12]}...", flush=True)
        return checked_at
    except BrokerError as exc:
        if exc.error_code == "sprsb_managed_node_revoked":
            invalidate_local_identity(
                "revoked",
                "Η σύνδεση με το Smart Pro System έχει ανακληθεί. Απαιτείται νέος κωδικός pairing για επανασύνδεση.",
            )
        elif exc.error_code in ("sprsb_managed_node_auth_failed", "sprsb_managed_node_inactive"):
            invalidate_local_identity(
                "reauthorization_required",
                "Η αποθηκευμένη σύνδεση δεν είναι πλέον έγκυρη. Απαιτείται νέος κωδικός pairing.",
            )
        else:
            with STATE_LOCK:
                STATE["settings_status"] = "error"
                STATE["settings_error"] = str(exc)
        raise RuntimeError(str(exc)) from exc
    except RuntimeError as exc:
        with STATE_LOCK:
            STATE["settings_status"] = "error"
            STATE["settings_error"] = str(exc)
        raise


def broker_post_binary(endpoint, payload, timeout=45, max_bytes=67108865):
    base = safe_broker_base_url()
    if not base:
        raise BrokerError("Η διεύθυνση της ασφαλούς υπηρεσίας δεν είναι έγκυρη.")
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        base + endpoint,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/octet-stream",
            "User-Agent": f"SmartProManagedSupport/{VERSION}",
        },
        method="POST",
    )
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            content_type = str(response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
            raw = response.read(max_bytes)
            if len(raw) >= max_bytes:
                raise BrokerError("Το πρόγραμμα σύνδεσης ξεπέρασε το επιτρεπόμενο μέγεθος.")
            return response.status, content_type, dict(response.headers.items()), raw
    except urllib.error.HTTPError as exc:
        raw = exc.read(131072)
        content_type = str(exc.headers.get("Content-Type") or "unknown").split(";", 1)[0].strip().lower()
        print(f"[managed] Broker {endpoint}: HTTP {exc.code}, Content-Type={content_type}", flush=True)
        try:
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except (ValueError, UnicodeDecodeError):
            data = {}
        error_code = str(data.get("code") or "") if isinstance(data, dict) else ""
        message = str(data.get("message") or "") if isinstance(data, dict) else ""
        if not message:
            message = f"Η ασφαλής υπηρεσία απέρριψε το αίτημα (HTTP {exc.code}, {content_type})."
        raise BrokerError(message, http_status=exc.code, content_type=content_type, error_code=error_code or None) from exc
    except (urllib.error.URLError, TimeoutError, ssl.SSLError) as exc:
        raise BrokerError("Δεν ήταν δυνατή η ασφαλής επικοινωνία με το Smart Pro System.") from exc


def verify_agent_and_discard(raw, expected_sha, expected_bytes):
    if len(raw) != expected_bytes:
        raise RuntimeError("Το μέγεθος του προγράμματος σύνδεσης δεν συμφωνεί με το εγκεκριμένο.")
    actual_sha = hashlib.sha256(raw).hexdigest()
    if not secrets.compare_digest(actual_sha, expected_sha):
        raise RuntimeError("Το ψηφιακό αποτύπωμα του προγράμματος σύνδεσης δεν συμφωνεί με το εγκεκριμένο.")
    if len(raw) < 64 or raw[:4] != b"\x7fELF" or raw[4] != 2 or raw[5] != 1:
        raise RuntimeError("Το πρόγραμμα σύνδεσης δεν έχει την αναμενόμενη Linux 64-bit μορφή.")
    machine = raw[18] | (raw[19] << 8)
    expected_machine = 183 if ARCH == "aarch64" else 62 if ARCH == "amd64" else -1
    if machine != expected_machine:
        raise RuntimeError("Το πρόγραμμα σύνδεσης δεν αντιστοιχεί στην αρχιτεκτονική αυτής της εγκατάστασης.")
    temp_path = None
    try:
        fd, temp_path = tempfile.mkstemp(prefix="smart_pro_managed_agent_", suffix=".bin", dir="/tmp")
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        with open(temp_path, "rb") as handle:
            disk_raw = handle.read(expected_bytes + 1)
        if len(disk_raw) != expected_bytes or not secrets.compare_digest(hashlib.sha256(disk_raw).hexdigest(), expected_sha):
            raise RuntimeError("Η τοπική επαλήθευση του προσωρινού προγράμματος σύνδεσης απέτυχε.")
    finally:
        if temp_path:
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                pass
            except OSError as exc:
                raise RuntimeError("Δεν ήταν δυνατή η ασφαλής διαγραφή του προσωρινού προγράμματος σύνδεσης.") from exc
    return actual_sha


def secure_agent_delivery_check():
    with STATE_LOCK:
        identity = STATE.get("identity")
    if not identity:
        raise RuntimeError("Η εγκατάσταση δεν είναι συνδεδεμένη.")
    if ARCH not in ("aarch64", "amd64"):
        raise RuntimeError("Η αρχιτεκτονική αυτής της εγκατάστασης δεν υποστηρίζεται ακόμη.")
    try:
        # A fresh verified settings pass is mandatory immediately before agent delivery.
        secure_settings_delivery_check()
        with STATE_LOCK:
            identity = STATE.get("identity")
        if not identity:
            raise RuntimeError("Η εγκατάσταση χρειάζεται νέα σύνδεση.")
        status, data = broker_post(
            "/agent/request",
            {
                "node_id": identity["node_id"],
                "node_secret": identity["node_secret"],
                "client_version": VERSION,
                "architecture": ARCH,
            },
        )
        if status != 201 or not data.get("success") or data.get("agent_delivery_authorized") is not True:
            raise RuntimeError("Δεν εγκρίθηκε η ασφαλής λήψη του προγράμματος σύνδεσης.")
        if data.get("agent_delivered") is not False or data.get("execution") is not False or data.get("remote_access") is not False:
            raise RuntimeError("Η απάντηση παραβίασε το όριο ασφαλείας της τρέχουσας έκδοσης.")
        ticket = str(data.get("agent_ticket") or "")
        if not re.fullmatch(r"SPMA-[A-Za-z0-9_-]{43}", ticket):
            raise RuntimeError("Η υπηρεσία επέστρεψε μη έγκυρο ticket λήψης προγράμματος.")
        expected_sha = str(data.get("expected_sha256") or "").lower()
        expected_bytes = int(data.get("expected_bytes") or 0)
        if not re.fullmatch(r"[a-f0-9]{64}", expected_sha) or expected_bytes < 100000 or expected_bytes > 67108864:
            raise RuntimeError("Η υπηρεσία επέστρεψε μη έγκυρα στοιχεία ελέγχου του προγράμματος.")
        status2, content_type, headers, raw = broker_post_binary(
            "/agent/consume",
            {
                "agent_ticket": ticket,
                "node_id": identity["node_id"],
                "node_secret": identity["node_secret"],
                "client_version": VERSION,
                "architecture": ARCH,
            },
        )
        ticket = None
        if status2 != 200 or content_type != "application/octet-stream":
            raise RuntimeError("Η ασφαλής λήψη του προγράμματος σύνδεσης δεν ολοκληρώθηκε.")
        header_sha = str(headers.get("X-Smart-Pro-Agent-SHA256") or headers.get("X-Smart-Pro-Agent-Sha256") or "").lower()
        header_arch = str(headers.get("X-Smart-Pro-Agent-Architecture") or "").lower()
        header_exec = str(headers.get("X-Smart-Pro-Agent-Execution") or "").lower()
        if header_sha and not secrets.compare_digest(header_sha, expected_sha):
            raise RuntimeError("Τα στοιχεία του προγράμματος άλλαξαν μεταξύ έγκρισης και λήψης.")
        if header_arch and not secrets.compare_digest(header_arch, ARCH):
            raise RuntimeError("Η υπηρεσία επέστρεψε πρόγραμμα άλλης αρχιτεκτονικής.")
        if header_exec and header_exec != "disabled":
            raise RuntimeError("Η απάντηση δεν επιβεβαιώνει ότι η εκτέλεση παραμένει απενεργοποιημένη.")
        actual_sha = verify_agent_and_discard(raw, expected_sha, expected_bytes)
        checked_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with STATE_LOCK:
            STATE["agent_status"] = "verified"
            STATE["agent_checked_at"] = checked_at
            STATE["agent_error"] = None
            STATE["agent_sha_hint"] = actual_sha[:12]
            STATE["agent_bytes"] = expected_bytes
        print(f"[managed] Secure managed agent verified and discarded: bytes={expected_bytes}, sha256={actual_sha[:12]}... execution=disabled", flush=True)
        return checked_at
    except BrokerError as exc:
        if exc.error_code == "sprsb_managed_node_revoked":
            invalidate_local_identity("revoked", "Η σύνδεση με το Smart Pro System έχει ανακληθεί. Απαιτείται νέος κωδικός pairing για επανασύνδεση.")
        elif exc.error_code in ("sprsb_managed_node_auth_failed", "sprsb_managed_node_inactive"):
            invalidate_local_identity("reauthorization_required", "Η αποθηκευμένη σύνδεση δεν είναι πλέον έγκυρη. Απαιτείται νέος κωδικός pairing.")
        else:
            with STATE_LOCK:
                STATE["agent_status"] = "error"
                STATE["agent_error"] = str(exc)
        raise RuntimeError(str(exc)) from exc
    except RuntimeError as exc:
        with STATE_LOCK:
            STATE["agent_status"] = "error"
            STATE["agent_error"] = str(exc)
        raise


def _verify_msh_bytes(raw, expected_sha, expected_bytes, expected_label):
    if not isinstance(raw, (bytes, bytearray)) or len(raw) != int(expected_bytes):
        raise RuntimeError("Το αρχείο ρυθμίσεων δεν έχει το εγκεκριμένο μέγεθος.")
    actual_sha = hashlib.sha256(raw).hexdigest()
    if not secrets.compare_digest(actual_sha, str(expected_sha).lower()):
        raise RuntimeError("Το αρχείο ρυθμίσεων δεν πέρασε τον έλεγχο ακεραιότητας.")
    parsed = parse_msh_bytes(raw)
    for required in ("MeshName", "MeshType", "MeshID", "ServerID", "MeshServer"):
        if not parsed.get(required):
            raise RuntimeError("Το αρχείο ρυθμίσεων δεν περιέχει όλα τα απαιτούμενα πεδία.")
    if not str(parsed.get("MeshServer") or "").lower().startswith("wss://"):
        raise RuntimeError("Η διεύθυνση της υπηρεσίας σύνδεσης δεν είναι ασφαλής.")
    if not re.fullmatch(r"SPMNG-[A-F0-9]{16}", expected_label or "") or not secrets.compare_digest(str(parsed.get("agentName") or ""), expected_label):
        raise RuntimeError("Το αρχείο ρυθμίσεων δεν αντιστοιχεί σε αυτή την εγκατάσταση.")
    return actual_sha


def _harden_msh_for_runtime(raw, expected_label):
    """Create an ephemeral, locally hardened MeshAgent config after the broker copy is verified."""
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise RuntimeError("Οι ρυθμίσεις εκτέλεσης δεν είναι έγκυρο κείμενο.") from exc

    blocked = {"forceupdate", "fakeupdate", "coredumpenabled", "disableupdate", "noupdatecoremodule"}
    kept = []
    for original in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = original.strip()
        if not line:
            continue
        if "=" in line:
            key = line.split("=", 1)[0].strip().lower()
            if key in blocked:
                continue
        kept.append(line)
    kept.extend(["disableUpdate=1", "noUpdateCoreModule=1"])
    hardened = ("\n".join(kept) + "\n").encode("utf-8")

    parsed = parse_msh_bytes(hardened)
    for required in ("MeshName", "MeshType", "MeshID", "ServerID", "MeshServer"):
        if not parsed.get(required):
            raise RuntimeError("Οι ασφαλείς ρυθμίσεις εκτέλεσης έχασαν απαιτούμενο πεδίο.")
    if not str(parsed.get("MeshServer") or "").lower().startswith("wss://"):
        raise RuntimeError("Η διεύθυνση της υπηρεσίας σύνδεσης δεν είναι ασφαλής.")
    if not secrets.compare_digest(str(parsed.get("agentName") or ""), str(expected_label or "")):
        raise RuntimeError("Οι ασφαλείς ρυθμίσεις εκτέλεσης δεν αντιστοιχούν σε αυτή την εγκατάσταση.")
    if str(parsed.get("disableUpdate") or "") != "1" or str(parsed.get("noUpdateCoreModule") or "") != "1":
        raise RuntimeError("Δεν εφαρμόστηκε η τοπική πολιτική απενεργοποίησης ενημερώσεων.")
    return hardened


def _verify_agent_bytes(raw, expected_sha, expected_bytes):
    if len(raw) != int(expected_bytes):
        raise RuntimeError("Το πρόγραμμα σύνδεσης δεν έχει το εγκεκριμένο μέγεθος.")
    actual_sha = hashlib.sha256(raw).hexdigest()
    if not secrets.compare_digest(actual_sha, str(expected_sha).lower()):
        raise RuntimeError("Το πρόγραμμα σύνδεσης δεν πέρασε τον έλεγχο ακεραιότητας.")
    if len(raw) < 64 or raw[:4] != b"\x7fELF" or raw[4] != 2 or raw[5] != 1:
        raise RuntimeError("Το πρόγραμμα σύνδεσης δεν έχει την αναμενόμενη Linux 64-bit μορφή.")
    machine = raw[18] | (raw[19] << 8)
    expected_machine = 183 if ARCH == "aarch64" else 62 if ARCH == "amd64" else -1
    if machine != expected_machine:
        raise RuntimeError("Το πρόγραμμα σύνδεσης δεν αντιστοιχεί στην αρχιτεκτονική αυτής της εγκατάστασης.")
    return actual_sha


def _download_settings_for_runtime(identity):
    bootstrap_authorization_check()
    status, data = broker_post("/msh/request", {
        "node_id": identity["node_id"], "node_secret": identity["node_secret"],
        "client_version": VERSION, "architecture": ARCH,
    })
    if status != 201 or not data.get("success") or data.get("msh_delivery_authorized") is not True:
        raise RuntimeError("Δεν εγκρίθηκε η προσωρινή λήψη ρυθμίσεων.")
    ticket = str(data.get("msh_ticket") or "")
    expected_sha = str(data.get("expected_sha256") or "").lower()
    expected_bytes = int(data.get("expected_bytes") or 0)
    label = str(data.get("agent_label") or "")
    if not re.fullmatch(r"SPMD-[A-Za-z0-9_-]{43}", ticket):
        raise RuntimeError("Μη έγκυρη προσωρινή άδεια ρυθμίσεων.")
    status2, data2 = broker_post("/msh/consume", {
        "msh_ticket": ticket, "node_id": identity["node_id"], "node_secret": identity["node_secret"],
        "client_version": VERSION, "architecture": ARCH,
    })
    if status2 != 200 or not data2.get("success"):
        raise RuntimeError("Η προσωρινή λήψη ρυθμίσεων απέτυχε.")
    msh = data2.get("msh") or {}
    try:
        raw = base64.b64decode(str(msh.get("data") or ""), validate=True)
    except Exception as exc:
        raise RuntimeError("Οι ρυθμίσεις δεν αποκωδικοποιήθηκαν σωστά.") from exc
    delivered_sha = str(msh.get("sha256") or "").lower()
    delivered_bytes = int(msh.get("bytes") or 0)
    delivered_label = str(msh.get("agent_label") or "")
    if not secrets.compare_digest(delivered_sha, expected_sha) or delivered_bytes != expected_bytes or not secrets.compare_digest(delivered_label, label):
        raise RuntimeError("Οι ρυθμίσεις άλλαξαν μεταξύ έγκρισης και λήψης.")
    _verify_msh_bytes(raw, expected_sha, expected_bytes, label)
    return raw


def _download_agent_for_runtime(identity):
    status, data = broker_post("/agent/request", {
        "node_id": identity["node_id"], "node_secret": identity["node_secret"],
        "client_version": VERSION, "architecture": ARCH,
    })
    if status != 201 or not data.get("success") or data.get("agent_delivery_authorized") is not True:
        raise RuntimeError("Δεν εγκρίθηκε η προσωρινή λήψη του προγράμματος σύνδεσης.")
    ticket = str(data.get("agent_ticket") or "")
    expected_sha = str(data.get("expected_sha256") or "").lower()
    expected_bytes = int(data.get("expected_bytes") or 0)
    if not re.fullmatch(r"SPMA-[A-Za-z0-9_-]{43}", ticket):
        raise RuntimeError("Μη έγκυρη προσωρινή άδεια προγράμματος.")
    status2, content_type, headers, raw = broker_post_binary("/agent/consume", {
        "agent_ticket": ticket, "node_id": identity["node_id"], "node_secret": identity["node_secret"],
        "client_version": VERSION, "architecture": ARCH,
    })
    if status2 != 200 or content_type != "application/octet-stream":
        raise RuntimeError("Η προσωρινή λήψη του προγράμματος σύνδεσης απέτυχε.")
    header_sha = str(headers.get("X-Smart-Pro-Agent-SHA256") or headers.get("X-Smart-Pro-Agent-Sha256") or "").lower()
    header_arch = str(headers.get("X-Smart-Pro-Agent-Architecture") or "").lower()
    if header_sha and not secrets.compare_digest(header_sha, expected_sha):
        raise RuntimeError("Το πρόγραμμα άλλαξε μεταξύ έγκρισης και λήψης.")
    if header_arch and not secrets.compare_digest(header_arch, ARCH):
        raise RuntimeError("Λήφθηκε πρόγραμμα διαφορετικής αρχιτεκτονικής.")
    _verify_agent_bytes(raw, expected_sha, expected_bytes)
    return raw


def _report_execution(identity, report_token, result_code, elapsed_seconds):
    try:
        broker_post("/execution/report", {
            "report_token": report_token, "node_id": identity["node_id"], "node_secret": identity["node_secret"],
            "result_code": result_code, "elapsed_seconds": int(max(0, elapsed_seconds)),
        }, timeout=10)
    except Exception as exc:
        print(f"[managed] Execution report failed: {type(exc).__name__}", flush=True)


def controlled_session_run(session_ref):
    with STATE_LOCK:
        identity = dict(STATE.get("identity") or {})
        STATE["execution_status"] = "starting"
        STATE["execution_error"] = None
        STATE["execution_started_at"] = None
        STATE["execution_ended_at"] = None
        STATE["execution_result"] = None
    if not identity:
        with STATE_LOCK:
            STATE["execution_status"] = "error"
            STATE["execution_error"] = "Η εγκατάσταση δεν είναι συνδεδεμένη."
        return
    report_token = None
    proc = None
    tempdir = None
    started_monotonic = None
    result_code = "launch_failed"
    try:
        status, data = broker_post("/execution/request", {
            "session_ref": session_ref, "node_id": identity["node_id"], "node_secret": identity["node_secret"],
            "client_version": VERSION, "architecture": ARCH,
        })
        if status != 201 or not data.get("success") or data.get("start_authorized") is not True:
            raise RuntimeError("Η προσωρινή άδεια έναρξης δεν εκδόθηκε.")
        if data.get("execution") is not False or data.get("remote_access") is not False or data.get("persistence") is not False:
            raise RuntimeError("Η άδεια έναρξης δεν είναι στη σωστή ασφαλή κατάσταση.")
        execution_ticket = str(data.get("execution_ticket") or "")
        report_token = str(data.get("report_token") or "")
        max_runtime = max(1, min(60, int(data.get("max_runtime_seconds") or 0)))
        if not re.fullmatch(r"SPMX-[A-Za-z0-9_-]{43}", execution_ticket) or not re.fullmatch(r"SPMR-[A-Za-z0-9_-]{43}", report_token):
            raise RuntimeError("Η υπηρεσία επέστρεψε μη έγκυρη προσωρινή άδεια έναρξης.")

        tempdir = tempfile.mkdtemp(prefix="smart_pro_managed_run_", dir="/tmp")
        os.chmod(tempdir, 0o700)
        msh_raw = _download_settings_for_runtime(identity)
        agent_raw = _download_agent_for_runtime(identity)
        msh_path = os.path.join(tempdir, "meshagent.msh")
        agent_path = os.path.join(tempdir, "meshagent")
        expected_label = str(parse_msh_bytes(msh_raw).get("agentName") or "")
        runtime_msh = _harden_msh_for_runtime(msh_raw, expected_label)
        with open(msh_path, "wb") as handle:
            handle.write(runtime_msh); handle.flush(); os.fsync(handle.fileno())
        os.chmod(msh_path, 0o600)
        with open(agent_path, "wb") as handle:
            handle.write(agent_raw); handle.flush(); os.fsync(handle.fileno())
        os.chmod(agent_path, 0o700)
        msh_raw = None; runtime_msh = None; agent_raw = None

        runtime_home = os.path.join(tempdir, "home")
        runtime_tmp = os.path.join(tempdir, "tmp")
        runtime_cfg = os.path.join(tempdir, "config")
        runtime_cache = os.path.join(tempdir, "cache")
        for private_dir in (runtime_home, runtime_tmp, runtime_cfg, runtime_cache):
            os.mkdir(private_dir, 0o700)
        runtime_env = os.environ.copy()
        runtime_env.update({
            "HOME": runtime_home,
            "TMPDIR": runtime_tmp,
            "XDG_CONFIG_HOME": runtime_cfg,
            "XDG_CACHE_HOME": runtime_cache,
        })

        status2, data2 = broker_post("/execution/consume", {
            "execution_ticket": execution_ticket, "node_id": identity["node_id"], "node_secret": identity["node_secret"],
            "client_version": VERSION, "architecture": ARCH,
        })
        execution_ticket = None
        if status2 != 200 or not data2.get("success") or data2.get("start_authorized") is not True:
            raise RuntimeError("Η τελική άδεια έναρξης δεν επιβεβαιώθηκε.")
        if data2.get("temporary_connect_only") is not True or data2.get("persistence") is not False:
            raise RuntimeError("Η τελική άδεια δεν επιβεβαιώνει προσωρινή λειτουργία χωρίς εγκατάσταση.")
        max_runtime = max(1, min(max_runtime, int(data2.get("max_runtime_seconds") or max_runtime)))
        started_monotonic = time.monotonic()
        with STATE_LOCK:
            STATE["execution_status"] = "running"
            STATE["execution_started_at"] = str(data2.get("started_at") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        proc = subprocess.Popen(["setsid", "./meshagent"], cwd=tempdir, env=runtime_env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT, close_fds=True)
        result_code = "runtime_limit"
        while True:
            elapsed = int(time.monotonic() - started_monotonic)
            if proc.poll() is not None:
                result_code = "agent_exit"
                print(f"[managed] MeshAgent foreground exited early: rc={proc.returncode}", flush=True)
                break
            if elapsed >= max_runtime:
                result_code = "runtime_limit"
                break
            try:
                _, watch = broker_post("/execution/watch", {
                    "report_token": report_token, "node_id": identity["node_id"], "node_secret": identity["node_secret"],
                }, timeout=8)
                if not watch.get("continue"):
                    result_code = "session_ended"
                    break
            except Exception:
                result_code = "stopped"
                break
            time.sleep(3)
    except Exception as exc:
        with STATE_LOCK:
            STATE["execution_status"] = "error"
            STATE["execution_error"] = str(exc)
        result_code = "launch_failed"
    finally:
        elapsed = int(time.monotonic() - started_monotonic) if started_monotonic is not None else 0
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate(); proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill(); proc.wait(timeout=2)
                except Exception:
                    pass
        if tempdir:
            shutil.rmtree(tempdir, ignore_errors=True)
        if report_token:
            _report_execution(identity, report_token, result_code, elapsed)
        with STATE_LOCK:
            if STATE.get("execution_status") != "error":
                STATE["execution_status"] = "finished"
                STATE["execution_error"] = None
            STATE["execution_ended_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            STATE["execution_result"] = result_code
        try:
            heartbeat_once()
        except Exception:
            pass
        print(f"[managed] Controlled runtime finished: result={result_code}, seconds={elapsed}, persistence=false", flush=True)


def start_controlled_session():
    with STATE_LOCK:
        identity = STATE.get("identity")
        session = dict(STATE.get("support_session") or {})
        execution_status = STATE.get("execution_status")
    if not identity:
        raise RuntimeError("Η εγκατάσταση δεν είναι συνδεδεμένη.")
    if session.get("status") != "accepted" or not session.get("start_ready"):
        raise RuntimeError("Η Smart Pro δεν έχει εγκρίνει ακόμη την έναρξη ή η έγκριση έληξε.")
    if execution_status in ("starting", "running"):
        raise RuntimeError("Η δοκιμαστική συνεδρία είναι ήδη σε εξέλιξη.")
    session_ref = str(session.get("session_ref") or "")
    threading.Thread(target=controlled_session_run, args=(session_ref,), name="smart-pro-controlled-runtime", daemon=True).start()
    return True


def accept_support_session():
    with STATE_LOCK:
        identity = STATE.get("identity")
        session = STATE.get("support_session")
    if not identity:
        raise RuntimeError("Η εγκατάσταση δεν είναι συνδεδεμένη.")
    if not session or session.get("status") != "authorized":
        raise RuntimeError("Δεν υπάρχει συνεδρία που να περιμένει αποδοχή.")
    try:
        status, data = broker_post(
            "/session/accept",
            {
                "session_ref": session["session_ref"],
                "node_id": identity["node_id"],
                "node_secret": identity["node_secret"],
            },
        )
        if status != 200 or not data.get("success") or data.get("accepted") is not True:
            raise RuntimeError("Η αποδοχή της συνεδρίας δεν ολοκληρώθηκε.")
        if data.get("execution") is not False or data.get("remote_access") is not False or data.get("technician_connected") is not False:
            raise RuntimeError("Η απάντηση παραβίασε το όριο ασφαλείας της τρέχουσας έκδοσης.")
        with STATE_LOCK:
            STATE["support_session"] = {
                "session_ref": str(data.get("session_ref") or session["session_ref"]),
                "status": "accepted",
                "expires_at": str(data.get("expires_at") or session.get("expires_at") or ""),
                "accepted_at": str(data.get("accepted_at") or ""),
            }
            STATE["support_session_error"] = None
        print("[managed] Customer consent recorded. execution=disabled remote_access=disabled", flush=True)
        return True
    except BrokerError as exc:
        with STATE_LOCK:
            STATE["support_session_error"] = str(exc)
        raise RuntimeError(str(exc)) from exc
    except RuntimeError as exc:
        with STATE_LOCK:
            STATE["support_session_error"] = str(exc)
        raise


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
            raise BrokerError("Το heartbeat δεν επιβεβαιώθηκε.")
        if data.get("remote_access") is not False or data.get("execution") is not False or data.get("meshcentral") is not False:
            raise RuntimeError("Η απάντηση παραβίασε το Managed Foundation security boundary.")
        interval = int(data.get("heartbeat_interval_seconds") or HEARTBEAT_SECONDS)
        interval = max(30, min(300, interval))
        session = data.get("support_session")
        parsed_session = None
        if session is not None:
            if not isinstance(session, dict):
                raise RuntimeError("Η υπηρεσία επέστρεψε μη έγκυρη κατάσταση συνεδρίας.")
            session_ref = str(session.get("session_ref") or "")
            session_status = str(session.get("status") or "")
            if not re.fullmatch(r"SPSS-[A-F0-9]{24}", session_ref) or session_status not in ("authorized", "accepted", "running"):
                raise RuntimeError("Η υπηρεσία επέστρεψε μη έγκυρη συνεδρία υποστήριξης.")
            parsed_session = {
                "session_ref": session_ref,
                "status": session_status,
                "expires_at": str(session.get("expires_at") or ""),
                "accepted_at": str(session.get("accepted_at") or ""),
                "start_ready": bool(session.get("start_ready")),
                "start_ready_until": str(session.get("start_ready_until") or ""),
                "runtime_active": bool(session.get("runtime_active")),
            }
        with STATE_LOCK:
            STATE["status"] = "ready"
            STATE["last_heartbeat"] = str(data.get("last_seen_at") or "")
            STATE["last_error"] = None
            STATE["heartbeat_interval"] = interval
            STATE["support_session"] = parsed_session
            STATE["support_session_error"] = None
    except BrokerError as exc:
        if exc.error_code == "sprsb_managed_node_revoked":
            invalidate_local_identity(
                "revoked",
                "Η σύνδεση με το Smart Pro System έχει ανακληθεί. Απαιτείται νέος κωδικός pairing για επανασύνδεση.",
            )
            return
        if exc.error_code in ("sprsb_managed_node_auth_failed", "sprsb_managed_node_inactive"):
            invalidate_local_identity(
                "reauthorization_required",
                "Η αποθηκευμένη σύνδεση δεν είναι πλέον έγκυρη. Απαιτείται νέος κωδικός pairing.",
            )
            return
        with STATE_LOCK:
            STATE["status"] = "connection_error"
            STATE["last_error"] = str(exc)
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
            "last_installation_ref": STATE.get("last_installation_ref"),
            "bootstrap_status": STATE.get("bootstrap_status"),
            "bootstrap_checked_at": STATE.get("bootstrap_checked_at"),
            "bootstrap_error": STATE.get("bootstrap_error"),
            "bootstrap_source_hint": STATE.get("bootstrap_source_hint"),
            "settings_status": STATE.get("settings_status"),
            "settings_checked_at": STATE.get("settings_checked_at"),
            "settings_error": STATE.get("settings_error"),
            "settings_sha_hint": STATE.get("settings_sha_hint"),
            "settings_bytes": STATE.get("settings_bytes"),
            "agent_status": STATE.get("agent_status"),
            "agent_checked_at": STATE.get("agent_checked_at"),
            "agent_error": STATE.get("agent_error"),
            "agent_sha_hint": STATE.get("agent_sha_hint"),
            "agent_bytes": STATE.get("agent_bytes"),
            "support_session": dict(STATE.get("support_session")) if STATE.get("support_session") else None,
            "support_session_error": STATE.get("support_session_error"),
            "execution_status": STATE.get("execution_status"),
            "execution_error": STATE.get("execution_error"),
            "execution_started_at": STATE.get("execution_started_at"),
            "execution_ended_at": STATE.get("execution_ended_at"),
            "execution_result": STATE.get("execution_result"),
        }


def esc(value):
    return html.escape(str(value or ""), quote=True)


def render_page(message=None, error=None):
    state = snapshot()
    identity = state["identity"]
    status = state["status"]
    if not identity:
        pairing_form = f'''
            <form method="post" action="pair" autocomplete="off">
              <input type="hidden" name="csrf" value="{esc(CSRF_TOKEN)}">
              <label for="pairing_code">Κωδικός pairing</label>
              <input id="pairing_code" name="pairing_code" type="text" inputmode="text" maxlength="32" placeholder="SPM-XXXX-XXXX-XXXX-XXXX" required autocapitalize="characters" spellcheck="false">
              <button type="submit">Σύνδεση εγκατάστασης</button>
            </form>'''
        previous_installation = esc(state.get("last_installation_ref") or "")
        if status == "revoked":
            badge = '<span class="badge revoked"><span></span>Απαιτείται νέα σύνδεση</span>'
            previous_html = f'<div class="previous">Προηγούμενη εγκατάσταση: <strong>{previous_installation}</strong></div>' if previous_installation else ""
            body = f'''
              <section class="card hero">
                <div class="eyebrow">SMART PRO MANAGED SUPPORT</div>
                <h1>Η σύνδεση με το Smart Pro System ανακλήθηκε</h1>
                <p class="lead">Το προηγούμενο managed credential καταργήθηκε τοπικά και δεν χρησιμοποιείται πλέον. Για να συνδεθεί ξανά η εγκατάσταση, χρειάζεται νέος one-time κωδικός pairing από το Smart Pro Support.</p>
                {previous_html}
                {pairing_form}
                <div class="note"><strong>Ασφάλεια:</strong> Η ανάκληση δεν ενεργοποιεί απομακρυσμένη πρόσβαση. Η νέα σύνδεση δημιουργεί νέα managed identity και νέο credential.</div>
              </section>'''
        elif status == "reauthorization_required":
            badge = '<span class="badge revoked"><span></span>Απαιτείται επανασύνδεση</span>'
            body = f'''
              <section class="card hero">
                <div class="eyebrow">SMART PRO MANAGED SUPPORT</div>
                <h1>Η αποθηκευμένη σύνδεση δεν είναι πλέον έγκυρη</h1>
                <p class="lead">Η εφαρμογή κατάργησε το μη αποδεκτό managed credential. Ζητήστε νέο one-time κωδικό pairing από το Smart Pro Support για ασφαλή επανασύνδεση.</p>
                {pairing_form}
                <div class="note"><strong>Ασφάλεια:</strong> Δεν ενεργοποιείται MeshAgent ή απομακρυσμένη πρόσβαση σε αυτό το στάδιο.</div>
              </section>'''
        else:
            badge = '<span class="badge neutral"><span></span>Δεν έχει γίνει σύνδεση</span>'
            body = f'''
              <section class="card hero">
                <div class="eyebrow">SMART PRO MANAGED SUPPORT</div>
                <h1>Σύνδεση με το Smart Pro System</h1>
                <p class="lead">Χρησιμοποιήστε τον προσωρινό κωδικό pairing που σας δόθηκε από το Smart Pro Support. Ο κωδικός χρησιμοποιείται μία φορά και δεν αποθηκεύεται από την εφαρμογή.</p>
                {pairing_form}
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
        session = state.get("support_session")
        if session and session.get("status") == "authorized":
            support_status = "Περιμένει τη δική σας έγκριση"
            consent_box = f'''
            <div class="bootstrap-box consent-box">
              <div><span>Εγκεκριμένη συνεδρία Smart Pro Support</span><strong>Υπάρχει διαθέσιμη συνεδρία υποστήριξης</strong><p>Η Smart Pro έχει εγκρίνει συνεδρία για αυτή την εγκατάσταση. Η αποδοχή σας καταγράφει τη συναίνεση, αλλά δεν ανοίγει ακόμη απομακρυσμένη πρόσβαση.</p></div>
              <form method="post" action="session-accept"><input type="hidden" name="csrf" value="{esc(CSRF_TOKEN)}"><button type="submit">Αποδοχή συνεδρίας</button></form>
            </div>'''
        elif session and session.get("status") == "accepted":
            accepted_at = esc(session.get("accepted_at") or "")
            if state.get("execution_status") in ("starting", "running"):
                support_status = "Η δοκιμαστική συνεδρία ξεκινά"
                consent_box = f'''
                <div class="bootstrap-box consent-box accepted">
                  <div><span>Δοκιμαστική απομακρυσμένη συνεδρία</span><strong>Η σύνδεση είναι σε εξέλιξη</strong><p>Η πρόσβαση είναι προσωρινή, χωρίς εγκατάσταση υπηρεσίας, και θα τερματιστεί αυτόματα το αργότερο σε 60 δευτερόλεπτα.</p></div>
                </div>'''
            elif session.get("start_ready"):
                support_status = "Έτοιμη για έναρξη"
                consent_box = f'''
                <div class="bootstrap-box consent-box accepted">
                  <div><span>Εγκεκριμένη συνεδρία Smart Pro Support</span><strong>Η Smart Pro είναι έτοιμη να ξεκινήσει</strong><p>Η συναίνεσή σας έχει καταγραφεί{(" · " + accepted_at) if accepted_at else ""}. Πατώντας «Έναρξη συνεδρίας» επιτρέπετε μία δοκιμαστική σύνδεση έως 60 δευτερόλεπτα. Δεν εγκαθίσταται μόνιμη υπηρεσία.</p></div>
                  <form method="post" action="session-start"><input type="hidden" name="csrf" value="{esc(CSRF_TOKEN)}"><button type="submit">Έναρξη συνεδρίας</button></form>
                </div>'''
            else:
                support_status = "Η συνεδρία εγκρίθηκε από εσάς"
                consent_box = f'''
                <div class="bootstrap-box consent-box accepted">
                  <div><span>Εγκεκριμένη συνεδρία Smart Pro Support</span><strong>Η αποδοχή καταγράφηκε</strong><p>Η συναίνεσή σας έχει καταγραφεί{(" · " + accepted_at) if accepted_at else ""}. Αναμένεται η τελική έγκριση έναρξης από τη Smart Pro.</p></div>
                </div>'''
        elif session and session.get("status") == "running":
            support_status = "Η δοκιμαστική συνεδρία είναι ενεργή"
            consent_box = f'''
            <div class="bootstrap-box consent-box accepted">
              <div><span>Δοκιμαστική απομακρυσμένη συνεδρία</span><strong>Προσωρινή σύνδεση σε εξέλιξη</strong><p>Η σύνδεση τερματίζεται αυτόματα και δεν εγκαθίσταται μόνιμη υπηρεσία.</p></div>
            </div>'''
        else:
            support_status = "Δεν υπάρχει ενεργή συνεδρία"
            consent_box = '''
            <div class="bootstrap-box">
              <div><span>Συνεδρία υποστήριξης</span><strong>Δεν υπάρχει εγκεκριμένη συνεδρία αυτή τη στιγμή</strong><p>Όταν εγκριθεί συνεδρία από τη Smart Pro, θα εμφανιστεί εδώ και θα ζητηθεί η ρητή αποδοχή σας.</p></div>
            </div>'''
        session_error = state.get("support_session_error")
        if session_error:
            consent_box += f'<div class="inline-warning">{esc(session_error)}</div>'
        execution_error = state.get("execution_error")
        if execution_error:
            consent_box += f'<div class="inline-warning">{esc(execution_error)}</div>'
        body = f'''
          <section class="card hero">
            <div class="eyebrow">SMART PRO MANAGED SUPPORT</div>
            <h1>{esc(status_title)}</h1>
            <p class="lead">{esc(status_text)}</p>
            <div class="facts">
              <div><span>Εγκατάσταση</span><strong>{esc(identity.get("installation_ref"))}</strong></div>
              <div><span>Κατάσταση υποστήριξης</span><strong>{esc(support_status)}</strong></div>
              <div><span>Τελευταία επιβεβαίωση</span><strong>{last_seen}</strong></div>
            </div>
            {error_html}
            {consent_box}
            <div class="note"><strong>Τρέχον στάδιο {esc(VERSION)}:</strong> Επιτρέπεται μόνο μία ελεγχόμενη δοκιμαστική σύνδεση έως 60 δευτερόλεπτα, μετά από έγκριση Smart Pro και ρητή ενέργεια του πελάτη. Δεν γίνεται εγκατάσταση υπηρεσίας ή μόνιμη πρόσβαση.</div>
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
.badge{{display:inline-flex;align-items:center;gap:8px;padding:8px 12px;border:1px solid var(--line);border-radius:999px;background:#101923;color:#d9e4ee;font-size:13px;white-space:nowrap}}.badge span{{width:9px;height:9px;border-radius:50%;background:#7c8b99;box-shadow:0 0 0 4px rgba(124,139,153,.09)}}.badge.ok span{{background:var(--green)}}.badge.warn span{{background:var(--amber)}}.badge.info span{{background:var(--blue)}}.badge.revoked span{{background:var(--red)}}
.card{{background:rgba(18,27,37,.97);border:1px solid var(--line);border-radius:18px;box-shadow:0 18px 42px rgba(0,0,0,.2)}}.hero{{padding:34px}}.eyebrow{{font-size:12px;font-weight:800;letter-spacing:.12em;color:var(--blue);margin-bottom:10px}}h1{{font-size:30px;line-height:1.15;margin:0 0 12px}}.lead{{color:#c4d0db;max-width:760px;margin:0 0 28px}}
form{{max-width:620px}}label{{display:block;font-weight:700;margin:0 0 8px}}input{{width:100%;padding:14px 15px;border-radius:11px;border:1px solid #34475b;background:#0d151e;color:#fff;font-size:16px;letter-spacing:.06em;outline:none}}input:focus{{border-color:var(--blue);box-shadow:0 0 0 3px rgba(77,180,230,.14)}}button{{margin-top:14px;border:0;border-radius:11px;background:#2f9fd2;color:#071018;font-weight:800;padding:13px 18px;font-size:15px;cursor:pointer}}button.secondary{{margin-top:0;background:#182635;color:#dce8f2;border:1px solid #34475b}}
.previous{{margin:-8px 0 22px;color:var(--muted)}}.previous strong{{color:var(--text)}}.note{{margin-top:24px;padding:15px 17px;border:1px solid #2c3c4c;border-radius:12px;background:#0e1720;color:#b8c6d3}}.notice{{margin:0 0 15px;padding:13px 16px;border-radius:12px;border:1px solid var(--line)}}.notice.success{{background:rgba(105,213,140,.08);border-color:rgba(105,213,140,.35)}}.notice.error,.inline-warning{{background:rgba(255,112,112,.08);border:1px solid rgba(255,112,112,.35);color:#ffd0d0}}.inline-warning{{padding:12px 14px;border-radius:10px;margin-top:18px}}
.facts{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:24px 0}}.bootstrap-box{{display:flex;align-items:center;justify-content:space-between;gap:18px;margin-top:18px;padding:16px 17px;border:1px solid #2c3c4c;border-radius:12px;background:#0e1720}}.bootstrap-box span{{display:block;color:var(--muted);font-size:12px;margin-bottom:4px}}.bootstrap-box strong{{display:block}}.bootstrap-box p{{margin:4px 0 0;color:#9fb0c0;font-size:13px}}.bootstrap-box form{{flex:0 0 auto}}.facts div{{border:1px solid var(--line);border-radius:12px;background:#0f1821;padding:15px}}.facts span{{display:block;color:var(--muted);font-size:12px;margin-bottom:5px}}.facts strong{{display:block;font-size:14px;overflow-wrap:anywhere}}footer{{margin-top:16px;color:#718295;font-size:12px;text-align:center}}
@media(max-width:700px){{header{{align-items:flex-start;flex-direction:column}}.hero{{padding:24px 20px}}h1{{font-size:25px}}.facts{{grid-template-columns:1fr}}.bootstrap-box{{align-items:stretch;flex-direction:column}}}}
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
        if path.endswith("/session-accept") or path == "/session-accept":
            if not snapshot()["identity"]:
                self.send_html(render_page(error="Η εγκατάσταση δεν είναι συνδεδεμένη."), 409)
                return
            try:
                accept_support_session()
                self.send_html(render_page(message="Η συνεδρία εγκρίθηκε από εσάς. Δεν έχει ξεκινήσει ακόμη απομακρυσμένη πρόσβαση."))
            except RuntimeError as exc:
                self.send_html(render_page(error=str(exc)), 400)
            return
        if path.endswith("/session-start") or path == "/session-start":
            if not snapshot()["identity"]:
                self.send_html(render_page(error="Η εγκατάσταση δεν είναι συνδεδεμένη."), 409)
                return
            try:
                start_controlled_session()
                self.send_html(render_page(message="Η δοκιμαστική σύνδεση ξεκινά και θα τερματιστεί αυτόματα το αργότερο σε 60 δευτερόλεπτα."))
            except RuntimeError as exc:
                self.send_html(render_page(error=str(exc)), 400)
            return
        if path.endswith("/agent-check") or path == "/agent-check":
            if not snapshot()["identity"]:
                self.send_html(render_page(error="Η εγκατάσταση δεν είναι συνδεδεμένη."), 409)
                return
            try:
                secure_agent_delivery_check()
                self.send_html(render_page(message="Το πρόγραμμα σύνδεσης λήφθηκε, επαληθεύτηκε και διαγράφηκε χωρίς να εκτελεστεί και χωρίς ενεργοποίηση απομακρυσμένης πρόσβασης."))
            except RuntimeError as exc:
                self.send_html(render_page(error=str(exc)), 400)
            return
        if path.endswith("/delivery-check") or path == "/delivery-check":
            if not snapshot()["identity"]:
                self.send_html(render_page(error="Η εγκατάσταση δεν είναι συνδεδεμένη."), 409)
                return
            try:
                secure_settings_delivery_check()
                self.send_html(render_page(message="Οι ασφαλείς ρυθμίσεις λήφθηκαν, επαληθεύτηκαν και διαγράφηκαν χωρίς ενεργοποίηση απομακρυσμένης πρόσβασης."))
            except RuntimeError as exc:
                self.send_html(render_page(error=str(exc)), 400)
            return
        if path.endswith("/bootstrap-check") or path == "/bootstrap-check":
            if not snapshot()["identity"]:
                self.send_html(render_page(error="Η εγκατάσταση δεν είναι συνδεδεμένη."), 409)
                return
            try:
                bootstrap_authorization_check()
                self.send_html(render_page(message="Ο ασφαλής έλεγχος προετοιμασίας ολοκληρώθηκε."))
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
