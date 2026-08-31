#!/bin/sh
set -eu

VERSION="${SMART_PRO_VERSION:-2.1.0}"
PORT="8098"

umask 077
ulimit -c 0 2>/dev/null || true

echo "===================================================="
echo "  Smart Pro System - Remote Support"
echo "===================================================="
echo "Κατάσταση: MANAGED BOOTSTRAP AUTHORIZATION FOUNDATION ${VERSION}"
echo "Το Ingress UI ακούει μόνο στο εσωτερικό port ${PORT}."
echo "Ενεργά: one-time pairing + authenticated heartbeat + bootstrap authorization check."
echo "Ανενεργά: .msh delivery, MeshAgent delivery/execution, remote access, technician presence."
echo "Τα managed credentials δεν εμφανίζονται στα logs."
echo "===================================================="

exec python3 /opt/smart-pro/ui_server.py
