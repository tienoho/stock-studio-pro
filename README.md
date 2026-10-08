# ⚡ AutoStock Studio v1.0

> **All-in-One AI Video Production Suite & Multi-Source Stock Media Downloader**  
> Thiết kế theo phong cách **Obsidian Dark & Electric Neon** hiện đại, xây dựng trên nền tảng **Clean Code & SOLID Architecture**, tích hợp trọn bộ quy trình từ kịch bản phân đoạn Claude JSON đến Stock Media, AI Voice, Khớp tiếng và Tự động hóa Workflow.

---

## 🌟 Tính Năng Nổi Bật (Key Features)

- 🎞️ **Multi-Source Stock Downloader**:
  - Tải video & ảnh độ phân giải cao tự động từ **Pexels**, **Pixabay**, **Vecteezy**.
  - Hỗ trợ tải thủ công thông minh từ **MotionArray** với bộ quét thư mục tải về (Downloads Watcher) tự phân loại theo từng Scene.
  - Xoay vòng đa tầng nhiều API Key thông minh (Round-robin), chống chạm giới hạn Rate Limit.
  - Cơ chế **Anti-Block & Adaptive Rate Limiting**: Tự điều chỉnh độ trễ tải, phát hiện lỗi 403 để tạm dừng cooldown an toàn.
  - Trình xem trước Video & Ảnh độ nét cao với điều khiển phát lại chuẩn xác.

- ✂️ **Cut & Mix Studio**:
  - Tự động cắt ngẫu nhiên các đoạn video ngắn (0.5s - 60s) từ kho media của từng phân cảnh.
  - Tự động xuất ra nhiều phiên bản video ghép thành phẩm (Final outputs) hoàn chỉnh bằng FFmpeg.

- 🎙️ **Voice TXT Studio**:
  - Tích hợp tạo giọng đọc AI từ văn bản hoặc kịch bản phân đoạn 20 phần.
  - Tích hợp **Microsoft Edge TTS** bản địa thuần Python (Hoài My, Nam Minh, Jenny...) miễn phí chất lượng cao, không cần Node.js.
  - Ghép và đồng bộ file phụ đề `.srt` thông minh với thời gian nghỉ linh hoạt.

- 🎬 **Scene Voice Matching**:
  - Tự động cắt ghép và khớp video cảnh tương ứng với từng câu thoại / giọng đọc voice bằng **Native FFmpeg Processor**.
  - Không phụ thuộc script ngoài, tự động scale 1080p, cắt ngẫu nhiên hoặc tuần tự và xuất video master hoàn chỉnh.

- 🧩 **Visual Workflow Canvas & Auto Mode**:
  - Hệ thống nút kéo thả (Node-based) kết nối trực quan toàn bộ các bước: *Load JSON $\rightarrow$ Search Stock $\rightarrow$ Random Select $\rightarrow$ Download $\rightarrow$ Cut/Mix $\rightarrow$ Create Voice $\rightarrow$ Voice Match*.
  - Giao diện ma trận lưới Dot Matrix hiện đại, cuộn chuột Zoom in/out mượt mà, căn chỉnh tự động (Auto-layout).
  - Đèn báo trạng thái trực tiếp cho từng Node (Idle, Đang chạy, Thành công, Lỗi).
  - Phím tắt năng suất cao: `Ctrl+1..6` (chuyển tab), `Ctrl+S` (lưu phiên vào SQLite), `F5` (chạy quy trình).
  - Lưu và nạp các preset mẫu quy trình một chạm bằng SQLite & JSON.

---

## 🏛️ Kiến Trúc Mã Nguồn (Architecture Overview)

Dự án được tái cấu trúc hoàn toàn theo nguyên lý **Clean Architecture** và **SOLID**:

```
stock-studio-pro/
├── .github/
│   └── workflows/
│       ├── ci.yml                       # 🔄 CI: Lint, compileall, automated testing (Qt offscreen)
│       └── release.yml                  # 🚀 CD: Automated PyInstaller build & GitHub Release
├── main.py                          # 🚀 Entry point chính của ứng dụng
├── run.bat                          # ⚡ Khởi chạy ứng dụng từ mã nguồn Python
├── run_exe.bat                      # 📦 Khởi chạy bản phát hành độc lập AutoStockStudio.exe
├── build.bat                        # 🛠️ Đóng gói Portable Release bằng PyInstaller
├── build_release.py                 # 📦 Kịch bản đóng gói tự động & tạo file ZIP phát hành
├── run_tests.py                     # 🧪 Trình chạy tự động toàn bộ Unit Tests
├── AutoStockStudio.spec             # ⚙️ Cấu hình đóng gói PyInstaller
├── requirements.txt                 # 📋 Danh sách thư viện Python
├── tests/                           # 🧪 Bộ Unit Test tự động (63 tests)
│   ├── test_core_models.py
│   ├── test_part_merger.py
│   ├── test_rate_limiter.py
│   ├── test_key_manager.py
│   ├── test_persistence.py
│   ├── test_ffmpeg_processor.py
│   ├── test_scene_voice_matcher.py
│   ├── test_edge_tts_service.py
│   ├── test_i18n.py
│   ├── test_ui_interactions.py
│   └── test_bug_fixes.py
└── src/
    ├── core/                        # 🎯 Tầng Domain & Entities
    │   ├── constants.py             # Hằng số, giới hạn API, tokens màu sắc
    │   ├── exceptions.py            # Domain exceptions (AutoStockError)
    │   ├── i18n/                    # I18nService, locales (vi.json, en.json)
    │   ├── interfaces/              # Abstractions (IMediaProvider, IRateLimiter, IConfigRepository...)
    │   └── models/                  # MediaItem, Scene, APIKey, Workflow data models
    ├── infrastructure/              # 🔌 Tầng Hạ Tầng Ngoại Vi
    │   ├── persistence/             # SqliteDatabase, SqliteConfigRepo, SqliteStateRepo, SqliteDownloadsRepo...
    │   ├── network/                 # AdaptiveRateLimiter, BlockDetector
    │   ├── media/                   # ThumbnailCache, FFmpegProcessor
    │   ├── providers/               # PexelsProvider, PixabayProvider, VecteezyProvider
    │   └── watcher/                 # DownloadsWatcher
    ├── application/                 # ⚙️ Tầng Nghiệp Vụ (Application Services)
    │   └── services/                # KeyManager, PartMerger, SmartDownloader, VideoCutService, SceneVoiceMatcher, EdgeTTSService
    └── ui/                          # 🖥️ Tầng Giao Diện Người Dùng (PyQt6)
        ├── main_window.py           # AutoStockMainWindow (Thin Controller)
        ├── styles/                  # theme.qss, tokens.py, vector SVG icon engine
        ├── components/              # StatBox, SceneListItem, ThumbnailCard, StatusPanel, ToastNotification...
        ├── dialogs/                 # SettingsDialog, JsonInputDialog, KeyManagementDialog, AssignSceneDialog
        ├── workers/                 # SearchWorker, DownloadWorker, VideoCutMergeWorker
        ├── workflow/                # WorkflowCanvas, WorkflowNodeItem, NodeToolWorker
        └── tabs/                    # DownloaderTab, CutMixTab, VoiceTab, SceneVoiceTab, AutoTab, WorkflowTab
```

---

## 🚀 Hướng Dẫn Cài Đặt & Chạy (Quick Start)

### 1. Yêu Cầu Hệ Thống
- **Hệ điều hành**: Windows 10 / 11 (64-bit)
- **Python**: Phiên bản 3.10 trở lên (khuyên dùng Python 3.11 - 3.13)
- **FFmpeg**: Có sẵn trong PATH để xử lý video & voice

### 2. Cài Đặt Thư Viện

```bash
git clone https://github.com/tienoho/stock-studio-pro.git
cd stock-studio-pro

pip install -r requirements.txt
```

### 3. Khởi Chạy Ứng Dụng

- **Cách 1 (Khuyên dùng)**: Nhấp đúp chuột vào file **`run.bat`** (hoặc **`run_exe.bat`** nếu chạy bản Portable .exe).
- **Cách 2**: Chạy qua dòng lệnh:
  ```bash
  python main.py
  ```

### 4. Chạy Kiểm Thử Tự Động (Unit Tests)

Dự án trang bị 63 unit tests tự động:
```bash
python run_tests.py
```
*Ghi chú trong môi trường CI không có màn hình*: Chạy với biến môi trường `QT_QPA_PLATFORM=offscreen`.

### 5. Đóng Gói Thành Bản Cài Đặt Độc Lập (.exe & .zip)

- **Cách 1**: Nhấp đúp chuột vào file **`build.bat`**.
- **Cách 2**: Chạy kịch bản tự động hóa Python:
  ```bash
  python build_release.py
  ```
Kịch bản sẽ tự động chạy toàn bộ bộ test, biên dịch PyInstaller, tạo thư mục `release_autostock_studio/` và nén thành `dist/AutoStockStudio-windows-x64.zip`.

---

## 🔄 Tích Hợp Luồng CI / CD (GitHub Actions)

Dự án đã được tích hợp quy trình CI/CD chuẩn công nghiệp:

### 1. Luồng CI (`.github/workflows/ci.yml`)
- **Kích hoạt**: Tự động chạy khi có `push` hoặc `pull_request` vào nhánh `main` / `master`.
- **Giai đoạn 1 (Code Quality)**:
  - Kiểm tra cú pháp bytecode với `python -m compileall`.
  - Quét lỗi cú pháp và undefined names với `flake8`.
- **Giai đoạn 2 (Automated Tests)**:
  - Chạy ma trận kiểm thử trên môi trường Windows (`windows-latest`) trên cả Python 3.10 và Python 3.11.
  - Sử dụng chế độ `QT_QPA_PLATFORM=offscreen` đảm bảo chạy mượt mà, không phụ thuộc vào màn hình hiển thị.

### 2. Luồng CD (`.github/workflows/release.yml`)
- **Kích hoạt**: Tự động khi gắn tag phiên bản (`git tag v1.0.0 && git push --tags`) hoặc kích hoạt thủ công qua giao diện `workflow_dispatch`.
- **Quy trình đóng gói**:
  - Chạy lại toàn bộ bộ kiểm thử để xác nhận chất lượng trước khi phát hành.
  - Biên dịch PyInstaller với cấu hình tối ưu.
  - Đóng gói file `AutoStockStudio-windows-x64.zip` và upload lên GitHub Actions Artifacts.
  - Tự động tạo bản **GitHub Release** đính kèm file ZIP và tự động tạo ghi chú phát hành (release notes).

---

## ⚙️ Cấu Hình API Keys

1. Khởi động ứng dụng, bấm vào nút **"⚙️ Cài đặt & API Keys"** ở thanh công cụ bên trái.
2. Thêm API Key cho các nền tảng mong muốn:
   - **Pexels API**: [Lấy key miễn phí](https://www.pexels.com/api/)
   - **Pixabay API**: [Lấy key miễn phí](https://pixabay.com/api/docs/)
   - **Vecteezy API**: [Lấy key miễn phí](https://www.vecteezy.com/api-docs/index.html)
3. Có thể thêm nhiều key cho cùng một nền tảng để ứng dụng tự động xoay vòng. Các key được tự động mã hóa Base64 khi lưu vào ổ đĩa.

---

## 📄 Bản Quyền & Giấy Phép
Dự án phát triển phục vụ mục đích tự động hóa sản xuất nội dung video tin tức & tài chính.
