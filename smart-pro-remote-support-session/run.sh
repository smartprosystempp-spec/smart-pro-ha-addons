#!/bin/sh
set -eu

VERSION="0.3.0"
CONFIG_PATH="/data/options.json"
VALIDATE_RESPONSE="/tmp/smart-pro-validation-response.json"
CONSUME_RESPONSE="/tmp/smart-pro-bootstrap-consume-response.json"

cleanup() {
  rm -f "$VALIDATE_RESPONSE" "$CONSUME_RESPONSE"
}
trap cleanup EXIT

echo "===================================================="
echo "  Smart Pro Remote Support - Προσωρινή Συνεδρία"
echo "===================================================="
echo "Κατάσταση: TEMPORARY BOOTSTRAP / PHASE A ${VERSION}"
echo ""

if [ ! -f "$CONFIG_PATH" ]; then
  echo "ΣΦΑΛΜΑ: Δεν βρέθηκε η διαμόρφωση της εφαρμογής."
  exit 1
fi

BROKER_URL="$(jq -r '.broker_url // empty' "$CONFIG_PATH")"
SESSION_CODE="$(jq -r '.session_code // empty' "$CONFIG_PATH")"

if [ -z "$BROKER_URL" ]; then
  echo "ΣΦΑΛΜΑ: Δεν έχει οριστεί endpoint επικύρωσης."
  exit 1
fi

case "$BROKER_URL" in
  https://*) ;;
  *)
    echo "ΣΦΑΛΜΑ: Επιτρέπεται μόνο HTTPS endpoint."
    exit 1
    ;;
esac

if [ -z "$SESSION_CODE" ]; then
  echo "ΣΦΑΛΜΑ: Δεν έχει συμπληρωθεί προσωρινός κωδικός συνεδρίας."
  exit 1
fi

SESSION_CODE="$(printf '%s' "$SESSION_CODE" | tr '[:lower:]' '[:upper:]' | tr -cd 'A-Z0-9-')"
if ! printf '%s' "$SESSION_CODE" | grep -Eq '^SP-[A-Z0-9]{4}-[A-Z0-9]{4}$'; then
  echo "ΣΦΑΛΜΑ: Ο κωδικός δεν έχει την αναμενόμενη μορφή SP-XXXX-XXXX."
  exit 1
fi

VALIDATE_PAYLOAD="$(jq -n \
  --arg code "$SESSION_CODE" \
  --arg client "home_assistant_os" \
  --arg client_version "$VERSION" \
  '{code:$code, client:$client, client_version:$client_version, request_bootstrap_ticket:true}')"

echo "1/2 Επικύρωση συνεδρίας και αίτημα one-time bootstrap ticket..."

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

if [ "$CURL_RC" -ne 0 ]; then
  echo "ΣΦΑΛΜΑ ΔΙΚΤΥΟΥ: Δεν ήταν δυνατή η επικοινωνία με τον Smart Pro Broker."
  echo "Ελέγξτε ότι υπάρχει σύνδεση Internet και ότι το Broker endpoint είναι προσβάσιμο."
  exit 1
fi

if ! jq empty "$VALIDATE_RESPONSE" >/dev/null 2>&1; then
  echo "ΣΦΑΛΜΑ: Ο Smart Pro Broker επέστρεψε μη αναμενόμενη απάντηση (HTTP ${VALIDATE_HTTP})."
  exit 1
fi

VALID="$(jq -r '.valid // false' "$VALIDATE_RESPONSE")"
if [ "$VALIDATE_HTTP" != "200" ] || [ "$VALID" != "true" ]; then
  REASON="$(jq -r '.data.reason // .reason // "unknown"' "$VALIDATE_RESPONSE")"
  MESSAGE="$(jq -r '.message // "Ο κωδικός δεν έγινε αποδεκτός."' "$VALIDATE_RESPONSE")"
  echo ""
  case "$REASON" in
    revoked) echo "ΑΠΟΤΥΧΙΑ: Ο προσωρινός κωδικός έχει ανακληθεί." ;;
    expired) echo "ΑΠΟΤΥΧΙΑ: Ο προσωρινός κωδικός έχει λήξει." ;;
    invalid) echo "ΑΠΟΤΥΧΙΑ: Ο προσωρινός κωδικός δεν είναι έγκυρος." ;;
    rate_limited) echo "ΑΠΟΤΥΧΙΑ: Έγιναν πολλές προσπάθειες. Δοκιμάστε ξανά αργότερα." ;;
    *) echo "ΑΠΟΤΥΧΙΑ: ${MESSAGE}" ;;
  esac
  echo "HTTP: ${VALIDATE_HTTP}"
  echo "Δεν ενεργοποιήθηκε καμία απομακρυσμένη πρόσβαση."
  exit 1
fi

BOOTSTRAP_AVAILABLE="$(jq -r '.bootstrap_available // false' "$VALIDATE_RESPONSE")"
BOOTSTRAP_TICKET="$(jq -r '.bootstrap_ticket // empty' "$VALIDATE_RESPONSE")"
BOOTSTRAP_ENDPOINT="$(jq -r '.bootstrap_endpoint // empty' "$VALIDATE_RESPONSE")"
BOOTSTRAP_EXPIRES="$(jq -r '.bootstrap_expires_at // empty' "$VALIDATE_RESPONSE")"

if [ "$BOOTSTRAP_AVAILABLE" != "true" ] || [ -z "$BOOTSTRAP_TICKET" ] || [ -z "$BOOTSTRAP_ENDPOINT" ]; then
  echo "ΣΦΑΛΜΑ: Ο Broker επικύρωσε τον κωδικό αλλά δεν επέστρεψε Phase A bootstrap ticket."
  echo "Επιβεβαιώστε ότι ο Smart Pro Remote Session Broker είναι έκδοση 0.3.0."
  exit 1
fi

case "$BOOTSTRAP_ENDPOINT" in
  https://*) ;;
  *)
    echo "ΣΦΑΛΜΑ: Το bootstrap endpoint που επέστρεψε ο Broker δεν είναι HTTPS."
    exit 1
    ;;
esac

# Το ticket δεν εμφανίζεται ποτέ στο log. Αφαιρούμε αμέσως το response file που το περιείχε.
rm -f "$VALIDATE_RESPONSE"

echo "ΕΠΙΤΥΧΙΑ: Ο session code είναι έγκυρος."
echo "Εκδόθηκε βραχύβιο one-time bootstrap ticket χωρίς να εμφανιστεί στο log."
[ -n "$BOOTSTRAP_EXPIRES" ] && echo "Λήξη bootstrap ticket (UTC): ${BOOTSTRAP_EXPIRES}"
echo ""
echo "2/2 Κατανάλωση one-time bootstrap ticket..."

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
  --max-time 20 \
  --output "$CONSUME_RESPONSE" \
  --write-out '%{http_code}' \
  --header 'Content-Type: application/json' \
  --header "User-Agent: SmartProRemoteSupportSession/${VERSION}" \
  --data "$CONSUME_PAYLOAD" \
  "$BOOTSTRAP_ENDPOINT")"
CURL_RC=$?
set -e

# Καθαρίζουμε τη μεταβλητή όσο πιο νωρίς γίνεται μετά την αποστολή.
BOOTSTRAP_TICKET=""
CONSUME_PAYLOAD=""

if [ "$CURL_RC" -ne 0 ]; then
  echo "ΣΦΑΛΜΑ ΔΙΚΤΥΟΥ: Δεν ήταν δυνατή η κατανάλωση του bootstrap ticket."
  exit 1
fi

if ! jq empty "$CONSUME_RESPONSE" >/dev/null 2>&1; then
  echo "ΣΦΑΛΜΑ: Ο Broker επέστρεψε μη αναμενόμενη bootstrap απάντηση (HTTP ${CONSUME_HTTP})."
  exit 1
fi

CONSUMED="$(jq -r '.consumed // false' "$CONSUME_RESPONSE")"
REMOTE_ACCESS="$(jq -r '.remote_access // false' "$CONSUME_RESPONSE")"

if [ "$CONSUME_HTTP" = "200" ] && [ "$CONSUMED" = "true" ] && [ "$REMOTE_ACCESS" = "false" ]; then
  echo ""
  echo "ΕΠΙΤΥΧΙΑ: Το one-time bootstrap ticket καταναλώθηκε μία φορά."
  echo "Η αλυσίδα session code → validation → bootstrap ticket → consume λειτουργεί σωστά."
  echo ""
  echo "ΣΗΜΑΝΤΙΚΟ: Η έκδοση ${VERSION} ΔΕΝ ενεργοποιεί ακόμη MeshCentral agent,"
  echo "enrollment, tunnel, Router ή άλλη απομακρυσμένη πρόσβαση."
  echo "TEMPORARY BOOTSTRAP PHASE A: ΟΛΟΚΛΗΡΩΘΗΚΕ"
  echo "===================================================="
  exit 0
fi

REASON="$(jq -r '.data.reason // .reason // "unknown"' "$CONSUME_RESPONSE")"
MESSAGE="$(jq -r '.message // "Το bootstrap ticket δεν έγινε αποδεκτό."' "$CONSUME_RESPONSE")"
echo ""
case "$REASON" in
  expired|session_expired) echo "ΑΠΟΤΥΧΙΑ: Το bootstrap ticket ή η συνεδρία έχει λήξει." ;;
  already_used|consumed|superseded) echo "ΑΠΟΤΥΧΙΑ: Το bootstrap ticket έχει ήδη χρησιμοποιηθεί ή αντικατασταθεί." ;;
  client_mismatch) echo "ΑΠΟΤΥΧΙΑ: Το bootstrap ticket δεν αντιστοιχεί σε αυτόν τον client." ;;
  rate_limited) echo "ΑΠΟΤΥΧΙΑ: Έγιναν πολλές bootstrap προσπάθειες. Δοκιμάστε ξανά αργότερα." ;;
  *) echo "ΑΠΟΤΥΧΙΑ: ${MESSAGE}" ;;
esac
echo "HTTP: ${CONSUME_HTTP}"
echo "Δεν ενεργοποιήθηκε καμία απομακρυσμένη πρόσβαση."
echo "===================================================="
exit 1
