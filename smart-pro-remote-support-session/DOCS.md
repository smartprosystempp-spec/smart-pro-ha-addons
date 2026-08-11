# Smart Pro Remote Support 0.7.6 — Phase F QA

## Required server
Smart Pro Remote Session Broker 0.9.1 or later.

## Execution model
0.7.6 intentionally changes only the final Phase F runtime mode. The previous `-connect` path exited cleanly before the watchdog window in live QA. The new contract is explicit: `ephemeral_foreground=true`, `foreground_no_install=true`, `persistence=false`.

The add-on starts `./meshagent` with no arguments from a private temporary directory. It never calls `-install`. The temporary `.msh` receives local safety overrides that disable binary self-update and remote core replacement.

## Live QA checkpoint
Use a fresh session code and fresh E/F arming. Start once only. Expected success:

`MESHAGENT STARTED, WATCHED & TERMINATED — NO PERSISTENCE`
`CONTROLLED EXECUTION PHASE F: ΟΛΟΚΛΗΡΩΘΗΚΕ`

Do not open remote desktop, terminal or files during this Phase F QA.
