# Smart Pro Remote Support - Προσωρινή Συνεδρία 0.7.3

Phase F HTTP header parser portability hotfix.

Η 0.7.3 διατηρεί το Debian/glibc runtime compatibility και το persistent one-shot guard της 0.7.2. Διορθώνει αποκλειστικά την ανάγνωση των Broker binary response headers ώστε τα HTTP header names να ελέγχονται case-insensitively με portable `awk tolower()` και να λειτουργούν σωστά και όταν HTTP/2 τα αποδίδει lowercase.

Οι τιμές architecture, SHA-256 και execution εξακολουθούν να απαιτούν ακριβή αντιστοίχιση. Πριν από execution παραμένουν οι έλεγχοι ELF/SHA/bytes/loader. Επιτρέπεται μόνο προσωρινό `MeshAgent -connect` έως 60s.

Δεν υπάρχει `-install`, service persistence, automatic restart, host networking, host filesystem mount ή privileged mode.
