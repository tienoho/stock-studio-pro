# ⚡ 1Click Stock Studio Pro v5.1

> **All-in-One AI Video Production Suite & Multi-Source Stock Media Downloader**  
> Thiết kế theo phong cách **Obsidian Dark & Electric Neon** hiện đại, tích hợp trọn bộ quy trình từ kịch bản phân đoạn Claude JSON đến Stock Media, AI Voice, Khớp tiếng và Tự động hóa Workflow.

---

## 🌟 Tính Năng Nổi Bật (Key Features)

- 🎞️ **Multi-Source Stock Downloader**:
  - Tải video & ảnh độ phân giải cao tự động từ **Pexels**, **Pixabay**, **Vecteezy**.
  - Hỗ trợ tải thủ công thông minh từ **MotionArray** với bộ quét thư mục tải về (Downloads Watcher) tự phân loại theo từng Scene.
  - Xoay vòng đa tầng nhiều API Key thông minh, chống chạm giới hạn Rate Limit.
  - Trình xem trước Video & Ảnh độ nét cao với điều khiển phát lại chuẩn xác.

- ✂️ **Cut & Mix Studio**:
  - Tự động cắt ngẫu nhiên các đoạn video ngắn (0.5s - 60s) từ kho media của từng phân cảnh.
  - Tự động xuất ra nhiều phiên bản video ghép thành phẩm (Final outputs) hoàn chỉnh.

- 🎙️ **Voice TXT Studio**:
  - Tích hợp tạo giọng đọc AI từ văn bản hoặc kịch bản phân đoạn 20 phần.
  - Ghép và đồng bộ file phụ đề `.srt` thông minh với thời gian nghỉ linh hoạt.

- 🎬 **Scene Voice Matching**:
  - Tự động cắt ghép và khớp video cảnh tương ứng với từng câu thoại / giọng đọc voice bằng FFmpeg.

- 🧩 **Visual Workflow Canvas & Auto Mode**:
  - Hệ thống nút kéo thả (Node-based) kết nối trực quan toàn bộ các bước: *Load JSON $\rightarrow$ Search Stock $\rightarrow$ Random Select $\rightarrow$ Download $\rightarrow$ Cut/Mix $\rightarrow$ Create Voice $\rightarrow$ Voice Match*.
  - Lưu và nạp các preset mẫu quy trình một chạm.

---

## 🚀 Hướng Dẫn Cài Đặt & Chạy (Quick Start)

### 1. Yêu Cầu Hệ Thống
- **Hệ điều hành**: Windows 10 / 11 (64-bit)
- **Python**: Phiên bản 3.10 trở lên
- **FFmpeg**: (Khuyến nghị cài đặt để sử dụng tính năng ghép video & khớp voice)

### 2. Cài Đặt Thư Viện

```bash
git clone https://github.com/khanh1234ttl-code/stock-studio-pro.git
cd stock-studio-pro

pip install -r requirements.txt
```

### 3. Khởi Chạy Ứng Dụng

- **Cách 1**: Nhấp đúp chuột vào file **`RUN_STUDIO_v5.1.bat`** (hoặc `chay_v5.bat`).
- **Cách 2**: Chạy qua Terminal:
  ```bash
  python stock_preview_v5.py
  ```

---

## ⚙️ Cấu Hình API Keys

1. Khởi động ứng dụng, bấm vào nút **"⚙️ Cài đặt & API Keys"** ở góc trái.
2. Thêm API Key cho các nền tảng mong muốn:
   - **Pexels API**: [Lấy key miễn phí](https://www.pexels.com/api/)
   - **Pixabay API**: [Lấy key miễn phí](https://pixabay.com/api/docs/)
   - **Vecteezy API**: [Lấy key miễn phí](https://www.vecteezy.com/api-docs/index.html)
3. Có thể thêm nhiều key cho cùng một nền tảng để ứng dụng tự động xoay vòng.

---

## 🛠️ Cấu Trúc Dự Án (Project Structure)

```
stock-studio-pro/
├── stock_preview_v5.py      # Source code chính của ứng dụng PyQt6
├── RUN_STUDIO_v5.1.bat      # File khởi chạy nhanh v5.1
├── chay_v5.bat              # File khởi chạy dự phòng
├── BUILD_RELEASE_v5.bat     # Kịch bản đóng gói PyInstaller Standalone
├── requirements.txt         # Danh sách thư viện Python
├── .gitignore               # Cấu hình bỏ qua file nhạy cảm và build cache
└── README.md                # Tài liệu hướng dẫn sử dụng
```

---

## 📄 Bản Quyền & Giấy Phép
Dự án phát triển phục vụ mục đích tự động hóa sản xuất nội dung video tin tức & tài chính.
