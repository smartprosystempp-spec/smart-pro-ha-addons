FROM alpine:latest
# Εγκατάσταση βασικών εργαλείων για το Linux του Home Assistant
RUN apk add --no-cache wget curl libc6-compat bash sudo

# Αντιγραφή του αρχείου εκκίνησης
COPY run.sh /
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
