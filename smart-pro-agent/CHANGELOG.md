# Smart Pro Managed Support 2.5.1

- Μικρό hotfix συμβατότητας της ελεγχόμενης δοκιμαστικής σύνδεσης.
- Δεν αλλάζει pairing, heartbeat, συναίνεση πελάτη, έγκριση έναρξης, χρονικό όριο ή server contract.
- Το `MeshAgent -connect` εκκινείται πλέον μέσα σε απομονωμένο pseudo-terminal (`script` από util-linux), όπως είχε απαιτηθεί και στην ήδη δοκιμασμένη Temporary ροή.
- Δεν γίνεται `-install`, service persistence ή μόνιμη πρόσβαση.
- Το `.msh` και το binary παραμένουν μόνο στον ιδιωτικό προσωρινό φάκελο και διαγράφονται στο τέλος.
- Καμία αλλαγή στην Temporary 0.9.0 ή στον Broker 0.22.0.
