# Controlled live QA — Phase F 0.7.5

Η 0.7.5 είναι στοχευμένο PTY-connect compatibility hotfix πάνω στην 0.7.4.

1. Κράτησε `smart-pro-system.gr` κλειδωμένο κατά το update. Ο Broker παραμένει 0.9.0.
2. Revoke την προηγούμενη 0.7.4 test session και καθάρισε το session code πριν δημιουργήσεις νέο.
3. Update το add-on σε 0.7.5 και επιβεβαίωσε `Stopped`, `Start on boot: OFF` και, αν υπάρχει Supervisor Watchdog toggle, `Watchdog: OFF`.
4. Μην αλλάξεις/σταματήσεις το ξεχωριστό managed add-on 1.0.1 για αυτό το QA.
5. Δημιούργησε fresh session, αποθήκευσε τον κωδικό και όπλισε Phase E και μετά Phase F.
6. Σταμάτα για checkpoint πριν από Start.
7. Στο ελεγχόμενο run επιτρέπεται μόνο μία `./meshagent -connect`, μέσω isolated pseudo-terminal, max 60s.
8. Το raw MeshAgent output παραμένει ιδιωτικό runtime diagnostic και διαγράφεται στο cleanup.
9. Expected success: `MESHAGENT STARTED, WATCHED & TERMINATED — NO PERSISTENCE`.
10. Δεν γίνεται operator desktop/terminal/file-access QA σε αυτή τη φάση.

Δεν υπάρχει `-install`, service persistence, host mounts, privileged mode ή δεύτερη επιτρεπόμενη execution για τον ίδιο session code.
