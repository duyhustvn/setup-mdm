FROM alpine:3.20

# Cài đặt các gói phụ thuộc
RUN apk add --no-cache ca-certificates python3 curl unzip

WORKDIR /app

# Tự động tải binary chính thức từ GitHub Releases
ARG NANOMDM_VERSION=v0.9.0
RUN curl -L -o /tmp/nanomdm.zip "https://github.com/micromdm/nanomdm/releases/download/${NANOMDM_VERSION}/nanomdm-linux-amd64-${NANOMDM_VERSION}.zip" && \
    unzip -j /tmp/nanomdm.zip -d /app/ && \
    rm /tmp/nanomdm.zip && \
    chmod +x /app/nanomdm-linux-amd64 /app/nano2nano-linux-amd64 && \
    ln -sf /app/nanomdm-linux-amd64 /app/nanomdm && \
    ln -sf /app/nano2nano-linux-amd64 /app/nano2nano

# Copy các script quản trị và hồ sơ cấu hình
COPY cmdr.py /app/cmdr.py
COPY serve.py /app/serve.py
COPY enroll.mobileconfig /app/enroll.mobileconfig

RUN chmod +x /app/cmdr.py /app/serve.py

EXPOSE 9000 8000

CMD ["/app/nanomdm", "-ca", "/app/ca.pem", "-api", "nanomdm", "-debug"]
