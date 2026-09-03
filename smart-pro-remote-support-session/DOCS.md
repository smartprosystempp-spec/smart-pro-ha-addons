# Smart Pro Remote Support 0.9.0

Η 0.9.0 συνδέει το customer-facing Ingress UI με τον controlled Phase F μηχανισμό. Μετά από έγκυρο code απαιτείται ξεχωριστό πάτημα «Έναρξη ασφαλούς σύνδεσης».

Ο κωδικός δεν χρειάζεται να αποθηκεύεται στη Διαμόρφωση. Η παλιά `session_code` επιλογή παραμένει προσωρινά μόνο για upgrade compatibility και αγνοείται από τη νέα ροή.

Δεν γίνεται `-install` ή service persistence. Η εκτέλεση παραμένει δεμένη με Broker E/F authorization, one-time tickets, watchdog/revoke και hard runtime deadline.


## Production runtime 0.9.2
Paid Guest 30/60/90 uses a server-authoritative runtime of purchased minutes plus a fixed 60-second non-billable startup allowance. Manual QA stays at 60 seconds. An Admin stop request is consumed by the watchdog and still performs the normal cleanup/report path.
