# 0.9.5 — Watch Transport Grace Hotfix

- Live 0.9.4 finding: a production watch curl timeout still ended a paid session with `watch_failed` after several minutes.
- Replaces the single immediate retry model with a bounded 30-second transport grace measured from the last valid HTTP 200 + JSON watch response.
- During transport degradation the current server-authoritative runtime is frozen; the client never infers or grants an extension locally.
- Watch retries occur after 2 seconds while still inside the bounded grace.
- If no valid server watch is restored within the grace, execution remains fail-closed with `watch_failed`.
- HTTP non-200, malformed JSON, runtime decrease, invalid runtime and absolute-cap violation remain immediately fail-closed and do not receive transport grace.
- Adds explicit DEGRADED / RECOVERED / FAIL-CLOSED log markers for live diagnosis.
- Broker 0.25.0, consent/extension DB contract, one-shot guard, single foreground MeshAgent execution, no-install policy, dynamic deadline and cleanup remain unchanged.

# 0.9.4 — Watch Transport Retry Hotfix

- Built directly from Temporary 0.9.3 Live Extension Consent Runtime.
- A single curl transport failure/timeout on the execution watch no longer immediately ends the session with `watch_failed`.
- Exactly one bounded retry is allowed after 2 seconds, using the same 5s connect / 10s total curl limits.
- Only transport-level curl failure is retryable. HTTP rejection, malformed JSON, runtime decrease, invalid runtime or 8-hour cap violation remain immediately fail-closed.
- The independent local hard-deadline guard remains authoritative during the retry; no extension is inferred locally and no runtime is added without a valid server response.
- Same MeshAgent process, no reconnect, no second execution, no `-install`, and normal cleanup/report behavior remain unchanged.

# 0.9.4 — Live Extension Consent Runtime

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
