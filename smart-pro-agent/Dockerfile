FROM debian:bookworm-slim

ARG BUILD_VERSION="2.5.1"
ARG BUILD_ARCH

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates \
        python3 \
        util-linux \
    && rm -rf /var/lib/apt/lists/*

COPY run.sh /run.sh
COPY ui_server.py /opt/smart-pro/ui_server.py
RUN chmod a+x /run.sh /opt/smart-pro/ui_server.py

ENV SMART_PRO_VERSION="${BUILD_VERSION}" \
    SMART_PRO_ARCH="${BUILD_ARCH}"

LABEL io.hass.version="${BUILD_VERSION}" \
      io.hass.type="app" \
      io.hass.arch="${BUILD_ARCH}"

CMD [ "/run.sh" ]
