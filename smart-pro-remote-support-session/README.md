# Smart Pro Remote Support - Προσωρινή Συνεδρία 0.7.1

## Phase F — Controlled MeshAgent Execution

Η 0.7.1 είναι το πρώτο build που επιτρέπεται να εκτελέσει MeshAgent, αλλά μόνο μετά από ολόκληρη την επαληθευμένη Phase D/E αλυσίδα και ξεχωριστή one-time Phase F Admin όπλιση.

Το MeshAgent εκτελείται μόνο με `-connect`, μέσα στο απομονωμένο Home Assistant add-on runtime, με `host_network: false`, χωρίς πρόσθετα host mounts/privileges και χωρίς install/service persistence. Το binary και το `.msh` υπάρχουν μόνο προσωρινά στο `/tmp`, το binary ξαναελέγχεται με SHA-256 αμέσως πριν το `chmod 700`, και υπάρχει hard runtime 60 δευτερολέπτων.

Κατά την εκτέλεση ο client κάνει watchdog polling στον Broker. Revoke, expiry, αλλαγή state ή watch failure οδηγεί σε fail-closed τερματισμό. Στο τέλος διαγράφονται binary, `.msh`, pid/log/db sidecars και αποστέλλεται τελικό audit report χωρίς secrets.

**Η Phase F δεν είναι ακόμη operator remote-support QA.** Το πρώτο live test ελέγχει μόνο lifecycle: start → temporary MeshCentral connect → watchdog → mandatory termination → cleanup.
