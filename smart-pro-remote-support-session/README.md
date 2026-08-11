# Smart Pro Remote Support - Προσωρινή Συνεδρία 0.7.2

Phase F runtime compatibility + one-shot safety hotfix.

Η 0.7.2 διατηρεί ολόκληρη την επαληθευμένη αλυσίδα Phase D/E/F, αλλά μεταφέρει το απομονωμένο add-on runtime σε glibc-compatible Debian ώστε το generic Linux MeshAgent να μπορεί να φορτωθεί σωστά. Πριν από `chmod` γίνεται static ELF loader check.

Για ασφάλεια υπάρχει persistent one-shot guard: ο ίδιος temporary session code δεν μπορεί να εκτελέσει δεύτερη Phase F προσπάθεια μετά από container/Supervisor restart. Για νέα προσπάθεια απαιτείται fresh session code και νέα Admin όπλιση.

Επιτρέπεται μόνο προσωρινό `MeshAgent -connect` έως 60s. Δεν υπάρχει `-install`, service persistence, automatic restart, host networking, host filesystem mount ή privileged mode.
