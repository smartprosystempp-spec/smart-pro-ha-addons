# Smart Pro System - Remote Support 2.5.1

Controlled Runtime PTY Compatibility Hotfix.

Η 2.5.1 διατηρεί ακριβώς την ίδια ασφαλή ροή της 2.5.0, αλλά εκκινεί το προσωρινό `MeshAgent -connect` μέσα σε pseudo-terminal για να παραμένει ενεργό σε headless Home Assistant add-on περιβάλλον.

Δεν εγκαθιστά υπηρεσία, δεν αφήνει μόνιμο agent και η δοκιμή τερματίζεται το αργότερο σε 60 δευτερόλεπτα.
