#!/bin/sh
set -eu

VERSION="0.9.6"
PORT="8099"

umask 077
ulimit -c 0 2>/dev/null || true

echo "===================================================="
echo "  Smart Pro Remote Support"
echo "===================================================="
echo "Κατάσταση: INGRESS ACTIVE-STATE RESTORATION HOTFIX ${VERSION}"
echo "Το Ingress UI ακούει μόνο μέσω Home Assistant στο εσωτερικό port ${PORT}."
echo "Ο προσωρινός code κρατιέται μόνο στη μνήμη και παραδίδεται στο Phase F core μέσω private stdin pipe."
echo "Δεν αποθηκεύεται session code στη νέα UI ροή και δεν καταγράφεται στα logs."
echo "Paid Guest 30/60/90 χρησιμοποιεί server-authoritative runtime με 60s startup allowance. Η 0.9.6 διατηρεί το ίδιο runtime contract και δέχεται μόνο εγκεκριμένες αυξήσεις χρόνου από το Broker/watchdog, χωρίς reconnect. Manual QA παραμένει hard-limited στα 60s."
echo "===================================================="

exec python3 /opt/smart-pro/ui_server.py
