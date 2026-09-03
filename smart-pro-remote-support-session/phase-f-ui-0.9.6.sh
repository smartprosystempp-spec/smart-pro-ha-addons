#!/bin/sh
set -eu

VERSION="0.9.6"
CONFIG_PATH="/data/options.json"
VALIDATE_RESPONSE="/tmp/smart-pro-validation-response.json"
CONSUME_RESPONSE="/tmp/smart-pro-bootstrap-consume-response.json"
RUNTIME_DIR="/tmp/smart-pro-phase-f-runtime"
MSH_TMP="$RUNTIME_DIR/meshagent.msh"
AGENT_TMP="$RUNTIME_DIR/meshagent"
AGENT_HEADERS="$RUNTIME_DIR/meshagent.headers"
AGENT_LOG="$RUNTIME_DIR/meshagent.runtime.log"
AGENT_PID_FILE="$RUNTIME_DIR/meshagent.pid"
ACTIVATION_REQUEST_RESPONSE="/tmp/smart-pro-activation-request-response.json"
ACTIVATION_CONSUME_RESPONSE="/tmp/smart-pro-activation-consume-response.json"
EXECUTION_REQUEST_RESPONSE="/tmp/smart-pro-execution-request-response.json"
EXECUTION_CONSUME_RESPONSE="/tmp/smart-pro-execution-consume-response.json"
EXECUTION_WATCH_RESPONSE="/tmp/smart-pro-execution-watch-response.json"
EXECUTION_REPORT_RESPONSE="/tmp/smart-pro-execution-report-response.json"
AGENT_PID=""
DEADLINE_GUARD_PID=""
HARD_DEADLINE_MARKER="$RUNTIME_DIR/.hard-deadline-reached"
RUNTIME_MAX_FILE="$RUNTIME_DIR/.runtime-max-seconds"
ABSOLUTE_RUNTIME_CAP=28860
WATCH_TRANSPORT_GRACE_SECONDS=30
WATCH_HTTP_STATUS_FILE="$RUNTIME_DIR/.watch-http-status"
RUN_GUARD_KEY_FILE="/data/.smart-pro-phase-f-one-shot.key"
RUN_GUARD_STATE_FILE="/data/.smart-pro-phase-f-last-attempt"
RUN_GUARD_FINGERPRINT=""
LAUNCH_COUNT_FILE="/data/.smart-pro-phase-f-launch-count-v093"

umask 077
ulimit -c 0 2>/dev/null || true

cleanup() {
  if [ -n "${DEADLINE_GUARD_PID:-}" ] && kill -0 "$DEADLINE_GUARD_PID" 2>/dev/null; then
    kill -TERM "$DEADLINE_GUARD_PID" 2>/dev/null || true
    wait "$DEADLINE_GUARD_PID" 2>/dev/null || true
  fi
  DEADLINE_GUARD_PID=""
  if [ -n "${AGENT_PID:-}" ] && kill -0 "$AGENT_PID" 2>/dev/null; then
    kill -TERM "$AGENT_PID" 2>/dev/null || true
    sleep 1
    kill -KILL "$AGENT_PID" 2>/dev/null || true
    wait "$AGENT_PID" 2>/dev/null || true
  fi
  AGENT_PID=""
  rm -f "$VALIDATE_RESPONSE" "$CONSUME_RESPONSE" "$ACTIVATION_REQUEST_RESPONSE" "$ACTIVATION_CONSUME_RESPONSE" \
    "$EXECUTION_REQUEST_RESPONSE" "$EXECUTION_CONSUME_RESPONSE" "$EXECUTION_WATCH_RESPONSE" "$EXECUTION_REPORT_RESPONSE" \
    "$AGENT_HEADERS"
  if [ -n "${RUNTIME_DIR:-}" ] && [ "$RUNTIME_DIR" = "/tmp/smart-pro-phase-f-runtime" ]; then
    rm -rf "$RUNTIME_DIR"
  fi
}
trap cleanup EXIT
trap 'exit 143' HUP TERM
trap 'exit 130' INT

fail() {
  echo "ΣΦΑΛΜΑ: $1"
  echo "Η ροή σταμάτησε fail-closed. Τυχόν Phase F process τερματίζεται από το cleanup trap και τα προσωρινά runtime files διαγράφονται."
  echo "ONE-SHOT SAFETY: Η αποτυχία θεωρείται χειρισμένη και το add-on τερματίζει καθαρά χωρίς αυτόματη δεύτερη execution προσπάθεια."
  exit 0
}

watch_request_once() {
  rm -f "$EXECUTION_WATCH_RESPONSE" "$WATCH_HTTP_STATUS_FILE"
  WATCH_RC=0
  WATCH_HTTP=""
  set +e
  curl --silent --show-error --proto '=https' --tlsv1.2 --connect-timeout 5 --max-time 10 \
    --output "$EXECUTION_WATCH_RESPONSE" --write-out '%{http_code}' \
    --header 'Content-Type: application/json' \
    --header "User-Agent: SmartProRemoteSupportSession/${VERSION}" \
    --data "$WATCH_PAYLOAD" "$EXECUTION_WATCH_ENDPOINT" > "$WATCH_HTTP_STATUS_FILE"
  WATCH_RC=$?
  set -e
  WATCH_HTTP="$(cat "$WATCH_HTTP_STATUS_FILE" 2>/dev/null || true)"
  rm -f "$WATCH_HTTP_STATUS_FILE"
}

activate_one_shot_guard() {
  [ -d /data ] || fail "Δεν είναι διαθέσιμο το persistent /data για το Phase F one-shot guard."
  if [ ! -s "$RUN_GUARD_KEY_FILE" ]; then
    GUARD_TMP="${RUN_GUARD_KEY_FILE}.tmp.$$"
    head -c 32 /dev/urandom | base64 | tr -d '\n' > "$GUARD_TMP" || fail "Δεν ήταν δυνατή η δημιουργία τοπικού one-shot guard key."
    chmod 600 "$GUARD_TMP" 2>/dev/null || true
    mv -f "$GUARD_TMP" "$RUN_GUARD_KEY_FILE" || fail "Δεν ήταν δυνατή η αποθήκευση του one-shot guard key."
  fi
  GUARD_SECRET="$(cat "$RUN_GUARD_KEY_FILE" 2>/dev/null || true)"
  [ -n "$GUARD_SECRET" ] || fail "Το one-shot guard key είναι κενό."
  RUN_GUARD_FINGERPRINT="$(printf '%s|%s|%s' "$GUARD_SECRET" "$BROKER_URL" "$SESSION_CODE" | sha256sum | awk '{print $1}')"
  GUARD_SECRET=""
  if [ -s "$RUN_GUARD_STATE_FILE" ] && [ "$(cat "$RUN_GUARD_STATE_FILE" 2>/dev/null || true)" = "$RUN_GUARD_FINGERPRINT" ]; then
    SESSION_CODE=""
    echo "ONE-SHOT GUARD: Ο ίδιος session code έχει ήδη επιχειρηθεί σε αυτό το add-on. Δεν γίνεται νέα επικοινωνία με Broker και δεν εκτελείται MeshAgent."
    echo "Για νέα ελεγχόμενη προσπάθεια απαιτείται fresh session code."
    exit 0
  fi
  GUARD_STATE_TMP="${RUN_GUARD_STATE_FILE}.tmp.$$"
  printf '%s\n' "$RUN_GUARD_FINGERPRINT" > "$GUARD_STATE_TMP" || fail "Δεν ήταν δυνατή η εγγραφή του one-shot guard state."
  chmod 600 "$GUARD_STATE_TMP" 2>/dev/null || true
  mv -f "$GUARD_STATE_TMP" "$RUN_GUARD_STATE_FILE" || fail "Δεν ήταν δυνατή η ενεργοποίηση του one-shot guard."
}

record_launch_instance() {
  [ -d /data ] || return 0
  CURRENT_COUNT=0
  if [ -s "$LAUNCH_COUNT_FILE" ]; then
    CURRENT_COUNT="$(cat "$LAUNCH_COUNT_FILE" 2>/dev/null || printf '0')"
  fi
  case "$CURRENT_COUNT" in
    ''|*[!0-9]*) CURRENT_COUNT=0 ;;
  esac
  CURRENT_COUNT=$((CURRENT_COUNT + 1))
  COUNT_TMP="${LAUNCH_COUNT_FILE}.tmp.$$"
  printf '%s\n' "$CURRENT_COUNT" > "$COUNT_TMP" 2>/dev/null || return 0
  chmod 600 "$COUNT_TMP" 2>/dev/null || true
  mv -f "$COUNT_TMP" "$LAUNCH_COUNT_FILE" 2>/dev/null || return 0
  echo "LAUNCH SAFETY: add-on process instance ${CURRENT_COUNT} για έκδοση ${VERSION}."
}

prepare_runtime_dir() {
  [ "$RUNTIME_DIR" = "/tmp/smart-pro-phase-f-runtime" ] || fail "Μη αναμενόμενο Phase F runtime path."
  rm -rf "$RUNTIME_DIR"
  mkdir -p "$RUNTIME_DIR" || fail "Δεν ήταν δυνατή η δημιουργία του ιδιωτικού Phase F runtime directory."
  chmod 700 "$RUNTIME_DIR" || fail "Δεν ήταν δυνατή η προστασία του Phase F runtime directory."
}

classify_startup_failure() {
  STARTUP_CATEGORY="unknown_startup_exit"
  [ -f "$AGENT_LOG" ] || return 0
  if grep -Eqi 'permission denied|operation not permitted|text file busy' "$AGENT_LOG"; then
    STARTUP_CATEGORY="execution_permission_denied"
  elif grep -Eqi 'error loading shared librar|symbol not found|relocation error|version .* not found' "$AGENT_LOG"; then
    STARTUP_CATEGORY="runtime_library_incompatible"
  elif grep -Eqi 'no such file or directory|not found' "$AGENT_LOG"; then
    STARTUP_CATEGORY="loader_or_runtime_missing"
  elif grep -Eqi 'bad web cert hash|certificate.*(error|fail|invalid)|tls.*(error|fail)' "$AGENT_LOG"; then
    STARTUP_CATEGORY="meshcentral_tls_or_certificate_rejected"
  elif grep -Eqi 'server url:|device group:|press ctrl-c to exit' "$AGENT_LOG"; then
    STARTUP_CATEGORY="meshagent_started_then_exited"
  elif grep -Eqi 'you can run the text version|usage:| -install| -uninstall| -update' "$AGENT_LOG"; then
    STARTUP_CATEGORY="meshagent_help_or_config_not_loaded"
  elif grep -Eqi 'unable to connect|connection refused|network is unreachable|name or service not known|temporary failure in name resolution|connect.*(fail|error)' "$AGENT_LOG"; then
    STARTUP_CATEGORY="meshcentral_connection_failed"
  fi
}

url_origin() {
  printf '%s' "$1" | sed -E 's#^(https://[^/]+).*$#\1#'
}

case "$(uname -m 2>/dev/null || true)" in
  aarch64|arm64) ARCHITECTURE="aarch64"; EXPECTED_MACHINE_HEX="b700" ;;
  x86_64|amd64) ARCHITECTURE="amd64"; EXPECTED_MACHINE_HEX="3e00" ;;
  *) fail "Η αρχιτεκτονική αυτού του Home Assistant host δεν υποστηρίζεται για Phase F." ;;
esac

echo "===================================================="
echo "  Smart Pro Remote Support - Προσωρινή Συνεδρία"
echo "===================================================="
echo "Κατάσταση: CONTROLLED MESHAGENT EXECUTION / PHASE F ${VERSION}"
echo "Αρχιτεκτονική QA: ${ARCHITECTURE}"
record_launch_instance
echo ""

[ -f "$CONFIG_PATH" ] || fail "Δεν βρέθηκε η διαμόρφωση της εφαρμογής."

BROKER_URL="$(jq -r '.broker_url // empty' "$CONFIG_PATH")"
SESSION_CODE=""
if IFS= read -r SESSION_CODE; then
  :
else
  fail "Δεν παραδόθηκε προσωρινός κωδικός από το ασφαλές Customer UI bridge."
fi

[ -n "$BROKER_URL" ] || fail "Δεν έχει οριστεί endpoint επικύρωσης."
case "$BROKER_URL" in
  https://*) ;;
  *) fail "Επιτρέπεται μόνο HTTPS endpoint." ;;
esac
BROKER_ORIGIN="$(url_origin "$BROKER_URL")"
[ -n "$BROKER_ORIGIN" ] || fail "Δεν ήταν δυνατή η επαλήθευση origin του Broker endpoint."

[ -n "$SESSION_CODE" ] || fail "Δεν έχει συμπληρωθεί προσωρινός κωδικός συνεδρίας."
SESSION_CODE="$(printf '%s' "$SESSION_CODE" | tr '[:lower:]' '[:upper:]' | tr -cd 'A-Z0-9-')"
printf '%s' "$SESSION_CODE" | grep -Eq '^SP-[A-Z0-9]{4}-[A-Z0-9]{4}$' || fail "Ο κωδικός δεν έχει την αναμενόμενη μορφή SP-XXXX-XXXX."

activate_one_shot_guard
prepare_runtime_dir

VALIDATE_PAYLOAD="$(jq -n \
  --arg code "$SESSION_CODE" \
  --arg client "home_assistant_os" \
  --arg client_version "$VERSION" \
  '{code:$code, client:$client, client_version:$client_version, request_bootstrap_ticket:true}')"
SESSION_CODE=""

echo "1/8 Επικύρωση συνεδρίας και αίτημα one-time bootstrap ticket..."
set +e
VALIDATE_HTTP="$(curl \
  --silent \
  --show-error \
  --proto '=https' \
  --tlsv1.2 \
  --connect-timeout 10 \
  --max-time 20 \
  --output "$VALIDATE_RESPONSE" \
  --write-out '%{http_code}' \
  --header 'Content-Type: application/json' \
  --header "User-Agent: SmartProRemoteSupportSession/${VERSION}" \
  --data "$VALIDATE_PAYLOAD" \
  "$BROKER_URL")"
CURL_RC=$?
set -e
VALIDATE_PAYLOAD=""

[ "$CURL_RC" -eq 0 ] || fail "Δεν ήταν δυνατή η επικοινωνία με τον Smart Pro Broker. Ελέγξτε Internet και προσβασιμότητα endpoint."
jq empty "$VALIDATE_RESPONSE" >/dev/null 2>&1 || fail "Ο Smart Pro Broker επέστρεψε μη αναμενόμενη απάντηση (HTTP ${VALIDATE_HTTP})."

VALID="$(jq -r '.valid // false' "$VALIDATE_RESPONSE")"
if [ "$VALIDATE_HTTP" != "200" ] || [ "$VALID" != "true" ]; then
  REASON="$(jq -r '.data.reason // .reason // "unknown"' "$VALIDATE_RESPONSE")"
  MESSAGE="$(jq -r '.message // "Ο κωδικός δεν έγινε αποδεκτός."' "$VALIDATE_RESPONSE")"
  case "$REASON" in
    revoked) fail "Ο προσωρινός κωδικός έχει ανακληθεί." ;;
    expired) fail "Ο προσωρινός κωδικός έχει λήξει." ;;
    invalid) fail "Ο προσωρινός κωδικός δεν είναι έγκυρος." ;;
    rate_limited) fail "Έγιναν πολλές προσπάθειες. Δοκιμάστε ξανά αργότερα." ;;
    *) fail "${MESSAGE} (HTTP ${VALIDATE_HTTP})" ;;
  esac
fi

BOOTSTRAP_AVAILABLE="$(jq -r '.bootstrap_available // false' "$VALIDATE_RESPONSE")"
BOOTSTRAP_TICKET="$(jq -r '.bootstrap_ticket // empty' "$VALIDATE_RESPONSE")"
BOOTSTRAP_ENDPOINT="$(jq -r '.bootstrap_endpoint // empty' "$VALIDATE_RESPONSE")"
BOOTSTRAP_EXPIRES="$(jq -r '.bootstrap_expires_at // empty' "$VALIDATE_RESPONSE")"
MODE="$(jq -r '.mode // empty' "$VALIDATE_RESPONSE")"

[ "$BOOTSTRAP_AVAILABLE" = "true" ] || fail "Ο Broker επικύρωσε τον κωδικό αλλά δεν επέστρεψε bootstrap ticket."
[ -n "$BOOTSTRAP_TICKET" ] || fail "Λείπει το one-time bootstrap ticket."
[ -n "$BOOTSTRAP_ENDPOINT" ] || fail "Λείπει το bootstrap endpoint."
case "$BOOTSTRAP_ENDPOINT" in
  https://*) ;;
  *) fail "Το bootstrap endpoint που επέστρεψε ο Broker δεν είναι HTTPS." ;;
esac
[ "$(url_origin "$BOOTSTRAP_ENDPOINT")" = "$BROKER_ORIGIN" ] || fail "Το bootstrap endpoint δεν ανήκει στο ίδιο HTTPS origin με τον Broker."
[ "$MODE" = "bootstrap_phase_d_agent_delivery" ] || fail "Ο Broker δεν είναι ακόμη σε Secure Agent Delivery Phase D για αυτόν τον client."

rm -f "$VALIDATE_RESPONSE"
echo "ΕΠΙΤΥΧΙΑ: Ο session code είναι έγκυρος."
echo "Εκδόθηκε βραχύβιο bootstrap ticket χωρίς να εμφανιστεί στο log."
[ -n "$BOOTSTRAP_EXPIRES" ] && echo "Λήξη bootstrap ticket (UTC): ${BOOTSTRAP_EXPIRES}"
echo ""

echo "2/8 Κατανάλωση bootstrap ticket και επαλήθευση READY .msh..."
CONSUME_PAYLOAD="$(jq -n \
  --arg ticket "$BOOTSTRAP_TICKET" \
  --arg client "home_assistant_os" \
  --arg client_version "$VERSION" \
  --arg architecture "$ARCHITECTURE" \
  '{ticket:$ticket, client:$client, client_version:$client_version, architecture:$architecture}')"

set +e
CONSUME_HTTP="$(curl \
  --silent \
  --show-error \
  --proto '=https' \
  --tlsv1.2 \
  --connect-timeout 10 \
  --max-time 25 \
  --output "$CONSUME_RESPONSE" \
  --write-out '%{http_code}' \
  --header 'Content-Type: application/json' \
  --header "User-Agent: SmartProRemoteSupportSession/${VERSION}" \
  --data "$CONSUME_PAYLOAD" \
  "$BOOTSTRAP_ENDPOINT")"
CURL_RC=$?
set -e

BOOTSTRAP_TICKET=""
CONSUME_PAYLOAD=""

[ "$CURL_RC" -eq 0 ] || fail "Δεν ήταν δυνατή η κατανάλωση του bootstrap ticket."
jq empty "$CONSUME_RESPONSE" >/dev/null 2>&1 || fail "Ο Broker επέστρεψε μη αναμενόμενη bootstrap απάντηση (HTTP ${CONSUME_HTTP})."

CONSUMED="$(jq -r '.consumed // false' "$CONSUME_RESPONSE")"
REMOTE_ACCESS="$(jq -r '.remote_access // false' "$CONSUME_RESPONSE")"
RESPONSE_MODE="$(jq -r '.mode // empty' "$CONSUME_RESPONSE")"

if [ "$CONSUME_HTTP" != "200" ] || [ "$CONSUMED" != "true" ]; then
  REASON="$(jq -r '.data.reason // .reason // "unknown"' "$CONSUME_RESPONSE")"
  MESSAGE="$(jq -r '.message // "Το bootstrap ticket δεν έγινε αποδεκτό."' "$CONSUME_RESPONSE")"
  case "$REASON" in
    expired|session_expired) fail "Το bootstrap ticket ή η συνεδρία έχει λήξει." ;;
    already_used|consumed|superseded) fail "Το bootstrap ticket έχει ήδη χρησιμοποιηθεί ή αντικατασταθεί." ;;
    client_mismatch) fail "Το bootstrap ticket δεν αντιστοιχεί σε αυτόν τον client." ;;
    unsupported_architecture) fail "Η αρχιτεκτονική δεν υποστηρίζεται από τον Broker για Phase D." ;;
    agents_not_ready|agent_readiness_metadata_invalid) fail "Ο Broker δεν έχει έγκυρο AGENTS READY state." ;;
    rate_limited) fail "Έγιναν πολλές bootstrap προσπάθειες. Δοκιμάστε ξανά αργότερα." ;;
    *) fail "${MESSAGE} (HTTP ${CONSUME_HTTP})" ;;
  esac
fi

[ "$REMOTE_ACCESS" = "false" ] || fail "Ο Broker επέστρεψε μη αναμενόμενη κατάσταση remote_access."
[ "$RESPONSE_MODE" = "bootstrap_phase_d_agent_delivery" ] || fail "Η bootstrap απάντηση δεν είναι Phase D delivery."

ENCODING="$(jq -r '.meshcentral_bootstrap.encoding // empty' "$CONSUME_RESPONSE")"
MSH_B64="$(jq -r '.meshcentral_bootstrap.data // empty' "$CONSUME_RESPONSE")"
EXPECTED_MSH_SHA="$(jq -r '.meshcentral_bootstrap.sha256 // empty' "$CONSUME_RESPONSE")"
EXPECTED_MSH_BYTES="$(jq -r '.meshcentral_bootstrap.bytes // 0' "$CONSUME_RESPONSE")"

[ "$ENCODING" = "base64" ] || fail "Το MeshCentral bootstrap δεν έχει την αναμενόμενη κωδικοποίηση."
[ -n "$MSH_B64" ] || fail "Ο Broker δεν παρέδωσε προσωρινό MeshCentral bootstrap."
printf '%s' "$EXPECTED_MSH_SHA" | grep -Eq '^[a-f0-9]{64}$' || fail "Το bootstrap fingerprint δεν είναι έγκυρο."
printf '%s' "$EXPECTED_MSH_BYTES" | grep -Eq '^[0-9]+$' || fail "Το bootstrap size metadata δεν είναι έγκυρο."

printf '%s' "$MSH_B64" | base64 -d > "$MSH_TMP" 2>/dev/null || fail "Δεν ήταν δυνατή η αποκωδικοποίηση του προσωρινού MeshCentral bootstrap."
MSH_B64=""

ACTUAL_MSH_BYTES="$(wc -c < "$MSH_TMP" | tr -d ' ')"
[ "$ACTUAL_MSH_BYTES" -ge 20 ] && [ "$ACTUAL_MSH_BYTES" -le 262144 ] || fail "Το προσωρινό .msh έχει μη αναμενόμενο μέγεθος."
[ "$ACTUAL_MSH_BYTES" = "$EXPECTED_MSH_BYTES" ] || fail "Το μέγεθος του προσωρινού .msh δεν συμφωνεί με το Broker metadata."
ACTUAL_MSH_SHA="$(sha256sum "$MSH_TMP" | awk '{print $1}')"
[ "$ACTUAL_MSH_SHA" = "$EXPECTED_MSH_SHA" ] || fail "Το SHA-256 του προσωρινού .msh δεν συμφωνεί με το Broker fingerprint."

for KEY in MeshName MeshType MeshID ServerID MeshServer; do
  grep -q "^${KEY}=" "$MSH_TMP" || fail "Το προσωρινό .msh λείπει απαιτούμενο πεδίο (${KEY})."
done
grep -qi '^MeshServer=wss://' "$MSH_TMP" || fail "Το προσωρινό .msh δεν χρησιμοποιεί ασφαλές WSS MeshServer."
EXPECTED_MSH_SHA=""
ACTUAL_MSH_SHA=""

echo "ΕΠΙΤΥΧΙΑ: Το READY .msh επαληθεύτηκε και κρατήθηκε μόνο προσωρινά για Phase F."
echo ""

echo "3/8 Έλεγχος ξεχωριστού one-time Agent Delivery Ticket..."
AGENT_AVAILABLE="$(jq -r '.agent_delivery.available // false' "$CONSUME_RESPONSE")"
AGENT_TICKET="$(jq -r '.agent_delivery.ticket // empty' "$CONSUME_RESPONSE")"
AGENT_ENDPOINT="$(jq -r '.agent_delivery.endpoint // empty' "$CONSUME_RESPONSE")"
AGENT_EXPIRES="$(jq -r '.agent_delivery.expires_at // empty' "$CONSUME_RESPONSE")"
AGENT_ARCH="$(jq -r '.agent_delivery.architecture // empty' "$CONSUME_RESPONSE")"
EXPECTED_AGENT_SHA="$(jq -r '.agent_delivery.sha256 // empty' "$CONSUME_RESPONSE")"
EXPECTED_AGENT_BYTES="$(jq -r '.agent_delivery.bytes // 0' "$CONSUME_RESPONSE")"
ACTIVATION_AVAILABLE="$(jq -r '.activation_authorization.available // false' "$CONSUME_RESPONSE")"
ACTIVATION_REQUEST_ENDPOINT="$(jq -r '.activation_authorization.request_endpoint // empty' "$CONSUME_RESPONSE")"
ACTIVATION_REQUIRES_ARM="$(jq -r '.activation_authorization.requires_admin_arm // false' "$CONSUME_RESPONSE")"

[ "$AGENT_AVAILABLE" = "true" ] || fail "Ο Broker δεν επέστρεψε διαθέσιμο Agent Delivery Ticket."
[ -n "$AGENT_TICKET" ] || fail "Λείπει το one-time Agent Delivery Ticket."
[ -n "$AGENT_ENDPOINT" ] || fail "Λείπει το agent delivery endpoint."
case "$AGENT_ENDPOINT" in
  https://*) ;;
  *) fail "Το agent delivery endpoint δεν είναι HTTPS." ;;
esac
[ "$(url_origin "$AGENT_ENDPOINT")" = "$BROKER_ORIGIN" ] || fail "Το agent delivery endpoint δεν ανήκει στο ίδιο HTTPS origin με τον Broker."
[ "$AGENT_ARCH" = "$ARCHITECTURE" ] || fail "Το Agent Delivery Ticket δεν αντιστοιχεί στην αρχιτεκτονική του host."
printf '%s' "$EXPECTED_AGENT_SHA" | grep -Eq '^[a-f0-9]{64}$' || fail "Το agent SHA-256 metadata δεν είναι έγκυρο."
printf '%s' "$EXPECTED_AGENT_BYTES" | grep -Eq '^[0-9]+$' || fail "Το agent size metadata δεν είναι έγκυρο."
[ "$EXPECTED_AGENT_BYTES" -ge 1048576 ] && [ "$EXPECTED_AGENT_BYTES" -le 67108864 ] || fail "Το agent size metadata είναι εκτός ασφαλών ορίων."
jq -e '.agent_delivery.execution == false' "$CONSUME_RESPONSE" >/dev/null 2>&1 || fail "Ο Broker δεν δήλωσε ρητά execution=false για Phase D."
[ "$ACTIVATION_AVAILABLE" = "true" ] || fail "Ο Broker δεν επέστρεψε Phase E activation authorization metadata."
[ "$ACTIVATION_REQUIRES_ARM" = "true" ] || fail "Ο Broker δεν απαιτεί ρητή Admin όπλιση για Phase E."
[ -n "$ACTIVATION_REQUEST_ENDPOINT" ] || fail "Λείπει το Phase E activation request endpoint."
case "$ACTIVATION_REQUEST_ENDPOINT" in
  https://*) ;;
  *) fail "Το Phase E activation request endpoint δεν είναι HTTPS." ;;
esac
[ "$(url_origin "$ACTIVATION_REQUEST_ENDPOINT")" = "$BROKER_ORIGIN" ] || fail "Το Phase E activation endpoint δεν ανήκει στο ίδιο HTTPS origin με τον Broker."
jq -e '.activation_authorization.execution == false and .activation_authorization.remote_access == false' "$CONSUME_RESPONSE" >/dev/null 2>&1 || fail "Ο Broker δεν κράτησε execution/remote_access κλειδωμένα για Phase E."
rm -f "$CONSUME_RESPONSE"

echo "ΕΠΙΤΥΧΙΑ: Το Agent Delivery Ticket είναι one-time, δεμένο με ${ARCHITECTURE} και execution=false."
[ -n "$AGENT_EXPIRES" ] && echo "Λήξη agent ticket (UTC): ${AGENT_EXPIRES}"
echo ""

echo "4/8 Προσωρινή λήψη και ακεραιότητα ELF/SHA πριν από οποιαδήποτε execution permission..."
AGENT_PAYLOAD="$(jq -n \
  --arg ticket "$AGENT_TICKET" \
  --arg client "home_assistant_os" \
  --arg client_version "$VERSION" \
  --arg architecture "$ARCHITECTURE" \
  '{ticket:$ticket, client:$client, client_version:$client_version, architecture:$architecture}')"

set +e
AGENT_HTTP="$(curl \
  --silent \
  --show-error \
  --proto '=https' \
  --tlsv1.2 \
  --connect-timeout 10 \
  --max-time 90 \
  --output "$AGENT_TMP" \
  --dump-header "$AGENT_HEADERS" \
  --write-out '%{http_code}' \
  --header 'Content-Type: application/json' \
  --header "User-Agent: SmartProRemoteSupportSession/${VERSION}" \
  --data "$AGENT_PAYLOAD" \
  "$AGENT_ENDPOINT")"
CURL_RC=$?
set -e

AGENT_PAYLOAD=""

[ "$CURL_RC" -eq 0 ] || fail "Δεν ήταν δυνατή η προσωρινή λήψη του agent binary."
[ "$AGENT_HTTP" = "200" ] || fail "Ο Broker δεν παρέδωσε agent binary (HTTP ${AGENT_HTTP})."
[ -s "$AGENT_TMP" ] || fail "Το προσωρινό agent binary είναι κενό."

grep -Eiq '^Content-Type:[[:space:]]*application/octet-stream([[:space:];]|$)' "$AGENT_HEADERS" || fail "Το agent response δεν έχει ασφαλές binary Content-Type."
header_value() {
  WANTED_HEADER="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
  awk -v wanted="$WANTED_HEADER" '
    {
      line=$0
      sub(/\r$/, "", line)
      pos=index(line, ":")
      if (pos > 0) {
        name=substr(line, 1, pos - 1)
        if (tolower(name) == wanted) {
          value=substr(line, pos + 1)
          sub(/^[[:space:]]*/, "", value)
          print value
          exit
        }
      }
    }' "$AGENT_HEADERS"
}

HEADER_ARCH="$(header_value 'X-Smart-Pro-Agent-Architecture')"
HEADER_SHA="$(header_value 'X-Smart-Pro-Agent-SHA256')"
HEADER_EXEC="$(header_value 'X-Smart-Pro-Agent-Execution')"
[ "$HEADER_ARCH" = "$ARCHITECTURE" ] || fail "Το binary response architecture header δεν συμφωνεί με το host."
[ "$HEADER_SHA" = "$EXPECTED_AGENT_SHA" ] || fail "Το binary response SHA header δεν συμφωνεί με το Agent Delivery Ticket."
[ "$HEADER_EXEC" = "disabled" ] || fail "Το binary response δεν δηλώνει execution disabled."

ACTUAL_AGENT_BYTES="$(wc -c < "$AGENT_TMP" | tr -d ' ')"
[ "$ACTUAL_AGENT_BYTES" = "$EXPECTED_AGENT_BYTES" ] || fail "Το μέγεθος του agent binary δεν συμφωνεί με το AGENTS READY metadata."
ACTUAL_AGENT_SHA="$(sha256sum "$AGENT_TMP" | awk '{print $1}')"
[ "$ACTUAL_AGENT_SHA" = "$EXPECTED_AGENT_SHA" ] || fail "Το SHA-256 του agent binary δεν συμφωνεί με το AGENTS READY metadata."

HEADER_HEX="$(od -An -tx1 -N20 "$AGENT_TMP" | tr -d ' \n')"
[ "$(printf '%s' "$HEADER_HEX" | cut -c1-8)" = "7f454c46" ] || fail "Το agent binary δεν είναι ELF."
[ "$(printf '%s' "$HEADER_HEX" | cut -c9-10)" = "02" ] || fail "Το agent binary δεν είναι ELF64."
[ "$(printf '%s' "$HEADER_HEX" | cut -c11-12)" = "01" ] || fail "Το agent binary δεν είναι little-endian ELF."
[ "$(printf '%s' "$HEADER_HEX" | cut -c37-40)" = "$EXPECTED_MACHINE_HEX" ] || fail "Το ELF e_machine δεν αντιστοιχεί στην αρχιτεκτονική ${ARCHITECTURE}."

# Phase F: το verified binary παραμένει προσωρινά ΜΗ εκτελέσιμο μέχρι το ξεχωριστό Phase F ticket consume.
rm -f "$AGENT_HEADERS"
ACTUAL_AGENT_SHA=""

[ -f "$AGENT_TMP" ] || fail "Το verified agent binary δεν είναι διαθέσιμο για το επόμενο Phase F authorization checkpoint."
echo "ΕΠΙΤΥΧΙΑ: Agent binary ${ARCHITECTURE}, μέγεθος, SHA-256 και ELF architecture επαληθεύτηκαν."
echo "Το binary παραμένει προσωρινά χωρίς executable permission μέχρι την τελική Phase F authorization."
echo ""

echo "5/8 Αίτημα one-time Phase E Activation Authorization Ticket..."
ACTIVATION_REQUEST_PAYLOAD="$(jq -n \
  --arg agent_ticket "$AGENT_TICKET" \
  --arg client "home_assistant_os" \
  --arg client_version "$VERSION" \
  --arg architecture "$ARCHITECTURE" \
  '{agent_ticket:$agent_ticket, client:$client, client_version:$client_version, architecture:$architecture}')"

set +e
ACTIVATION_REQUEST_HTTP="$(curl \
  --silent \
  --show-error \
  --proto '=https' \
  --tlsv1.2 \
  --connect-timeout 10 \
  --max-time 20 \
  --output "$ACTIVATION_REQUEST_RESPONSE" \
  --write-out '%{http_code}' \
  --header 'Content-Type: application/json' \
  --header "User-Agent: SmartProRemoteSupportSession/${VERSION}" \
  --data "$ACTIVATION_REQUEST_PAYLOAD" \
  "$ACTIVATION_REQUEST_ENDPOINT")"
CURL_RC=$?
set -e

AGENT_TICKET=""
ACTIVATION_REQUEST_PAYLOAD=""

[ "$CURL_RC" -eq 0 ] || fail "Δεν ήταν δυνατή η αίτηση Phase E authorization."
jq empty "$ACTIVATION_REQUEST_RESPONSE" >/dev/null 2>&1 || fail "Ο Broker επέστρεψε μη αναμενόμενη Phase E authorization απάντηση (HTTP ${ACTIVATION_REQUEST_HTTP})."

if [ "$ACTIVATION_REQUEST_HTTP" != "200" ]; then
  REASON="$(jq -r '.data.reason // .reason // "unknown"' "$ACTIVATION_REQUEST_RESPONSE")"
  MESSAGE="$(jq -r '.message // "Η Phase E authorization δεν εγκρίθηκε."' "$ACTIVATION_REQUEST_RESPONSE")"
  case "$REASON" in
    not_armed) fail "Η συγκεκριμένη συνεδρία δεν έχει οπλιστεί από Admin για Phase E." ;;
    agent_delivery_too_old) fail "Το verified agent delivery είναι πολύ παλιό για Phase E authorization." ;;
    client_mismatch) fail "Το Phase E authorization δεν αντιστοιχεί σε αυτόν τον client." ;;
    rate_limited) fail "Έγιναν πολλές Phase E authorization προσπάθειες. Δοκιμάστε ξανά αργότερα." ;;
    *) fail "${MESSAGE} (HTTP ${ACTIVATION_REQUEST_HTTP})" ;;
  esac
fi

ACTIVATION_AUTHORIZED="$(jq -r '.authorized // false' "$ACTIVATION_REQUEST_RESPONSE")"
ACTIVATION_TICKET="$(jq -r '.ticket // empty' "$ACTIVATION_REQUEST_RESPONSE")"
ACTIVATION_CONSUME_ENDPOINT="$(jq -r '.endpoint // empty' "$ACTIVATION_REQUEST_RESPONSE")"
ACTIVATION_EXPIRES="$(jq -r '.expires_at // empty' "$ACTIVATION_REQUEST_RESPONSE")"
ACTIVATION_ARCH="$(jq -r '.architecture // empty' "$ACTIVATION_REQUEST_RESPONSE")"
ACTIVATION_SHA="$(jq -r '.sha256 // empty' "$ACTIVATION_REQUEST_RESPONSE")"
ACTIVATION_BYTES="$(jq -r '.bytes // 0' "$ACTIVATION_REQUEST_RESPONSE")"

[ "$ACTIVATION_AUTHORIZED" = "true" ] || fail "Ο Broker δεν εξέδωσε Phase E authorization ticket."
[ -n "$ACTIVATION_TICKET" ] || fail "Λείπει το one-time Phase E activation ticket."
[ "$ACTIVATION_ARCH" = "$ARCHITECTURE" ] || fail "Το Phase E ticket δεν αντιστοιχεί στην αρχιτεκτονική του host."
[ "$ACTIVATION_SHA" = "$EXPECTED_AGENT_SHA" ] || fail "Το Phase E ticket δεν είναι δεμένο με το verified agent SHA-256."
[ "$ACTIVATION_BYTES" = "$EXPECTED_AGENT_BYTES" ] || fail "Το Phase E ticket δεν είναι δεμένο με το verified agent byte count."
[ -n "$ACTIVATION_CONSUME_ENDPOINT" ] || fail "Λείπει το Phase E activation consume endpoint."
case "$ACTIVATION_CONSUME_ENDPOINT" in
  https://*) ;;
  *) fail "Το Phase E consume endpoint δεν είναι HTTPS." ;;
esac
[ "$(url_origin "$ACTIVATION_CONSUME_ENDPOINT")" = "$BROKER_ORIGIN" ] || fail "Το Phase E consume endpoint δεν ανήκει στο ίδιο HTTPS origin με τον Broker."
jq -e '.execution == false and .remote_access == false and .mode == "activation_authorization_phase_e"' "$ACTIVATION_REQUEST_RESPONSE" >/dev/null 2>&1 || fail "Η Phase E authorization απάντηση δεν είναι execution-locked."
rm -f "$ACTIVATION_REQUEST_RESPONSE"

echo "ΕΠΙΤΥΧΙΑ: Εκδόθηκε one-time Phase E authorization ticket μετά από Admin arming και verified Phase D delivery."
[ -n "$ACTIVATION_EXPIRES" ] && echo "Λήξη activation ticket (UTC): ${ACTIVATION_EXPIRES}"
echo ""

echo "6/8 Κατανάλωση Phase E authorization ticket — χωρίς execution..."
ACTIVATION_CONSUME_PAYLOAD="$(jq -n \
  --arg ticket "$ACTIVATION_TICKET" \
  --arg client "home_assistant_os" \
  --arg client_version "$VERSION" \
  --arg architecture "$ARCHITECTURE" \
  '{ticket:$ticket, client:$client, client_version:$client_version, architecture:$architecture}')"

set +e
ACTIVATION_CONSUME_HTTP="$(curl \
  --silent \
  --show-error \
  --proto '=https' \
  --tlsv1.2 \
  --connect-timeout 10 \
  --max-time 20 \
  --output "$ACTIVATION_CONSUME_RESPONSE" \
  --write-out '%{http_code}' \
  --header 'Content-Type: application/json' \
  --header "User-Agent: SmartProRemoteSupportSession/${VERSION}" \
  --data "$ACTIVATION_CONSUME_PAYLOAD" \
  "$ACTIVATION_CONSUME_ENDPOINT")"
CURL_RC=$?
set -e

ACTIVATION_CONSUME_PAYLOAD=""

[ "$CURL_RC" -eq 0 ] || fail "Δεν ήταν δυνατή η κατανάλωση του Phase E authorization ticket."
jq empty "$ACTIVATION_CONSUME_RESPONSE" >/dev/null 2>&1 || fail "Ο Broker επέστρεψε μη αναμενόμενη Phase E consume απάντηση (HTTP ${ACTIVATION_CONSUME_HTTP})."
[ "$ACTIVATION_CONSUME_HTTP" = "200" ] || fail "Το Phase E authorization ticket δεν καταναλώθηκε (HTTP ${ACTIVATION_CONSUME_HTTP})."

jq -e '.authorized == true and .consumed == true and .execution == false and .remote_access == false and .mode == "activation_authorization_phase_e"' "$ACTIVATION_CONSUME_RESPONSE" >/dev/null 2>&1 || fail "Η τελική Phase E απάντηση δεν είναι authorization-only."
FINAL_ARCH="$(jq -r '.architecture // empty' "$ACTIVATION_CONSUME_RESPONSE")"
FINAL_SHA="$(jq -r '.sha256 // empty' "$ACTIVATION_CONSUME_RESPONSE")"
FINAL_BYTES="$(jq -r '.bytes // 0' "$ACTIVATION_CONSUME_RESPONSE")"
[ "$FINAL_ARCH" = "$ARCHITECTURE" ] || fail "Η τελική Phase E αρχιτεκτονική δεν συμφωνεί."
[ "$FINAL_SHA" = "$EXPECTED_AGENT_SHA" ] || fail "Το τελικό Phase E SHA-256 δεν συμφωνεί."
[ "$FINAL_BYTES" = "$EXPECTED_AGENT_BYTES" ] || fail "Το τελικό Phase E byte count δεν συμφωνεί."
EXECUTION_AVAILABLE="$(jq -r '.execution_authorization.available // false' "$ACTIVATION_CONSUME_RESPONSE")"
EXECUTION_REQUEST_ENDPOINT="$(jq -r '.execution_authorization.request_endpoint // empty' "$ACTIVATION_CONSUME_RESPONSE")"
EXECUTION_REQUIRES_ARM="$(jq -r '.execution_authorization.requires_admin_arm // false' "$ACTIVATION_CONSUME_RESPONSE")"
EXECUTION_MAX_RUNTIME_HINT="$(jq -r '.execution_authorization.max_runtime_seconds // 0' "$ACTIVATION_CONSUME_RESPONSE")"
[ "$EXECUTION_AVAILABLE" = "true" ] || fail "Ο Broker δεν επέστρεψε Phase F execution authorization metadata."
[ "$EXECUTION_REQUIRES_ARM" = "true" ] || fail "Ο Broker δεν απαιτεί ξεχωριστή Admin όπλιση για Phase F."
[ -n "$EXECUTION_REQUEST_ENDPOINT" ] || fail "Λείπει το Phase F execution request endpoint."
case "$EXECUTION_REQUEST_ENDPOINT" in https://*) ;; *) fail "Το Phase F execution request endpoint δεν είναι HTTPS." ;; esac
[ "$(url_origin "$EXECUTION_REQUEST_ENDPOINT")" = "$BROKER_ORIGIN" ] || fail "Το Phase F execution endpoint δεν ανήκει στο ίδιο HTTPS origin με τον Broker."
case "$EXECUTION_MAX_RUNTIME_HINT" in 60|1860|3660|5460) ;; *) fail "Το Phase F runtime policy δεν αντιστοιχεί σε εγκεκριμένη διάρκεια 60s QA ή 30/60/90 λεπτών + startup allowance." ;; esac
jq -e '.execution_authorization.temporary_connect == false and .execution_authorization.ephemeral_foreground == true and .execution_authorization.foreground_no_install == true and .execution_authorization.persistence == false and .execution_authorization.sandboxed_addon == true and .execution_authorization.mode == "controlled_execution_phase_f_ephemeral_foreground"' "$ACTIVATION_CONSUME_RESPONSE" >/dev/null 2>&1 || fail "Η Phase E απάντηση δεν διαφημίζει το hardened Phase F ephemeral-foreground contract."
rm -f "$ACTIVATION_CONSUME_RESPONSE"

echo "ΕΠΙΤΥΧΙΑ: Η one-time Phase E authorization chain ολοκληρώθηκε."
echo ""

echo "7/8 Αίτημα και κατανάλωση one-time Phase F execution ticket..."
EXECUTION_REQUEST_PAYLOAD="$(jq -n \
  --arg activation_ticket "$ACTIVATION_TICKET" \
  --arg client "home_assistant_os" \
  --arg client_version "$VERSION" \
  --arg architecture "$ARCHITECTURE" \
  '{activation_ticket:$activation_ticket, client:$client, client_version:$client_version, architecture:$architecture}')"
set +e
EXECUTION_REQUEST_HTTP="$(curl --silent --show-error --proto '=https' --tlsv1.2 --connect-timeout 10 --max-time 20 \
  --output "$EXECUTION_REQUEST_RESPONSE" --write-out '%{http_code}' --header 'Content-Type: application/json' \
  --header "User-Agent: SmartProRemoteSupportSession/${VERSION}" --data "$EXECUTION_REQUEST_PAYLOAD" "$EXECUTION_REQUEST_ENDPOINT")"
CURL_RC=$?
set -e
ACTIVATION_TICKET=""
EXECUTION_REQUEST_PAYLOAD=""
[ "$CURL_RC" -eq 0 ] || fail "Δεν ήταν δυνατή η αίτηση Phase F execution authorization."
jq empty "$EXECUTION_REQUEST_RESPONSE" >/dev/null 2>&1 || fail "Ο Broker επέστρεψε μη αναμενόμενη Phase F request απάντηση (HTTP ${EXECUTION_REQUEST_HTTP})."
if [ "$EXECUTION_REQUEST_HTTP" != "200" ]; then
  REASON="$(jq -r '.data.reason // .reason // "unknown"' "$EXECUTION_REQUEST_RESPONSE")"
  case "$REASON" in
    not_armed) fail "Η συγκεκριμένη συνεδρία δεν έχει οπλιστεί από Admin για Phase F." ;;
    activation_too_old) fail "Η Phase E authorization είναι πολύ παλιά για Phase F." ;;
    *) fail "Η Phase F execution authorization δεν εγκρίθηκε (HTTP ${EXECUTION_REQUEST_HTTP})." ;;
  esac
fi
EXECUTION_TICKET="$(jq -r '.ticket // empty' "$EXECUTION_REQUEST_RESPONSE")"
EXECUTION_REPORT_TOKEN="$(jq -r '.report_token // empty' "$EXECUTION_REQUEST_RESPONSE")"
EXECUTION_CONSUME_ENDPOINT="$(jq -r '.endpoint // empty' "$EXECUTION_REQUEST_RESPONSE")"
EXECUTION_WATCH_ENDPOINT="$(jq -r '.watch_endpoint // empty' "$EXECUTION_REQUEST_RESPONSE")"
EXECUTION_REPORT_ENDPOINT="$(jq -r '.report_endpoint // empty' "$EXECUTION_REQUEST_RESPONSE")"
EXECUTION_ARCH="$(jq -r '.architecture // empty' "$EXECUTION_REQUEST_RESPONSE")"
EXECUTION_SHA="$(jq -r '.sha256 // empty' "$EXECUTION_REQUEST_RESPONSE")"
EXECUTION_BYTES="$(jq -r '.bytes // 0' "$EXECUTION_REQUEST_RESPONSE")"
EXECUTION_MAX_RUNTIME="$(jq -r '.max_runtime_seconds // 0' "$EXECUTION_REQUEST_RESPONSE")"
[ -n "$EXECUTION_TICKET" ] && [ -n "$EXECUTION_REPORT_TOKEN" ] || fail "Λείπει Phase F execution/report token."
[ "$EXECUTION_ARCH" = "$ARCHITECTURE" ] || fail "Το Phase F ticket δεν αντιστοιχεί στην αρχιτεκτονική του host."
[ "$EXECUTION_SHA" = "$EXPECTED_AGENT_SHA" ] || fail "Το Phase F ticket δεν είναι δεμένο με το verified agent SHA-256."
[ "$EXECUTION_BYTES" = "$EXPECTED_AGENT_BYTES" ] || fail "Το Phase F ticket δεν είναι δεμένο με το verified byte count."
case "$EXECUTION_MAX_RUNTIME" in 60|1860|3660|5460) ;; *) fail "Το Phase F max runtime δεν αντιστοιχεί σε εγκεκριμένη διάρκεια 60s QA ή 30/60/90 λεπτών + startup allowance." ;; esac
for EP in "$EXECUTION_CONSUME_ENDPOINT" "$EXECUTION_WATCH_ENDPOINT" "$EXECUTION_REPORT_ENDPOINT"; do
  case "$EP" in https://*) ;; *) fail "Phase F endpoint δεν είναι HTTPS." ;; esac
  [ "$(url_origin "$EP")" = "$BROKER_ORIGIN" ] || fail "Phase F endpoint δεν ανήκει στο Broker origin."
done
jq -e '.execution == false and .temporary_connect == false and .ephemeral_foreground == true and .foreground_no_install == true and .persistence == false and .sandboxed_addon == true and .mode == "controlled_execution_phase_f_ephemeral_foreground"' "$EXECUTION_REQUEST_RESPONSE" >/dev/null 2>&1 || fail "Η Phase F request απάντηση δεν είναι στο hardened ephemeral-foreground contract."
rm -f "$EXECUTION_REQUEST_RESPONSE"

EXECUTION_CONSUME_PAYLOAD="$(jq -n --arg ticket "$EXECUTION_TICKET" --arg client "home_assistant_os" --arg client_version "$VERSION" --arg architecture "$ARCHITECTURE" '{ticket:$ticket, client:$client, client_version:$client_version, architecture:$architecture}')"
set +e
EXECUTION_CONSUME_HTTP="$(curl --silent --show-error --proto '=https' --tlsv1.2 --connect-timeout 10 --max-time 20 \
  --output "$EXECUTION_CONSUME_RESPONSE" --write-out '%{http_code}' --header 'Content-Type: application/json' \
  --header "User-Agent: SmartProRemoteSupportSession/${VERSION}" --data "$EXECUTION_CONSUME_PAYLOAD" "$EXECUTION_CONSUME_ENDPOINT")"
CURL_RC=$?
set -e
EXECUTION_TICKET=""
EXECUTION_CONSUME_PAYLOAD=""
[ "$CURL_RC" -eq 0 ] || fail "Δεν ήταν δυνατή η κατανάλωση του Phase F execution ticket."
jq empty "$EXECUTION_CONSUME_RESPONSE" >/dev/null 2>&1 || fail "Ο Broker επέστρεψε μη αναμενόμενη Phase F consume απάντηση (HTTP ${EXECUTION_CONSUME_HTTP})."
[ "$EXECUTION_CONSUME_HTTP" = "200" ] || fail "Το Phase F execution ticket δεν καταναλώθηκε (HTTP ${EXECUTION_CONSUME_HTTP})."
jq -e '.authorized == true and .consumed == true and .execution == true and .temporary_connect == false and .ephemeral_foreground == true and .foreground_no_install == true and .persistence == false and .sandboxed_addon == true and .mode == "controlled_execution_phase_f_ephemeral_foreground"' "$EXECUTION_CONSUME_RESPONSE" >/dev/null 2>&1 || fail "Η τελική Phase F απάντηση δεν επιτρέπει μόνο hardened ephemeral foreground execution."
FINAL_EXEC_ARCH="$(jq -r '.architecture // empty' "$EXECUTION_CONSUME_RESPONSE")"
FINAL_EXEC_SHA="$(jq -r '.sha256 // empty' "$EXECUTION_CONSUME_RESPONSE")"
FINAL_EXEC_BYTES="$(jq -r '.bytes // 0' "$EXECUTION_CONSUME_RESPONSE")"
FINAL_MAX_RUNTIME="$(jq -r '.max_runtime_seconds // 0' "$EXECUTION_CONSUME_RESPONSE")"
[ "$FINAL_EXEC_ARCH" = "$ARCHITECTURE" ] && [ "$FINAL_EXEC_SHA" = "$EXPECTED_AGENT_SHA" ] && [ "$FINAL_EXEC_BYTES" = "$EXPECTED_AGENT_BYTES" ] || fail "Η τελική Phase F binding δεν συμφωνεί με το verified binary."
[ "$FINAL_MAX_RUNTIME" = "$EXECUTION_MAX_RUNTIME" ] || fail "Το Phase F runtime policy άλλαξε μεταξύ request και consume."
rm -f "$EXECUTION_CONSUME_RESPONSE"
echo "ΕΠΙΤΥΧΙΑ: Phase F execution authorization καταναλώθηκε one-time. Επιτρέπεται μόνο ephemeral foreground MeshAgent χωρίς -install/service persistence για ${EXECUTION_MAX_RUNTIME}s."
echo ""

echo "8/8 Ελεγχόμενη ephemeral foreground εκτέλεση MeshAgent και υποχρεωτικός τερματισμός..."
[ -f "$RUNTIME_DIR/meshagent" ] && [ -f "$RUNTIME_DIR/meshagent.msh" ] || fail "Το canonical MeshAgent runtime layout δεν είναι πλήρες."
echo "ΕΠΙΤΥΧΙΑ: Canonical runtime layout έτοιμο: meshagent + meshagent.msh στον ίδιο ιδιωτικό προσωρινό φάκελο."
# Static ELF runtime-loader compatibility check before any executable permission.
ELF_INTERP="$(readelf -l "$AGENT_TMP" 2>/dev/null | sed -n 's/.*Requesting program interpreter: \([^]]*\)\].*/\1/p' | head -n 1)"
if [ -n "$ELF_INTERP" ]; then
  [ -x "$ELF_INTERP" ] || fail "Ο απαιτούμενος ELF runtime loader του verified MeshAgent δεν υπάρχει στο add-on runtime."
fi
echo "ΕΠΙΤΥΧΙΑ: Το add-on runtime είναι συμβατό με τον ELF loader του verified MeshAgent."
# Last-second integrity check immediately before changing executable permission.
PREEXEC_SHA="$(sha256sum "$AGENT_TMP" | awk '{print $1}')"
[ "$PREEXEC_SHA" = "$EXPECTED_AGENT_SHA" ] || fail "Το verified MeshAgent άλλαξε πριν την εκτέλεση."
chmod 700 "$AGENT_TMP" || fail "Δεν ήταν δυνατή η προσωρινή executable permission στο verified binary."

# Phase F local MSH hardening. Keep identity/connection fields intact while refusing
# self-update, remote core replacement and crash-dump persistence during this ephemeral QA run.
MSH_HARDENED="$RUNTIME_DIR/meshagent.msh.hardened"
awk -F= '
  $1 != "disableUpdate" &&
  $1 != "noUpdateCoreModule" &&
  $1 != "forceUpdate" &&
  $1 != "fakeUpdate" &&
  $1 != "coreDumpEnabled" { print }
' "$MSH_TMP" > "$MSH_HARDENED" || fail "Δεν ήταν δυνατή η δημιουργία hardened προσωρινού .msh."
printf 'disableUpdate=1\nnoUpdateCoreModule=1\n' >> "$MSH_HARDENED"
chmod 600 "$MSH_HARDENED" || fail "Δεν ήταν δυνατή η προστασία του hardened προσωρινού .msh."
mv -f "$MSH_HARDENED" "$MSH_TMP" || fail "Δεν ήταν δυνατή η ενεργοποίηση του hardened προσωρινού .msh."
for KEY in MeshName MeshType MeshID ServerID MeshServer; do
  grep -q "^${KEY}=" "$MSH_TMP" || fail "Το hardened προσωρινό .msh αλλοίωσε απαιτούμενο πεδίο (${KEY})."
done
grep -q '^disableUpdate=1$' "$MSH_TMP" || fail "Το hardened προσωρινό .msh δεν απενεργοποίησε self-update."
grep -q '^noUpdateCoreModule=1$' "$MSH_TMP" || fail "Το hardened προσωρινό .msh δεν κλείδωσε remote core replacement."
! grep -Eq '^(forceUpdate|fakeUpdate|coreDumpEnabled)=' "$MSH_TMP" || fail "Το hardened προσωρινό .msh περιέχει απαγορευμένο update/dump flag."
echo "ΕΠΙΤΥΧΙΑ: Εφαρμόστηκε local ephemeral policy: disableUpdate + noUpdateCoreModule, χωρίς αλλαγή Mesh identity/server fields."

command -v setsid >/dev/null 2>&1 || fail "Λείπει το isolated process-session helper από το add-on runtime."
echo "ΕΠΙΤΥΧΙΑ: Το verified MeshAgent θα ξεκινήσει ως foreground process χωρίς arguments και χωρίς -install."
HARD_KILL_GRACE=2
CURRENT_MAX_RUNTIME="$EXECUTION_MAX_RUNTIME"
case "$CURRENT_MAX_RUNTIME" in ''|*[!0-9]*) fail "Μη έγκυρο αρχικό runtime όριο." ;; esac
[ "$CURRENT_MAX_RUNTIME" -ge 60 ] && [ "$CURRENT_MAX_RUNTIME" -le "$ABSOLUTE_RUNTIME_CAP" ] || fail "Το αρχικό runtime όριο είναι εκτός ασφαλούς εύρους."
printf '%s\n' "$CURRENT_MAX_RUNTIME" > "$RUNTIME_MAX_FILE" || fail "Δεν ήταν δυνατή η ενεργοποίηση του δυναμικού runtime ορίου."
chmod 600 "$RUNTIME_MAX_FILE" 2>/dev/null || true
START_TS="$(date +%s)"
(
  cd "$RUNTIME_DIR"
  export HOME="$RUNTIME_DIR"
  export TMPDIR="$RUNTIME_DIR"
  export XDG_CONFIG_HOME="$RUNTIME_DIR"
  export XDG_CACHE_HOME="$RUNTIME_DIR"
  exec setsid ./meshagent >"$AGENT_LOG" 2>&1
) &
AGENT_PID=$!
printf '%s\n' "$AGENT_PID" > "$AGENT_PID_FILE"
(
  while kill -0 "$AGENT_PID" 2>/dev/null; do
    GUARD_MAX="$(cat "$RUNTIME_MAX_FILE" 2>/dev/null || printf '0')"
    case "$GUARD_MAX" in ''|*[!0-9]*) GUARD_MAX=0 ;; esac
    if [ "$GUARD_MAX" -lt 60 ] || [ "$GUARD_MAX" -gt "$ABSOLUTE_RUNTIME_CAP" ]; then
      printf '%s\n' "invalid-runtime-policy" > "$HARD_DEADLINE_MARKER"
      kill -TERM "$AGENT_PID" 2>/dev/null || true
      sleep "$HARD_KILL_GRACE"
      kill -KILL "$AGENT_PID" 2>/dev/null || true
      break
    fi
    GUARD_NOW="$(date +%s)"
    GUARD_ELAPSED=$((GUARD_NOW - START_TS))
    GUARD_SOFT_STOP=$((GUARD_MAX - HARD_KILL_GRACE))
    if [ "$GUARD_ELAPSED" -ge "$GUARD_SOFT_STOP" ]; then
      printf '%s\n' "$GUARD_MAX" > "$HARD_DEADLINE_MARKER"
      kill -TERM "$AGENT_PID" 2>/dev/null || true
      sleep "$HARD_KILL_GRACE"
      kill -KILL "$AGENT_PID" 2>/dev/null || true
      break
    fi
    sleep 1
  done
) &
DEADLINE_GUARD_PID=$!
sleep 3
STARTUP_EXIT_CODE=""
STARTUP_CATEGORY=""
if ! kill -0 "$AGENT_PID" 2>/dev/null; then
  if [ -n "${DEADLINE_GUARD_PID:-}" ] && kill -0 "$DEADLINE_GUARD_PID" 2>/dev/null; then
    kill -TERM "$DEADLINE_GUARD_PID" 2>/dev/null || true
    wait "$DEADLINE_GUARD_PID" 2>/dev/null || true
  fi
  DEADLINE_GUARD_PID=""
  set +e; wait "$AGENT_PID"; AGENT_RC=$?; set -e
  STARTUP_EXIT_CODE="$AGENT_RC"
  classify_startup_failure
  AGENT_PID=""
  RESULT_CODE="startup_failed"
else
  RESULT_CODE="completed"
  LAST_WATCH_OK_TS="$(date +%s)"
  WATCH_TRANSPORT_DEGRADED=0
  echo "ΕΠΙΤΥΧΙΑ: Το MeshAgent ξεκίνησε ως ephemeral foreground process μέσα στο απομονωμένο add-on runtime."
  echo "DYNAMIC HARD DEADLINE: αρχικό όριο ${CURRENT_MAX_RUNTIME}s. Εγκεκριμένη παράταση μπορεί να αυξήσει μόνο το server-authoritative όριο· local fail-safe cap ${ABSOLUTE_RUNTIME_CAP}s."
  echo "WATCH TRANSPORT POLICY: transient curl failures επιτρέπονται μόνο μέσα σε bounded ${WATCH_TRANSPORT_GRACE_SECONDS}s grace από το τελευταίο έγκυρο server watch. Το local deadline δεν αυξάνεται χωρίς HTTP 200 + έγκυρο JSON."
  echo "Watch/revoke παραμένουν fail-closed και μπορούν να τερματίσουν νωρίτερα."
  while kill -0 "$AGENT_PID" 2>/dev/null; do
    NOW_TS="$(date +%s)"
    ELAPSED=$((NOW_TS - START_TS))
    if [ "$ELAPSED" -ge "$CURRENT_MAX_RUNTIME" ]; then
      printf '%s\n' "$CURRENT_MAX_RUNTIME" > "$HARD_DEADLINE_MARKER"
      kill -KILL "$AGENT_PID" 2>/dev/null || true
      RESULT_CODE="completed"
      break
    fi
    WATCH_PAYLOAD="$(jq -n --arg report_token "$EXECUTION_REPORT_TOKEN" --arg client "home_assistant_os" --arg client_version "$VERSION" --arg architecture "$ARCHITECTURE" '{report_token:$report_token, client:$client, client_version:$client_version, architecture:$architecture}')"
    watch_request_once
    if [ "$WATCH_RC" -ne 0 ]; then
      WATCH_FAIL_TS="$(date +%s)"
      WATCH_SINCE_OK=$((WATCH_FAIL_TS - LAST_WATCH_OK_TS))
      rm -f "$EXECUTION_WATCH_RESPONSE"
      WATCH_PAYLOAD=""
      if [ "$WATCH_SINCE_OK" -lt "$WATCH_TRANSPORT_GRACE_SECONDS" ]; then
        WATCH_TRANSPORT_DEGRADED=1
        echo "WATCH TRANSPORT DEGRADED: curl rc=${WATCH_RC}; ${WATCH_SINCE_OK}s από το τελευταίο έγκυρο watch. Το server-authoritative runtime παραμένει ${CURRENT_MAX_RUNTIME}s· νέα προσπάθεια σε 2s."
        sleep 2
        continue
      fi
      echo "WATCH TRANSPORT FAIL-CLOSED: δεν υπήρξε έγκυρο server watch για ${WATCH_SINCE_OK}s (όριο ${WATCH_TRANSPORT_GRACE_SECONDS}s)."
      RESULT_CODE="watch_failed"
      break
    fi
    WATCH_PAYLOAD=""
    if [ "$WATCH_HTTP" != "200" ] || ! jq empty "$EXECUTION_WATCH_RESPONSE" >/dev/null 2>&1; then
      RESULT_CODE="watch_failed"
      rm -f "$EXECUTION_WATCH_RESPONSE"
      break
    fi
    LAST_WATCH_OK_TS="$(date +%s)"
    if [ "$WATCH_TRANSPORT_DEGRADED" -eq 1 ]; then
      echo "WATCH TRANSPORT RECOVERED: έγκυρο HTTP 200 + JSON αποκαταστάθηκε· συνεχίζεται η ίδια MeshAgent execution χωρίς reconnect."
      WATCH_TRANSPORT_DEGRADED=0
    fi
    CONTINUE_RUN="$(jq -r '.continue // false' "$EXECUTION_WATCH_RESPONSE")"
    WATCH_REASON="$(jq -r '.reason // empty' "$EXECUTION_WATCH_RESPONSE")"
    WATCH_MAX_RUNTIME="$(jq -r '.max_runtime_seconds // 0' "$EXECUTION_WATCH_RESPONSE")"
    rm -f "$EXECUTION_WATCH_RESPONSE"
    case "$WATCH_MAX_RUNTIME" in ''|*[!0-9]*) RESULT_CODE="watch_failed"; break ;; esac
    if [ "$WATCH_MAX_RUNTIME" -lt "$CURRENT_MAX_RUNTIME" ] || [ "$WATCH_MAX_RUNTIME" -gt "$ABSOLUTE_RUNTIME_CAP" ]; then
      RESULT_CODE="watch_failed"
      break
    fi
    if [ "$WATCH_MAX_RUNTIME" -gt "$CURRENT_MAX_RUNTIME" ]; then
      OLD_MAX_RUNTIME="$CURRENT_MAX_RUNTIME"
      CURRENT_MAX_RUNTIME="$WATCH_MAX_RUNTIME"
      RUNTIME_MAX_TMP="${RUNTIME_MAX_FILE}.tmp.$$"
      printf '%s\n' "$CURRENT_MAX_RUNTIME" > "$RUNTIME_MAX_TMP" || { RESULT_CODE="watch_failed"; break; }
      chmod 600 "$RUNTIME_MAX_TMP" 2>/dev/null || true
      mv -f "$RUNTIME_MAX_TMP" "$RUNTIME_MAX_FILE" || { RESULT_CODE="watch_failed"; break; }
      ADDED_SECONDS=$((CURRENT_MAX_RUNTIME - OLD_MAX_RUNTIME))
      echo "SESSION EXTENSION APPLIED: +${ADDED_SECONDS}s | νέο server-authoritative runtime=${CURRENT_MAX_RUNTIME}s | ίδια MeshAgent execution, χωρίς reconnect."
    fi
    if [ "$CONTINUE_RUN" != "true" ]; then
      if [ "$WATCH_REASON" = "admin_stop_requested" ]; then
        RESULT_CODE="terminated_by_admin"
      else
        RESULT_CODE="revoked"
      fi
      break
    fi
    REMAINING=$((CURRENT_MAX_RUNTIME - ELAPSED))
    if [ "$REMAINING" -gt 5 ]; then
      sleep 5
    elif [ "$REMAINING" -gt 0 ]; then
      sleep "$REMAINING"
    fi
  done
  if ! kill -0 "$AGENT_PID" 2>/dev/null && [ "$RESULT_CODE" = "completed" ] && [ ! -s "$HARD_DEADLINE_MARKER" ]; then
    RESULT_CODE="agent_exited"
  fi
fi

if [ -n "${DEADLINE_GUARD_PID:-}" ] && kill -0 "$DEADLINE_GUARD_PID" 2>/dev/null; then
  kill -TERM "$DEADLINE_GUARD_PID" 2>/dev/null || true
  wait "$DEADLINE_GUARD_PID" 2>/dev/null || true
fi
DEADLINE_GUARD_PID=""
if [ -n "${AGENT_PID:-}" ] && kill -0 "$AGENT_PID" 2>/dev/null; then
  kill -TERM "$AGENT_PID" 2>/dev/null || true
  sleep 1
  kill -KILL "$AGENT_PID" 2>/dev/null || true
fi
if [ -n "${AGENT_PID:-}" ]; then
  set +e; wait "$AGENT_PID"; AGENT_RC=$?; set -e
fi
AGENT_PID=""
END_TS="$(date +%s)"
WALL_SECONDS=$((END_TS - START_TS))
if [ -s "$HARD_DEADLINE_MARKER" ]; then
  RUNTIME_SECONDS="$EXECUTION_MAX_RUNTIME"
else
  RUNTIME_SECONDS="$WALL_SECONDS"
  if [ "$RUNTIME_SECONDS" -gt "$EXECUTION_MAX_RUNTIME" ]; then
    RUNTIME_SECONDS="$EXECUTION_MAX_RUNTIME"
  fi
fi
rm -rf "$RUNTIME_DIR"
[ ! -e "$RUNTIME_DIR" ] || fail "Δεν ολοκληρώθηκε το Phase F runtime cleanup."

REPORT_PAYLOAD="$(jq -n --arg report_token "$EXECUTION_REPORT_TOKEN" --arg client "home_assistant_os" --arg client_version "$VERSION" --arg architecture "$ARCHITECTURE" --arg result_code "$RESULT_CODE" --argjson runtime_seconds "$RUNTIME_SECONDS" '{report_token:$report_token, client:$client, client_version:$client_version, architecture:$architecture, result_code:$result_code, runtime_seconds:$runtime_seconds}')"
set +e
REPORT_HTTP="$(curl --silent --show-error --proto '=https' --tlsv1.2 --connect-timeout 5 --max-time 10 --output "$EXECUTION_REPORT_RESPONSE" --write-out '%{http_code}' --header 'Content-Type: application/json' --header "User-Agent: SmartProRemoteSupportSession/${VERSION}" --data "$REPORT_PAYLOAD" "$EXECUTION_REPORT_ENDPOINT")"
REPORT_RC=$?
set -e
EXECUTION_REPORT_TOKEN=""
REPORT_PAYLOAD=""
REPORT_OK=false
if [ "$REPORT_RC" -eq 0 ] && [ "$REPORT_HTTP" = "200" ] && jq -e --arg rc "$RESULT_CODE" '.reported == true and .result_code == $rc' "$EXECUTION_REPORT_RESPONSE" >/dev/null 2>&1; then
  REPORT_OK=true
fi
rm -f "$EXECUTION_REPORT_RESPONSE"

EXPECTED_AGENT_SHA=""
EXPECTED_AGENT_BYTES=""
if [ "$RESULT_CODE" != "completed" ] && [ "$RESULT_CODE" != "terminated_by_admin" ]; then
  if [ "$RESULT_CODE" = "startup_failed" ]; then
    echo "ΔΙΑΓΝΩΣΗ Phase F: startup_failed; exit_code=${STARTUP_EXIT_CODE:-unknown}; category=${STARTUP_CATEGORY:-unknown_startup_exit}."
    echo "Το raw MeshAgent output δεν εμφανίζεται για να μην εκτεθούν runtime στοιχεία ή secrets."
  fi
  fail "Η controlled Phase F execution τερματίστηκε fail-closed (${RESULT_CODE})."
fi
[ "$REPORT_OK" = "true" ] || fail "Το MeshAgent τερματίστηκε και καθαρίστηκε, αλλά απέτυχε το Phase F completion audit report."

if [ "$RESULT_CODE" = "terminated_by_admin" ]; then
  echo "ΕΠΙΤΥΧΙΑ: Ο τεχνικός ζήτησε πρόωρο τερματισμό. Το MeshAgent σταμάτησε με ασφάλεια μετά από ${RUNTIME_SECONDS}s και όλα τα runtime files διαγράφηκαν."
else
  echo "ΕΠΙΤΥΧΙΑ: Το ephemeral foreground MeshAgent τερματίστηκε με audited runtime ${RUNTIME_SECONDS}s (hard max ${EXECUTION_MAX_RUNTIME}s) και όλα τα runtime files διαγράφηκαν."
fi
if [ "$WALL_SECONDS" -gt "$EXECUTION_MAX_RUNTIME" ]; then
  echo "ΣΗΜΕΙΩΣΗ QA: συνολικό wall-clock μαζί με watchdog/cleanup/report preparation ήταν ${WALL_SECONDS}s· ο MeshAgent είχε ήδη τερματιστεί από το ανεξάρτητο hard deadline."
fi
echo "Δεν έγινε install/service persistence. Δεν έγινε δεύτερη εκτέλεση."
echo "MESHAGENT STARTED, WATCHED & TERMINATED — NO PERSISTENCE"
echo "CONTROLLED EXECUTION PHASE F: ΟΛΟΚΛΗΡΩΘΗΚΕ"
echo "===================================================="
exit 0
