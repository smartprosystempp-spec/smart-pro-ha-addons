# Οδηγίες — Προσωρινή Συνεδρία 0.3.0

## Σκοπός αυτής της έκδοσης
Η 0.3.0 ολοκληρώνει το **Temporary Bootstrap Phase A** χωρίς πραγματικό remote access. Ελέγχει ολόκληρη την ασφαλή αλυσίδα:

`session code → validation → one-time bootstrap ticket → consume → audit`

## Διαμόρφωση
Στην καρτέλα **Διαμόρφωση** παραμένουν δύο πεδία:

- **Endpoint επικύρωσης**: προρυθμισμένο στο Smart Pro System.
- **Προσωρινός κωδικός συνεδρίας**: ο κωδικός `SP-XXXX-XXXX` που δημιουργεί ο Admin από WordPress → Remote Sessions.

Το bootstrap ticket δεν συμπληρώνεται από τον χρήστη και δεν εμφανίζεται στο log. Εκδίδεται αυτόματα από τον Broker και καταναλώνεται αμέσως από την εφαρμογή.

## Controlled QA 0.3.0
1. Ενημερώστε πρώτα τον Smart Pro Remote Session Broker σε 0.3.0.
2. Δημιουργήστε νέο test session code.
3. Βάλτε τον code στη Διαμόρφωση της εφαρμογής και αποθηκεύστε.
4. Πατήστε **Έναρξη** μία φορά.
5. Στο log πρέπει να εμφανιστούν διαδοχικά:
   - επιτυχής validation,
   - έκδοση one-time bootstrap ticket χωρίς εμφάνιση της τιμής,
   - επιτυχής consume,
   - `TEMPORARY BOOTSTRAP PHASE A: ΟΛΟΚΛΗΡΩΘΗΚΕ`.
6. Στον Broker, μετά από refresh, πρέπει να αυξηθεί το `Validations` και το `Bootstrap A` να δείξει issued/consumed.
7. Ανακαλέστε τον test session code.
8. Καθαρίστε τον κωδικό από τη Διαμόρφωση της εφαρμογής.

## Σημαντικό
Η 0.3.0 **δεν** ενεργοποιεί MeshCentral agent, enrollment, tunnel, Router ή remote access. Το πραγματικό remote-access bootstrap παραμένει επόμενο, ξεχωριστό security checkpoint.
