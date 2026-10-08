# ⚡ AutoStock Studio Pro (v1.1 Enterprise)

> **All-in-One AI Video Production Suite & Multi-Source Stock Media Downloader**  
> Thiết kế theo phong cách **Obsidian Dark & Clean Light Modern**, xây dựng trên nền tảng **Clean Architecture & SOLID Principles**, tích hợp trọn bộ quy trình từ kịch bản phân đoạn Claude JSON đến Stock Media, AI Voiceover, Khớp hình & tiếng tự động, và Visual Workflow Node Canvas.

---

## 🌟 Tính Năng Nổi Bật (Key Features)

### 🎞️ 1. Multi-Source Stock Media Downloader (6 Nền Tảng Tài Nguyên)
- **Nguồn Miễn Phí Hoàn Toàn (Zero API Key)**:
  - 🌐 **Wikimedia Commons**: Kho tư liệu khổng lồ của Wikimedia Foundation với hàng triệu ảnh và video chất lượng cao (WebM/MP4). **Hoàn toàn miễn phí 100%, không cần đăng ký tài khoản hay API key**.
  - 🎨 **Openverse**: Hơn 700 triệu tác phẩm ảnh Creative Commons & Public Domain từ WordPress Foundation. **Tự do tìm kiếm và tải về tức thì, không cần API key**.
- **Nguồn Stock Chuyên Nghiệp (Có API Key & Quét Tải Về)**:
  - 📸 **Pexels & Pixabay**: Kho ảnh và video 4K phong phú, tích hợp xoay vòng API key thông minh (Round-Robin).
  - 🎥 **Coverr**: Kho footage video miễn phí cho nhà sáng tạo nội dung, hỗ trợ xác thực qua Coverr API Key.
  - 🎨 **Vecteezy**: Kho vector và hình ảnh chất lượng cao.
  - ⚡ **MotionArray Assistant**: Giám sát thư mục tải về (Downloads Watcher), tự động nhận diện tệp tải thủ công từ MotionArray và tự động gán vào đúng phân cảnh (Scene).
- **Cơ chế Chống Khóa (Anti-Block) & Bộ Đệm Thích Ứng**:
  - `AdaptiveRateLimiter`: Tự động đo lường và thích ứng độ trễ mạng để không bị máy chủ CDN chặn.
  - `BlockDetector`: Nhận diện phản hồi 403 Forbidden và tự kích hoạt khoảng nghỉ Cooldown an toàn.
  - `ThumbnailCache`: Bộ đệm ảnh 2 tầng (Disk Cache + Bounded LRU Memory Cache), overlay huy hiệu thời lượng video tự động.
  - Trình xem trước độ nét cao (`PreviewModal`) tích hợp trình phát video đa phương tiện và nút *Xem Nguồn* trên trình duyệt web.

### ✂️ 2. Cut & Mix Studio
- Tự động cắt ngẫu nhiên các đoạn video ngắn (0.5s – 60s) từ kho media thu thập được của từng phân cảnh.
- Loại bỏ thông minh các video định dạng dọc (9:16) để đảm bảo thành phẩm 16:9 1080p đồng nhất.
- Hỗ trợ xuất ngẫu nhiên nhiều phiên bản hoàn chỉnh (*Final outputs*) cho mỗi cảnh với bộ chuyển mã FFmpeg nội tại.

### 🎙️ 3. Voice TXT Studio & Đồng Bộ Phụ Đề
- **Native Microsoft Edge TTS**: Tích hợp công nghệ giọng đọc AI tự nhiên bản địa thuần Python (Hoài My, Nam Minh, Jenny, Guy, Aria...). Hoàn toàn miễn phí, không yêu cầu Node.js hay API key ngoài.
- Tự động tạo giọng đọc hàng loạt từ các tệp văn bản lẻ hoặc kịch bản phân đoạn JSON.
- **Subtitle Service**: Tự động sinh file phụ đề `.srt` bám sát từng từ đọc, hỗ trợ ghép nhiều tệp `.srt` thành một kịch bản hoàn chỉnh với khoảng nghỉ tùy chỉnh (`gap_ms`).
- **Master Audio Concatenator**: Hỗ trợ ghép nối liên tục toàn bộ các câu thoại (`.mp3`, `.wav`, `.aac`, `.m4a`) thành một tệp âm thanh tổng thể (*Master Voice*).

### 🎬 4. Native Scene Voice Matching (Khớp Video Với Lời Thoại)
- Tự động đo thời lượng từng câu thoại từ file `.srt`, tệp âm thanh lẻ hoặc kịch bản JSON.
- Tự động cắt video/ảnh tương ứng của từng phân cảnh theo đúng độ dài giọng đọc bằng **FFmpegProcessor**.
- Hỗ trợ scale chuẩn 1920x1080 30fps Lanczos, tự động lặp (loop) video nếu footage ngắn hơn giọng đọc, hoặc chèn clip màu bảo toàn timeline nếu thiếu media.
- Tự động hòa âm giọng đọc (*Audio Muxing*) và ghép nối toàn bộ các đoạn thành video master hoàn chỉnh.

### 🧩 5. Visual Workflow Canvas & Chế Độ Auto
- **Node Canvas Kéo Thả Trực Quan**: Kết nối logic toàn bộ quy trình: *Load JSON $\rightarrow$ Search Stock $\rightarrow$ Random Select $\rightarrow$ Download $\rightarrow$ Cut/Mix $\rightarrow$ Create Voice $\rightarrow$ Voice Match*.
- Đèn báo trạng thái thời gian thực cho từng node (Idle, Running, Success, Error).
- Giao diện ma trận chấm (Dot Matrix) hiện đại, cuộn chuột Zoom in/out, tự động dàn trang (Auto-layout).
- Quản lý và lưu trữ preset mẫu quy trình một chạm vào cơ sở dữ liệu SQLite.

### 💾 6. Enterprise SQLite Persistence
- Toàn bộ dữ liệu cấu hình, lịch sử tải về, trạng thái phiên làm việc và mẫu quy trình được lưu trữ bền vững trong cơ sở dữ liệu **SQLite**.
- Tự động di chuyển (Auto-migration) an toàn từ các định dạng cấu hình cũ (JSON / Pickle) sang SQLite khi khởi động ứng dụng.

### 🚀 7. Enterprise Auto-Updater & In-Place Installer
- Tự động kiểm tra bản cập nhật mới từ **GitHub Releases** khi mở ứng dụng.
- Tải về nền theo luồng (Streaming Background Download) với hiển thị phần trăm, dung lượng và tốc độ tải thực (MB/s).
- Kiểm tra tính toàn vẹn gói nén ZIP và giải nén an toàn chống lỗ hổng Zip Slip.
- Tự động cài đặt tại chỗ (In-Place Auto-Installer): Tự động sinh kịch bản ngầm (`_apply_update.bat`), thay thế tệp và khởi động lại ứng dụng mượt mà không cần người dùng can thiệp thủ công.

### 📜 8. Universal Script Ingestion (Đa Định Dạng Kịch Bản Toàn Diện)
- **Hỗ Trợ 5+ Định Dạng Kịch Bản Phổ Biến**:
  - 📄 **JSON (`.json`)**: Kịch bản Claude AI, OpenAI, hoặc cấu trúc phân cảnh tùy biến.
  - 📝 **Văn Bản Thuần (`.txt`)**: Tự động bóc tách phân cảnh có đánh số (`Cảnh 1:`, `Scene 1:`, `Phần 1:`), mốc thời gian (`[00:00 - 00:05]`, `(5s)`), từ khóa đi kèm (`| Từ khóa: ...`), hoặc từng đoạn văn bản.
  - 💬 **Phụ Đề Video (`.srt`)**: Bóc tách chỉ số phân cảnh, timecode chuẩn xác từng mili-giây, tính toán thời lượng và chuyển phụ đề thành thoại kịch bản.
  - 📊 **Bảng Tính Excel (`.xlsx`, `.xls`) & CSV/TSV (`.csv`, `.tsv`)**: Tự động ánh xạ thông minh các cột tiếng Việt & tiếng Anh (`Cảnh / STT / Scene`, `Lời thoại / Nội dung`, `Từ khóa / Keywords`, `Thời lượng / Duration`). Tích hợp engine thuần XML/ZIP dự phòng.
- **Trích Xuất Từ Khóa Tự Động (Smart Keyword Extractor)**:
  - Tự động làm sạch, lọc từ dừng (Stopwords tiếng Việt & tiếng Anh), nhận diện cụm danh từ và vị trí địa danh, sinh bộ từ khóa tìm kiếm stock media tối ưu (`primary_keywords`, `secondary_keywords`).
- **Kéo Thả Trực Quan (Drag & Drop Everywhere)**:
  - Kéo thả tệp bất kỳ (`.json`, `.txt`, `.srt`, `.xlsx`, `.csv`) vào cửa sổ chính hoặc thanh Timeline để nạp kịch bản tức thì.

---

## 🏛️ Kiến Trúc Mã Nguồn (Clean Architecture & SOLID)

Mã nguồn được phân tách chặt chẽ theo các tầng độc lập, tuân thủ nguyên lý Đảo ngược Phụ thuộc (DIP) và Đơn trách nhiệm (SRP):

```
stock-studio-pro/
├── .github/
│   └── workflows/
│       ├── ci.yml                       # 🔄 CI: Code quality (flake8), compileall, 119 unit tests (Qt offscreen)
│       └── release.yml                  # 🚀 CD: PyInstaller packaging & automated GitHub Release
├── main.py                              # 🚀 Điểm khởi chạy chính của ứng dụng
├── run.bat                              # ⚡ Khởi chạy nhanh ứng dụng từ mã nguồn Python
├── run_exe.bat                          # 📦 Khởi chạy bản phát hành độc lập AutoStockStudio.exe
├── build.bat                            # 🛠️ Đóng gói bản Portable Release bằng PyInstaller
├── build_release.py                     # 📦 Kịch bản đóng gói tự động & tạo file ZIP phát hành
├── run_tests.py                         # 🧪 Trình chạy tự động toàn bộ Unit Tests (119 tests)
├── AutoStockStudio.spec                 # ⚙️ Cấu hình đóng gói PyInstaller
├── requirements.txt                     # 📋 Danh sách thư viện Python
├── tests/                               # 🧪 Bộ Unit Test tự động (119 tests)
│   ├── test_clean_architecture.py       # Kiểm thử tuân thủ SOLID & Interface Liskov
│   ├── test_free_providers.py           # Kiểm thử Wikimedia, Openverse, Coverr & Zero-key
│   ├── test_core_models.py              # Kiểm thử Scene, format_duration, srt_time_to_seconds
│   ├── test_part_merger.py              # Kiểm thử gộp kịch bản Claude đa phân đoạn
│   ├── test_rate_limiter.py             # Kiểm thử Adaptive Rate Limiter & Block Detector
│   ├── test_key_manager.py              # Kiểm thử xoay vòng API Key & giới hạn hạn mức
│   ├── test_persistence.py              # Kiểm thử SQLite Config, State, History Repositories
│   ├── test_ffmpeg_processor.py         # Kiểm thử wrapper FFmpeg CLI & xử lý video
│   ├── test_scene_voice_matcher.py      # Kiểm thử cắt ghép video theo thời lượng giọng đọc
│   ├── test_edge_tts_service.py         # Kiểm thử tổng hợp giọng đọc Edge TTS & SubMaker
│   ├── test_i18n.py                     # Kiểm thử hệ thống đa ngôn ngữ (Tiếng Việt / English)
│   ├── test_ui_interactions.py          # Kiểm thử tương tác UI, phím tắt & Stepper pipeline
│   ├── test_update_checker.py           # Kiểm thử kiểm tra phiên bản & kịch bản cập nhật
│   └── test_theme_manager.py            # Kiểm thử giao diện Obsidian Dark & Light theme
└── src/
    ├── core/                            # 🎯 Tầng Domain & Entities
    │   ├── constants.py                 # Hằng số hệ thống, giới hạn tải, bảng màu tokens
    │   ├── exceptions.py                # Định nghĩa các ngoại lệ nghiệp vụ (AutoStockError)
    │   ├── i18n/                        # I18nService & từ điển ngôn ngữ (vi.json, en.json)
    │   ├── interfaces/                  # Interface trừu tượng (IMediaProvider, IConfigRepository...)
    │   └── models/                      # MediaItem, Scene, APIKey, Workflow data models
    ├── infrastructure/                  # 🔌 Tầng Hạ Tầng Ngoại Vi (Frameworks & Drivers)
    │   ├── persistence/                 # SqliteDatabase, SqliteConfigRepo, SqliteStateRepo, SqliteDownloadsRepo
    │   ├── network/                     # AdaptiveRateLimiter, BlockDetector, User-Agent rotator
    │   ├── media/                       # ThumbnailCache (LRU bounded), FFmpegProcessor
    │   ├── providers/                   # WikimediaProvider, OpenverseProvider, CoverrProvider, PexelsProvider, PixabayProvider, VecteezyProvider
    │   └── watcher/                     # DownloadsWatcher (giám sát thư mục tải về)
    ├── application/                     # ⚙️ Tầng Nghiệp Vụ (Application Services)
    │   └── services/                    # MediaProviderRegistry, KeyManager, PartMerger, SmartDownloader, VideoCutService, SceneVoiceMatcher, EdgeTTSService, SubtitleService, UpdateChecker
    └── ui/                              # 🖥️ Tầng Giao Diện Người Dùng (PyQt6 Presentation Layer)
        ├── main_window.py               # AutoStockMainWindow (Responsive Thin Controller)
        ├── styles/                      # theme_manager.py, tokens.py, vector SVG icon engine
        ├── components/                  # StatBox, SceneListItem, ThumbnailCard, StatusPanel, ToastNotification, PreviewModal, ApiKeyManagerWidget
        ├── dialogs/                     # SettingsDialog, JsonInputDialog, KeyManagementDialog, AssignSceneDialog, UpdateDialog
        ├── workers/                     # SearchWorker, DownloadWorker, VideoCutWorker, SceneVoiceWorker, VoiceGenerationWorker, UpdateWorker
        ├── workflow/                    # WorkflowCanvas, WorkflowNodeItem, Canvas
        └── tabs/                        # DownloaderTab, CutMixTab, VoiceTab, SceneVoiceTab, AutoTab, WorkflowTab
```

---

## 🚀 Hướng Dẫn Cài Đặt & Sử Dụng (Quick Start)

### 1. Yêu Cầu Môi Trường
- **Hệ điều hành**: Windows 10 / 11 (64-bit).
- **Python**: Phiên bản 3.10 trở lên (khuyên dùng Python 3.11 hoặc 3.12).
- **FFmpeg**: Đã cài đặt và có trong biến môi trường `PATH`.

### 2. Cài Đặt Mã Nguồn

```bash
git clone https://github.com/tienoho/stock-studio-pro.git
cd stock-studio-pro

pip install -r requirements.txt
```

### 3. Khởi Chạy Ứng Dụng

- **Cách 1 (Nhanh nhất)**: Nhấp đúp vào file **`run.bat`** (hoặc **`run_exe.bat`** nếu sử dụng bản đóng gói .exe).
- **Cách 2 (Dòng lệnh)**:
  ```bash
  python main.py
  ```

### 4. Kiểm Thử Hệ Thống (Automated Test Suite)

Dự án sở hữu bộ test tự động toàn diện với **119 unit tests** và **8 bài kiểm thử áp lực**:
```bash
# Chạy bộ Unit Tests
python run_tests.py

# Chạy bộ kiểm thử áp lực giao diện & vòng đời
python scripts/hunt_bugs.py

# Kiểm tra chất lượng mã nguồn với Flake8
flake8 src tests --count --select=E9,F63,F7,F82 --show-source --statistics
```

### 5. Đóng Gói Thành Bản Cài Đặt Độc Lập (.exe & .zip)

- **Cách 1**: Nhấp đúp vào file **`build.bat`**.
- **Cách 2**: Chạy qua kịch bản tự động hóa Python:
  ```bash
  python build_release.py
  ```
Kịch bản sẽ tự động chạy toàn bộ bộ kiểm thử, biên dịch PyInstaller, tạo thư mục `release_autostock_studio/` và nén thành tệp phát hành `dist/AutoStockStudio-windows-x64.zip`.

---

## ⚙️ Hướng Dẫn Cấu Hình API Keys

1. Khởi động ứng dụng, bấm phím tắt **`F2`** hoặc nút **"⚙️ Cài đặt & API Keys"** ở góc trái.
2. Cấu hình các nền tảng:
   - 🌟 **Wikimedia Commons & Openverse**: **100% Miễn phí, không cần cấu hình bất kỳ API Key nào**! Bạn có thể bắt đầu tìm kiếm và tải ảnh/video ngay lập tức.
   - 📸 **Pexels API**: [Lấy API key miễn phí tại Pexels](https://www.pexels.com/api/)
   - 🖼️ **Pixabay API**: [Lấy API key miễn phí tại Pixabay](https://pixabay.com/api/docs/)
   - 🎥 **Coverr API**: [Lấy API key tại Coverr.co](https://coverr.co/)
   - 🎨 **Vecteezy API**: [Lấy API key tại Vecteezy](https://www.vecteezy.com/api-docs/index.html)
3. Bạn có thể thêm nhiều khóa cho cùng một nền tảng. Hệ thống sẽ tự động xoay tua Round-Robin và tự động khóa các key bị quá hạn mức để đảm bảo tiến trình tải không bị gián đoạn.

---

## 🔄 Tích Hợp CI / CD (GitHub Actions)

Dự án tích hợp đầy đủ quy trình kiểm soát chất lượng chuẩn doanh nghiệp:
- **CI Pipeline (`.github/workflows/ci.yml`)**:
  - Chạy trên mỗi lần `push` và `pull_request`.
  - Kiểm tra cú pháp Bytecode (`python -m compileall`).
  - Kiểm tra nghiêm ngặt cú pháp và biến chưa định nghĩa (`flake8 --select=E9,F63,F7,F82`).
  - Chạy ma trận 119 bài kiểm thử trên môi trường ảo hóa Windows (`windows-latest`) trên cả Python 3.10 và Python 3.11 với chế độ `QT_QPA_PLATFORM=offscreen`.
- **CD Release Pipeline (`.github/workflows/release.yml`)**:
  - Tự động kích hoạt khi gắn tag phiên bản (`git tag v1.1.0 && git push --tags`) hoặc chạy thủ công qua `workflow_dispatch`.
  - Tự động đóng gói bản phát hành Windows Portable độc lập, tạo mã băm SHA-256 Checksum và đăng tải trực tiếp lên **GitHub Releases**.

---

## 📄 Bản Quyền & Giấy Phép (License)

Dự án phát triển phục vụ mục đích tự động hóa quy trình sản xuất nội dung video, tin tức và tài chính chuyên nghiệp. Mọi đóng góp và báo lỗi xin vui lòng tạo Issue hoặc Pull Request trên GitHub.
