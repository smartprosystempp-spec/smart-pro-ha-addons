# Smart Pro Managed Support 2.1.0 — QA Notes

## Preconditions

- Broker 0.17.0 installed.
- Managed node remains ACTIVE and paired.
- Managed enrollment source is READY.
- Site/API reachable during QA.

## Controlled test

1. Update 2.0.2 -> 2.1.0 without deleting the add-on or `/data`.
2. Confirm the same installation remains paired and heartbeat resumes.
3. Open Ingress.
4. Press **Έλεγχος ασφαλούς προετοιμασίας** once.
5. Expected UI: authorization confirmed, with explicit notice that no `.msh` was downloaded and no remote access was enabled.
6. Refresh WordPress -> Managed Support.
7. Expected: one new Managed Bootstrap Authorization row with status `CONSUMED`, matching ACTIVE node/installation/architecture.

## Stop checkpoint

After the ticket is `CONSUMED`, stop for the day. Leave the managed node ACTIVE. Do not enable `.msh` delivery, MeshAgent delivery/execution or any remote runtime.
