# 0.9.3 — Live Extension Consent Runtime

- Dynamic server-authoritative runtime ceiling can increase only after Broker-approved customer extension consent.
- Same foreground MeshAgent process continues; no reconnect/reinstall.
- Local deadline guard reads a protected runtime-max file and remains fail-closed with an 8-hour absolute safety cap.
- Manual QA stays 60s; initial paid 30/60/90 contract remains unchanged.

# 0.9.2 — Production Session Runtime Foundation

- Paid Guest 30/60/90 sessions now accept only the exact Broker runtime policies 1860/3660/5460 seconds (purchased time + fixed 60s startup allowance).
- Manual QA remains exactly 60 seconds.
- Admin stop requests are recognized via watchdog and complete with normal cleanup/report instead of a fail-closed error.
- Same foreground/no-arguments MeshAgent invocation, no install/service persistence, one-shot authorization, SHA/ELF validation and cleanup.

# 0.9.1 — Session Duration Contract Foundation

- Διαβάζει μόνο το non-secret `support_contract` από τον Broker validation response.
- Εμφανίζει 30/60/90 λεπτά μόνο όταν η διάρκεια προέρχεται από πραγματικό paid Guest Support Case.
- Οι χειροκίνητες QA συνεδρίες εμφανίζονται ξεκάθαρα ως QA χωρίς εμπορική διάρκεια.
- Δεν αλλάζει ακόμη ο Phase F runtime: παραμένει hard-limited στα 60s.
- Δεν αλλάζουν one-shot guard, E/F authorization, MeshAgent invocation, watcher/revoke, cleanup ή no-persistence πολιτική.

# Changelog

## 0.9.0
- Added explicit customer Start after code validation.
- Added short-lived in-memory code handoff and private stdin bridge to Phase F.
- Added single-active-execution guard and shutdown child termination.
- Added running/completed/fail-closed customer status pages.
- Preserved Phase F hard deadline, one-shot safety, no-install execution and cleanup.

## 0.8.0
- Added validation-only customer Ingress UI.
