# Smart Pro System - Remote Support 2.0.0

Managed Identity & Customer UI Foundation για μόνιμες εγκαταστάσεις Smart Pro System.

Η 2.0.0 υλοποιεί μόνο:
- one-time pairing προς Smart Pro Remote Session Broker 0.15.0+,
- τοπική ασφαλή αποθήκευση managed node credential στο `/data`,
- authenticated heartbeat,
- Home Assistant Ingress customer UI.

Δεν υλοποιεί MeshCentral enrollment, MeshAgent download/execution, remote desktop, terminal, file access ή technician-presence detection.

Το slug παραμένει `smart_pro_agent`, ώστε να αποτελεί την ελεγχόμενη εξέλιξη της legacy 1.0.1.
