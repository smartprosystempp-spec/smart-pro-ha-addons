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
