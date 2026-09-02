#!/bin/sh
set -eu

VERSION="${SMART_PRO_VERSION:-2.5.1}"
PORT="8098"

umask 077
ulimit -c 0 2>/dev/null || true

echo "===================================================="
echo "  Smart Pro System - Remote Support"
echo "===================================================="
echo "Κατάσταση: MANAGED CONTROLLED RUNTIME ${VERSION}"
echo "Το Ingress UI ακούει μόνο στο εσωτερικό port ${PORT}."
echo "Ενεργά: pairing + heartbeat + έγκριση συνεδρίας + ρητή αποδοχή πελάτη + ελεγχόμενη δοκιμαστική σύνδεση έως 60s."
echo "Το .msh και το πρόγραμμα σύνδεσης αποθηκεύονται μόνο σε προσωρινό φάκελο κατά τη δοκιμή και διαγράφονται αμέσως μετά."
echo "Απαγορεύονται: install/service persistence, μόνιμη πρόσβαση και εκτέλεση χωρίς πρόσφατη έγκριση Smart Pro + ενέργεια πελάτη."
echo "Τα managed credentials δεν εμφανίζονται στα logs."
echo "===================================================="

exec python3 /opt/smart-pro/ui_server.py
