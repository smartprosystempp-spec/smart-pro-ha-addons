# Smart Pro Remote Support — Temporary Session 0.7.7

Phase F hard-runtime completion build. Requires Smart Pro Remote Session Broker 0.9.2+.

The verified MeshAgent is executed only as an **ephemeral foreground process without arguments and without `-install`** inside the isolated Home Assistant add-on runtime. The canonical temporary `meshagent + meshagent.msh` layout and the 0.7.6 connectivity path are unchanged.

0.7.7 adds an independent local runtime deadline: graceful TERM begins two seconds before the Broker limit and KILL is the final fallback at the configured max runtime. This deadline is independent of watch HTTP polling, so network/report cleanup cannot extend MeshAgent execution.

Security boundary remains:
- one-time Phase E + Phase F authorization;
- last-second SHA-256 + ELF/loader verification;
- `disableUpdate=1` and `noUpdateCoreModule=1`;
- no `-install`, no service creation, no persistence;
- no host networking/privileged mounts;
- mandatory runtime-file cleanup;
- one-shot session guard and launch counter.
