#!/bin/sh
set -eu

VERSION="0.2.0"
CONFIG_PATH="/data/options.json"
RESPONSE_FILE="/tmp/smart-pro-broker-response.json"

cleanup() {
  rm -f "$RESPONSE_FILE"
}
trap cleanup EXIT

echo "===================================================="
echo "  Smart Pro Remote Support - Προσωρινή Συνεδρία"
echo "===================================================="
echo "Κατάσταση: ΕΛΕΓΧΟΣ ΚΩΔΙΚΟΥ / VALIDATION BRIDGE ${VERSION}"
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
    echo "ΣΦΑΛΜΑ: Για την αποστολή προσωρινού κωδικού επιτρέπεται μόνο HTTPS endpoint."
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

PAYLOAD="$(jq -n \
  --arg code "$SESSION_CODE" \
  --arg client "home_assistant_os" \
  --arg client_version "$VERSION" \
  '{code:$code, client:$client, client_version:$client_version}')"

echo "Γίνεται ασφαλής επικύρωση του προσωρινού κωδικού..."

set +e
HTTP_CODE="$(curl \
  --silent \
  --show-error \
  --location \
  --proto '=https' \
  --tlsv1.2 \
  --connect-timeout 10 \
  --max-time 20 \
  --output "$RESPONSE_FILE" \
  --write-out '%{http_code}' \
  --header 'Content-Type: application/json' \
  --header "User-Agent: SmartProRemoteSupportSession/${VERSION}" \
  --data "$PAYLOAD" \
  "$BROKER_URL")"
CURL_RC=$?
set -e

if [ "$CURL_RC" -ne 0 ]; then
  echo "ΣΦΑΛΜΑ ΔΙΚΤΥΟΥ: Δεν ήταν δυνατή η επικοινωνία με τον Smart Pro Broker."
  echo "Ελέγξτε ότι υπάρχει σύνδεση Internet και δοκιμάστε ξανά."
  exit 1
fi

if ! jq empty "$RESPONSE_FILE" >/dev/null 2>&1; then
  echo "ΣΦΑΛΜΑ: Ο Smart Pro Broker επέστρεψε μη αναμενόμενη απάντηση (HTTP ${HTTP_CODE})."
  exit 1
fi

VALID="$(jq -r '.valid // false' "$RESPONSE_FILE")"
if [ "$HTTP_CODE" = "200" ] && [ "$VALID" = "true" ]; then
  EXPIRES="$(jq -r '.expires_at // ""' "$RESPONSE_FILE")"
  echo ""
  echo "ΕΠΙΤΥΧΙΑ: Ο προσωρινός κωδικός είναι έγκυρος."
  [ -n "$EXPIRES" ] && echo "Λήξη κωδικού (UTC): ${EXPIRES}"
  echo "Η επικοινωνία Home Assistant ↔ Smart Pro Broker λειτουργεί σωστά."
  echo ""
  echo "ΣΗΜΑΝΤΙΚΟ: Η έκδοση ${VERSION} ΔΕΝ ενεργοποιεί ακόμη MeshCentral agent,"
  echo "tunnel, Router ή άλλη απομακρυσμένη πρόσβαση."
  echo "===================================================="
  exit 0
fi

REASON="$(jq -r '.data.reason // .reason // "unknown"' "$RESPONSE_FILE")"
MESSAGE="$(jq -r '.message // "Ο κωδικός δεν έγινε αποδεκτός."' "$RESPONSE_FILE")"

echo ""
case "$REASON" in
  revoked)
    echo "ΑΠΟΤΥΧΙΑ: Ο προσωρινός κωδικός έχει ανακληθεί."
    ;;
  expired)
    echo "ΑΠΟΤΥΧΙΑ: Ο προσωρινός κωδικός έχει λήξει."
    ;;
  invalid)
    echo "ΑΠΟΤΥΧΙΑ: Ο προσωρινός κωδικός δεν είναι έγκυρος."
    ;;
  rate_limited)
    echo "ΑΠΟΤΥΧΙΑ: Έγιναν πολλές προσπάθειες. Δοκιμάστε ξανά αργότερα."
    ;;
  *)
    echo "ΑΠΟΤΥΧΙΑ: ${MESSAGE}"
    ;;
esac

echo "HTTP: ${HTTP_CODE}"
echo "Δεν ενεργοποιήθηκε καμία απομακρυσμένη πρόσβαση."
echo "===================================================="
exit 1
