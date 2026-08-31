# Changelog

## 2.0.2 — Revocation & Safe Re-pair UX

- Requires Broker 0.15.1+ for explicit revoked-node heartbeat state.
- Distinguishes a real Broker revocation response from temporary HTTP/network failures such as the Plesk site lock.
- On explicit revocation, removes the local managed credential and moves the UI to a clear “Απαιτείται νέα σύνδεση” state.
- Allows a fresh one-time pairing without reinstalling the add-on or manually deleting `/data`.
- Generic invalid/inactive managed credentials also fail closed into a reauthorization-required state.
- Temporary HTML 401 / network failures preserve the existing identity and continue automatic heartbeat retries.
- Fixes the customer UI stage label to use the actual running version dynamically.
- Still does not download or execute MeshAgent and does not enable remote access.

## 2.0.1 — Safe HTTP Diagnostics Hotfix
- Built directly from 2.0.0 Managed Identity & Customer UI Foundation.
- Does not change pairing, heartbeat, credential storage, Broker endpoints or security boundaries.
- Adds safe HTTP diagnostics for Broker rejection: status code and Content-Type only.
- Does not log pairing codes, node secrets, request bodies or response bodies.
- Temporary Support 0.9.0 remains byte-for-byte unchanged.

## 2.0.0 — Managed Identity & Customer UI Foundation
- Replaces the legacy 1.0.1 runtime architecture with an identity-only managed foundation.
- Keeps the stable slug `smart_pro_agent`.
- Removes direct static MeshAgent/.msh download and permanent `/data/meshagent` execution path.
- Restricts supported architectures to `aarch64` and `amd64` for the controlled rollout.
- Changes `host_network` from `true` to `false`.
- Adds Home Assistant Ingress customer UI on internal port 8098.
- Adds one-time pairing against Smart Pro Remote Session Broker 0.15.0+.
- Stores only the resulting managed node credential locally with restrictive file permissions.
- Adds authenticated heartbeat.
- Does NOT enable MeshCentral enrollment, MeshAgent execution, remote access or technician presence.

## 1.0.1 — Legacy baseline
- Historical managed runtime. Preserved only as rollback/source reference and not used as the security model for 2.x.
