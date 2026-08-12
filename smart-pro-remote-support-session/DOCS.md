# Smart Pro Remote Support 0.8.0 — Customer Code Entry Foundation

## Test goal

Prove that a customer can enter a one-time support code in a proper Smart Pro Home Assistant UI instead of the technical app Configuration screen.

## Expected flow

1. Start the Smart Pro Remote Support app manually.
2. Open **Web UI**.
3. Enter a valid `SP-XXXX-XXXX` guest support code.
4. The page confirms that the code is valid.
5. Stop here. Version 0.8.0 does not request bootstrap material, does not execute MeshAgent and does not activate remote access.

## Security boundary

- Home Assistant Ingress only; no host port is published.
- Requests from sources other than the documented Ingress proxy are rejected.
- HTTPS-only Broker endpoint.
- Local code-format check before any Broker request.
- Per-process CSRF token for form submission.
- `Cache-Control: no-store` and restrictive response headers.
- Code is not persisted by the UI and is never written to application logs.

## Known-good execution core

`phase-f-0.7.7.sh` is the exact 0.7.7 script from the supplied live-tested package and is not executed in this version.
