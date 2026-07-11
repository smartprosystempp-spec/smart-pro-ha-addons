#!/bin/sh

echo "=========================================="
echo "  Smart Pro System - Remote Support"
echo "=========================================="
echo "Γίνεται απευθείας λήψη και εκκίνηση του πράκτορα..."

# 1. Λήψη του εκτελέσιμου αρχείου
wget -q "https://support.smart-pro-system.com/meshagents?id=26" -O /meshagent

# 2. Λήψη του αρχείου ρυθμίσεων (προσοχή στα μονά εισαγωγικά, είναι κρίσιμα!)
wget -q 'https://support.smart-pro-system.com/meshsettings?id=U6JxVGtHVArUuU1GiE8XO8byJMA4B3MoeKyv3gLi3q9zqWU$MTdaAHNJzONotTZr' -O /meshagent.msh

# 3. Δίνουμε δικαιώματα εκτέλεσης
chmod +x /meshagent

# 4. Εκτέλεση του προγράμματος στο προσκήνιο
exec /meshagent
