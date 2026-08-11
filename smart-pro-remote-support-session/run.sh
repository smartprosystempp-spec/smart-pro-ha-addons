#!/bin/sh
set -eu

VERSION="0.6.0"
CONFIG_PATH="/data/options.json"
VALIDATE_RESPONSE="/tmp/smart-pro-validation-response.json"
CONSUME_RESPONSE="/tmp/smart-pro-bootstrap-consume-response.json"
MSH_TMP="/tmp/smart-pro-temporary-bootstrap.msh"
AGENT_TMP="/tmp/smart-pro-meshagent-delivery.bin"
AGENT_HEADERS="/tmp/smart-pro-meshagent-delivery.headers"
ACTIVATION_REQUEST_RESPONSE="/tmp/smart-pro-activation-request-response.json"
ACTIVATION_CONSUME_RESPONSE="/tmp/smart-pro-activation-consume-response.json"

umask 077
ulimit -c 0 2>/dev/null || true

cleanup() {
  rm -f "$VALIDATE_RESPONSE" "$CONSUME_RESPONSE" "$MSH_TMP" "$AGENT_TMP" "$AGENT_HEADERS" "$ACTIVATION_REQUEST_RESPONSE" "$ACTIVATION_CONSUME_RESPONSE"
}
trap cleanup EXIT
trap 'exit 143' HUP TERM
trap 'exit 130' INT

fail() {
  echo "ΣΦΑΛΜΑ: $1"
  echo "Δεν ενεργοποιήθηκε καμία απομακρυσμένη πρόσβαση."
  exit 1
}

url_origin() {
  printf '%s' "$1" | sed -E 's#^(https://[^/]+).*$#\1#'
}

case "$(uname -m 2>/dev/null || true)" in
  aarch64|arm64) ARCHITECTURE="aarch64"; EXPECTED_MACHINE_HEX="b700" ;;
  x86_64|amd64) ARCHITECTURE="amd64"; EXPECTED_MACHINE_HEX="3e00" ;;
  *) fail "Η αρχιτεκτονική αυτού του Home Assistant host δεν υποστηρίζεται για Phase E." ;;
esac

echo "===================================================="
echo "  Smart Pro Remote Support - Προσωρινή Συνεδρία"
echo "===================================================="
echo "Κατάσταση: ACTIVATION AUTHORIZATION READINESS / PHASE E ${VERSION}"
echo "Αρχιτεκτονική QA: ${ARCHITECTURE}"
echo ""

[ -f "$CONFIG_PATH" ] || fail "Δεν βρέθηκε η διαμόρφωση της εφαρμογής."

BROKER_URL="$(jq -r '.broker_url // empty' "$CONFIG_PATH")"
SESSION_CODE="$(jq -r '.session_code // empty' "$CONFIG_PATH")"

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

VALIDATE_PAYLOAD="$(jq -n \
  --arg code "$SESSION_CODE" \
  --arg client "home_assistant_os" \
  --arg client_version "$VERSION" \
  '{code:$code, client:$client, client_version:$client_version, request_bootstrap_ticket:true}')"
SESSION_CODE=""

echo "1/6 Επικύρωση συνεδρίας και αίτημα one-time bootstrap ticket..."
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

echo "2/6 Κατανάλωση bootstrap ticket και επαλήθευση READY .msh..."
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
rm -f "$MSH_TMP"
EXPECTED_MSH_SHA=""
ACTUAL_MSH_SHA=""

echo "ΕΠΙΤΥΧΙΑ: Το READY .msh επαληθεύτηκε και διαγράφηκε."
echo ""

echo "3/6 Έλεγχος ξεχωριστού one-time Agent Delivery Ticket..."
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

echo "4/6 Προσωρινή λήψη, ακεραιότητα ELF/SHA και άμεση διαγραφή agent..."
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
HEADER_ARCH="$(awk 'BEGIN{IGNORECASE=1} /^X-Smart-Pro-Agent-Architecture:/{gsub("\r",""); sub(/^[^:]*:[[:space:]]*/,""); print; exit}' "$AGENT_HEADERS")"
HEADER_SHA="$(awk 'BEGIN{IGNORECASE=1} /^X-Smart-Pro-Agent-SHA256:/{gsub("\r",""); sub(/^[^:]*:[[:space:]]*/,""); print; exit}' "$AGENT_HEADERS")"
HEADER_EXEC="$(awk 'BEGIN{IGNORECASE=1} /^X-Smart-Pro-Agent-Execution:/{gsub("\r",""); sub(/^[^:]*:[[:space:]]*/,""); print; exit}' "$AGENT_HEADERS")"
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

# Phase D security boundary: ποτέ chmod +x, ποτέ exec. Το binary υπάρχει μόνο για verification.
rm -f "$AGENT_TMP" "$AGENT_HEADERS"
ACTUAL_AGENT_SHA=""

[ ! -e "$AGENT_TMP" ] || fail "Το προσωρινό agent binary δεν διαγράφηκε."
echo "ΕΠΙΤΥΧΙΑ: Agent binary ${ARCHITECTURE}, μέγεθος, SHA-256 και ELF architecture επαληθεύτηκαν."
echo "Το binary διαγράφηκε αμέσως. Δεν έγινε chmod και δεν εκτελέστηκε."
echo ""

echo "5/6 Αίτημα one-time Phase E Activation Authorization Ticket..."
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

echo "6/6 Κατανάλωση Phase E authorization ticket — χωρίς execution..."
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

ACTIVATION_TICKET=""
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
rm -f "$ACTIVATION_CONSUME_RESPONSE"

EXPECTED_AGENT_SHA=""
EXPECTED_AGENT_BYTES=""

echo "ΕΠΙΤΥΧΙΑ: Η one-time Phase E authorization chain ολοκληρώθηκε."
echo "ΣΗΜΑΝΤΙΚΟ: Η έκδοση ${VERSION} ΔΕΝ κάνει chmod και ΔΕΝ εκτελεί MeshCentral agent,"
echo "δεν δημιουργεί tunnel / Router και δεν ενεργοποιεί remote access."
echo "ACTIVATION AUTHORIZED — NOT EXECUTED"
echo "ACTIVATION AUTHORIZATION PHASE E: ΟΛΟΚΛΗΡΩΘΗΚΕ"
echo "===================================================="
exit 0
