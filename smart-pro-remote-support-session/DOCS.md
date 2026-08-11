# Controlled live QA — Phase F 0.7.1

1. Keep the public Smart Pro site locked while installing Broker 0.9.0 and add-on 0.7.1.
2. Confirm Broker Vault READY + AGENTS READY and Home Assistant 0.7.1 stopped/manual-only.
3. Create a fresh 60-minute session code. Save it in Home Assistant.
4. Arm Phase E, then arm Phase F for exactly that session.
5. Temporarily unlock `smart-pro-system.gr`.
6. Press Start exactly once.
7. The add-on must complete Phase D + Phase E + Phase F authorization, verify the binary again, `chmod 700` only that verified temporary file, and launch `MeshAgent -connect` in the add-on container.
8. During the <=60 second window, only confirm that one temporary device appears online in the MeshCentral Temporary Sessions group. Do not open remote desktop/terminal/files.
9. The client must terminate the process automatically, delete all temporary runtime files, and report completion to the Broker.
10. Expected final log: `MESHAGENT STARTED, WATCHED & TERMINATED — NO PERSISTENCE`.
11. Re-lock the site, revoke the test session and clear the Home Assistant session code.

Fail closed on any error. Never press Start a second time until logs are reviewed.
