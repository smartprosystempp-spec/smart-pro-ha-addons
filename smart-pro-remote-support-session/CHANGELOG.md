# Changelog

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
