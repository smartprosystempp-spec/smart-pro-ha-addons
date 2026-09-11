# Changelog repository

## 2026-09-11 — Repository separation / cleanup

- Το repository περιορίζεται πλέον αποκλειστικά στο **Smart Pro Remote Support 0.9.6** για Temporary / Guest συνεδρίες.
- Η legacy Managed εφαρμογή `smart-pro-agent` 2.5.2 αφαιρείται από το ενεργό repository χωρίς να τροποποιείται και παραδίδεται ως ξεχωριστό ιστορικό archive.
- Τα root README / Architecture / Security / upload instructions ενημερώνονται ώστε να περιγράφουν τη σημερινή πραγματική δομή.
- Το Temporary 0.9.6 add-on tree παραμένει byte-for-byte αμετάβλητο σε αυτό το cleanup.
- Δεν αλλάζει Guest runtime, Broker contract, session duration, extension consent, watch/revoke, MeshAgent execution ή cleanup behavior.

## Ιστορικό

Το repository είχε αρχικά δημιουργηθεί ως κοινή βάση Managed + Temporary. Αυτό το μοντέλο έχει πλέον εγκαταλειφθεί: το Managed Support 3.x διατηρεί δικό του ανεξάρτητο repository και το παρόν repository παραμένει μόνο για Temporary / Guest Support.
