# Controlled live QA — Phase F 0.7.3

Η 0.7.3 είναι HTTP response-header parser portability hotfix πάνω στην 0.7.2. Το live 0.7.2 σταμάτησε fail-closed πριν από `chmod`/execution επειδή το `X-Smart-Pro-Agent-Architecture` δεν αναγνώστηκε σωστά στο Debian/HTTP2 path.

1. Keep `smart-pro-system.gr` locked while updating. Broker remains 0.9.0.
2. Revoke the failed 0.7.2 session and clear the Home Assistant session code.
3. Update the add-on to 0.7.3 and confirm Stopped/manual-only.
4. Create a fresh 60-minute session, save the code, arm Phase E and then Phase F.
5. Temporarily unlock `smart-pro-system.gr`.
6. Press Start exactly once. The persistent one-shot guard remains active before the first Broker request.
7. Agent response headers must be parsed case-insensitively and still match exact architecture/SHA/execution values.
8. The verified ELF must pass the glibc loader preflight before `chmod 700`.
9. Only `MeshAgent -connect` is allowed, sandboxed in the add-on container, max 60 seconds; no operator desktop/terminal/files in this lifecycle QA.
10. Expected success checkpoint: `MESHAGENT STARTED, WATCHED & TERMINATED — NO PERSISTENCE`.
11. Whether success or fail-closed: re-lock the site, revoke the session, and clear the Home Assistant session code.

No `-install`, no service persistence, no host mounts, no privileged mode, no automatic second execution attempt.
