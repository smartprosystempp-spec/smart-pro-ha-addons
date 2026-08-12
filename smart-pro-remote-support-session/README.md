# Smart Pro Remote Support — Customer Code Entry 0.8.0

Version 0.8.0 starts the customer-facing Home Assistant experience without changing the proven Phase F execution core.

## What this build does

- Adds a Home Assistant Ingress web interface for the temporary `SP-XXXX-XXXX` support code.
- Uses Home Assistant authentication/Ingress and exposes no host port.
- Accepts requests only from the Home Assistant Ingress proxy address.
- Performs local format validation before contacting the Broker.
- Validates the code over HTTPS without requesting a bootstrap ticket.
- Does not persist the code in the new UI flow and does not include it in logs.
- Does **not** start MeshAgent or remote access in 0.8.0.

## Phase F preservation

The exact live-verified 0.7.7 `run.sh` is preserved as `phase-f-0.7.7.sh` in this package. It is intentionally **not invoked** by 0.8.0. This gives us a clean customer-UI checkpoint before wiring the new UI to the proven execution chain.

The legacy `session_code` configuration field remains temporarily in the schema only to avoid upgrade warnings. The 0.8.0 runtime ignores it.
