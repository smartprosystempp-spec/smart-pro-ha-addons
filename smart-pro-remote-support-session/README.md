# Smart Pro Remote Support - Προσωρινή Συνεδρία 0.7.4

Phase F canonical MeshAgent runtime-layout + launch telemetry hotfix.

Η 0.7.4 διατηρεί όλα τα security controls της 0.7.3 και αλλάζει μόνο το τελευταίο runtime boundary ώστε να αντιγράφει το canonical Linux manual-connect layout του MeshAgent: ιδιωτικός προσωρινός φάκελος με αρχεία ακριβώς `meshagent` και `meshagent.msh`, `cd` στον ίδιο φάκελο και μία μόνο εκτέλεση `./meshagent -connect`.

Προσθέτει επίσης persistent, μη μυστικό launch counter στο `/data`, ώστε κάθε πραγματική εκκίνηση του add-on process να αφήνει σαφή γραμμή `LAUNCH SAFETY` στο log. Το υπάρχον one-shot guard εξακολουθεί να μπλοκάρει τον ίδιο session code πριν από οποιοδήποτε Broker request.

Παραμένουν: Debian/glibc runtime, strict SHA/bytes/ELF/architecture checks, `chmod 700` μόνο μετά το Phase F consume, Broker watchdog έως 60s, fail-closed cleanup, `boot: manual_only`, `startup: once`, `host_network:false`, χωρίς host mounts/privileged mode.

Δεν υπάρχει `-install`, service persistence ή δεύτερη επιτρεπόμενη MeshAgent execution για τον ίδιο session code.
