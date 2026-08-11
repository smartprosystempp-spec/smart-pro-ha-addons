# Οδηγίες — Προσωρινή Συνεδρία 0.6.0

## Σκοπός αυτής της έκδοσης
Η 0.6.0 υλοποιεί το **Activation Authorization Readiness Phase E** χωρίς MeshAgent execution:

`session code → validation → bootstrap ticket → READY .msh verify/delete → one-time Agent Delivery Ticket → binary verify/delete → Admin-armed activation authorization ticket → one-time consume → execution=false`

## Προϋποθέσεις
- Smart Pro Remote Session Broker 0.8.0+.
- MeshCentral Temporary Bootstrap Vault: `READY`.
- Agent Binary Readiness: `AGENTS READY` για ARM64 και AMD64.
- Νέα προσωρινή συνεδρία με Phase E κατάσταση `Κλειδωμένο` πριν από την όπλιση.
- Public site κλειδωμένο κατά την εγκατάσταση/checkpoint και προσωρινά ανοικτό μόνο για το ελεγχόμενο live run.

## Controlled QA 0.6.0
1. Ενημερώστε τον Broker σε 0.8.0 με το public site κλειδωμένο.
2. Επιβεβαιώστε ότι Vault `READY`, Agents `AGENTS READY` και το ιστορικό συνεδριών παραμένουν.
3. Ενημερώστε το Home Assistant add-on σε 0.6.0 και επιβεβαιώστε `boot: manual_only`, `startup: once`, stopped.
4. Δημιουργήστε νέο test session code και αποθηκεύστε τον στο add-on.
5. Στον Broker πατήστε **Όπλιση Phase E** μόνο για αυτή τη νέα συνεδρία.
6. Ανοίξτε προσωρινά το public site και εκτελέστε το add-on μία φορά.
7. Το επιτυχές log πρέπει να καταλήγει σε:
   - `ACTIVATION AUTHORIZED — NOT EXECUTED`
   - `ACTIVATION AUTHORIZATION PHASE E: ΟΛΟΚΛΗΡΩΘΗΚΕ`
8. Μετά το QA: ξανακλείδωμα site, ανάκληση test session, καθαρισμός session code.

## Security boundary
- Το binary διαγράφεται **πριν** ζητηθεί Phase E activation authorization.
- Δεν γίνεται `chmod +x`.
- Δεν εκτελείται MeshAgent.
- Δεν δημιουργείται tunnel / Router ή remote access.
- Το activation authorization απαιτεί ρητή Admin όπλιση.
- Τα authorization responses πρέπει να δηλώνουν `execution=false` και `remote_access=false`.
