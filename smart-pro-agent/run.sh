#!/bin/sh
set -eu

VERSION="${SMART_PRO_VERSION:-2.4.0}"
PORT="8098"

umask 077
ulimit -c 0 2>/dev/null || true

echo "===================================================="
echo "  Smart Pro System - Remote Support"
echo "===================================================="
echo "Κατάσταση: MANAGED CUSTOMER CONSENT FOUNDATION ${VERSION}"
echo "Το Ingress UI ακούει μόνο στο εσωτερικό port ${PORT}."
echo "Ενεργά: pairing + heartbeat + εμφάνιση εγκεκριμένης συνεδρίας + ρητή αποδοχή πελάτη."
echo "Το .msh και το πρόγραμμα σύνδεσης αποθηκεύονται μόνο προσωρινά για τοπική επαλήθευση και διαγράφονται αμέσως."
echo "Ανενεργά: MeshAgent execution/install, remote access, technician presence."
echo "Τα managed credentials δεν εμφανίζονται στα logs."
echo "===================================================="

exec python3 /opt/smart-pro/ui_server.py
