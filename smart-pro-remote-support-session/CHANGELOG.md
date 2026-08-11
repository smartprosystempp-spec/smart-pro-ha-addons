# Changelog

## 0.5.0 — Secure Agent Delivery Phase D
- Απαιτεί Smart Pro Remote Session Broker 0.7.0+ με Vault `READY` και `AGENTS READY`.
- Διατηρεί το Secure Bootstrap Delivery της 0.4.0.
- Ανιχνεύει host architecture (`aarch64` / `amd64`) και τη δεσμεύει στο Phase D request.
- Λαμβάνει ξεχωριστό one-time Agent Delivery Ticket μετά το επιτυχές `.msh` delivery.
- Απαιτεί ρητό `execution=false` πριν από οποιαδήποτε λήψη binary.
- Κατεβάζει προσωρινά το εγκεκριμένο MeshAgent binary μόνο στο `/tmp`.
- Ελέγχει HTTPS same-origin endpoint, binary Content-Type, architecture/SHA/execution headers, ακριβές byte count, SHA-256, ELF64, little-endian και `e_machine`.
- Διαγράφει αμέσως το binary μετά την επαλήθευση.
- **Δεν υπάρχει chmod +x ή MeshAgent execution.**
- Καμία δημιουργία tunnel, Router ή remote access.
- Success checkpoint: `AGENT DELIVERED & VERIFIED — NOT EXECUTED`.

## 0.4.0 — Secure Bootstrap Delivery Phase B
- Απαιτεί Smart Pro Remote Session Broker 0.5.0+ με MeshCentral Vault `READY`.
- Διατηρεί validation + one-time ticket flow.
- Λαμβάνει μόνο το επαληθευμένο `.msh` μέσω του one-time ticket.
- Ελέγχει encoding, μέγεθος, SHA-256 και βασικά `.msh` πεδία.
- Δεν εμφανίζει `.msh`, MeshID, ServerID ή MeshServer values στο log.
- Το `.msh` γράφεται μόνο προσωρινά στο `/tmp` με `umask 077` και διαγράφεται αμέσως.
- Καμία λήψη/εκτέλεση agent, tunnel, Router ή remote access.
- Παραμένει `boot: manual_only`, `startup: once`, `host_network:false`.

## 0.3.0 — Temporary Bootstrap Phase A
- Διατηρεί το validation flow της 0.2.0.
- Ζητά one-time bootstrap ticket από Broker 0.3.0.
- Το ticket είναι βραχύβιο και δεν εμφανίζεται στα logs.
- Αυτόματη άμεση κατανάλωση του ticket σε ξεχωριστό endpoint.
- Καθαρό success checkpoint `TEMPORARY BOOTSTRAP PHASE A: ΟΛΟΚΛΗΡΩΘΗΚΕ`.
- Καμία λήψη agent, MeshCentral enrollment, tunnel ή remote access.
- Παραμένει `boot: manual_only`, `startup: once`, `host_network:false`.

## 0.2.0 — Validation Bridge
- Υποχρεωτικός προσωρινός κωδικός συνεδρίας.
- HTTPS-only επικοινωνία με Smart Pro Remote Session Broker.
- Ελληνικά status/error logs.
- Αναγνώριση active / invalid / expired / revoked / rate-limited.
- Καμία λήψη agent ή MeshCentral bootstrap.

## 0.1.0 — Foundation
- Πρώτη πειραματική βάση.
- `boot: manual_only`.
- Χωρίς remote-access runtime.
- Χωρίς agent download ή enrollment configuration.
