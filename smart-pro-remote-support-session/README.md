# Smart Pro Remote Support - Προσωρινή Συνεδρία 0.7.5

Phase F PTY-connect compatibility hotfix.

Η 0.7.5 βασίζεται απευθείας στην 0.7.4. Διατηρεί το canonical runtime layout `meshagent` + `meshagent.msh` στον ίδιο ιδιωτικό προσωρινό φάκελο και **δεν αλλάζει** το Phase F authorization contract: επιτρέπεται ακριβώς μία προσωρινή εκτέλεση `./meshagent -connect`.

Η αλλαγή είναι μόνο στον τρόπο που φιλοξενείται το επίσημο text/manual connect mode: το `-connect` εκτελείται μέσω isolated pseudo-terminal (`script` από util-linux), χωρίς operator input και χωρίς να εμφανίζεται raw MeshAgent output. Αυτό δοκιμάζει στοχευμένα την υπόθεση ότι το προηγούμενο headless/background stdin επέστρεφε άμεσα EOF και οδηγούσε σε clean `exit_code=0`.

Παραμένουν: Debian/glibc runtime, strict header/SHA/bytes/ELF/loader checks, Admin-armed Phase E/F one-time tickets, last-second SHA, `chmod 700` μόνο στο verified binary, persistent one-shot guard, launch counter, Broker watchdog έως 60s και mandatory cleanup.

Δεν υπάρχει `-install`, service persistence, host mount, privileged mode ή host networking. Η 0.7.5 δεν πειράζει το ξεχωριστό managed add-on 1.0.1.
