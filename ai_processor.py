import logging
from typing import Optional
from json_db import JsonDatabase

GEMINI_MODELS = [
    "gemini-3.6-flash",
    "gemini-3.0-flash",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash"
]

STYLE_PRESETS = {
    "bilingual": (
        "Bạn là một biên tập viên tin tức song ngữ chuyên nghiệp. Hãy đọc bài đăng từ @{author} và thực hiện:\n"
        "1. Tóm tắt ý chính và trình bày theo dạng SONG NGỮ (Tiếng Việt và Tiếng Anh bên dưới).\n"
        "2. Sử dụng định dạng ngắn gọn, súc tích, đính kèm emoji phù hợp.\n\n"
        "Nội dung bài đăng gốc:\n{text}"
    ),
    "journalistic": (
        "Bạn là một nhà báo biên tập tin quốc tế. Hãy đọc bài đăng từ @{author} và biên tập lại bài viết theo PHONG CÁCH BÁO CHÍ:\n"
        "1. Tạo một tiêu đề báo chí hấp dẫn bằng Tiếng Việt.\n"
        "2. Viết lại nội dung thành một bản tin ngắn gọn 2-3 đoạn văn chuẩn phong cách báo chí chuyên nghiệp bằng Tiếng Việt.\n\n"
        "Nội dung bài đăng gốc:\n{text}"
    )
}

class AIProcessor:
    def __init__(self, db: Optional[JsonDatabase] = None, api_key: str = "", model_name: str = "gemini-3.6-flash"):
        self.db = db
        self.api_key = api_key
        self.model_name = model_name
        self.client = None
        self._init_client()

    def set_config(self, api_key: str, model_name: str = "gemini-3.6-flash"):
        self.api_key = api_key
        self.model_name = model_name or "gemini-3.6-flash"
        self._init_client()

    def _init_client(self):
        if not self.api_key:
            self.client = None
            return
        try:
            from google import genai
            self.client = genai.Client(api_key=self.api_key)
        except Exception as e:
            logging.error(f"Lỗi khởi tạo Gemini API client: {e}")
            self.client = None

    def summarize_news(self, author: str, raw_text: str, custom_prompt: Optional[str] = None, style_preset: str = "bilingual", short_limit: int = 40, url: str = "", published_at: str = "") -> str:
        """
        Tóm tắt hoặc biên tập lại tin tức bằng Gemini API với Cache, Short-Post Bypass và Error Handling.
        """
        raw_text_clean = raw_text.strip()

        # 1. Bypass Gemini if post is too short to save API quota
        if len(raw_text_clean) < short_limit:
            logging.info(f"Bài viết quá ngắn ({len(raw_text_clean)} ký tự < {short_limit}), bỏ qua tóm tắt Gemini API.")
            return raw_text_clean

        # 2. Check Cache
        if self.db:
            cached = self.db.get_cached_summary(raw_text_clean)
            if cached:
                logging.info("Sử dụng kết quả tóm tắt từ Cache cho bài đăng.")
                return cached

        # 3. Check Client / Key
        if not self.client or not self.api_key:
            return f"⚠️ *(Gemini AI không khả dụng: Chưa cấu hình API Key)*\n\n{raw_text_clean}"

        # 4. Prepare Prompt
        if custom_prompt and custom_prompt.strip():
            prompt_template = custom_prompt
        else:
            prompt_template = STYLE_PRESETS.get(style_preset, STYLE_PRESETS["bilingual"])

        prompt = prompt_template.replace("{author}", author).replace("{text}", raw_text_clean)

        # 5. Call Gemini API
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
            )
            if response and response.text:
                summary = response.text.strip()
                
                # Save to cache & history
                if self.db:
                    self.db.cache_summary(raw_text_clean, summary)
                    self.db.add_history(author, prompt, raw_text_clean, summary, url=url, published_at=published_at)
                    
                return summary
            return f"⚠️ *(Gemini AI không khả dụng: Không nhận được kết quả tóm tắt)*\n\n{raw_text_clean}"
        except Exception as e:
            err_msg = str(e)
            if hasattr(e, "message") and getattr(e, "message"):
                err_msg = e.message
            elif "API key not valid" in err_msg:
                err_msg = "API key không hợp lệ"
            elif "quota" in err_msg.lower():
                err_msg = "Đã hết Quota sử dụng API"
            elif "connect" in err_msg.lower():
                err_msg = "Lỗi kết nối mạng tới Gemini API"
            
            logging.error(f"Lỗi gọi Gemini API ({self.model_name}): {err_msg}")
            return f"⚠️ *(Gemini AI không khả dụng: {err_msg})*\n\n{raw_text_clean}"

    def test_connection(self) -> tuple[bool, str]:
        """Kiểm tra kết nối tới Gemini API với Key hiện tại."""
        if not self.api_key:
            return False, "Chưa nhập API Key"
        try:
            from google import genai
            client = genai.Client(api_key=self.api_key)
            response = client.models.generate_content(
                model=self.model_name,
                contents="Trả lời 'OK' bằng duy nhất một từ để kiểm tra kết nối."
            )
            if response and response.text:
                return True, f"Kết nối thành công! Gemini ({self.model_name}) phản hồi: {response.text.strip()}"
            return False, "Không nhận được phản hồi từ Gemini API"
        except Exception as e:
            return False, f"Kết nối thất bại: {str(e)}"
