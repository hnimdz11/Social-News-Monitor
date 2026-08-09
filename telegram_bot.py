import httpx
import logging
from typing import Optional

def escape_markdown_v1(text: str) -> str:
    """Escapes special characters for Telegram legacy Markdown format."""
    # Special characters in Telegram Markdown: *, _, `, [
    # Escape backslashes first, then special characters
    chars = ['\\', '*', '_', '`', '[']
    for c in chars:
        text = text.replace(c, f"\\{c}")
    return text

class TelegramNotifier:
    def __init__(self, bot_token: str = "", default_chat_id: str = ""):
        self.bot_token = bot_token
        self.default_chat_id = default_chat_id

    def set_config(self, bot_token: str, default_chat_id: str):
        self.bot_token = bot_token
        self.default_chat_id = default_chat_id

    @property
    def api_url(self) -> str:
        return f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

    def send_message(self, text: str, chat_id: Optional[str] = None, parse_mode: str = "Markdown", disable_preview: bool = False) -> tuple[bool, str]:
        """
        Gửi tin nhắn Telegram với định dạng Markdown.
        """
        target_chat_id = chat_id or self.default_chat_id
        if not self.bot_token:
            return False, "Chưa cấu hình Telegram Bot Token"
        if not target_chat_id:
            return False, "Chưa cấu hình Telegram Chat ID"

        if len(text) > 4000:
            text = text[:3900] + "\n\n*(...Nội dung đã bị cắt ngắn...)*"

        payload = {
            "chat_id": target_chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_preview
        }

        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.post(self.api_url, json=payload)
                data = response.json()
                if response.status_code == 200 and data.get("ok"):
                    return True, "Gửi tin nhắn Telegram thành công!"
                else:
                    error_desc = data.get("description", response.text)
                    return False, f"Lỗi Telegram API: {error_desc}"
        except Exception as e:
            logging.error(f"Lỗi gửi tin nhắn Telegram: {e}")
            return False, f"Lỗi kết nối Telegram: {str(e)}"

    def format_news_post(self, author: str, summary: str, original_url: str, published_at: str = "") -> str:
        """
        Định dạng tin nhắn chuẩn Telegram Markdown theo đúng yêu cầu:
        Tên tài khoản + Link bài gốc + Bản tóm tắt bằng tiếng việt + Thời gian đăng
        """
        display_time = published_at if published_at else "Mới cập nhật"

        message = (
            f"👤 *Tên tài khoản:* @{author}\n"
            f"🔗 *Link bài gốc:* [Xem bài đăng trên X]({original_url})\n\n"
            f"📝 *Bản tóm tắt:* \n{summary}\n\n"
            f"⏰ *Thời gian đăng:* {display_time}"
        )
        return message

    def test_connection(self) -> tuple[bool, str]:
        """Kiểm tra Telegram Bot Token và Chat ID."""
        test_msg = "🔔 *Kiểm tra kết nối Telegram Bot thành công!*\nPhần mềm News Monitor đã sẵn sàng kết nối Group của bạn."
        return self.send_message(test_msg)
