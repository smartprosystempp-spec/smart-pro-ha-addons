# Smart Pro Remote Support - Προσωρινή Συνεδρία 0.4.0

Η 0.4.0 είναι το **Secure Bootstrap Delivery Phase B** ανάμεσα στο Home Assistant OS και τον Smart Pro Remote Session Broker 0.5.0+.

> **Δεν είναι ακόμη λειτουργική έκδοση remote access.**

## Τι κάνει

- Επικυρώνει τον προσωρινό session code `SP-XXXX-XXXX` μέσω HTTPS.
- Ζητά βραχύβιο one-time bootstrap ticket.
- Καταναλώνει το ticket μόνο μία φορά.
- Λαμβάνει προσωρινά από τον Broker το επαληθευμένο MeshCentral `.msh`.
- Ελέγχει SHA-256, μέγεθος και βασικά πεδία χωρίς να εμφανίζει τις τιμές τους στο log.
- Αποθηκεύει το `.msh` μόνο προσωρινά στο `/tmp` με περιορισμένα permissions.
- Διαγράφει το `.msh` αμέσως μετά το QA.
- Τερματίζεται μετά τον έλεγχο (`startup: once`).
- Δεν ξεκινά αυτόματα στο boot (`boot: manual_only`).

## Τι δεν κάνει ακόμη

- Δεν κατεβάζει MeshCentral agent.
- Δεν εκτελεί MeshCentral agent.
- Δεν δημιουργεί tunnel / Router connection.
- Δεν δίνει remote desktop ή άλλη απομακρυσμένη πρόσβαση.
- Δεν περιέχει enrollment identifier ή άλλο στατικό MeshCentral bootstrap secret στο δημόσιο repository.
