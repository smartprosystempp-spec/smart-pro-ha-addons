# Managed Support 2.0.2

Η 2.0.2 ολοκληρώνει το identity/revocation UX foundation: όταν ο Broker 0.15.1+ επιβεβαιώσει ότι το paired node έχει ανακληθεί, το add-on διαγράφει το τοπικό managed credential και ζητά νέο one-time pairing. Προσωρινά HTTP/network failures δεν διαγράφουν την identity. MeshAgent, MeshCentral enrollment και remote access παραμένουν ανενεργά.

# Smart Pro Managed Remote Support — 2.0.0 Foundation

## Σκοπός
Η εφαρμογή παραμένει εγκατεστημένη σε διαχειριζόμενη εγκατάσταση, αλλά η έκδοση 2.0.0 δεν παρέχει ακόμη απομακρυσμένη πρόσβαση. Δημιουργεί μόνο ασφαλή managed identity και heartbeat.

## Pairing
1. Ο διαχειριστής δημιουργεί one-time pairing code στον Smart Pro Remote Session Broker 0.15.0+.
2. Ο πελάτης ανοίγει το Ingress UI της εφαρμογής και εισάγει τον κωδικό.
3. Ο κωδικός καταναλώνεται μία φορά και δεν αποθηκεύεται από την εφαρμογή.
4. Η εφαρμογή αποθηκεύει μόνο το managed node identity/secret στο `/data/managed_identity.json` με permissions 0600.
5. Από εκεί και μετά αποστέλλεται authenticated heartbeat περίπου κάθε 60 δευτερόλεπτα.

## Security boundary
- `host_network: false`
- architectures: `aarch64`, `amd64`
- HTTPS-only Broker URL
- CA/TLS verification από το λειτουργικό
- no MeshAgent binary
- no `.msh`
- no chmod/exec agent path
- no remote access
- no technician presence
- no session code persistence
- managed secret δεν εμφανίζεται στο UI ή στα logs

## Σημαντικό
Η Temporary/Guest εφαρμογή `smart_pro_remote_support_session` 0.9.0 είναι ξεχωριστό component και δεν τροποποιείται από αυτό το release.
