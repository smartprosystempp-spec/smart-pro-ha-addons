#!/bin/sh

echo "=========================================="
echo "  Smart Pro System - Remote Support"
echo "=========================================="
echo "Γίνεται σύνδεση με τον κεντρικό server..."

wget "https://support.smart-pro-system.com/meshagents?script=1" -O ./meshinstall.sh && chmod 755 ./meshinstall.sh && ./meshinstall.sh https://support.smart-pro-system.com 'U6JxVGtHVArUuU1GiE8XO8byJMA4B3MoeKyv3gLi3q9zqWU$MTdaAHNJzONotTZr'

# Αυτή η εντολή κρατάει το πρόγραμμα ενεργό
tail -f /dev/null
