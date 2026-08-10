FROM alpine:3.20

RUN apk add --no-cache ca-certificates curl jq

COPY run.sh /
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
