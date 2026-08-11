# Smart Pro Remote Support - Προσωρινή Συνεδρία 0.3.0

Η 0.3.0 είναι το **Temporary Bootstrap Phase A** ανάμεσα στο Home Assistant OS και τον Smart Pro Remote Session Broker.

> **Δεν είναι ακόμη λειτουργική έκδοση remote access.**

## Τι κάνει

- Επικυρώνει τον προσωρινό session code `SP-XXXX-XXXX` μέσω HTTPS.
- Ζητά από τον Broker βραχύβιο one-time bootstrap ticket.
- Δεν εμφανίζει το ticket στο log.
- Καταναλώνει το ticket αμέσως σε δεύτερο Broker endpoint.
- Επιβεβαιώνει ότι το ticket μπορεί να χρησιμοποιηθεί μόνο ως Phase A proof.
- Τερματίζεται μετά τον έλεγχο (`startup: once`).
- Δεν ξεκινά αυτόματα στο boot (`boot: manual_only`).

## Τι δεν κάνει ακόμη

- Δεν κατεβάζει MeshCentral agent.
- Δεν λαμβάνει `.msh`, enrollment key, MeshID ή ServerID.
- Δεν δημιουργεί tunnel / Router connection.
- Δεν δίνει remote desktop ή άλλη απομακρυσμένη πρόσβαση.
