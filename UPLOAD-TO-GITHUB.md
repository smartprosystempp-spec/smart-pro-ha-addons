# Ενημέρωση του Home Assistant repository

Το πακέτο αυτό είναι **repository cleanup**, όχι νέο Guest runtime release.

## Πριν την αλλαγή

1. Κρατήστε backup του σημερινού GitHub repository.
2. Κρατήστε ξεχωριστά το παρεχόμενο archive της legacy Managed 2.5.2.
3. Μην χρησιμοποιήσετε τη διαγραφή του repository folder ως μέθοδο απεγκατάστασης κάποιου ήδη εγκατεστημένου add-on.

## Ενημέρωση GitHub

1. Στη ρίζα του υπάρχοντος repository αφαιρέστε τον φάκελο `smart-pro-agent/`.
2. Αφήστε μόνο τον φάκελο `smart-pro-remote-support-session/`.
3. Αντικαταστήστε τα root αρχεία με τα αρχεία αυτού του clean package.
4. Κάντε commit/push.
5. Home Assistant → Add-on Store → έλεγχος για ενημερώσεις / refresh repository.

## Αναμενόμενο αποτέλεσμα

- Το repository εμφανίζει μόνο **Smart Pro Remote Support 0.9.6**.
- Δεν προσφέρεται πλέον η legacy Managed 2.5.2 από αυτό το repository.
- Το Temporary add-on παραμένει στην 0.9.6 και δεν απαιτεί runtime migration από αυτό το cleanup.
- Το σημερινό Smart Pro Managed Support 3.x συνεχίζει αποκλειστικά από το δικό του repository.

## Μην κάνετε

- Μην αντιγράψετε ξανά το `smart-pro-agent/` στο ενεργό Guest repository.
- Μην αλλάξετε Guest session code / Broker URL / runtime αρχεία στο πλαίσιο αυτού του cleanup.
- Μην διαγράψετε το legacy 2.5.2 archive αν θέλετε να διατηρηθεί το ιστορικό υλοποίησης.
