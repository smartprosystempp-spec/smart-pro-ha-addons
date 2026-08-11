# Οδηγίες — Προσωρινή Συνεδρία 0.4.0

## Σκοπός αυτής της έκδοσης
Η 0.4.0 ολοκληρώνει το **Secure Bootstrap Delivery Phase B** χωρίς πραγματικό remote access:

`session code → validation → one-time ticket → server-side READY .msh → temporary delivery → fingerprint/field verification → secure deletion → audit`

## Διαμόρφωση
Στην καρτέλα **Διαμόρφωση** παραμένουν δύο πεδία:

- **Endpoint Smart Pro Broker**: προρυθμισμένο στο Smart Pro System.
- **Προσωρινός κωδικός συνεδρίας**: ο κωδικός `SP-XXXX-XXXX` που δημιουργεί ο Admin.

Το enrollment identifier παραμένει αποκλειστικά στον WordPress Broker. Δεν υπάρχει στο GitHub ή στη διαμόρφωση του Home Assistant.

## Controlled QA 0.4.0
1. Ο Smart Pro Remote Session Broker πρέπει να είναι 0.5.0+ και το MeshCentral Vault να είναι `READY`.
2. Δημιουργήστε νέο test session code.
3. Βάλτε τον code στη Διαμόρφωση της εφαρμογής και αποθηκεύστε.
4. Πατήστε **Έναρξη** μία φορά.
5. Στο log πρέπει να εμφανιστούν:
   - validation,
   - one-time ticket,
   - ασφαλής προσωρινή λήψη `.msh`,
   - SHA-256 / size / required-field verification,
   - ασφαλής διαγραφή,
   - `SECURE BOOTSTRAP DELIVERY PHASE B: ΟΛΟΚΛΗΡΩΘΗΚΕ`.
6. Στον Broker πρέπει να καταγραφεί issued / consumed / delivered.
7. Ανακαλέστε τον test session code και καθαρίστε τον code από τη Διαμόρφωση.

## Σημαντικό
Η 0.4.0 **δεν** κατεβάζει ή εκτελεί MeshCentral agent και δεν ενεργοποιεί tunnel, Router ή remote access.
