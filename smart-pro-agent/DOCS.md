# Managed Support 2.5.1 — QA checkpoint

1. Broker παραμένει 0.22.0.
2. Η εγκατάσταση πρέπει να είναι paired και ACTIVE.
3. Δημιουργείται νέα δοκιμαστική συνεδρία, γίνεται αποδοχή πελάτη και πρόσφατη έγκριση έναρξης 60″.
4. Ο πελάτης πατά μία φορά «Έναρξη συνεδρίας».
5. Αναμένεται το managed node να εμφανιστεί προσωρινά στο MeshCentral.
6. Η δοκιμή σταματά αυτόματα <=60s.
7. Στο WordPress αναμένεται REPORT με αποτέλεσμα runtime_limit ή session_ended, όχι άμεσο agent_exit.
8. Μετά το τέλος δεν πρέπει να παραμένει `meshagent`, `.msh` ή service persistence.
