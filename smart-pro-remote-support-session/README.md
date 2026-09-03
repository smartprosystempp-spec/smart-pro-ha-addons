# Smart Pro Remote Support — Customer Start & Controlled Execution Bridge 0.9.0

Version 0.9.0 connects the customer-facing Home Assistant Ingress UI to the previously live-verified controlled Phase F execution chain.

## Security model
- Code validation happens first without requesting bootstrap material.
- After validation the code is held only in short-lived process memory for up to 5 minutes.
- Remote execution requires a separate explicit customer action: **Έναρξη ασφαλούς σύνδεσης**.
- The code is passed to the Phase F shell through a private stdin pipe; it is not written to Home Assistant options, command-line arguments, temporary code files, or logs.
- Only one Phase F execution can be active inside the add-on at a time.
- Existing one-shot guard, Broker authorization chain, SHA/ELF checks, revoke/watch, server-authoritative hard deadline (manual QA 60s; paid Guest 30/60/90 + 60s startup allowance), no-install policy and cleanup remain in the execution core.
- Add-on shutdown terminates any active Phase F child process.
