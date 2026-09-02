# Smart Pro Managed Support 2.2.0 — QA Notes

## Προϋποθέσεις

- Broker 0.18.0 εγκατεστημένο.
- Managed node ACTIVE και ήδη paired.
- Managed enrollment source READY.
- Site/API προσβάσιμο κατά το QA.

## Ελεγχόμενη δοκιμή

1. Update 2.1.0 -> 2.2.0 χωρίς διαγραφή add-on ή `/data`.
2. Επιβεβαίωση ότι η ίδια εγκατάσταση παραμένει συνδεδεμένη και το heartbeat συνεχίζεται.
3. Άνοιγμα Ingress.
4. Πάτημα **«Έλεγχος ασφαλούς λήψης ρυθμίσεων»** μία φορά.
5. Αναμενόμενο UI: οι ρυθμίσεις λήφθηκαν, επαληθεύτηκαν και διαγράφηκαν, χωρίς απομακρυσμένη πρόσβαση.
6. WordPress -> Managed Support -> refresh.
7. Αναμενόμενα: ένα νέο bootstrap authorization `CONSUMED` και ένα νέο settings-delivery ticket `CONSUMED` για το ίδιο ACTIVE node.

## Σημείο στάσης

Μετά το PASS σταματάμε. Δεν ενεργοποιούμε MeshAgent delivery/execution ή remote runtime στο ίδιο release.
