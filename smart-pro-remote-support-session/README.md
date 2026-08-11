# Smart Pro Remote Support - Προσωρινή Συνεδρία 0.6.0

Η 0.6.0 είναι το **Activation Authorization Readiness Phase E** ανάμεσα στο Home Assistant OS και τον Smart Pro Remote Session Broker 0.8.0+.

> **Δεν είναι ακόμη λειτουργική έκδοση remote access. Το MeshAgent δεν εκτελείται.**

## Τι κάνει
- Επικυρώνει προσωρινό session code `SP-XXXX-XXXX` μέσω HTTPS.
- Διατηρεί την ασφαλή one-time bootstrap / READY `.msh` αλυσίδα.
- Δηλώνει πραγματική host αρχιτεκτονική `aarch64` ή `amd64`.
- Λαμβάνει readiness-pinned Agent Delivery Ticket και επαληθεύει ακριβές μέγεθος, SHA-256 και ELF architecture.
- Διαγράφει αμέσως το agent binary.
- Μόνο μετά τη διαγραφή ζητά ξεχωριστό **Phase E Activation Authorization Ticket**.
- Το Phase E ticket εκδίδεται μόνο όταν ο Admin έχει οπλίσει ρητά τη συγκεκριμένη συνεδρία.
- Επιβεβαιώνει one-time consume και απαιτεί `execution=false` / `remote_access=false`.
- Τερματίζεται μετά τον έλεγχο (`startup: once`) και δεν ξεκινά στο boot (`boot: manual_only`).

## Security boundary
- Δεν γίνεται `chmod +x`.
- Δεν εκτελείται MeshAgent.
- Δεν γίνεται install/service persistence.
- Δεν δημιουργείται tunnel / Router connection.
- Δεν δίνεται remote desktop ή άλλη απομακρυσμένη πρόσβαση.
- Δεν εμφανίζονται enrollment identifier, `.msh` body, Agent Delivery Ticket ή Activation Ticket στα logs.

Success checkpoint:

`ACTIVATION AUTHORIZED — NOT EXECUTED`
