# Controlled live QA — Phase F 0.7.4

Η 0.7.4 είναι στοχευμένο runtime-layout και restart-observability hotfix πάνω στην 0.7.3.

1. Κράτησε `smart-pro-system.gr` κλειδωμένο κατά το update. Ο Broker παραμένει 0.9.0.
2. Αν δεν έχει ήδη γίνει cleanup της προηγούμενης 0.7.3 συνεδρίας, κάνε revoke και καθάρισε το HA session code.
3. Update το add-on σε 0.7.4 και επιβεβαίωσε `Stopped` / manual-only.
4. Πριν από live run, έλεγξε στο Home Assistant ότι **Start on boot είναι OFF** και, αν εμφανίζεται επιλογή **Watchdog**, ότι είναι επίσης **OFF**.
5. Δημιούργησε fresh 60-minute session, αποθήκευσε τον κωδικό και όπλισε Phase E και μετά Phase F.
6. Ξεκλείδωσε προσωρινά το site και πάτησε Start ακριβώς μία φορά.
7. Το log πρέπει να εμφανίσει `LAUNCH SAFETY: add-on process instance ...` για κάθε πραγματικό container/process launch.
8. Πριν από execution πρέπει να εμφανιστεί canonical-layout checkpoint για `meshagent + meshagent.msh`.
9. Επιτρέπεται μόνο `./meshagent -connect`, sandboxed στο add-on container, max 60s. Δεν γίνεται operator desktop/terminal/files QA σε αυτή τη φάση.
10. Expected success: `MESHAGENT STARTED, WATCHED & TERMINATED — NO PERSISTENCE`.
11. Είτε success είτε fail-closed: ξανακλείδωσε το site, revoke session και καθάρισε το session code πριν από νέα εργασία.

Δεν υπάρχει `-install`, service persistence, host mounts, privileged mode ή δεύτερη επιτρεπόμενη execution για τον ίδιο session code.
