import threading
import time
import logging
from typing import Callable, Optional
from json_db import JsonDatabase
from monitor import SocialMonitor
from ai_processor import AIProcessor
from telegram_bot import TelegramNotifier

try:
    from plyer import notification
    HAS_PLYER = True
except ImportError:
    HAS_PLYER = False

class MonitorService:
    def __init__(self, db: JsonDatabase):
        self.db = db
        self.monitor = SocialMonitor()
        self.ai = AIProcessor(db=self.db)
        self.telegram = TelegramNotifier()
        
        self.is_running = False
        self._thread: Optional[threading.Thread] = None
        self.poll_interval = 60
        
        self.on_log_callback: Optional[Callable[[str, str], None]] = None
        self.on_stats_callback: Optional[Callable[[int, int, int], None]] = None
        self.on_post_received_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        
        self.stats = {
            "checked": 0,
            "sent": 0,
            "errors": 0
        }
        
        self._reload_config()

    def _reload_config(self):
        gemini_key = self.db.get_setting("gemini_api_key", "")
        gemini_model = self.db.get_setting("gemini_model", "gemini-3.6-flash")
        bot_token = self.db.get_setting("telegram_bot_token", "")
        chat_id = self.db.get_setting("telegram_chat_id", "")
        self.poll_interval = int(self.db.get_setting("poll_interval", 60))

        self.ai.set_config(api_key=gemini_key, model_name=gemini_model)
        self.telegram.set_config(bot_token=bot_token, default_chat_id=chat_id)

    def log(self, level: str, message: str):
        self.db.add_log(level, message)
        if self.on_log_callback:
            try:
                self.on_log_callback(level, message)
            except Exception:
                pass

    def send_windows_toast(self, title: str, message: str):
        """Hiển thị thông báo bong bóng Windows Toast Notification."""
        if HAS_PLYER:
            try:
                notification.notify(
                    title=title[:60],
                    message=message[:200],
                    app_name="News Monitor",
                    timeout=5
                )
            except Exception as e:
                logging.debug(f"Lỗi thông báo Toast: {e}")

    def start(self):
        if self.is_running:
            return
        self._reload_config()
        self.is_running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self.log("INFO", "Phần mềm bắt đầu tiến trình theo dõi tự động.")

    def stop(self):
        if not self.is_running:
            return
        self.is_running = False
        self.log("INFO", "Tạm dừng tiến trình theo dõi.")

    def _run_loop(self):
        while self.is_running:
            try:
                self._check_accounts()
            except Exception as e:
                self.stats["errors"] += 1
                self.log("ERROR", f"Lỗi trong chu kỳ theo dõi: {e}")

            for _ in range(self.poll_interval):
                if not self.is_running:
                    break
                time.sleep(1)

    def check_now(self):
        """Kích hoạt kiểm tra ngay lập tức."""
        self._reload_config()
        thread = threading.Thread(target=self._check_accounts, daemon=True)
        thread.start()

    def send_test_latest_post(self, account_identifier: Optional[str] = None) -> tuple[bool, str]:
        """
        Gửi bài đăng mới nhất của nguồn tin để test kết nối Gemini & Telegram.
        """
        self._reload_config()
        if not account_identifier:
            accounts = self.db.get_accounts(active_only=True)
            if not accounts:
                accounts = self.db.get_accounts(active_only=False)
            if not accounts:
                return False, "Chưa có tài khoản nguồn tin nào trong danh sách."
            identifier = accounts[0]["identifier"]
            display_name = accounts[0].get("display_name") or identifier
        else:
            identifier = account_identifier.strip().lstrip("@")
            accounts = self.db.get_accounts()
            display_name = identifier
            for a in accounts:
                if a["identifier"].lower() == identifier.lower():
                    display_name = a.get("display_name") or identifier
                    break

        self.log("INFO", f"🧪 Đang thực hiện test với bài viết mới nhất từ @{identifier}...")
        collect_media = bool(self.db.get_setting("collect_media", False))
        posts, error = self.monitor.fetch_x_account_posts(identifier, collect_media=collect_media)

        if error:
            self.log("ERROR", f"Lỗi lấy bài test từ @{identifier}: {error}")
            return False, error

        if not posts:
            msg = f"Không tìm thấy bài đăng gốc nào từ @{identifier} để test."
            self.log("WARNING", msg)
            return False, msg

        # Take the newest post
        post = posts[0]
        custom_prompt = self.db.get_setting("custom_prompt", "")
        style_preset = self.db.get_setting("style_preset", "bilingual")
        short_limit = int(self.db.get_setting("short_post_limit", 40))
        use_gemini = bool(self.db.get_setting("use_gemini", True))

        self.log("INFO", f"Phát hiện bài test từ @{identifier}: {post.content[:60]}...")

        if use_gemini:
            summary = self.ai.summarize_news(
                author=display_name,
                raw_text=post.content,
                custom_prompt=custom_prompt,
                style_preset=style_preset,
                short_limit=short_limit,
                url=post.url,
                published_at=post.published_at
            )
        else:
            summary = post.content
            self.db.add_history(display_name, "", post.content, post.content, url=post.url, published_at=post.published_at)

        if self.on_post_received_callback:
            try:
                self.on_post_received_callback({
                    "account": identifier,
                    "raw_text": post.content,
                    "summary": summary,
                    "url": post.url,
                    "published_at": post.published_at
                })
            except Exception:
                pass

        msg = self.telegram.format_news_post(
            author=display_name,
            summary=f"🧪 *[BÀI ĐĂNG THỬ NGHIỆM - TEST]*\n\n{summary}",
            original_url=post.url,
            published_at=post.published_at
        )

        success, tg_err = self.telegram.send_message(msg)
        if success:
            self.stats["sent"] += 1
            self.db.mark_post_seen(post.post_id, "X", identifier, post.content, post.url, post.published_at)
            self.log("SUCCESS", f"✅ Đã gửi bài đăng TEST của @{identifier} thành công qua Telegram!")
            self.send_windows_toast(f"Test tin từ @{identifier}", summary)
            if self.on_stats_callback:
                self.on_stats_callback(self.stats["checked"], self.stats["sent"], self.stats["errors"])
            return True, f"Đã gửi bài đăng test của @{identifier} thành công qua Telegram!"
        else:
            self.stats["errors"] += 1
            self.log("ERROR", f"Không thể gửi bài test Telegram của @{identifier}: {tg_err}")
            if self.on_stats_callback:
                self.on_stats_callback(self.stats["checked"], self.stats["sent"], self.stats["errors"])
            return False, f"Lỗi gửi Telegram: {tg_err}"

    def _check_accounts(self):
        accounts = self.db.get_accounts(active_only=True)
        if not accounts:
            self.log("WARNING", "Chưa có tài khoản nào được bật theo dõi.")
            return

        custom_prompt = self.db.get_setting("custom_prompt", "")
        style_preset = self.db.get_setting("style_preset", "bilingual")
        short_limit = int(self.db.get_setting("short_post_limit", 40))
        collect_media = bool(self.db.get_setting("collect_media", False))
        skip_existing = bool(self.db.get_setting("skip_existing_on_start", True))
        max_age_hours = float(self.db.get_setting("max_post_age_hours", 6))
        use_gemini = bool(self.db.get_setting("use_gemini", True))

        for acc in accounts:
            if not self.is_running and threading.current_thread() == self._thread:
                break

            identifier = acc["identifier"]
            display_name = acc.get("display_name") or identifier
            self.log("INFO", f"Đang kiểm tra bài đăng từ @{identifier}...")

            posts, error = self.monitor.fetch_x_account_posts(identifier, collect_media=collect_media)
            self.stats["checked"] += 1

            if error:
                self.stats["errors"] += 1
                self.log("ERROR", error)
                continue

            if not posts:
                self.log("INFO", f"Không có bài đăng gốc từ @{identifier}.")
                continue

            # Anti-Spam Feature 1: Cold-start Baseline Seeding
            # If account is newly added and skip_existing_on_start is enabled, mark all current posts as seen
            if skip_existing and not self.db.has_seen_posts_for_account(identifier):
                for p in posts:
                    self.db.mark_post_seen(p.post_id, "X", identifier, p.content, p.url, p.published_at)
                self.log("INFO", f"ℹ️ [THIẾT LẬP BAN ĐẦU] Đã khởi tạo {len(posts)} bài viết cũ của @{identifier} làm mốc (Bỏ qua không gửi Telegram). Từ bây giờ chỉ thông báo bài MỚI!")
                continue

            new_posts_count = 0
            for post in reversed(posts):
                if self.db.is_post_seen(post.post_id):
                    continue

                # Anti-Spam Feature 2: Time Window Cutoff
                # Ignore posts older than max_post_age_hours
                if max_age_hours > 0 and post.is_older_than_hours(max_age_hours):
                    self.db.mark_post_seen(post.post_id, "X", identifier, post.content, post.url, post.published_at)
                    self.log("INFO", f"ℹ️ Bỏ qua bài viết cũ từ @{identifier} (Đã đăng hơn {max_age_hours} giờ trước).")
                    continue

                new_posts_count += 1
                self.log("INFO", f"Phát hiện bài mới từ @{identifier}: {post.content[:60]}...")

                # Process with Gemini AI if enabled, otherwise send original post text
                if use_gemini:
                    summary = self.ai.summarize_news(
                        author=display_name,
                        raw_text=post.content,
                        custom_prompt=custom_prompt,
                        style_preset=style_preset,
                        short_limit=short_limit,
                        url=post.url,
                        published_at=post.published_at
                    )
                else:
                    self.log("INFO", f"Chế độ Gemini AI đang TẮT. Gửi trực tiếp toàn bộ bài gốc của @{identifier}.")
                    summary = post.content
                    self.db.add_history(display_name, "", post.content, post.content, url=post.url, published_at=post.published_at)

                if self.on_post_received_callback:
                    try:
                        self.on_post_received_callback({
                            "account": identifier,
                            "raw_text": post.content,
                            "summary": summary,
                            "url": post.url,
                            "published_at": post.published_at
                        })
                    except Exception:
                        pass

                # Format Telegram Markdown
                msg = self.telegram.format_news_post(
                    author=display_name,
                    summary=summary,
                    original_url=post.url,
                    published_at=post.published_at
                )

                # Send Telegram Notification
                success, tg_err = self.telegram.send_message(msg)
                if success:
                    self.stats["sent"] += 1
                    self.db.mark_post_seen(post.post_id, "X", identifier, post.content, post.url, post.published_at)
                    self.log("SUCCESS", f"Đã gửi thông báo cho bài đăng của @{identifier} qua Telegram Group!")
                    
                    # Show Windows Toast
                    self.send_windows_toast(f"Tin mới từ @{identifier}", summary)
                else:
                    self.stats["errors"] += 1
                    self.log("ERROR", f"Không thể gửi Telegram cho bài viết của @{identifier}: {tg_err}")

            if new_posts_count == 0:
                self.log("INFO", f"Không có bài đăng gốc mới từ @{identifier}.")

        if self.on_stats_callback:
            try:
                self.on_stats_callback(self.stats["checked"], self.stats["sent"], self.stats["errors"])
            except Exception:
                pass
