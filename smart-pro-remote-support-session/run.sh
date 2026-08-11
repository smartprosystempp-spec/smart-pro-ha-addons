#!/bin/sh
set -eu

VERSION="0.4.0"
CONFIG_PATH="/data/options.json"
VALIDATE_RESPONSE="/tmp/smart-pro-validation-response.json"
CONSUME_RESPONSE="/tmp/smart-pro-bootstrap-consume-response.json"
MSH_TMP="/tmp/smart-pro-temporary-bootstrap.msh"

umask 077
ulimit -c 0 2>/dev/null || true

cleanup() {
  rm -f "$VALIDATE_RESPONSE" "$CONSUME_RESPONSE" "$MSH_TMP"
}
trap cleanup EXIT
trap 'exit 143' HUP TERM
trap 'exit 130' INT

fail() {
  echo "ΣΦΑΛΜΑ: $1"
  echo "Δεν ενεργοποιήθηκε καμία απομακρυσμένη πρόσβαση."
  exit 1
}

echo "===================================================="
echo "  Smart Pro Remote Support - Προσωρινή Συνεδρία"
echo "===================================================="
echo "Κατάσταση: SECURE BOOTSTRAP DELIVERY / PHASE B ${VERSION}"
echo ""

[ -f "$CONFIG_PATH" ] || fail "Δεν βρέθηκε η διαμόρφωση της εφαρμογής."

BROKER_URL="$(jq -r '.broker_url // empty' "$CONFIG_PATH")"
SESSION_CODE="$(jq -r '.session_code // empty' "$CONFIG_PATH")"

[ -n "$BROKER_URL" ] || fail "Δεν έχει οριστεί endpoint επικύρωσης."
case "$BROKER_URL" in
  https://*) ;;
  *) fail "Επιτρέπεται μόνο HTTPS endpoint." ;;
esac

[ -n "$SESSION_CODE" ] || fail "Δεν έχει συμπληρωθεί προσωρινός κωδικός συνεδρίας."
SESSION_CODE="$(printf '%s' "$SESSION_CODE" | tr '[:lower:]' '[:upper:]' | tr -cd 'A-Z0-9-')"
printf '%s' "$SESSION_CODE" | grep -Eq '^SP-[A-Z0-9]{4}-[A-Z0-9]{4}$' || fail "Ο κωδικός δεν έχει την αναμενόμενη μορφή SP-XXXX-XXXX."

VALIDATE_PAYLOAD="$(jq -n \
  --arg code "$SESSION_CODE" \
  --arg client "home_assistant_os" \
  --arg client_version "$VERSION" \
  '{code:$code, client:$client, client_version:$client_version, request_bootstrap_ticket:true}')"

# Δεν χρειαζόμαστε ξανά τον plaintext session code μετά τη δημιουργία του request body.
SESSION_CODE=""

echo "1/3 Επικύρωση συνεδρίας και αίτημα one-time bootstrap ticket..."
set +e
VALIDATE_HTTP="$(curl \
  --silent \
  --show-error \
  --location \
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

if [ "$CURL_RC" -ne 0 ]; then
  fail "Δεν ήταν δυνατή η επικοινωνία με τον Smart Pro Broker. Ελέγξτε Internet και προσβασιμότητα endpoint."
fi
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
[ "$MODE" = "bootstrap_phase_b_delivery" ] || fail "Ο Broker δεν είναι ακόμη σε Secure Bootstrap Delivery Phase B για αυτόν τον client."

rm -f "$VALIDATE_RESPONSE"
echo "ΕΠΙΤΥΧΙΑ: Ο session code είναι έγκυρος."
echo "Εκδόθηκε βραχύβιο one-time bootstrap ticket χωρίς να εμφανιστεί στο log."
[ -n "$BOOTSTRAP_EXPIRES" ] && echo "Λήξη bootstrap ticket (UTC): ${BOOTSTRAP_EXPIRES}"
echo ""

echo "2/3 Κατανάλωση ticket και ασφαλής προσωρινή λήψη επαληθευμένου .msh..."
CONSUME_PAYLOAD="$(jq -n \
  --arg ticket "$BOOTSTRAP_TICKET" \
  --arg client "home_assistant_os" \
  --arg client_version "$VERSION" \
  '{ticket:$ticket, client:$client, client_version:$client_version}')"

set +e
CONSUME_HTTP="$(curl \
  --silent \
  --show-error \
  --location \
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
    rate_limited) fail "Έγιναν πολλές bootstrap προσπάθειες. Δοκιμάστε ξανά αργότερα." ;;
    *) fail "${MESSAGE} (HTTP ${CONSUME_HTTP})" ;;
  esac
fi

[ "$REMOTE_ACCESS" = "false" ] || fail "Ο Broker επέστρεψε μη αναμενόμενη κατάσταση remote_access."
[ "$RESPONSE_MODE" = "bootstrap_phase_b_delivery" ] || fail "Η bootstrap απάντηση δεν είναι Phase B delivery."

ENCODING="$(jq -r '.meshcentral_bootstrap.encoding // empty' "$CONSUME_RESPONSE")"
MSH_B64="$(jq -r '.meshcentral_bootstrap.data // empty' "$CONSUME_RESPONSE")"
EXPECTED_SHA="$(jq -r '.meshcentral_bootstrap.sha256 // empty' "$CONSUME_RESPONSE")"
EXPECTED_BYTES="$(jq -r '.meshcentral_bootstrap.bytes // 0' "$CONSUME_RESPONSE")"

[ "$ENCODING" = "base64" ] || fail "Το MeshCentral bootstrap δεν έχει την αναμενόμενη κωδικοποίηση."
[ -n "$MSH_B64" ] || fail "Ο Broker δεν παρέδωσε προσωρινό MeshCentral bootstrap."
printf '%s' "$EXPECTED_SHA" | grep -Eq '^[a-f0-9]{64}$' || fail "Το bootstrap fingerprint δεν είναι έγκυρο."
printf '%s' "$EXPECTED_BYTES" | grep -Eq '^[0-9]+$' || fail "Το bootstrap size metadata δεν είναι έγκυρο."

printf '%s' "$MSH_B64" | base64 -d > "$MSH_TMP" 2>/dev/null || fail "Δεν ήταν δυνατή η αποκωδικοποίηση του προσωρινού MeshCentral bootstrap."
MSH_B64=""
rm -f "$CONSUME_RESPONSE"

ACTUAL_BYTES="$(wc -c < "$MSH_TMP" | tr -d ' ')"
[ "$ACTUAL_BYTES" -ge 20 ] && [ "$ACTUAL_BYTES" -le 262144 ] || fail "Το προσωρινό .msh έχει μη αναμενόμενο μέγεθος."
[ "$ACTUAL_BYTES" = "$EXPECTED_BYTES" ] || fail "Το μέγεθος του προσωρινού .msh δεν συμφωνεί με το Broker metadata."
ACTUAL_SHA="$(sha256sum "$MSH_TMP" | awk '{print $1}')"
[ "$ACTUAL_SHA" = "$EXPECTED_SHA" ] || fail "Το SHA-256 του προσωρινού .msh δεν συμφωνεί με το Broker fingerprint."

# Ελέγχουμε μόνο ότι υπάρχουν τα βασικά πεδία. Δεν εμφανίζουμε καμία τιμή στο log.
for KEY in MeshName MeshType MeshID ServerID MeshServer; do
  grep -q "^${KEY}=" "$MSH_TMP" || fail "Το προσωρινό .msh λείπει απαιτούμενο πεδίο (${KEY})."
done
grep -qi '^MeshServer=wss://' "$MSH_TMP" || fail "Το προσωρινό .msh δεν χρησιμοποιεί ασφαλές WSS MeshServer."

echo "ΕΠΙΤΥΧΙΑ: Το one-time ticket καταναλώθηκε μία φορά."
echo "Το επαληθευμένο .msh παραδόθηκε προσωρινά χωρίς να εμφανιστεί στο log."
echo ""
echo "3/3 Έλεγχος ακεραιότητας και ασφαλής διαγραφή προσωρινού .msh..."

rm -f "$MSH_TMP"
EXPECTED_SHA=""
ACTUAL_SHA=""

echo "ΕΠΙΤΥΧΙΑ: Fingerprint, μέγεθος και βασικά .msh πεδία επαληθεύτηκαν."
echo "Το προσωρινό .msh διαγράφηκε αμέσως μετά το QA."
echo ""
echo "ΣΗΜΑΝΤΙΚΟ: Η έκδοση ${VERSION} ΔΕΝ κατεβάζει ή εκτελεί MeshCentral agent,"
echo "δεν δημιουργεί tunnel / Router και δεν ενεργοποιεί remote access."
echo "SECURE BOOTSTRAP DELIVERY PHASE B: ΟΛΟΚΛΗΡΩΘΗΚΕ"
echo "===================================================="
exit 0
