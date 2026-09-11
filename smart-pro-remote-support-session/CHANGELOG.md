# Changelog

## 0.9.7 — Presentation & Documentation Polish

- Καθαρό customer-facing κείμενο στην κάρτα του Home Assistant.
- Νέα ελληνική τεκμηρίωση με τη ροή κωδικός → επιβεβαίωση → ρητή έναρξη σύνδεσης.
- Το Ingress footer γίνεται `Smart Pro System · Προσωρινή Υποστήριξη` αντί για engineering runtime label.
- Διευκρινίζεται ότι ο προσωρινός κωδικός δημιουργείται από τον ασφαλή σύνδεσμο της συνεδρίας.
- Η Διαμόρφωση εξηγεί ότι το Broker endpoint είναι προρυθμισμένο και δεν αλλάζει στην κανονική χρήση.
- Το execution core παραμένει λειτουργικά ίδιο με την επαληθευμένη 0.9.6. Το νέο `phase-f-ui-0.9.7.sh` είναι η ίδια ροή με αλλαγή μόνο του version marker.
- Δεν αλλάζουν code validation, Phase E/F authorization, duration contract, extension consent, watch/revoke, MeshAgent foreground execution ή cleanup.

## 0.9.6 — Ingress Active-State Restoration

- Επαναφορά της ενεργής in-memory οθόνης συνεδρίας μετά από refresh/re-open του Ingress.
- Χωρίς επαναφορά κωδικού, δεύτερο validation, νέα authorization ή δεύτερο MeshAgent process.
