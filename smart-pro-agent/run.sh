#!/bin/sh
set -eu

VERSION="${SMART_PRO_VERSION:-2.2.0}"
PORT="8098"

umask 077
ulimit -c 0 2>/dev/null || true

echo "===================================================="
echo "  Smart Pro System - Remote Support"
echo "===================================================="
echo "Κατάσταση: MANAGED SECURE SETTINGS DELIVERY FOUNDATION ${VERSION}"
echo "Το Ingress UI ακούει μόνο στο εσωτερικό port ${PORT}."
echo "Ενεργά: one-time pairing + authenticated heartbeat + ασφαλής προετοιμασία + one-time επαλήθευση managed .msh."
echo "Το managed .msh αποθηκεύεται μόνο προσωρινά για τοπική επαλήθευση και διαγράφεται αμέσως."
echo "Ανενεργά: MeshAgent delivery/execution, remote access, technician presence."
echo "Τα managed credentials δεν εμφανίζονται στα logs."
echo "===================================================="

exec python3 /opt/smart-pro/ui_server.py
