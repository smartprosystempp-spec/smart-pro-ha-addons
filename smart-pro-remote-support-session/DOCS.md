# Controlled live QA — Phase F 0.7.2

Η 0.7.2 είναι runtime compatibility + one-shot safety hotfix μετά το live `exit_code=127 / loader_or_runtime_missing`.

1. Keep `smart-pro-system.gr` locked while updating the add-on. Broker remains 0.9.0.
2. Confirm Home Assistant shows 0.7.2 and the add-on is stopped/manual-only.
3. Revoke any previously consumed/failed session and ensure the Home Assistant session code is empty.
4. Create a fresh 60-minute session, save the fresh code, arm Phase E and then Phase F.
5. Temporarily unlock `smart-pro-system.gr`.
6. Press Start exactly once. The persistent one-shot guard is written before the first Broker request; an automatic container retry with the same session code will exit before network/agent execution.
7. The verified binary must pass architecture/SHA/bytes plus the new static ELF runtime-loader compatibility check before `chmod 700`.
8. The only permitted execution remains `MeshAgent -connect`, sandboxed in the add-on container, for at most 60 seconds. Do not open remote desktop/terminal/files during this Phase F lifecycle QA.
9. Expected success checkpoint: `MESHAGENT STARTED, WATCHED & TERMINATED — NO PERSISTENCE`.
10. Whether success or fail-closed: re-lock the site, revoke the session, and clear the Home Assistant session code before any further step.

No `-install`, no service persistence, no host mounts, no privileged mode, no automatic second execution attempt.
