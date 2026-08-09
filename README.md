# ⚡ Social News Monitor

**Social News Monitor** là ứng dụng tự động theo dõi bài đăng mới trên **X (Twitter)**, tóm tắt và biên tập tin tức thông minh bằng **Google Gemini AI**, sau đó tự động gửi thông báo trực tiếp đến **Telegram Channel / Group**.

Ứng dụng hỗ trợ cả giao diện **GUI** trực quan và chế độ **Headless CLI** tối ưu để chạy 24/7 trên Cloud VPS (Google Cloud, AWS, DigitalOcean,...).

---

## ✨ Tính năng nổi bật

- 📡 **Theo dõi X (Twitter) không cần API Key trả phí**: Tự động lấy bài đăng gốc mới nhất từ danh sách tài khoản X thông qua cơ chế RSS/Nitter/RSSHub bridges.
- 🤖 **Tóm tắt tin tức bằng Gemini AI**: Tóm tắt và biên tập tự động theo phong cách **Song ngữ (Việt - Anh)** hoặc **Báo chí chuyên nghiệp**. Hỗ trợ tùy chỉnh model (`gemini-3.6-flash`, `gemini-2.5-pro`,...) và Custom Prompt.
- 📲 **Tự động chuyển tiếp Telegram**: Đẩy tin tức đã qua xử lý kèm link bài gốc và mốc thời gian GMT+7 tới Telegram Channel/Group.
- 🖥️ **Hỗ trợ 2 chế độ (GUI & Headless CLI)**:
  - **GUI**: Giao diện CustomTkinter hiện đại, dễ dàng quản lý tài khoản, cấu hình API, kiểm tra kết nối và xem lịch sử.
  - **CLI**: Chạy ngầm mượt mà trên Linux/Windows Server 24/7 với tham số `--cli`.
- ⚡ **Tối ưu Quota & Bộ nhớ tạm**: Tự động bypass AI với bài viết quá ngắn và lưu Cache bản tóm tắt để tiết kiệm Gemini API Quota.
- ⏱️ **Bộ lọc tin thông minh**: Giới hạn độ tuổi bài đăng (VD: trong 24h) và chống trùng lặp dữ liệu bằng JSON Database.

---

## 🛠️ Cài đặt

### 1. Yêu cầu hệ thống
- Python >= 3.10

### 2. Cài đặt dependencies
```bash
git clone https://github.com/hnimdz11/SocialNewsMonitor.git
cd SocialNewsMonitor
pip install httpx feedparser python-telegram-bot google-genai customtkinter
```

---

## 🚀 Hướng dẫn sử dụng

### 1. Giao diện GUI (Desktop)
```bash
python main.py
```
> Trong GUI, bạn cấu hình:
> - **Gemini API Key** & **Telegram Bot Token / Chat ID**.
> - Danh sách tài khoản X cần theo dõi (VD: `elontusk`, `OpenAI`).
> - Tần suất quét và phong cách tóm tắt AI.

### 2. Chế độ Headless CLI (Server / Cloud VPS 24/7)
```bash
python main.py --cli
```
*Lưu ý: Ứng dụng sẽ tự động tải các thông số cấu hình đã lưu trong cơ sở dữ liệu để chạy liên tục mà không cần giao diện.*

---

## 📂 Cấu trúc thư mục

```text
├── main.py            # Entry point (Khởi chạy GUI hoặc CLI Headless)
├── gui.py             # Giao diện người dùng CustomTkinter
├── service.py         # Service quản lý luồng quét tin tự động
├── monitor.py         # Module cào & xử lý dữ liệu từ X (Twitter)
├── ai_processor.py    # Module tích hợp Google Gemini AI
├── telegram_bot.py    # Module gửi thông báo Telegram Bot
├── json_db.py         # Quản lý DB lưu cấu hình, cache & lịch sử
└── assets/            # Icon và tài nguyên giao diện
```

---

## 📜 License
Phát hành theo giấy phép **MIT License**.
