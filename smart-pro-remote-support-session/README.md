# Smart Pro Remote Support — Temporary Session 0.7.6

Phase F ephemeral-foreground compatibility update.

The add-on preserves the verified session → bootstrap → .msh → agent delivery → Phase E → Phase F chain.
After a Broker 0.9.1 one-time execution consume it runs the verified MeshAgent as an **ephemeral foreground process with no command-line install action**.

Security boundary:
- No `-install`, no service registration, no boot persistence.
- Private `/tmp` runtime directory only; `HOME`, `TMPDIR` and XDG cache/config paths are redirected there.
- Local `.msh` safety override forces `disableUpdate=1` and `noUpdateCoreModule=1`, and strips force/fake update and crash-dump flags.
- Last-second SHA-256 check before chmod 700.
- Hard Broker-controlled runtime (currently 60s), watchdog polling and fail-closed revoke/watch failure.
- Entire runtime directory is deleted after termination.
- Phase F does not authorize operator remote desktop, terminal or file access.

This release requires Smart Pro Remote Session Broker 0.9.1+ for Phase F.
