FROM alpine:3.20

# Cài đặt ca-certificates và python3 (để chạy cmdr.py và serve.py nếu cần)
RUN apk add --no-cache ca-certificates python3 curl

WORKDIR /app

# Copy các binary và script
COPY nanomdm-linux-amd64 /app/nanomdm
COPY nano2nano-linux-amd64 /app/nano2nano
COPY cmdr.py /app/cmdr.py
COPY serve.py /app/serve.py
COPY enroll.mobileconfig /app/enroll.mobileconfig

RUN chmod +x /app/nanomdm /app/nano2nano /app/cmdr.py /app/serve.py

EXPOSE 9000 8000

CMD ["/app/nanomdm", "-ca", "/app/ca.pem", "-api", "nanomdm", "-debug"]
