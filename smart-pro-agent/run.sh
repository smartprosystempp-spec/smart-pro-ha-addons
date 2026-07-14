#!/bin/sh

echo "=========================================="
echo "  Smart Pro System - Remote Support"
echo "=========================================="
echo "Προετοιμασία μόνιμου χώρου αποθήκευσης..."

# Μεταφερόμαστε στον μόνιμο φάκελο /data που δεν σβήνεται ποτέ στις επανεκκινήσεις
cd /data

echo "Γίνεται απευθείας λήψη και εκκίνηση του πράκτορα..."

# 1. Λήψη του εκτελέσιμου αρχείου στον φάκελο /data
wget -q "https://support.smart-pro-system.com/meshagents?id=26" -O /data/meshagent

# 2. Λήψη του αρχείου ρυθμίσεων στον φάκελο /data
wget -q 'https://support.smart-pro-system.com/meshsettings?id=U6JxVGtHVArUuU1GiE8XO8byJMA4B3MoeKyv3gLi3q9zqWU$MTdaAHNJzONotTZr' -O /data/meshagent.msh

# 3. Δίνουμε δικαιώματα εκτέλεσης
chmod +x /data/meshagent

# 4. Εκτέλεση του προγράμματος από τον μόνιμο φάκελο
exec /data/meshagent
