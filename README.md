# Hệ Thống Quản Trị Thiết Bị Apple (Self-Hosted Apple MDM + SCEP)

> **Tài liệu hướng dẫn từ số 0 (Zero-to-Hero):** Giải thích kiến trúc, luồng hoạt động, cấu trúc thành phần và quy trình thiết lập toàn diện một hệ thống Mobile Device Management (MDM) cho thiết bị Apple (iOS, iPadOS, macOS) sử dụng **NanoMDM** và **MicroMDM SCEP**.

---

## 📑 Mục Lục
1. [Hệ Thống Này Là Gì?](#1-hệ-thống-này-là-gì)
2. [Sơ Đồ Kiến Trúc & Luồng Hoạt Động](#2-sơ-đồ-kiến-trúc--luồng-hoạt-động)
3. [Giải Thích Các Thuật Ngữ Cốt Lõi](#3-giải-thích-các-thuật-ngữ-cốt-lõi)
4. [Cấu Trúc Thư Mục Dự Án](#4-cấu-trúc-thư-mục-dự-án)
5. [Hướng Dẫn Thiết Lập Từng Bước (Step-by-Step Setup)](#5-hướng-dẫn-thiết-lập-từng-bước)
   - [Bước 1: Khởi động SCEP CA Server](#bước-1-khởi-động-scep-ca-server)
   - [Bước 2: Tạo Apple MDM Push Certificate (Push Topic)](#bước-2-tạo-apple-mdm-push-certificate-push-topic)
   - [Bước 3: Khởi động NanoMDM & Nạp Push Certificate](#bước-3-khởi-động-nanomdm--nạp-push-certificate)
   - [Bước 4: Cấu hình Hồ Sơ Đăng Ký (enroll.mobileconfig)](#bước-4-cấu-hình-hồ-sơ-đăng-ký-enrollmobileconfig)
   - [Bước 5: Khởi động Web Portal phục vụ tải hồ sơ (serve.py)](#bước-5-khởi-động-web-portal-phục-vụ-tải-hồ-sơ-servepy)
   - [Bước 6: Thực hiện Đăng Ký (Enroll) trên thiết bị Apple](#bước-6-thực-hiện-đăng-ký-enroll-trên-thiết-bị-apple)
   - [Bước 7: Ra lệnh Điều khiển & Giám sát Thiết bị](#bước-7-ra-lệnh-điều-khiển--giám-sát-thiết-bị)
6. [Sổ Tay Xử Lý Sự Cố & Câu Hỏi Thường Gặp (FAQ)](#6-sổ-tay-xử-lý-sự-cố--faq)

---

## 1. Hệ Thống Này Là Gì?

Hệ thống này cho phép bạn **tự xây dựng một máy chủ MDM độc lập** (tương tự như Jamf, Microsoft Intune, VMware Workspace ONE) để:
* Cấp phát chứng chỉ định danh số (`device.crt`) an toàn cho thiết bị Apple.
* Quản lý, giám sát thông số phần cứng, mức pin, phiên bản hệ điều hành từ xa.
* Gửi lệnh điều khiển (khóa máy, xóa máy, cài đặt hồ sơ cấu hình, quản lý Wi-Fi/VPN...).

### 4 Thành phần chính trong hệ thống:
1. **SCEP Server (`micromdm/scep`):** Đóng vai trò là Tổ chức phát hành chứng chỉ nội bộ (CA). Tiếp nhận yêu cầu từ iPhone/Mac và cấp chứng chỉ định danh thiết bị.
2. **NanoMDM Server (`nanomdm`):** Máy chủ MDM trung tâm siêu nhẹ. Tiếp nhận đăng ký, lưu trữ trạng thái thiết bị và quản lý hàng đợi lệnh điều khiển.
3. **Apple APNs (Apple Push Notification service):** Cổng thông báo của Apple. NanoMDM thông qua APNs để "đánh thức" thiết bị kết nối về server nhận lệnh qua Internet.
4. **Web Portal (`serve.py`):** Cổng thông tin nội bộ cho phép người dùng mở Safari trên iPhone/Mac để tải và cài đặt hồ sơ đăng ký chỉ với 1 click.

---

## 2. Sơ Đồ Kiến Trúc & Luồng Hoạt Động

### Sơ đồ tổng thể hệ thống:

```text
                               +-----------------------------+
                               |     Apple APNs Gateway      |
                               |    (api.push.apple.com)     |
                               +-----------------------------+
                                      ^               |
                 (1) Gửi Push Wake-up |               | (2) Đánh thức thiết bị
                                      |               v
+------------------+         +------------------+     |     +------------------+
|   Quản Trị Viên   | ======> |  NanoMDM Server  |     +===> |  Thiết Bị Apple  |
|  (cmdr.py / CLI) | Ra lệnh |   (Cổng: 9000)   | <======== | (iPhone/iPad/Mac)|
+------------------+         +------------------+  Báo cáo  +------------------+
                                                      kết quả         |
                                                                      |
    +-------------------------+                 Xin chứng chỉ         |
    |  Web Portal (serve.py)  | <=====================================+
    |       (Cổng: 8000)      |         Tải enroll.mobileconfig       |
    +-------------------------+                                       v
                                                            +------------------+
                                                            |   SCEP Server    |
                                                            |   (Cổng: 8080)   |
                                                            +------------------+
```

---

### 2 Giai đoạn vận hành cốt lõi:

#### Giai đoạn 1: Đăng ký thiết bị (Enrollment Flow)
1. Người dùng mở **Safari** trên iPhone/Mac truy cập vào `Web Portal (serve.py)` tải file `enroll.mobileconfig`.
2. Thiết bị đọc cấu hình SCEP, tự sinh cặp khóa RSA trên phần cứng (Secure Enclave) rồi gửi yêu cầu CSR đến `SCEP Server`.
3. `SCEP Server` ký và trả về chứng chỉ định danh (`device.crt`).
4. Thiết bị dùng `device.crt` gửi gói tin `Authenticate` đến `NanoMDM Server`.
5. Thiết bị liên hệ với Apple APNs để xin `Push Token` dựa trên `Push Topic`, rồi gửi gói `TokenUpdate` nộp Push Token cho NanoMDM. Quá trình Enroll hoàn tất!

#### Giai đoạn 2: Quản trị & Ra lệnh (Command & Monitoring Flow)
1. Quản trị viên dùng script `cmdr.py` nạp lệnh (ví dụ: `DeviceInformation`, `DeviceLock`) vào hàng đợi của `NanoMDM Server`.
2. `NanoMDM` dùng Push Certificate gửi tín hiệu qua máy chủ `Apple APNs`.
3. `Apple APNs` chuyển tiếp thông báo đánh thức (Wake-up) xuống iPhone/Mac qua Internet.
4. Thiết bị tự động "thức dậy" trong chế độ nền, kết nối về `NanoMDM Server` lấy lệnh về thi hành.
5. Thiết bị gửi báo cáo kết quả (`Acknowledged` kèm dữ liệu) ngược lại cho `NanoMDM`.

---

## 3. Giải Thích Các Thuật Ngữ Cốt Lõi

* **`enroll.mobileconfig` (Configuration Profile):** File cấu hình chuẩn XML Plist của Apple. Đóng vai trò là "chiếc phong bì" chứa 2 gói cấu hình con: gói SCEP (hướng dẫn xin chứng chỉ) và gói MDM (hướng dẫn kết nối về máy chủ quản lý).
* **`Payload`:** Một "tờ hướng dẫn cụ thể" bên trong file `.mobileconfig`:
  * `com.apple.security.scep`: Hướng dẫn kết nối SCEP CA.
  * `com.apple.mdm`: Hướng dẫn kết nối NanoMDM và đăng ký APNs.
* **`SCEP` (Simple Certificate Enrollment Protocol):** Giao thức chuẩn công nghiệp giúp thiết bị tự động xin cấp chứng chỉ số mà không cần can thiệp thủ công.
* **`device.crt`:** Chứng chỉ số định danh do SCEP cấp riêng cho từng thiết bị, dùng để xác thực mTLS giữa thiết bị và NanoMDM.
* **`Push Topic`:** Chuỗi định danh duy nhất (dạng `com.apple.mgmt.External.<uuid>`) do Apple cấp khi tạo chứng chỉ Push. Thiết bị dựa vào chuỗi này để biết nó cần "lắng nghe" thông báo từ máy chủ nào.
* **`UDID` (Unique Device Identifier):** Mã định danh phần cứng duy nhất của chiếc iPhone/Mac (ví dụ: `00008140-000265A63652801C`). Mọi lệnh quản trị đều nhắm tới mã này.
* **`SignMessage = true`:** Tham số yêu cầu thiết bị ký số vào header HTTP `Mdm-Signature`. Cực kỳ quan trọng khi máy chủ đứng sau reverse proxy hoặc Cloudflare Tunnel (nơi không hỗ trợ mTLS ở tầng mạng).

---

## 4. Cấu Trúc Thư Mục Dự Án

```text
/home/vbox/projects/mdm/
├── .gitignore                          # Cấu hình bảo mật, chặn commit private key và database
├── README.md                           # Toàn bộ tài liệu hướng dẫn hệ thống
├── ca.pem                              # Chứng chỉ CA công khai của SCEP
├── push.pem                            # File gộp chứng chỉ APNs từ Apple + Private Key (nạp vào NanoMDM)
│
├── nanomdm-linux-amd64-v0.9.0/         # Thư mục máy chủ NanoMDM
│   ├── nanomdm-linux-amd64             # Binary thực thi của NanoMDM Server
│   ├── enroll.mobileconfig             # Hồ sơ cấu hình đăng ký MDM cho thiết bị
│   ├── cmdr.py                         # Công cụ sinh lệnh MDM (DeviceInformation, Lock, Restart...)
│   ├── serve.py                        # Web Portal phục vụ trang tải hồ sơ chuẩn Apple MIME type
│   └── dbkv/                           # Database cục bộ lưu trữ cert, token và thiết bị đã enroll
│       ├── cert_auth/                  # Lưu liên kết giữa cert hash và UDID thiết bị
│       ├── enrollments/                # Dữ liệu đăng ký, token APNs của từng thiết bị
│       ├── push_cert/                  # Lưu Push Certificate đã nạp
│       └── queue/                      # Hàng đợi lệnh và báo cáo kết quả thi hành từ thiết bị
│
└── scep/                               # Thư mục máy chủ SCEP CA
    └── depot/                          # Nơi lưu trữ khóa CA và cơ sở dữ liệu sổ cái
        ├── ca.key                      # Khóa bí mật của CA (bảo mật tuyệt đối)
        ├── ca.pem                      # Chứng chỉ công khai của CA
        ├── index.txt                   # Sổ cái OpenSSL theo dõi các chứng chỉ đã cấp
        └── *.pem                       # Các chứng chỉ thiết bị (device.crt) đã được cấp
```

---

## 5. Hướng Dẫn Thiết Lập Từng Bước

### Bước 1: Khởi động SCEP CA Server

Máy chủ SCEP chạy dưới dạng Docker container, gắn thư mục `scep/depot` làm nơi lưu trữ dữ liệu.

```bash
docker run -d --name scep \
  -v /home/vbox/projects/mdm/scep/depot:/depot \
  -p 8080:8080 \
  micromdm/scep:latest -allowrenew 0
```
> [!IMPORTANT]
> **Cờ `-allowrenew 0`:** Bắt buộc phải có để SCEP Server luôn cho phép cấp phát chứng chỉ mới cho nhiều thiết bị mà không bị chặn bởi cơ chế kiểm tra trùng tên của sổ cái `index.txt`.

Kiểm tra trạng thái SCEP:
```bash
curl -s "http://localhost:8080/scep?operation=GetCACert" | head -c 20
# Nếu xuất hiện dữ liệu nhị phân chứng chỉ nghĩa là SCEP đã hoạt động tốt.
```

---

### Bước 2: Tạo Apple MDM Push Certificate (Push Topic)

Do Apple APNs chỉ chấp nhận kết nối có chứng chỉ do Apple ký, bạn sử dụng dịch vụ trung gian cộng đồng miễn phí `mdmcert.download` để ký CSR mà không cần tài khoản Apple Developer trả phí:

1. **Đăng ký tài khoản:** Truy cập [mdmcert.download/registration](https://mdmcert.download/registration) bằng email có tên miền riêng (không dùng Gmail/Yahoo). Bấm link xác nhận trong hòm thư.
2. **Tải công cụ `mdmctl`:**
   ```bash
   wget https://github.com/micromdm/micromdm/releases/download/v1.13.1/micromdm_v1.13.1.zip
   unzip micromdm_v1.13.1.zip
   chmod +x build/linux/mdmctl
   ```
3. **Tạo yêu cầu ký:**
   ```bash
   ./build/linux/mdmctl mdmcert.download -new -email your-email@yourdomain.com
   ```
   *Lệnh này sinh ra khóa `mdmcert.download.push.key` và gửi CSR lên mdmcert.*
4. **Giải mã file nhận từ email:**
   Tải file đính kèm trong email về (ví dụ `mdm_signed_request.xxxx.p7`) và giải mã:
   ```bash
   ./build/linux/mdmctl mdmcert.download -decrypt /path/to/file-dinh-kem
   # Kết quả sinh ra file: mdmcert.download.push.req
   ```
5. **Tải cert từ Apple Portal:**
   * Truy cập [identity.apple.com/pushcert](https://identity.apple.com/pushcert), đăng nhập Apple ID bất kỳ.
   * Chọn **Create a Certificate**, upload file `mdmcert.download.push.req`.
   * Tải chứng chỉ do Apple cấp về (ví dụ `MDM_ Jesse Peterson_Certificate.pem`).
6. **Ghép chứng chỉ và Private Key:**
   ```bash
   (cat "MDM_ Jesse Peterson_Certificate.pem"; echo ""; cat mdmcert.download.push.key) > push.pem
   ```
7. **Lấy Push Topic:**
   ```bash
   openssl x509 -noout -subject -in push.pem
   # Tìm giá trị: UID=com.apple.mgmt.External.<uuid>
   ```

---

### Bước 3: Khởi động NanoMDM & Nạp Push Certificate

1. **Khởi động NanoMDM Server (Cổng 9000):**
   ```bash
   cd /home/vbox/projects/mdm/nanomdm-linux-amd64-v0.9.0
   ./nanomdm-linux-amd64 -ca ../ca.pem -api nanomdm -debug
   ```

2. **Nạp `push.pem` vào NanoMDM qua API:**
   ```bash
   cat /home/vbox/projects/mdm/push.pem | curl -s -T - -u nanomdm:nanomdm 'http://127.0.0.1:9000/v1/pushcert'
   ```
   *Phản hồi thành công:*
   ```json
   {
       "not_after": "2027-09-28T14:50:14Z",
       "topic": "com.apple.mgmt.External.6a0a852b-efaa-4267-94ca-f1a3e6a9e43e"
   }
   ```

---

### Bước 4: Cấu hình Hồ Sơ Đăng Ký (`enroll.mobileconfig`)

Mở file `nanomdm-linux-amd64-v0.9.0/enroll.mobileconfig` và kiểm tra 3 thông số chính:

1. **SCEP URL (dòng 19):** Trỏ về đường dẫn SCEP (qua Cloudflare Tunnel hoặc IP máy).
   ```xml
   <key>URL</key>
   <string>https://<cloudflare-scep-url>/scep</string>
   ```
2. **MDM ServerURL (dòng 52):** Trỏ về đường dẫn NanoMDM `/mdm`.
   ```xml
   <key>ServerURL</key>
   <string>https://<cloudflare-mdm-url>/mdm</string>
   ```
3. **Push Topic (dòng 56):** Điền Push Topic lấy từ Bước 2.
   ```xml
   <key>Topic</key>
   <string>com.apple.mgmt.External.6a0a852b-efaa-4267-94ca-f1a3e6a9e43e</string>
   ```

---

### Bước 5: Khởi động Web Portal phục vụ tải hồ sơ (`serve.py`)

Do NanoMDM không kèm giao diện web phân phối file, ta dùng script Python `serve.py` trên cổng 8000:

```bash
cd /home/vbox/projects/mdm/nanomdm-linux-amd64-v0.9.0
python3 serve.py
```

Tạo đường dẫn công khai ra Internet bằng Cloudflare Tunnel:
```bash
cloudflared tunnel --url http://localhost:8000
```
Cloudflare sẽ cung cấp một đường link (ví dụ: `https://asylum-pendant-escape-suzuki.trycloudflare.com`).

---

### Bước 6: Thực hiện Đăng Ký (Enroll) trên thiết bị Apple

1. **Tải hồ sơ:**
   * Mở trình duyệt **Safari** trên iPhone/iPad/Mac và truy cập đường link Cloudflare của Web Portal.
   * Nhấn nút **"Cài Đặt Hồ Sơ MDM"** -> Chọn **Cho phép (Allow)**.
2. **Cài đặt vào hệ thống:**
   * **Trên iPhone/iPad:** Mở **Cài đặt (Settings)** > Bấm vào mục **Đã tải về hồ sơ (Profile Downloaded)** ở ngay đầu trang > Bấm **Cài đặt (Install)** > Nhập mật khẩu máy và xác nhận tin cậy.
   * **Trên máy Mac:** Vào **Cài đặt hệ thống** > **Quyền riêng tư & Bảo mật** > **Hồ sơ** > Nhấp đúp vào **Enrollment Profile** và bấm **Cài đặt**.
3. **Xác nhận thành công từ Log NanoMDM:**
   ```text
   msg=cert associated enrollment=new id=00008140-000265A63652801C hash=f4d430bc...
   msg=Authenticate serial_number=HG3Q25R61Y
   msg=TokenUpdate
   ```
   *Thiết bị đã chính thức kết nối và nhận diện thành công!*

---

### Bước 7: Ra lệnh Điều khiển & Giám sát Thiết bị

Mọi lệnh điều khiển đều được sinh ra từ `cmdr.py` và nạp vào hàng đợi NanoMDM qua `curl`:

#### 1. Lệnh lấy thông tin chi tiết máy (`DeviceInformation`):
```bash
python3 cmdr.py DevInfo OSVersion Model DeviceName BatteryLevel WiFiMAC BluetoothMAC SerialNumber | \
curl -s -T - -u nanomdm:nanomdm 'http://127.0.0.1:9000/v1/enqueue/<UDID>'
```
*(Thay `<UDID>` bằng mã máy của bạn, ví dụ: `00008140-000265A63652801C`).*

**Phản hồi của NanoMDM khi bắn APNs thành công:**
```json
{
    "status": {
        "00008140-000265A63652801C": {
            "push_result": "2F972609-B533-67B5-0ADF-0AB1D0AC1E02"
        }
    },
    "request_type": "DeviceInformation"
}
```
*`push_result` chính là mã xác nhận do Apple APNs Gateway trả về.*

#### 2. Xem kết quả thiết bị gửi về:
Báo cáo của thiết bị được lưu tại:
```bash
cat nanomdm-linux-amd64-v0.9.0/dbkv/queue/*/*/<UDID>.*.queueitem.report
```

**Dữ liệu thực tế iPhone báo cáo:**
```xml
<dict>
	<key>Status</key>
	<string>Acknowledged</string>
	<key>UDID</key>
	<string>00008140-000265A63652801C</string>
	<key>QueryResponses</key>
	<dict>
		<key>DeviceName</key>
		<string>iPhone của VCS</string>
		<key>Model</key>
		<string>MYNE3VN</string>
		<key>OSVersion</key>
		<string>26.6.1</string>
		<key>BatteryLevel</key>
		<real>0.35</real>
	</dict>
</dict>
```

#### 3. Các lệnh quản trị khác:
* **Khóa màn hình máy từ xa:**
  ```bash
  python3 cmdr.py DeviceLock --pin 123456 | curl -s -T - -u nanomdm:nanomdm 'http://127.0.0.1:9000/v1/enqueue/<UDID>'
  ```
* **Khởi động lại máy:**
  ```bash
  python3 cmdr.py RestartDevice | curl -s -T - -u nanomdm:nanomdm 'http://127.0.0.1:9000/v1/enqueue/<UDID>'
  ```
* **Xem danh sách chứng chỉ đang cài trên máy:**
  ```bash
  python3 cmdr.py CertificateList | curl -s -T - -u nanomdm:nanomdm 'http://127.0.0.1:9000/v1/enqueue/<UDID>'
  ```

---

## 6. Sổ Tay Xử Lý Sự Cố & FAQ

### Q1: SCEP báo lỗi `failed to sign CSR: err="DN already exists"`?
* **Nguyên nhân:** Do file sổ cái CA `scep/depot/index.txt` bị vướng bản ghi chứng chỉ cũ còn hạn, trong khi thiết bị gửi CSR có Subject rỗng khiến SCEP hiểu lầm là bị trùng tên.
* **Xử lý:**
  1. Xóa sạch file sổ cái: `sudo truncate -s 0 /home/vbox/projects/mdm/scep/depot/index.txt`
  2. Đảm bảo chạy Docker SCEP với cờ `-allowrenew 0`.

### Q2: Chứng chỉ `device.crt` nằm ở đâu sau khi enroll?
* **Trên Server SCEP:** Nằm tại `scep/depot/<Mã_Hash>.<Serial>.pem`.
  * Có thể copy ra xem: `sudo cp scep/depot/*.pem device.crt && openssl x509 -noout -text -in device.crt`
* **Trên NanoMDM:** Được lưu dưới dạng mã hash tại `nanomdm-linux-amd64-v0.9.0/dbkv/cert_auth/`.
* **Trên Thiết bị:** Nằm trong phần cứng bảo mật (Keychain / Secure Enclave) của iPhone/Mac.

### Q3: Chạy `cmdr.py` bị lỗi `invalid choice`?
* **Nguyên nhân:** `cmdr.py` chỉ là script sinh nội dung XML Plist ra màn hình (`stdout`), không phải script gửi HTTP nên không nhận cờ `-id` hay `-api`.
* **Xử lý:** Luôn dùng dấu pipe (`|`) đẩy nội dung từ `cmdr.py` vào lệnh `curl` gửi tới endpoint `/v1/enqueue/<UDID>`.

### Q4: Lỗi `CommandFormatError` khi gửi `DeviceInformation`?
* **Nguyên nhân:** Theo chuẩn Apple, lệnh `DeviceInformation` bắt buộc phải kèm theo ít nhất một trường cần truy vấn trong mảng `Queries`.
* **Xử lý:** Thêm các trường cần lấy vào sau `DevInfo` (ví dụ: `python3 cmdr.py DevInfo OSVersion Model DeviceName BatteryLevel`).

### Q5: Lưu ý về Cloudflare Quick Tunnel (`trycloudflare.com`)?
* Quick Tunnel là liên kết tạm thời. Nếu bạn khởi động lại lệnh `cloudflared`, domain ngẫu nhiên sẽ thay đổi. Hãy nhớ cập nhật lại `URL` (SCEP) và `ServerURL` (MDM) trong `enroll.mobileconfig` trước khi cài đặt cho thiết bị mới.

### Q6: Gia hạn Push Certificate hàng năm (Renew)?
* Apple Push Certificate có hạn **365 ngày**. Hàng năm bạn phải đăng nhập lại **đúng Apple ID cũ** trên [identity.apple.com/pushcert](https://identity.apple.com/pushcert) và nhấn nút **Renew**. Tuyệt đối không bấm tạo mới vì sẽ làm đổi Push Topic, khiến toàn bộ thiết bị cũ mất liên lạc và phải enroll lại.
