# Smart Pro Remote Support 0.7.7 — Final Phase F Live QA

Requires Smart Pro Remote Session Broker 0.9.2 or later.

## What changed from successful 0.7.6
The working ephemeral foreground MeshAgent path is unchanged. 0.7.7 only hardens the runtime boundary after live 0.7.6 proved that the device appears in MeshCentral and disconnects after the controlled window.

The local hard-deadline guard is independent from Broker watch polling:
- graceful TERM at `max_runtime - 2s`;
- KILL fallback by `max_runtime`;
- audited runtime never reports a successful completion above the Broker maximum;
- Broker completion must return `result_code=completed`.

## Live checkpoint
Use a fresh session and fresh E/F arming. Start once only. Do not open MeshCentral Remote Desktop / Terminal / Files during Phase F. Export up to 5000 log lines after the add-on stops.

Expected final lines:

`MESHAGENT STARTED, WATCHED & TERMINATED — NO PERSISTENCE`

`CONTROLLED EXECUTION PHASE F: ΟΛΟΚΛΗΡΩΘΗΚΕ`

The runtime line must show audited runtime `<= 60s` (normally 60s for the deadline test).
