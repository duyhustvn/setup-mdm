FROM alpine:3.20

RUN apk add --no-cache ca-certificates curl unzip

ARG SCEP_VERSION=v2.3.0

RUN curl -L -o /tmp/scepserver.zip "https://github.com/micromdm/scep/releases/download/${SCEP_VERSION}/scepserver-linux-amd64-${SCEP_VERSION}.zip" && \
    unzip -j /tmp/scepserver.zip -d /usr/bin/ && \
    rm /tmp/scepserver.zip && \
    curl -L -o /tmp/scepclient.zip "https://github.com/micromdm/scep/releases/download/${SCEP_VERSION}/scepclient-linux-amd64-${SCEP_VERSION}.zip" && \
    unzip -j /tmp/scepclient.zip -d /usr/bin/ && \
    rm /tmp/scepclient.zip && \
    mv /usr/bin/scepserver-linux-amd64 /usr/bin/scepserver && \
    mv /usr/bin/scepclient-linux-amd64 /usr/bin/scepclient && \
    chmod +x /usr/bin/scepserver /usr/bin/scepclient

EXPOSE 8080

VOLUME ["/depot"]

ENTRYPOINT ["scepserver"]
