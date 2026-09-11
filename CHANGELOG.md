# Changelog repository

## 2026-09-11 — Temporary Support 0.9.7 presentation/documentation polish

- Το ενεργό add-on ενημερώνεται από 0.9.6 σε **0.9.7**.
- Η αλλαγή είναι presentation/documentation release πάνω στην επαληθευμένη 0.9.6 runtime βάση.
- Καθαρίζονται η περιγραφή του Home Assistant, το Ingress footer και η customer-facing τεκμηρίωση.
- Η Διαμόρφωση εξηγεί πλέον καθαρά ότι το Smart Pro endpoint είναι προρυθμισμένο και δεν απαιτεί αλλαγή στην κανονική χρήση.
- Το Phase F execution core παραμένει ίδιο λειτουργικά· το 0.9.7 runtime script αλλάζει μόνο version marker.
- Δεν αλλάζουν Guest code validation, Phase E/F authorization, 30/60/90 duration contract, extension consent, watch/revoke, MeshAgent execution ή cleanup.

## 2026-09-11 — Repository separation / cleanup

- Το repository περιορίστηκε αποκλειστικά στο Smart Pro Remote Support για Temporary / Guest συνεδρίες.
- Η legacy Managed εφαρμογή `smart-pro-agent` 2.5.2 αφαιρέθηκε από το ενεργό repository και παραδόθηκε ως ξεχωριστό ιστορικό archive.
- Το Smart Pro Managed Support 3.x παραμένει σε ανεξάρτητο repository.
