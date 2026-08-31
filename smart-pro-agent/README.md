# Smart Pro System - Remote Support 2.1.0

Managed Bootstrap Authorization QA για μόνιμες εγκαταστάσεις Smart Pro System.

Η 2.1.0 διατηρεί το live-verified foundation της 2.0.2:
- one-time pairing,
- ασφαλή τοπική managed identity,
- authenticated heartbeat,
- recovery μετά από προσωρινό network/Plesk failure,
- explicit revoke detection,
- local credential cleanup και safe re-pair.

## Νέο στην 2.1.0

Προστίθεται μόνο το κουμπί **«Έλεγχος ασφαλούς προετοιμασίας»** για ελεγχόμενο QA με Broker 0.17.0+.

Η εφαρμογή:
1. ζητά ένα 180-second one-time bootstrap authorization ticket,
2. το κρατά μόνο στη μνήμη,
3. το καταναλώνει αμέσως με δεύτερο authenticated request,
4. απορρίπτει fail-closed οποιαδήποτε απάντηση δηλώνει `.msh` delivery, Agent delivery, execution ή remote access.

Δεν λαμβάνει enrollment identifier ή `.msh`, δεν κατεβάζει/chmod/εκτελεί MeshAgent και δεν ενεργοποιεί remote access.
