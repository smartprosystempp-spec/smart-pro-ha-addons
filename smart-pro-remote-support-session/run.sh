#!/bin/sh
set -eu

VERSION="0.9.0"
PORT="8099"

umask 077
ulimit -c 0 2>/dev/null || true

echo "===================================================="
echo "  Smart Pro Remote Support"
echo "===================================================="
echo "Κατάσταση: CUSTOMER START & CONTROLLED EXECUTION BRIDGE ${VERSION}"
echo "Το Ingress UI ακούει μόνο μέσω Home Assistant στο εσωτερικό port ${PORT}."
echo "Ο προσωρινός code κρατιέται μόνο στη μνήμη και παραδίδεται στο Phase F core μέσω private stdin pipe."
echo "Δεν αποθηκεύεται session code στη νέα UI ροή και δεν καταγράφεται στα logs."
echo "Η remote execution απαιτεί ξεχωριστό ρητό πάτημα του πελάτη και παραμένει one-shot/fail-closed/hard-limited."
echo "===================================================="

exec python3 /opt/smart-pro/ui_server.py
