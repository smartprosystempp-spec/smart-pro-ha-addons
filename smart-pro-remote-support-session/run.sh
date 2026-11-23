#!/bin/sh
set -eu

VERSION="0.9.9"
PORT="8099"

umask 077
ulimit -c 0 2>/dev/null || true

echo "===================================================="
echo "  Smart Pro Remote Support"
echo "===================================================="
echo "Κατάσταση: TEMPORARY CUSTOMER SUPPORT ${VERSION}"
echo "Το Ingress UI ακούει μόνο μέσω Home Assistant στο εσωτερικό port ${PORT}."
echo "Ο προσωρινός κωδικός κρατιέται μόνο στη μνήμη και παραδίδεται στο Phase F core μέσω private stdin pipe."
echo "Δεν αποθηκεύεται session code στη customer UI ροή και δεν καταγράφεται στα logs."
echo "Paid Guest 30/60/90 διατηρεί server-authoritative runtime με 60s startup allowance και μόνο εγκεκριμένες αυξήσεις χρόνου, χωρίς reconnect."
echo "Χωρίς MeshAgent -install, service persistence ή αυτόματη δεύτερη execution προσπάθεια."
echo "===================================================="

exec python3 /opt/smart-pro/ui_server.py
