import os
import json
import time
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

DATA_DIR = "data"

class JsonDatabase:
    def __init__(self, data_dir: str = DATA_DIR):
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.settings_file = os.path.join(self.data_dir, "settings.json")
        self.accounts_file = os.path.join(self.data_dir, "accounts.json")
        self.seen_posts_file = os.path.join(self.data_dir, "seen_posts.json")
        self.history_file = os.path.join(self.data_dir, "history.json")
        self.cache_file = os.path.join(self.data_dir, "cache.json")
        self.logs_file = os.path.join(self.data_dir, "logs.json")

        self._init_files()

    def _read_json(self, filepath: str, default: Any) -> Any:
        if not os.path.exists(filepath):
            return default
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default

    def _write_json(self, filepath: str, data: Any):
        temp_file = filepath + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(temp_file, filepath)

    def _init_files(self):
        if not os.path.exists(self.settings_file):
            default_settings = {
                "gemini_api_key": "",
                "gemini_model": "gemini-3.6-flash",
                "telegram_bot_token": "",
                "telegram_chat_id": "",
                "poll_interval": 60,
                "style_preset": "bilingual",
                "custom_prompt": (
                    "Bạn là một biên tập viên tin tức chuyên nghiệp. Hãy biên tập lại bài đăng từ @{author}.\n"
                    "Yêu cầu:\n"
                    "1. Tóm tắt ý chính và trình bày song ngữ (Tiếng Việt và Tiếng Anh ngắn gọn).\n"
                    "2. Giữ nguyên tính chính xác của thông tin.\n\n"
                    "Nội dung bài đăng gốc:\n{text}"
                ),
                "collect_media": False,
                "short_post_limit": 40,
                "skip_existing_on_start": True,
                "max_post_age_hours": 6,
                "use_gemini": True
            }
            self._write_json(self.settings_file, default_settings)

        if not os.path.exists(self.accounts_file):
            self._write_json(self.accounts_file, [])
        if not os.path.exists(self.seen_posts_file):
            self._write_json(self.seen_posts_file, {})
        if not os.path.exists(self.history_file):
            self._write_json(self.history_file, [])
        if not os.path.exists(self.cache_file):
            self._write_json(self.cache_file, {})
        if not os.path.exists(self.logs_file):
            self._write_json(self.logs_file, [])

    # Settings
    def get_setting(self, key: str, default: Any = None) -> Any:
        settings = self._read_json(self.settings_file, {})
        return settings.get(key, default)

    def set_setting(self, key: str, value: Any):
        settings = self._read_json(self.settings_file, {})
        settings[key] = value
        self._write_json(self.settings_file, settings)

    def get_all_settings(self) -> Dict[str, Any]:
        return self._read_json(self.settings_file, {})

    # Accounts
    def get_accounts(self, active_only: bool = False) -> List[Dict[str, Any]]:
        accounts = self._read_json(self.accounts_file, [])
        if active_only:
            return [a for a in accounts if a.get("is_active", True)]
        return accounts

    def add_account(self, identifier: str, display_name: str = "", platform: str = "x") -> bool:
        identifier = identifier.strip().lstrip("@")
        if not identifier:
            return False
        accounts = self.get_accounts()
        for a in accounts:
            if a["identifier"].lower() == identifier.lower():
                return False # Duplicate

        new_acc = {
            "id": int(time.time() * 1000),
            "platform": platform,
            "identifier": identifier,
            "display_name": display_name or identifier,
            "is_active": True,
            "added_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        accounts.append(new_acc)
        self._write_json(self.accounts_file, accounts)
        return True

    def delete_account(self, account_id: int):
        accounts = self.get_accounts()
        accounts = [a for a in accounts if a["id"] != account_id]
        self._write_json(self.accounts_file, accounts)

    def toggle_account(self, account_id: int, is_active: bool):
        accounts = self.get_accounts()
        for a in accounts:
            if a["id"] == account_id:
                a["is_active"] = is_active
                break
        self._write_json(self.accounts_file, accounts)

    # Seen Posts (Duplicate Detection)
    def is_post_seen(self, post_id: str) -> bool:
        seen = self._read_json(self.seen_posts_file, {})
        return post_id in seen

    def has_seen_posts_for_account(self, account_identifier: str) -> bool:
        seen = self._read_json(self.seen_posts_file, {})
        acc_lower = account_identifier.lower()
        for v in seen.values():
            if isinstance(v, dict) and v.get("account", "").lower() == acc_lower:
                return True
        return False

    def mark_post_seen(self, post_id: str, platform: str, account_identifier: str, title: str, url: str, published_at: Optional[str] = None):
        seen = self._read_json(self.seen_posts_file, {})
        seen[post_id] = {
            "platform": platform,
            "account": account_identifier,
            "title": title[:100],
            "url": url,
            "published_at": published_at,
            "processed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        # Keep seen posts manageable (e.g. max 5000)
        if len(seen) > 5000:
            keys_to_remove = list(seen.keys())[:1000]
            for k in keys_to_remove:
                del seen[k]
        self._write_json(self.seen_posts_file, seen)

    # Gemini Cache
    def _hash_text(self, text: str) -> str:
        return hashlib.md5(text.strip().encode("utf-8")).hexdigest()

    def get_cached_summary(self, post_content: str) -> Optional[str]:
        cache = self._read_json(self.cache_file, {})
        h = self._hash_text(post_content)
        return cache.get(h)

    def cache_summary(self, post_content: str, summary: str):
        cache = self._read_json(self.cache_file, {})
        h = self._hash_text(post_content)
        cache[h] = summary
        self._write_json(self.cache_file, cache)

    def clear_cache(self):
        self._write_json(self.cache_file, {})

    # History Log (Prompts & Summaries categorized by source)
    def add_history(self, account: str, prompt: str, raw_text: str, summary: str, url: str = "", published_at: str = ""):
        history = self._read_json(self.history_file, [])
        entry = {
            "id": hashlib.md5(f"{account}_{url}_{time.time()}".encode("utf-8")).hexdigest(),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "account": account.strip().lstrip("@"),
            "prompt": prompt,
            "raw_text": raw_text,
            "summary": summary,
            "url": url,
            "published_at": published_at
        }
        history.insert(0, entry)
        if len(history) > 2000:
            history = history[:2000]
        self._write_json(self.history_file, history)

    def get_history(self, account_filter: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        history = self._read_json(self.history_file, [])
        if account_filter and account_filter != "Tất cả nguồn tin":
            clean_acc = account_filter.strip().lstrip("@").lower()
            return [h for h in history if h.get("account", "").strip().lstrip("@").lower() == clean_acc][:limit]
        return history[:limit]

    # Application Logs
    def add_log(self, level: str, message: str):
        logs = self._read_json(self.logs_file, [])
        log_entry = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "level": level,
            "message": message
        }
        logs.insert(0, log_entry)
        if len(logs) > 500:
            logs = logs[:500]
        self._write_json(self.logs_file, logs)

    def get_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        logs = self._read_json(self.logs_file, [])
        return logs[:limit]

    def clear_logs(self):
        self._write_json(self.logs_file, [])

    # Export & Import Config
    def export_config(self, export_path: str) -> bool:
        try:
            bundle = {
                "settings": self._read_json(self.settings_file, {}),
                "accounts": self._read_json(self.accounts_file, []),
                "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(bundle, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    def import_config(self, import_path: str) -> bool:
        try:
            with open(import_path, "r", encoding="utf-8") as f:
                bundle = json.load(f)
            if "settings" in bundle:
                self._write_json(self.settings_file, bundle["settings"])
            if "accounts" in bundle:
                self._write_json(self.accounts_file, bundle["accounts"])
            return True
        except Exception:
            return False

    # Cleanup Old Data
    def cleanup_old_data(self) -> Dict[str, int]:
        seen = self._read_json(self.seen_posts_file, {})
        logs = self._read_json(self.logs_file, [])
        history = self._read_json(self.history_file, [])
        cache = self._read_json(self.cache_file, {})

        cleared_seen = len(seen)
        cleared_logs = len(logs)
        cleared_history = len(history)
        cleared_cache = len(cache)

        self._write_json(self.seen_posts_file, {})
        self._write_json(self.logs_file, [])
        self._write_json(self.history_file, [])
        self._write_json(self.cache_file, {})

        return {
            "cleared_seen": cleared_seen,
            "cleared_logs": cleared_logs,
            "cleared_history": cleared_history,
            "cleared_cache": cleared_cache
        }
