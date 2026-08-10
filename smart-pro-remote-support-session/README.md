# Smart Pro Remote Support - Προσωρινή Συνεδρία 0.2.0

Η 0.2.0 είναι το πρώτο **Validation Bridge** ανάμεσα στο Home Assistant OS και τον Smart Pro Remote Session Broker.

> **Δεν είναι ακόμη λειτουργική έκδοση remote access.**

## Τι κάνει

- Ζητά προσωρινό κωδικό συνεδρίας `SP-XXXX-XXXX`.
- Στέλνει τον κωδικό μόνο μέσω HTTPS στον Smart Pro Broker.
- Εμφανίζει καθαρά αν ο κωδικός είναι έγκυρος, άκυρος, ληγμένος ή ανακληθείς.
- Τερματίζεται μετά τον έλεγχο (`startup: once`).
- Δεν ξεκινά αυτόματα στο boot (`boot: manual_only`).

## Τι δεν κάνει ακόμη

- Δεν κατεβάζει MeshCentral agent.
- Δεν χρησιμοποιεί `.msh` ή enrollment configuration.
- Δεν δημιουργεί tunnel / Router connection.
- Δεν δίνει remote desktop ή άλλη απομακρυσμένη πρόσβαση.
