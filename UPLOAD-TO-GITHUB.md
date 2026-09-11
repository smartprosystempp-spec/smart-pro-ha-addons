# Ενημέρωση Home Assistant repository σε Temporary Support 0.9.7

## Τι αλλάζει

Το repository παραμένει αποκλειστικά για το **Smart Pro Remote Support / Temporary Guest Support**. Η έκδοση 0.9.7 είναι μικρό presentation/documentation update πάνω στην επαληθευμένη 0.9.6.

## Ενημέρωση GitHub

1. Κρατήστε backup του σημερινού repository.
2. Στη ρίζα του repository ανεβάστε τα περιεχόμενα αυτού του package, διατηρώντας τον φάκελο `smart-pro-remote-support-session/`.
3. Μην προσθέσετε ξανά το παλιό `smart-pro-agent/` Managed 2.5.2.
4. Commit/push.
5. Home Assistant → Add-on Store → Check for updates / refresh repository.
6. Update Smart Pro Remote Support **0.9.6 → 0.9.7** χωρίς uninstall.

## Live visual check

- Επιβεβαιώστε έκδοση 0.9.7.
- Ανοίξτε Πληροφορίες, Τεκμηρίωση, Διαμόρφωση και Ingress.
- Μην δημιουργήσετε νέα paid/Guest συνεδρία μόνο για αυτό το presentation QA.
- Start on boot πρέπει να παραμένει OFF και Watchdog OFF.

## Μην κάνετε

- Μην αλλάξετε το προρυθμισμένο Smart Pro endpoint.
- Μην ενεργοποιήσετε Start on boot ή Watchdog για το Temporary add-on.
- Μην κάνετε runtime/session test αν δεν εμφανιστεί λειτουργική παλινδρόμηση.
