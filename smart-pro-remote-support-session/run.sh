#!/bin/sh
set -eu

VERSION="0.8.0"
PORT="8099"

umask 077
ulimit -c 0 2>/dev/null || true

echo "===================================================="
echo "  Smart Pro Remote Support"
echo "===================================================="
echo "Κατάσταση: CUSTOMER CODE ENTRY FOUNDATION ${VERSION}"
echo "Το Ingress UI ακούει μόνο μέσω Home Assistant στο εσωτερικό port ${PORT}."
echo "Η ${VERSION} κάνει μόνο validation προσωρινού κωδικού."
echo "Δεν εκτελεί MeshAgent και δεν ενεργοποιεί απομακρυσμένη πρόσβαση."
echo "===================================================="

exec python3 /opt/smart-pro/ui_server.py
