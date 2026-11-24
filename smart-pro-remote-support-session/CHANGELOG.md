# Changelog

## 0.12.0 — Αυτόματη πρόσβαση τεχνικού στο Home Assistant (τοπικός proxy)

- Νέο αρχείο `ha_proxy.py`: μικρός τοπικός proxy (127.0.0.1:80 μέσα στο add-on → Home Assistant). Ξεκινά ΜΟΝΟ όταν ο πελάτης πατήσει «Δημιουργία προσωρινού λογαριασμού» και σταματά πριν διαγραφεί ο λογαριασμός, στο τέλος της συνεδρίας (ή στον τερματισμό του add-on). Αν δεν ξεκινήσει, δεν δημιουργείται λογαριασμός.
- Keep-alive: οι συνδέσεις μένουν ανοιχτές μετά από κάθε απάντηση. Αυτό ήταν η αιτία που το dashboard του Home Assistant δεν συνδεόταν μέσω relay (το πρώτο μήνυμα ταυτοποίησης του browser χανόταν όταν ο relay έπρεπε να ανοίξει νέο tunnel).
- Αφαιρεί headers `X-Forwarded-*`/`Forwarded`/`Via`/`X-Real-IP` (το Home Assistant τα απορρίπτει με 400 όταν δεν έχει ρυθμιστεί reverse proxy) και `Sec-WebSocket-Extensions`.
- Εύρεση Home Assistant αυτόματα: δοκιμάζει 172.30.32.1:80, homeassistant:80, homeassistant:8123, 172.30.32.1:8123.
- Streaming για μεγάλες/ατέλειωτες απαντήσεις, chunked request bodies, HEAD/204/304, WebSocket με απευθείας μεταφορά.
- Καταγράφει μόνο έναρξη/λήξη και αριθμούς αιτημάτων. Δεν καταγράφει διαδρομές, headers, cookies ή περιεχόμενο.
- Ακούει μόνο στο loopback του container. Δεν αλλάζει τίποτα στον execution core (`phase-f-ui-0.12.0.sh`: μόνο version marker).
- Δοκιμές: 23 έλεγχοι proxy με ψεύτικο Home Assistant (keep-alive, headers, WebSocket, streaming, σφάλματα) και 11 έλεγχοι κύκλου ζωής.

## 0.11.0 — Προαιρετικός προσωρινός λογαριασμός Home Assistant για τον τεχνικό

- Στην οθόνη «σύνδεση ενεργή» εμφανίζεται κουμπί «Δημιουργία προσωρινού λογαριασμού» με σαφή εξήγηση. Τίποτα δεν δημιουργείται χωρίς το πάτημά του.
- Δημιουργείται ένας λογαριασμός διαχειριστή (μόνο τοπική σύνδεση), στέλνεται κρυπτογραφημένος στο Broker και διαγράφεται αυτόματα όταν τελειώσει η συνεδρία. Αν η αποστολή αποτύχει, ο λογαριασμός διαγράφεται αμέσως.
- Δεύτερη ασφάλεια: καθαρισμός υπολοίπων στην εκκίνηση και στον τερματισμό του add-on.
- config.yaml: νέα άδεια homeassistant_api. Dockerfile: openssl. Νέο αρχείο ha_account.py.
- Execution core (phase-f-ui-0.11.0.sh): μόνο version marker + αρχείο context για τον λογαριασμό. Χωρίς αλλαγή σε validation, watch/revoke, παράταση ή cleanup.

## 0.10.0 — Παράταση χωρίς έγκριση: ενημέρωση πελάτη & σαφέστερα κείμενα

- Όταν ο τεχνικός προσθέτει χρόνο, η οθόνη του πελάτη δείχνει «Ο τεχνικός πρόσθεσε N λεπτά στη συνεδρία» (αθροιστικά).
- Το «Χρόνος υποστήριξης: Απομένουν…» γίνεται «Χρόνος που απομένει: Υπολείπονται περίπου N λεπτά».
- Αφαιρέθηκε η αναφορά σε έγκριση παράτασης από το email.
- Execution core (phase-f-ui-0.10.0.sh): μόνο version marker. Χωρίς αλλαγή σε validation, authorization, watch/revoke ή cleanup.

## 0.9.9 — Active connection indicator & time left

- Μόλις ξεκινήσει η σύνδεση, η οθόνη γίνεται πράσινη: «Η σύνδεση είναι ενεργή. Ο τεχνικός μπορεί να συνδεθεί τώρα.» (αντί για μόνιμο κίτρινο «σε εξέλιξη»).
- Εμφανίζεται εκτίμηση χρόνου που απομένει («Απομένουν περίπου N λεπτά»), υπολογισμένη από το υπάρχον runtime όριο· περιλαμβάνει εγκεκριμένη παράταση.
- Μήνυμα ότι ο τεχνικός μπορεί να προτείνει παράταση που εγκρίνεται από τον σύνδεσμο του email.
- Το execution core (phase-f-ui-0.9.9.sh) αλλάζει μόνο στο version marker. Χωρίς αλλαγή σε validation, authorization, παράταση, watch/revoke ή cleanup.

## 0.9.8 — Customer wording & clearer two-step screens

- Οι οθόνες δείχνουν «Βήμα 1 από 2» (κωδικός) και «Βήμα 2 από 2» (πάτημα «Έναρξη ασφαλούς σύνδεσης»). Το προειδοποιητικό πλαίσιο στο βήμα 2 λέει καθαρά ότι η σύνδεση δεν έχει ξεκινήσει.
- Η διάρκεια εμφανίζεται ουδέτερα (όχι πράσινο «έτοιμο») και λέει ότι μετράει από το πάτημα «Έναρξη ασφαλούς σύνδεσης».
- Αφαιρέθηκαν όροι όπως HTTPS, logs, Διαμόρφωση, agent, runtime, Phase F, Broker/watchdog, fail-closed από κείμενα προς τον πελάτη.
- Νέα περιγραφή στην κάρτα του Home Assistant.
- Το execution core (phase-f-ui-0.9.8.sh) αλλάζει μόνο στο version marker. Χωρίς αλλαγή σε validation, authorization, διάρκεια, παράταση, watch/revoke ή cleanup.

## 0.9.7 — Presentation & Documentation Polish

- Καθαρό customer-facing κείμενο στην κάρτα του Home Assistant.
- Νέα ελληνική τεκμηρίωση με τη ροή κωδικός → επιβεβαίωση → ρητή έναρξη σύνδεσης.
- Το Ingress footer γίνεται `Smart Pro System · Προσωρινή Υποστήριξη` αντί για engineering runtime label.
- Διευκρινίζεται ότι ο προσωρινός κωδικός δημιουργείται από τον ασφαλή σύνδεσμο της συνεδρίας.
- Η Διαμόρφωση εξηγεί ότι το Broker endpoint είναι προρυθμισμένο και δεν αλλάζει στην κανονική χρήση.
- Το execution core παραμένει λειτουργικά ίδιο με την επαληθευμένη 0.9.6. Το νέο `phase-f-ui-0.9.7.sh` είναι η ίδια ροή με αλλαγή μόνο του version marker.
- Δεν αλλάζουν code validation, Phase E/F authorization, duration contract, extension consent, watch/revoke, MeshAgent foreground execution ή cleanup.

## 0.9.6 — Ingress Active-State Restoration

- Επαναφορά της ενεργής in-memory οθόνης συνεδρίας μετά από refresh/re-open του Ingress.
- Χωρίς επαναφορά κωδικού, δεύτερο validation, νέα authorization ή δεύτερο MeshAgent process.
