FROM debian:bookworm-slim

ARG BUILD_VERSION="0.8.0"
ARG BUILD_ARCH

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        jq \
        binutils \
        util-linux \
        python3 \
    && rm -rf /var/lib/apt/lists/*

COPY run.sh /
COPY ui_server.py /opt/smart-pro/ui_server.py
COPY phase-f-0.7.7.sh /opt/smart-pro/phase-f-0.7.7.sh
RUN chmod a+x /run.sh /opt/smart-pro/ui_server.py /opt/smart-pro/phase-f-0.7.7.sh

LABEL io.hass.version="${BUILD_VERSION}" \
      io.hass.type="app" \
      io.hass.arch="${BUILD_ARCH}"

CMD [ "/run.sh" ]
