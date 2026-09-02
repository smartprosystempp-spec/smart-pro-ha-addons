# Smart Pro System - Remote Support 2.5.2

Η 2.5.2 είναι ελεγχόμενο compatibility update του Managed Support.

Μετά από έγκριση Smart Pro και ρητή ενέργεια του πελάτη, το επαληθευμένο MeshAgent εκκινείται προσωρινά σε foreground λειτουργία από ιδιωτικό `/tmp` runtime με canonical `meshagent` + `meshagent.msh`. Δεν χρησιμοποιεί `-install`, δεν δημιουργεί υπηρεσία και δεν αφήνει μόνιμη πρόσβαση.

Το προσωρινό `.msh` σκληραίνει τοπικά ώστε να μην επιτρέπονται agent/core updates ή core dumps κατά τη δοκιμή. HOME/TMPDIR/XDG paths παραμένουν μέσα στον προσωρινό runtime φάκελο, ο οποίος διαγράφεται μετά τη λήξη.

Το ανώτατο όριο runtime παραμένει 60 δευτερόλεπτα και ο Broker 0.22.1 παραμένει authoritative για έγκριση, watch και report.
