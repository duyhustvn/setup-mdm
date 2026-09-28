# Hướng Dẫn Quản Lý Chứng Chỉ MDM & Cấu Hình Push Topic (NanoMDM + SCEP)

Tài liệu này tổng hợp toàn bộ kiến thức, kiến trúc, vai trò của từng file/thành phần, và quy trình chi tiết từng bước về việc cấp phát chứng chỉ thiết bị (`device.crt`), tạo **Apple MDM Push Certificate (Push Topic)**, thiết lập Web Portal phục vụ tải hồ sơ, giải quyết lỗi sổ cái `index.txt`, hoàn tất luồng **Enrollment** vào **NanoMDM**, và **gửi lệnh giám sát/điều khiển thiết bị**.

---

## 1. Tổng quan Kiến trúc: SCEP vs APNs Push Topic

Trong giải pháp Apple MDM (cụ thể là file `enroll.mobileconfig`), có 2 thành phần độc lập:

| Thành phần | Payload trong Profile | Vai trò & Mục đích | Có cần Push Topic / Apple ID không? |
| :--- | :--- | :--- | :--- |
| **SCEP (Device Identity)** | `com.apple.security.scep` | Cấp phát chứng chỉ định danh thiết bị (`device.crt`) từ CA nội bộ để xác thực mTLS giữa thiết bị và MDM Server (hoặc VPN, Wi-Fi 802.1X). | ❌ **Không cần**. Hoàn toàn do SCEP Server nội bộ ký cấp. |
| **MDM Payload (APNs Push)** | `com.apple.mdm` | Đăng ký thiết bị vào hệ thống MDM để nhận lệnh điều khiển từ xa (wipe, lock, install profile, query info). | ✔️ **Bắt buộc**. Cần Apple Push Certificate và trường `Topic` hợp lệ. |

### Câu hỏi thường gặp: "Chỉ enroll để lấy `device.crt` thì có cần Push Topic không?"
- **Nếu chỉ cần cấp phát `device.crt` cho thiết bị:** 
  - Bạn **không cần** Push Topic hay Apple Developer/Apple ID.
  - Chỉ cần xóa bỏ block payload `com.apple.mdm` khỏi `enroll.mobileconfig`, chỉ giữ lại block `com.apple.security.scep`. Thiết bị sẽ liên hệ thẳng với `scepserver` để lấy cert.
- **Nếu muốn hoàn tất luồng MDM Enrollment vào NanoMDM:** 
  - Trường `<key>Topic</key>` trong `com.apple.mdm` là bắt buộc về mặt cú pháp.
  - Nếu điền Topic giả (dummy): Thiết bị vẫn lấy được `device.crt` qua SCEP và gửi gói `Authenticate` lên NanoMDM, nhưng máy sẽ **không thể nhận bất kỳ lệnh MDM nào sau đó** vì Apple MDM phụ thuộc 100% vào APNs Push Notification để đánh thức thiết bị.

---

## 2. Bảng Vai Trò Của Các File Sinh Ra Trong Quá Trình Tạo Cert

| Tên File | Nguồn Gốc | Vai Trò & Mục Đích Sử Dụng |
| :--- | :--- | :--- |
| **`mdmcert.download.push.csr`** | Lệnh `-new` sinh ra | File yêu cầu ký chứng chỉ (Certificate Signing Request) thô tạo cục bộ. Dùng để gửi lên `mdmcert.download`, **không thể** upload trực tiếp lên Apple. |
| **`mdmcert.download.push.key`** | Lệnh `-new` sinh ra | **Private Key** của Push Certificate. Cực kỳ quan trọng, phải giữ bí mật và không được làm mất (dùng để ghép thành `push.pem`). |
| **`mdmcert.download.pki.crt`** & **`mdmcert.download.pki.key`** | Lệnh `-new` sinh ra | Cặp khóa trao đổi (Exchange PKI Keypair). `mdmcert.download` dùng public cert này để mã hóa file phản hồi gửi về mail của bạn. |
| **File đính kèm từ Email** *(vd: `mdm_signed_request....p7`)* | `mdmcert.download` gửi qua email | File chứa kết quả CSR đã được Apple Vendor ký nhưng **đang bị mã hóa** bằng `pki.crt`. Cần dùng lệnh `-decrypt` để giải mã. |
| **`mdmcert.download.push.req`** | Lệnh `-decrypt` sinh ra | File yêu cầu hoàn chỉnh (định dạng plist có chữ ký CMS). **Đây chính là file dùng để upload lên cổng Apple**. |
| **`MDM_ ..._Certificate.pem`** | Tải về từ Apple Portal | Chứng chỉ APNs Push Certificate chính thức do Apple CA cấp và ký nhận cho server MDM của bạn. |
| **`push.pem`** | Lệnh `cat` gộp lại | File tổng hợp chứa cả **Certificate từ Apple** và **Private Key** (`push.key`). Dùng để nạp thẳng vào NanoMDM qua API `/v1/pushcert`. |

---

## 3. Vai Trò Cốt Lõi Của "Push Topic" Trong Apple MDM

* **Định dạng:** Chuỗi định danh duy nhất có tiền tố `com.apple.mgmt.External.<uuid>` (được lưu tại trường `UID` trong Push Certificate do Apple cấp).
* **Cơ chế hoạt động:**
  1. **Trên Thiết bị:** Khi cài file `enroll.mobileconfig`, thiết bị đọc trường `<key>Topic</key>`, liên hệ với Apple APNs Server và đăng ký: *"Tôi muốn lắng nghe các thông báo push thuộc Topic này"*. Apple APNs sẽ trả về cho thiết bị một `Push Token`. Thiết bị sau đó gửi Token này về NanoMDM trong bản tin `TokenUpdate`.
  2. **Trên NanoMDM:** Khi quản trị viên gửi lệnh (ví dụ: cài profile, xóa máy, khóa máy), NanoMDM dùng `push.pem` kết nối tới Apple APNs qua HTTP/2 TLS. APNs xác thực rằng NanoMDM sở hữu đúng Push Certificate mang Topic đó, rồi chuyển tiếp thông báo "Wake-up" đến thiết bị.
  3. **Kết luận:** Nếu Topic không khớp hoặc chứng chỉ không hợp lệ, thiết bị sẽ không bao giờ nhận được thông báo để kết nối vào NanoMDM lấy lệnh.

---

## 4. Hướng dẫn Từng Bước Tạo Push Topic Certificate (Qua `mdmcert.download`)

### Yêu cầu chuẩn bị
1. **Email có tên miền riêng (Organizational / Custom Domain):**
   - `mdmcert.download` **chặn** các email cá nhân/miễn phí (`@gmail.com`, `@yahoo.com`, `@outlook.com`...).
   - Bạn cần email có domain riêng (ví dụ: `admin@yourdomain.com`).
   - *Mẹo:* Nếu đã có domain, bạn có thể bật **Cloudflare Email Routing** (miễn phí) để forward mail từ domain riêng về Gmail cá nhân.
2. **Một tài khoản Apple ID bất kỳ:**
   - Apple ID cá nhân thông thường (Gmail đều được), miễn phí.
   - Dùng để đăng nhập vào cổng [identity.apple.com/pushcert](https://identity.apple.com/pushcert).

---

### Các bước thực hiện:

#### Bước 1: Đăng ký tài khoản trên `mdmcert.download`
1. Truy cập [https://mdmcert.download/registration](https://mdmcert.download/registration).
2. Điền thông tin họ tên, tổ chức và địa chỉ email tên miền riêng.
3. Kiểm tra hộp thư và nhấn vào liên kết xác nhận (verification link).

#### Bước 2: Tải công cụ `mdmctl`
```bash
# Tải bản release v1.13.1
wget https://github.com/micromdm/micromdm/releases/download/v1.13.1/micromdm_v1.13.1.zip

# Giải nén
unzip micromdm_v1.13.1.zip

# Phân quyền thực thi cho binary mdmctl trên Linux
chmod +x build/linux/mdmctl
```
*(Lưu ý: Thông báo Warning về việc MicroMDM v1 chuyển sang "Maintenance mode" trên GitHub chỉ là thông báo về server v1 để nhường chỗ cho NanoMDM, công cụ `mdmctl` vẫn hoạt động bình thường).*

#### Bước 3: Tạo khóa và gửi yêu cầu ký CSR
Chạy lệnh sau với email đã đăng ký và xác thực ở Bước 1:
```bash
./build/linux/mdmctl mdmcert.download -new -email your-email@yourdomain.com
```
Lệnh này sẽ tự động tạo ra:
* `mdmcert.download.push.key` và `mdmcert.download.push.csr`
* `mdmcert.download.pki.key` và `mdmcert.download.pki.crt`
Đồng thời gửi yêu cầu lên API của `mdmcert.download`.

#### Bước 4: Nhận và giải mã file CSR
1. Kiểm tra email, bạn sẽ nhận được một file đính kèm mã hóa (ví dụ: `mdm_signed_request.xxxx.plist.b64.p7`).
2. Lưu file đó vào thư mục dự án và chạy lệnh giải mã:
   ```bash
   ./build/linux/mdmctl mdmcert.download -decrypt /path/to/file-dinh-kem
   ```
3. Lệnh này sẽ dùng `mdmcert.download.pki.key` để giải mã và tạo ra file:
   **`mdmcert.download.push.req`**

#### Bước 5: Tải Push Certificate từ Apple Push Certificates Portal
1. Truy cập [https://identity.apple.com/pushcert](https://identity.apple.com/pushcert).
2. Đăng nhập bằng tài khoản Apple ID của bạn.
3. Bấm **Create a Certificate**, tích chọn đồng ý điều khoản.
4. Tải file **`mdmcert.download.push.req`** ở Bước 4 lên.
5. Sau khi Apple xử lý thành công, bấm **Download** để tải về chứng chỉ (file thường có tên dạng `MDM_ ..._Certificate.pem`).

#### Bước 6: Ghép Certificate và Private Key thành `push.pem`
> [!IMPORTANT]
> File chứng chỉ tải từ Apple về thường **không có ký tự xuống dòng (`\n`) ở cuối file**. Nếu chỉ dùng `cat cert key > push.pem`, dòng cuối cert và dòng đầu key sẽ bị dính liền vào nhau gây lỗi OpenSSL/NanoMDM.

Lệnh ghép chuẩn xác có chèn ký tự xuống dòng:
```bash
(cat "MDM_ Jesse Peterson_Certificate.pem"; echo ""; cat mdmcert.download.push.key) > push.pem
```

Kiểm tra tính hợp lệ và trích xuất Topic bằng OpenSSL:
```bash
openssl x509 -noout -subject -in push.pem
```
Kết quả hiển thị:
```text
subject=UID=com.apple.mgmt.External.6a0a852b-efaa-4267-94ca-f1a3e6a9e43e, CN=APSP:6a0a852b-efaa-4267-94ca-f1a3e6a9e43e, C=US
```
Chuỗi nằm sau `UID=` chính là **Push Topic**.

---

## 5. Nạp Chứng Chỉ Vào NanoMDM Server

Do file `push.pem` đã chứa đầy đủ cả Certificate và Private Key, ta chỉ cần truyền nội dung file này qua API:
```bash
cat push.pem | curl -s -T - -u nanomdm:nanomdm 'http://127.0.0.1:9000/v1/pushcert'
```

*Giải thích câu lệnh:*
* `cat push.pem |`: Đẩy nội dung cert + key vào luồng dữ liệu chuẩn (`stdin`).
* `-T -`: Tùy chọn upload file của `curl`, dấu `-` đại diện cho việc đọc dữ liệu từ `stdin`.
* `-u nanomdm:nanomdm`: Xác thực Basic Auth theo định dạng `username:api_key`. Ở đây password chính là giá trị truyền vào cờ `-api` của NanoMDM khi khởi động.
* Endpoint `/v1/pushcert`: API nhận cert của NanoMDM.

**Kết quả phản hồi thành công:**
```json
{
    "not_after": "2027-09-28T14:50:14Z",
    "topic": "com.apple.mgmt.External.6a0a852b-efaa-4267-94ca-f1a3e6a9e43e"
}
```

---

## 6. Giải Phẫu Chi Tiết File Hồ Sơ Đăng Ký (`enroll.mobileconfig`)

Trong hệ sinh thái Apple, file `.mobileconfig` là một **Configuration Profile (Hồ sơ cấu hình)** tuân thủ định dạng Property List (XML plist).

### Cấu trúc dạng cây (Tree Structure)

```text
📦 Hồ sơ bao ngoài (PayloadType: Configuration)
 │
 ├── 📄 Payload 1: com.apple.security.scep (Cấu hình xin chứng chỉ)
 │    ├── URL: Đường dẫn tới SCEP Server
 │    ├── Challenge: Mật khẩu xác thực SCEP
 │    ├── Keysize: 2048, Key Type: RSA
 │    └── PayloadUUID: CB90E976-AD44-4B69-8108-8095E6260978 (Mã nhận diện cert)
 │
 └── 📄 Payload 2: com.apple.mdm (Cấu hình kết nối MDM)
      ├── ServerURL: Endpoint nhận lệnh của NanoMDM
      ├── Topic: com.apple.mgmt.External.6a0a852b-... (Topic APNs)
      ├── IdentityCertificateUUID: CB90E976-AD44-4B69-8108-8095E6260978 (Trỏ vào SCEP)
      ├── SignMessage: true (Ký số request bằng cert thiết bị)
      └── AccessRights: 8191 (Toàn quyền quản trị)
```

---

### Ý nghĩa của các trường chuẩn Apple (Bắt đầu bằng `Payload...`)

Apple quy định mọi thành phần cấu hình đều phải có các thuộc tính metadata bắt buộc sau:

| Thuộc Tính (Key) | Kiểu Dữ Liệu | Ý Nghĩa & Vai Trò |
| :--- | :--- | :--- |
| **`PayloadType`** | String | Xác định **loại cấu hình**. Ví dụ: `Configuration` (hồ sơ tổng), `com.apple.security.scep` (cấp phát chứng chỉ), hoặc `com.apple.mdm` (quản trị MDM). |
| **`PayloadIdentifier`** | String | Tên định danh theo chuẩn domain ngược (ví dụ: `com.github.micromdm.nanomdm`). Dùng để hệ điều hành nhận diện profile: nếu bạn cài lại profile có cùng Identifier, máy sẽ **cập nhật đè lên** thay vì cài trùng. |
| **`PayloadUUID`** | String | Chuỗi UUID v4 duy nhất toàn cầu. Apple dùng mã này để **liên kết chéo (cross-reference)** giữa các payload với nhau. |
| **`PayloadVersion`** | Integer | Phiên bản cấu trúc dữ liệu của Apple, giá trị mặc định luôn là `1`. |
| **`PayloadDisplayName`** | String | Tên hiển thị thân thiện hiển thị trên giao diện người dùng trong mục **Settings (Cài đặt) > VPN & Device Management** trên iOS/macOS. |
| **`PayloadContent`** | Array / Dict | Phần "ruột" chứa nội dung chi tiết của payload đó (mảng các payload con hoặc các tham số kỹ thuật). |

---

### Các tham số kỹ thuật cốt lõi cần hiểu rõ

#### 1. Trong Payload SCEP (`com.apple.security.scep`):
* **`URL`**: Đường dẫn thiết bị gọi tới để xin cấp cert (ví dụ qua Cloudflare Tunnel: `https://.../scep`).
* **`Key Type` & `Keysize`**: Tạo cặp khóa RSA 2048-bit trực tiếp trên phần cứng máy (Secure Enclave / Keychain).
* **`Key Usage: 5`**: Giá trị bitmask đại diện cho `Digital Signature (1) + Key Encipherment (4) = 5`. Đây là chuẩn bắt buộc cho chứng chỉ mTLS dùng để xác thực client.
* **`Challenge`**: Chuỗi mật khẩu bắt tay với SCEP Server nếu server có bật chế độ kiểm tra mật khẩu.

#### 2. Trong Payload MDM (`com.apple.mdm`):
* **`IdentityCertificateUUID`**: **Cực kỳ quan trọng.** Trường này chứa đúng giá trị `PayloadUUID` của Payload SCEP ở trên. Nhờ vậy, thiết bị biết lấy đúng chứng chỉ vừa được SCEP cấp để làm chứng chỉ định danh gửi lên MDM.
* **`Topic`**: Push Topic của Apple APNs mà bạn đã trích xuất từ `push.pem`.
* **`ServerURL`**: Đường dẫn mà thiết bị dùng để gửi bản tin `Authenticate`, `TokenUpdate` và nhận lệnh MDM từ NanoMDM.
* **`SignMessage: true`**:
  * **Tại sao bắt buộc khi dùng Cloudflare Tunnel?** Cloudflare Quick Tunnel (`trycloudflare.com`) không chuyển tiếp chứng chỉ client mTLS ở tầng kết nối TLS. Khi bật `SignMessage = true`, thiết bị Apple sẽ tự động ký số nội dung HTTP request bằng cert của nó và đặt vào header `Mdm-Signature`. NanoMDM sẽ đọc header này để trích xuất `device.crt` mà không cần mTLS ở tầng mạng.
* **`AccessRights: 8191`**: `8191` tương ứng với `0x1FFF` (bật toàn bộ bit cờ phân quyền quản trị trong chuẩn Apple: đọc thông tin máy, cài đặt/gỡ profile, khóa máy, xóa máy từ xa...).

---

## 7. Cấu Hình Web Portal Phục Vụ Tải Hồ Sơ (`serve.py`)

Do cả `scepserver` (chỉ là CA ký cert) lẫn `nanomdm` (chỉ là MDM engine) đều không có sẵn cổng phân phối file tĩnh, ta triển khai một Web Server mini bằng Python:

### Script `serve.py`
Script nằm tại `nanomdm-linux-amd64-v0.9.0/serve.py`, lắng nghe cổng `8000`:
* Cung cấp giao diện web thân thiện với nút bấm **"Cài Đặt Hồ Sơ MDM"**.
* **Đặc biệt quan trọng về MIME Type:** Đăng ký header HTTP:
  ```http
  Content-Type: application/x-apple-aspen-config
  ```
  Nhờ header này, trình duyệt Safari trên thiết bị Apple sẽ không tải file về dạng văn bản thô mà tự động kích hoạt trình cài đặt hồ sơ hệ thống (*"Trang web này đang cố gắng tải về một hồ sơ cấu hình..."*).

### Chạy Server & Tạo Public Tunnel:
```bash
# 1. Chạy Web Server Enrollment (Port 8000)
cd nanomdm-linux-amd64-v0.9.0
python3 serve.py

# 2. Tạo đường link Internet bằng Cloudflare Tunnel
cloudflared tunnel --url http://localhost:8000
```
Người dùng chỉ cần mở **Safari** trên iPhone/Mac và truy cập đường link Cloudflare vừa sinh ra để bắt đầu enroll.

---

## 8. Cơ Chế Sổ Cái CA `index.txt` & Xử Lý Lỗi `DN already exists`

### 1. File `index.txt` là gì? Nằm ở đâu?
* **Vị trí:** `scep/depot/index.txt` (được mount vào container SCEP tại `/depot/index.txt`).
* **Bản chất:** Đây là file cơ sở dữ liệu dạng bảng phẳng (flat-file) theo chuẩn của **OpenSSL CA**. Mỗi khi SCEP Server cấp một chứng chỉ mới, nó sẽ lưu 1 dòng vào file này:
  ```text
  V    270928155942Z    06    f4d430bc...6.pem    /CN=...
  ```
  * `V`: Trạng thái Valid (hợp lệ).
  * `270928...`: Ngày giờ hết hạn.
  * `06`: Số Serial cấp cho chứng chỉ.
  * Cột cuối: Tên định danh (Distinguished Name - DN).

### 2. Nguyên nhân lỗi `failed to sign CSR: err="DN already exists"`:
* Khi thiết bị gửi CSR lên SCEP mà không chỉ định trước trường `Subject` trong profile, thiết bị sẽ gửi DN rỗng (`dn = ""`).
* Mã nguồn `micromdm/scep` sử dụng hàm `strings.HasSuffix(line, "")` để kiểm tra tên DN trong file `index.txt`. Do mọi chuỗi đều có đuôi là `""`, SCEP nhận diện nhầm là bị trùng tên với một chứng chỉ đã cấp trước đó đang còn hạn (theo cơ chế kiểm tra gia hạn `-allowrenew 14`).

### 3. Cách xử lý triệt để:
1. **Dọn sạch sổ cái khi bị kẹt:**
   ```bash
   sudo truncate -s 0 scep/depot/index.txt
   ```
2. **Cấu hình SCEP Server luôn cho phép cấp phát mới:**
   Khi khởi động container SCEP, luôn truyền thêm tham số **`-allowrenew 0`**:
   ```bash
   docker run -it --rm -v ./depot:/depot -p 8080:8080 micromdm/scep:latest -allowrenew 0
   ```
   *(Cờ `-allowrenew 0` tắt hoàn toàn kiểm tra trùng lặp thời hạn, đảm bảo enroll hàng loạt thiết bị ổn định 100%).*

---

## 9. Quy Trình Enroll Thiết Bị Thực Tế & Nhật Ký Giao Tiếp (Logs)

### Các bước trên thiết bị Apple:
1. Mở **Safari** truy cập link portal (ví dụ: `https://...trycloudflare.com`).
2. Nhấn nút **"Cài Đặt Hồ Sơ MDM"** -> Chọn **Cho phép (Allow)**.
3. Vào **Settings (Cài đặt)** > **Profile Downloaded (Đã tải về hồ sơ)** > Bấm **Install (Cài đặt)** > Nhập mật khẩu máy và đồng ý tin cậy chứng chỉ CA.

### Luồng tương tác ngầm giữa Thiết bị và Hệ thống Server:

```text
[Thiết bị Apple]                       [SCEP Server]                  [NanoMDM Server]
       |                                     |                                |
       |--- 1. GET /scep?op=GetCACert ------>|                                |
       |<-- 2. Trả về ca.pem ----------------|                                |
       |                                     |                                |
       |--- 3. POST /scep?op=PKIOperation -->|                                |
       |<-- 4. Ký và trả về device.crt ------|                                |
       |                                                                      |
       |--- 5. PUT /mdm (Authenticate: Serial, Model, UDID) ----------------->|
       |<-- 6. 200 OK (Xác thực cert thành công) ----------------------------|
       |                                                                      |
       |--- (Thiết bị xin Push Token từ Apple APNs bằng Topic)                |
       |                                                                      |
       |--- 7. PUT /mdm (TokenUpdate: APNs Token, PushMagic) ---------------->|
       |<-- 8. 200 OK (Ghi nhận Push Token) ----------------------------------|
```

### Log thực tế chứng minh hoàn tất thành công:

#### 1. Phía SCEP Server (`PKIOperation` thành công):
```text
level=info ts=2026-09-28T15:59:41Z caller=logutil.go:70 component=http method=GET status=200 path="/scep?operation=GetCACert"
level=info ts=2026-09-28T15:59:41Z caller=logutil.go:70 component=http method=GET status=200 path="/scep?operation=GetCACaps"
ts=2026-09-28T15:59:42Z caller=scep.go:271 msg="parsed scep pkiMessage" scep_message_type="PKCSReq (19)"
ts=2026-09-28T15:59:42Z caller=scep.go:366 msg="decrypt pkiEnvelope" has_challenge=true
level=info ts=2026-09-28T15:59:42Z caller=service_logging.go:47 component=scep_service method=PKIOperation err=null took=54.192ms
level=info ts=2026-09-28T15:59:42Z caller=logutil.go:70 component=http method=POST status=200 path="/scep?operation=PKIOperation"
```

#### 2. Phía NanoMDM Server (Tiếp nhận danh tính và Push Token):
```text
ts=2026-09-28T22:59:43+07:00 level=info handler=log method=PUT path=/mdm agent=MDM/1.0
ts=2026-09-28T22:59:43+07:00 level=info service=certauth msg=cert associated enrollment=new id=00008140-000265A63652801C hash=f4d430bc105e545520b26f774679f8973a99f6e9dc983a9d59a4a543b46caade
ts=2026-09-28T22:59:43+07:00 level=info service=nanomdm id=00008140-000265A63652801C type=Device msg=Authenticate serial_number=HG3Q25R61Y
ts=2026-09-28T22:59:43+07:00 level=info handler=log method=PUT path=/mdm agent=MDM/1.0
ts=2026-09-28T22:59:43+07:00 level=info service=nanomdm id=00008140-000265A63652801C type=Device msg=TokenUpdate
```

*Ý nghĩa các sự kiện:*
* `cert associated`: Bóc tách `device.crt` từ header client, xác thực chữ ký CA thành công và lưu liên kết cert hash `f4d430bc...` với máy.
* `Authenticate`: Thiết bị chính thức đăng ký danh tính (UDID: `00008140-000265A63652801C`, Serial Number: `HG3Q25R61Y`).
* `TokenUpdate`: Thiết bị xin thành công **APNs Push Token** từ Apple và nộp về cho NanoMDM lưu lại.

#### 3. Dữ liệu lưu trữ trong Database NanoMDM (`dbkv/`):
```text
nanomdm-linux-amd64-v0.9.0/dbkv/
├── cert_auth/f4/d4/f4d430bc...hash_cert       # Liên kết cert hash -> UDID
└── enrollments/00/00/00008140-000265A63652801C/
    ├── .token                                 # Push Token do Apple APNs cấp
    ├── .push_magic                            # Khóa PushMagic
    ├── .topic                                 # com.apple.mgmt.External.6a0a852b-...
    ├── .enrolled_at                           # Thời gian đăng ký
    └── .last_seen_at                          # Lần tương tác gần nhất
```

---

## 10. Hướng Dẫn Ra Lệnh & Giám Sát Thiết Bị (Device Management & Monitoring)

Sau khi thiết bị đã enroll thành công, máy chủ có thể gửi lệnh điều khiển và giám sát từ xa thông qua mạng **Apple APNs**.

### 1. Cơ chế gửi lệnh của NanoMDM
NanoMDM tách biệt 2 công việc:
1. **Tạo lệnh (Generator):** Sử dụng script `cmdr.py` để sinh ra nội dung gói tin XML Plist chuẩn của Apple ra `stdout`.
2. **Nạp lệnh vào hàng đợi (Enqueue API):** Dùng lệnh `curl` gửi nội dung XML này qua phương thức `PUT` vào endpoint `/v1/enqueue/<UDID>` của NanoMDM.

### 2. Lệnh truy vấn thông tin thiết bị (`DeviceInformation`)

Chạy lệnh sau để yêu cầu thiết bị gửi về các thông số phần cứng, hệ điều hành và trạng thái pin:
```bash
python3 cmdr.py DevInfo OSVersion Model DeviceName BatteryLevel WiFiMAC BluetoothMAC SerialNumber | \
curl -s -T - -u nanomdm:nanomdm 'http://127.0.0.1:9000/v1/enqueue/<UDID>'
```
*(Thay `<UDID>` bằng mã máy của bạn, ví dụ: `00008140-000265A63652801C`).*

**Kết quả phản hồi khi nạp lệnh thành công:**
```json
{
    "status": {
        "00008140-000265A63652801C": {
            "push_result": "2F972609-B533-67B5-0ADF-0AB1D0AC1E02"
        }
    },
    "command_uuid": "56f4ffab-2a33-4884-bb53-0b4559defb0f",
    "request_type": "DeviceInformation"
}
```
* `push_result`: Mã xác nhận `apns-id` do chính Apple APNs Gateway trả về, chứng minh tín hiệu đánh thức máy đã được Apple tiếp nhận và bắn thẳng tới điện thoại.

---

### 3. Xem báo cáo phản hồi từ thiết bị

Sau vài giây, thiết bị Apple sẽ tự động thức dậy, thực thi lệnh và gửi kết quả về máy chủ. Kết quả được lưu tại thư mục:
```text
nanomdm-linux-amd64-v0.9.0/dbkv/queue/00/00/<UDID>.<COMMAND_UUID>.queueitem.report
```

Xem kết quả phản hồi của thiết bị:
```bash
cat nanomdm-linux-amd64-v0.9.0/dbkv/queue/*/*/<UDID>.*.queueitem.report
```

**Dữ liệu thực tế iPhone báo cáo về:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>CommandUUID</key>
	<string>56f4ffab-2a33-4884-bb53-0b4559defb0f</string>
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
		<real>0.34999999999999998</real>
	</dict>
</dict>
</plist>
```

* **`Status = Acknowledged`**: Thiết bị xác nhận đã thực thi lệnh thành công.
* **`DeviceName`**: Tên hiển thị của máy (`iPhone của VCS`).
* **`Model`**: Mã dòng máy (`MYNE3VN`).
* **`OSVersion`**: Phiên bản iOS đang chạy (`26.6.1`).
* **`BatteryLevel`**: Mức pin hiện tại (`0.35` ~ `35%`).

---

### 4. Danh sách các trường có thể giám sát (`Queries`):

Bạn có thể truyền thêm bất kỳ trường nào dưới đây vào lệnh `DevInfo`:
* `DeviceName`: Tên thiết bị
* `Model`: Model máy
* `OSVersion`: Phiên bản hệ điều hành
* `BatteryLevel`: Mức pin
* `SerialNumber`: Số Serial
* `WiFiMAC`, `BluetoothMAC`: Địa chỉ MAC mạng
* `IsDeviceLocatorActive`: Trạng thái bật/tắt Tìm iPhone (Find My)
* `IsSupervised`: Máy có đang bật chế độ Giám sát (Supervised) không
* `AvailableDeviceCapacity`: Dung lượng bộ nhớ còn trống

---

### 5. Một số lệnh quản trị hữu ích khác:

| Lệnh | Cú pháp thực thi | Chức năng |
| :--- | :--- | :--- |
| **Kiểm tra bảo mật** | `python3 cmdr.py SecurityInfo \| curl -s -T - -u nanomdm:nanomdm 'http://127.0.0.1:9000/v1/enqueue/<UDID>'` | Kiểm tra passcode, trạng thái mã hóa, FaceID/TouchID. |
| **Danh sách chứng chỉ** | `python3 cmdr.py CertificateList \| curl -s -T - -u nanomdm:nanomdm 'http://127.0.0.1:9000/v1/enqueue/<UDID>'` | Liệt kê tất cả chứng chỉ số đang cài trên máy. |
| **Khóa máy từ xa** | `python3 cmdr.py DeviceLock --pin 123456 \| curl -s -T - -u nanomdm:nanomdm 'http://127.0.0.1:9000/v1/enqueue/<UDID>'` | Khóa màn hình thiết bị ngay lập tức bằng mã PIN. |
| **Khởi động lại máy** | `python3 cmdr.py RestartDevice \| curl -s -T - -u nanomdm:nanomdm 'http://127.0.0.1:9000/v1/enqueue/<UDID>'` | Yêu cầu máy khởi động lại từ xa. |

---

## 11. Các Lưu Ý Sống Còn (Important Notes)

1. **Bản chất của Cloudflare Quick Tunnel (`trycloudflare.com`):**
   - Quick Tunnel là kết nối tạm thời. Nếu bạn dừng hoặc khởi động lại tiến trình `cloudflared`, Cloudflare sẽ sinh ra một URL subdomain ngẫu nhiên mới.
   - Khi đó, bạn **phải cập nhật lại `URL` (SCEP) và `ServerURL` (MDM)** trong file `enroll.mobileconfig` trước khi mang đi cài cho thiết bị mới.
2. **Chu kỳ gia hạn Push Certificate (Renew hàng năm):**
   - Apple MDM Push Certificate có hạn **365 ngày** (1 năm).
   - Hàng năm, bạn **bắt buộc phải đăng nhập đúng tài khoản Apple ID cũ** trên trang `identity.apple.com/pushcert` và bấm **Renew**.
   - Tuyệt đối **không bấm Create a Certificate mới** bằng Apple ID khác khi đã có thiết bị đang quản lý, vì tạo mới sẽ sinh ra Push Topic khác, khiến toàn bộ thiết bị cũ mất khả năng nhận lệnh và phải thu hồi enroll lại từ đầu.
3. **Bảo mật Private Key:**
   - File `mdmcert.download.push.key` và `push.pem` tuyệt đối không để lộ hoặc làm mất, vì không thể khôi phục private key nếu bị xóa.
