# Changelog

## 0.7.4 — Phase F Canonical Runtime Layout & Launch Telemetry Hotfix

- Αντιμετωπίζει το live 0.7.3 `startup_failed; exit_code=0; category=unknown_startup_exit`.
- Αφαιρεί την υπόθεση ότι renamed binary/`.msh` names είναι ισοδύναμα για manual connect.
- Χρησιμοποιεί ιδιωτικό `/tmp/smart-pro-phase-f-runtime/` με filenames ακριβώς `meshagent` και `meshagent.msh`.
- Εκτελεί από τον ίδιο working directory ακριβώς `./meshagent -connect`.
- Προσθέτει persistent launch counter στο `/data` και log marker `LAUNCH SAFETY` για κάθε πραγματικό add-on process launch.
- Διατηρεί το persistent one-shot guard που μπλοκάρει reuse του ίδιου session code πριν από οποιοδήποτε Broker request.
- Επεκτείνει μόνο την ασφαλή startup classification για help/config-not-loaded output χωρίς να εμφανίζει raw MeshAgent output.
- Διατηρεί Debian/glibc, strict header/SHA/bytes/ELF/loader checks, one-time Phase E/F tickets, chmod 700 μόνο στο verified binary, max 60s watchdog και mandatory cleanup.
- Δεν αλλάζει Broker 0.9.0, Vault/AGENTS READY, privileges, host networking ή persistence boundary.

## 0.7.3 — Phase F HTTP Header Parser Portability Hotfix

- Διορθώνει το live 0.7.2 fail-closed στο Step 4: `binary response architecture header` mismatch.
- Root cause: το Debian runtime χρησιμοποιεί `mawk`, όπου το `IGNORECASE=1` δεν είναι portable· HTTP/2 μπορεί να αποδώσει response header names σε lowercase.
- Αντικαθιστά το header parser με POSIX-compatible `tolower()` comparison, ώστε header names να αντιμετωπίζονται σωστά case-insensitively όπως απαιτεί το HTTP.
- Ελέγχει architecture / SHA-256 / execution headers με το ίδιο αυστηρό value matching.
- Διατηρεί αμετάβλητα Debian/glibc runtime, ELF loader preflight, persistent one-shot guard, ένα μόνο `MeshAgent -connect`, 60s watchdog και mandatory cleanup.
- Δεν αλλάζει Broker, tickets, Phase E/F arming, persistence boundary ή privileges.

## 0.7.2 — Phase F Runtime Compatibility & One-Shot Safety Hotfix

- Αντιμετωπίζει το live `startup_failed; exit_code=127; category=loader_or_runtime_missing`.
- Αλλάζει το add-on container από Alpine/musl σε Debian bookworm-slim (glibc-compatible) χωρίς host mounts, privileged mode ή host networking.
- Προσθέτει static `readelf` check του PT_INTERP/ELF runtime loader πριν από οποιοδήποτε `chmod`.
- Προσθέτει persistent one-shot guard στο `/data`: ο ίδιος session code δεν μπορεί να προκαλέσει δεύτερη Broker/Phase F execution προσπάθεια μετά από Supervisor/container restart.
- Οι χειρισμένες fail-closed καταλήξεις τερματίζουν καθαρά μετά το mandatory cleanup ώστε να αποφεύγεται restart loop.
- Παραμένει ακριβώς ένα `MeshAgent -connect`, έως 60s, χωρίς `-install`, service persistence ή automatic restart.

## 0.7.1 — Phase F Startup Diagnostics Hotfix

- Δεν αλλάζει το Phase F authorization/execution boundary.
- Δεν προσθέτει δεύτερη εκτέλεση, install, service persistence, host mounts ή privileged mode.
- Σε `startup_failed` καταγράφει μόνο ασφαλή διάγνωση: process exit code και κατηγορία αποτυχίας.
- Το raw MeshAgent runtime output δεν εμφανίζεται και εξακολουθεί να διαγράφεται στο cleanup.
- Οι κατηγορίες διάγνωσης καλύπτουν permission/noexec, loader/runtime library, TLS/certificate, connection και early-exit περιπτώσεις.
- Παραμένει fail-closed με mandatory cleanup και Phase F audit report.

# 0.7.0 — Controlled MeshAgent Execution Phase F

- First controlled MeshAgent execution build.
- Requires Broker 0.9.0+, consumed Phase E authorization and separate one-time Phase F Admin arming.
- Retains verified READY `.msh` and exact verified binary only in `/tmp` until execution authorization is consumed.
- Rechecks SHA-256 immediately before `chmod 700`.
- Executes only `MeshAgent -connect`; no `-install`, service or persistence.
- Hard max runtime 60 seconds.
- Watchdog polls Broker; revoke/expiry/watch failure terminates fail-closed.
- Mandatory PID/process cleanup and deletion of binary, `.msh`, log and db sidecars.
- Final execution report is sent to Broker without tickets/secrets in logs.


## 0.6.0 — Activation Authorization Readiness Phase E
- Keeps the full Phase D secure `.msh` and agent-binary verification chain.
- Requires Broker 0.8.0+.
- Requires explicit Admin arming of the exact temporary session.
- Requests a separate one-time activation authorization only after verified agent delivery.
- Verifies activation ticket binding to architecture, SHA-256, and exact byte count.
- Consumes the activation ticket once and requires `execution=false` and `remote_access=false`.
- Deletes the agent binary before requesting activation authorization.
- Does not chmod or execute MeshAgent.
- Does not create tunnel, Router, or remote access.
- Success checkpoint: `ACTIVATION AUTHORIZED — NOT EXECUTED`.


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
