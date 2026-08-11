# Smart Pro Remote Support - Προσωρινή Συνεδρία 0.5.0

Η 0.5.0 είναι το **Secure Agent Delivery Phase D** ανάμεσα στο Home Assistant OS και τον Smart Pro Remote Session Broker 0.7.0+.

> **Δεν είναι ακόμη λειτουργική έκδοση remote access. Το MeshAgent δεν εκτελείται.**

## Τι κάνει

- Επικυρώνει τον προσωρινό session code `SP-XXXX-XXXX` μέσω HTTPS.
- Διατηρεί το one-time bootstrap ticket και την ασφαλή παράδοση/επαλήθευση του READY `.msh`.
- Δηλώνει την πραγματική host αρχιτεκτονική ως `aarch64` ή `amd64`.
- Λαμβάνει ξεχωριστό, βραχύβιο, one-time **Agent Delivery Ticket** δεμένο με συνεδρία/client/version/IP/architecture/SHA/μέγεθος.
- Κατεβάζει το agent binary μόνο προσωρινά στο `/tmp`.
- Ελέγχει response headers, ακριβές μέγεθος, SHA-256, ELF64, little-endian και το σωστό `e_machine`.
- Διαγράφει αμέσως το binary μετά το QA.
- Τερματίζεται μετά τον έλεγχο (`startup: once`).
- Δεν ξεκινά αυτόματα στο boot (`boot: manual_only`).

## Security boundary της Phase D

- Δεν γίνεται `chmod +x` στο MeshAgent.
- Δεν εκτελείται MeshAgent.
- Δεν δημιουργείται tunnel / Router connection.
- Δεν δίνεται remote desktop ή άλλη απομακρυσμένη πρόσβαση.
- Δεν εμφανίζεται enrollment identifier, `.msh` content ή Agent Delivery Ticket στα logs.
- Ο client απαιτεί ρητό `execution=false` στο Agent Delivery metadata και `X-Smart-Pro-Agent-Execution: disabled` στο binary response.
