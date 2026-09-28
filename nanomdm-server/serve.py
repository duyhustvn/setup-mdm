#!/usr/bin/env python3
import http.server
import socketserver
import os
import mimetypes

PORT = 8000
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

# Đăng ký MIME type chuẩn của Apple cho file .mobileconfig
mimetypes.add_type("application/x-apple-aspen-config", ".mobileconfig")

HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NanoMDM Device Enrollment</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: #f5f5f7;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
        }
        .card {
            background: white;
            padding: 32px 24px;
            border-radius: 18px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.08);
            text-align: center;
            max-width: 400px;
            width: 90%;
        }
        .icon {
            font-size: 48px;
            margin-bottom: 12px;
        }
        h2 { margin: 8px 0; color: #1d1d1f; font-size: 22px; }
        p { color: #6e6e73; font-size: 14px; line-height: 1.5; margin: 12px 0 24px; }
        .btn {
            display: inline-block;
            background: #0071e3;
            color: white;
            padding: 14px 28px;
            border-radius: 24px;
            text-decoration: none;
            font-weight: 600;
            font-size: 16px;
            transition: all 0.2s ease;
        }
        .btn:hover { background: #0077ed; transform: scale(1.02); }
        .footer { margin-top: 28px; font-size: 12px; color: #a1a1a6; }
    </style>
</head>
<body>
    <div class="card">
        <div class="icon">📱</div>
        <h2>NanoMDM Enrollment</h2>
        <p>Nhấn vào nút bên dưới trên thiết bị Apple (iPhone, iPad hoặc Mac) để tải về và kích hoạt hồ sơ quản lý thiết bị.</p>
        <a href="/enroll.mobileconfig" class="btn">Cài Đặt Hồ Sơ MDM</a>
        <div class="footer">NanoMDM &bull; Apple Device Management</div>
    </div>
</body>
</html>
"""

class EnrollmentHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode("utf-8"))
            return
        return super().do_GET()

    def end_headers(self):
        if self.path.endswith(".mobileconfig"):
            self.send_header("Content-Type", "application/x-apple-aspen-config")
        super().end_headers()

if __name__ == "__main__":
    # Cho phép tái sử dụng cổng ngay lập tức khi restart
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), EnrollmentHandler) as httpd:
        print(f"=== Server Enrollment đang chạy ===")
        print(f"Local address : http://0.0.0.0:{PORT}")
        print(f"Direct file   : http://0.0.0.0:{PORT}/enroll.mobileconfig")
        print(f"Thu muc phuc vu: {DIRECTORY}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nĐã dừng server.")
