# Smart Pro Managed Support 2.5.2

- Διορθώνει την πραγματική ελεγχόμενη εκκίνηση μετά τα live `agent_exit` 4–5s της 2.5.1.
- Χρησιμοποιεί το ήδη live-verified μοντέλο της Temporary 0.7.6: foreground `./meshagent` χωρίς `-connect` και χωρίς `-install`.
- Διατηρεί canonical προσωρινά ονόματα `meshagent` + `meshagent.msh`.
- Σκληραίνει μόνο το προσωρινό runtime `.msh`: αφαιρεί force/fake update και core-dump flags και επιβάλλει `disableUpdate=1`, `noUpdateCoreModule=1`.
- HOME/TMPDIR/XDG config/cache οδηγούνται μέσα στον ιδιωτικό προσωρινό φάκελο της συνεδρίας.
- Η συνεδρία παραμένει one-time, απαιτεί έγκριση Smart Pro + αποδοχή πελάτη και έχει server runtime cap έως 60s.
- Δεν γίνεται εγκατάσταση υπηρεσίας, persistence ή δεύτερη αυτόματη εκτέλεση.
- Broker 0.22.1 παραμένει ως έχει. Temporary 0.9.0 δεν αλλάζει.
