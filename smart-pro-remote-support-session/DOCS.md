# Οδηγίες — Προσωρινή Συνεδρία 0.5.0

## Σκοπός αυτής της έκδοσης
Η 0.5.0 ολοκληρώνει το **Secure Agent Delivery Phase D** χωρίς activation:

`session code → validation → bootstrap ticket → READY .msh verify/delete → one-time Agent Delivery Ticket → architecture-bound binary delivery → SHA/ELF verify → secure deletion → audit`

## Προϋποθέσεις
- Smart Pro Remote Session Broker 0.7.0+.
- MeshCentral Temporary Bootstrap Vault: `READY`.
- Agent Binary Readiness: `AGENTS READY` για ARM64 και AMD64.
- Public site παραμένει κλειδωμένο κατά το controlled QA, εκτός αν απαιτηθεί ρητά διαφορετικό checkpoint.

## Controlled QA 0.5.0
1. Εγκαταστήστε/ενημερώστε μόνο την εφαρμογή 0.5.0. **Μην την ξεκινήσετε ακόμη.**
2. Επιβεβαιώστε ότι εμφανίζεται έκδοση 0.5.0 και ότι παραμένει `boot: manual_only` / `startup: once`.
3. Σταματήστε για checkpoint πριν δημιουργηθεί νέος session code.
4. Μόνο στο επόμενο checkpoint δημιουργείται νέος test session code και εκτελείται η εφαρμογή μία φορά.
5. Το επιτυχές log πρέπει να καταλήγει σε:
   - `AGENT DELIVERED & VERIFIED — NOT EXECUTED`
   - `SECURE AGENT DELIVERY PHASE D: ΟΛΟΚΛΗΡΩΘΗΚΕ`
6. Δεν πρέπει να εμφανιστεί καμία ένδειξη chmod, execution, tunnel, Router ή remote access.

## Σημαντικό
Η 0.5.0 **κατεβάζει μόνο προσωρινά για verification** το εγκεκριμένο MeshAgent binary. Το binary διαγράφεται και δεν εκτελείται. Η ενεργοποίηση agent ανήκει σε ξεχωριστή επόμενη φάση και δεν πρέπει να γίνει στο Phase D checkpoint.
