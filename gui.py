import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import threading
import time
import os
import webbrowser

from json_db import JsonDatabase
from service import MonitorService
from ai_processor import AIProcessor, GEMINI_MODELS
from telegram_bot import TelegramNotifier

# Light Theme Edition
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

def get_resource_path(relative_path: str) -> str:
    """Lấy đường dẫn tài nguyên làm việc chuẩn cả khi chạy script Python và đóng gói PyInstaller EXE."""
    import sys
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)

class NewsMonitorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Social News Monitor AI - Mindz")
        self.geometry("1080 x 760")
        self.minsize(980, 680)

        ico_path = get_resource_path(os.path.join("assets", "app_icon.ico"))
        if os.path.exists(ico_path):
            try:
                self.iconbitmap(ico_path)
            except Exception:
                pass

        self.db = JsonDatabase()
        self.service = MonitorService(self.db)

        self.service.on_log_callback = self.on_service_log
        self.service.on_stats_callback = self.on_service_stats
        self.service.on_post_received_callback = self.on_service_post_received

        self.protocol("WM_DELETE_WINDOW", self.on_close_window)

        self._create_layout()
        self._load_saved_settings()
        self._refresh_accounts_list()
        self._load_recent_logs()
        self._refresh_source_filter_dropdown()
        self._refresh_dashboard_feed()

    def _create_layout(self):
        # Header / Status Bar
        header = ctk.CTkFrame(self, corner_radius=8, fg_color="#f0f4f8")
        header.pack(fill="x", padx=15, pady=10)

        title_lbl = ctk.CTkLabel(header, text="⚡ Social News Monitor AI", font=ctk.CTkFont(size=18, weight="bold"), text_color="#1e293b")
        title_lbl.pack(side="left", padx=15, pady=10)

        self.status_badge = ctk.CTkLabel(header, text="● Đang tạm dừng", text_color="#dc2626", font=ctk.CTkFont(size=13, weight="bold"))
        self.status_badge.pack(side="right", padx=15, pady=10)

        # Tabview Navigation
        self.tabview = ctk.CTkTabview(self, width=1040, height=660)
        self.tabview.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        self.tab_dashboard = self.tabview.add("📊 Dashboard & Bài đăng")
        self.tab_accounts = self.tabview.add("👥 Tài khoản Theo dõi")
        self.tab_gemini = self.tabview.add("🤖 Gemini AI")
        self.tab_telegram = self.tabview.add("✈ Telegram Bot")
        self.tab_history = self.tabview.add("📜 Lịch sử Bài đăng")
        self.tab_settings = self.tabview.add("⚙ Cài đặt & Quản lý")
        self.tab_about = self.tabview.add("ℹ️ Giới thiệu")

        self._build_dashboard_tab()
        self._build_accounts_tab()
        self._build_gemini_tab()
        self._build_telegram_tab()
        self._build_history_tab()
        self._build_settings_tab()
        self._build_about_tab()

    # --- Dashboard Tab ---
    def _build_dashboard_tab(self):
        # Top Stats Cards
        stats_frame = ctk.CTkFrame(self.tab_dashboard, fg_color="transparent")
        stats_frame.pack(fill="x", pady=(5, 5))

        self.card_accounts = self._create_stat_card(stats_frame, "Tài khoản đang bật", "0", "#2563eb")
        self.card_checked = self._create_stat_card(stats_frame, "Lần kiểm tra", "0", "#7c3aed")
        self.card_sent = self._create_stat_card(stats_frame, "Tin gửi Telegram", "0", "#059669")
        self.card_errors = self._create_stat_card(stats_frame, "Lỗi phát sinh", "0", "#dc2626")

        # Action Buttons Control Frame
        ctrl_frame = ctk.CTkFrame(self.tab_dashboard, fg_color="#f8fafc")
        ctrl_frame.pack(fill="x", pady=(5, 10), padx=5)

        self.btn_start = ctk.CTkButton(ctrl_frame, text="▶ Bắt đầu Theo dõi", fg_color="#059669", hover_color="#047857", command=self.start_monitoring, font=ctk.CTkFont(weight="bold"))
        self.btn_start.pack(side="left", padx=10, pady=8)

        self.btn_stop = ctk.CTkButton(ctrl_frame, text="⏸ Tạm dừng", fg_color="#dc2626", hover_color="#b91c1c", command=self.stop_monitoring, state="disabled", font=ctk.CTkFont(weight="bold"))
        self.btn_stop.pack(side="left", padx=10, pady=8)

        self.btn_check_now = ctk.CTkButton(ctrl_frame, text="🔄 Kiểm tra Ngay", fg_color="#2563eb", hover_color="#1d4ed8", command=self.check_now, font=ctk.CTkFont(weight="bold"))
        self.btn_check_now.pack(side="left", padx=10, pady=8)

        self.btn_test_latest = ctk.CTkButton(ctrl_frame, text="🧪 Test Bài Mới Nhất", fg_color="#7c3aed", hover_color="#6d28d9", command=self.send_test_latest, font=ctk.CTkFont(weight="bold"))
        self.btn_test_latest.pack(side="left", padx=10, pady=8)

        # Dual Panel Container: Left (Live Feed & History Filter) / Right (Logs)
        main_split = ctk.CTkFrame(self.tab_dashboard, fg_color="transparent")
        main_split.pack(fill="both", expand=True, padx=5, pady=0)

        # Left Sub-panel: Feed View categorized by News Source
        feed_panel = ctk.CTkFrame(main_split, fg_color="#f8fafc", corner_radius=8, border_width=1, border_color="#e2e8f0")
        feed_panel.pack(side="left", fill="both", expand=True, padx=(0, 5))

        feed_header = ctk.CTkFrame(feed_panel, fg_color="transparent")
        feed_header.pack(fill="x", padx=10, pady=8)

        lbl_feed = ctk.CTkLabel(feed_header, text="📰 Bài đăng mới thu thập:", font=ctk.CTkFont(size=14, weight="bold"), text_color="#1e293b")
        lbl_feed.pack(side="left")

        # Source Filter Dropdown
        self.combo_source_filter = ctk.CTkComboBox(
            feed_header,
            values=["Tất cả nguồn tin"],
            command=lambda val: self._refresh_dashboard_feed(),
            width=180
        )
        self.combo_source_filter.set("Tất cả nguồn tin")
        self.combo_source_filter.pack(side="right", padx=(5, 0))

        lbl_filter = ctk.CTkLabel(feed_header, text="Nguồn tin:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#475569")
        lbl_filter.pack(side="right", padx=(10, 2))

        self.feed_scroll = ctk.CTkScrollableFrame(feed_panel, height=320, fg_color="#ffffff")
        self.feed_scroll.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # Right Sub-panel: Real-time Logs Box
        log_panel = ctk.CTkFrame(main_split, fg_color="#f8fafc", corner_radius=8, border_width=1, border_color="#e2e8f0", width=340)
        log_panel.pack(side="right", fill="both", expand=False, padx=(5, 0))

        log_hdr = ctk.CTkFrame(log_panel, fg_color="transparent")
        log_hdr.pack(fill="x", padx=10, pady=8)

        log_lbl = ctk.CTkLabel(log_hdr, text="📋 Nhật ký (Logs):", font=ctk.CTkFont(size=14, weight="bold"), text_color="#1e293b")
        log_lbl.pack(side="left")

        self.log_box = ctk.CTkTextbox(log_panel, height=320, font=ctk.CTkFont(family="Consolas", size=11), fg_color="#ffffff", text_color="#0f172a", width=320)
        self.log_box.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _create_stat_card(self, parent, title: str, init_val: str, color: str):
        card = ctk.CTkFrame(parent, corner_radius=10, border_width=1.5, border_color=color, fg_color="#ffffff")
        card.pack(side="left", fill="both", expand=True, padx=5)

        lbl_title = ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=12), text_color="#64748b")
        lbl_title.pack(pady=(8, 2))

        lbl_val = ctk.CTkLabel(card, text=init_val, font=ctk.CTkFont(size=22, weight="bold"), text_color=color)
        lbl_val.pack(pady=(0, 8))
        return lbl_val

    # --- Accounts Tab ---
    def _build_accounts_tab(self):
        add_frame = ctk.CTkFrame(self.tab_accounts, fg_color="#f8fafc")
        add_frame.pack(fill="x", pady=10, padx=5)

        lbl = ctk.CTkLabel(add_frame, text="Tài khoản X (Twitter): @", font=ctk.CTkFont(weight="bold"), text_color="#1e293b")
        lbl.pack(side="left", padx=10, pady=10)

        self.entry_account = ctk.CTkEntry(add_frame, placeholder_text="Ví dụ: elonmusk, OpenAI...", width=250)
        self.entry_account.pack(side="left", padx=10, pady=10)

        btn_add = ctk.CTkButton(add_frame, text="➕ Thêm Tài khoản", command=self.add_account, fg_color="#2563eb", hover_color="#1d4ed8")
        btn_add.pack(side="left", padx=10, pady=10)

        list_lbl = ctk.CTkLabel(self.tab_accounts, text="Danh sách tài khoản X đang quản lý:", font=ctk.CTkFont(size=14, weight="bold"), text_color="#1e293b")
        list_lbl.pack(anchor="w", pady=(10, 5), padx=5)

        self.acc_scroll = ctk.CTkScrollableFrame(self.tab_accounts, height=380, fg_color="#ffffff")
        self.acc_scroll.pack(fill="both", expand=True, padx=5, pady=5)

    # --- Gemini Tab ---
    def _build_gemini_tab(self):
        frame = ctk.CTkScrollableFrame(self.tab_gemini, fg_color="#ffffff")
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.switch_use_gemini = ctk.CTkSwitch(frame, text="🤖 Bật sử dụng Gemini AI để tóm tắt / biên tập tin tức (Khi TẮT sẽ gửi thẳng toàn bộ bài gốc)", font=ctk.CTkFont(weight="bold"))
        self.switch_use_gemini.pack(anchor="w", pady=(5, 15))

        lbl_key = ctk.CTkLabel(frame, text="Gemini API Key:", font=ctk.CTkFont(weight="bold"), text_color="#1e293b")
        lbl_key.pack(anchor="w", pady=(5, 2))

        self.entry_gemini_key = ctk.CTkEntry(frame, placeholder_text="Nhập Google Gemini API Key...", show="*", width=500)
        self.entry_gemini_key.pack(anchor="w", pady=(0, 10))

        lbl_model = ctk.CTkLabel(frame, text="Mô hình Gemini (Mới nhất):", font=ctk.CTkFont(weight="bold"), text_color="#1e293b")
        lbl_model.pack(anchor="w", pady=(5, 2))

        self.combo_gemini_model = ctk.CTkComboBox(frame, values=GEMINI_MODELS, width=300)
        self.combo_gemini_model.set("gemini-3.6-flash")
        self.combo_gemini_model.pack(anchor="w", pady=(0, 10))

        lbl_style = ctk.CTkLabel(frame, text="Phong cách Biên tập Mặc định:", font=ctk.CTkFont(weight="bold"), text_color="#1e293b")
        lbl_style.pack(anchor="w", pady=(5, 2))

        self.combo_style = ctk.CTkComboBox(frame, values=["Song ngữ Anh - Việt", "Phong cách Báo chí"], width=300)
        self.combo_style.set("Song ngữ Anh - Việt")
        self.combo_style.pack(anchor="w", pady=(0, 10))

        lbl_prompt = ctk.CTkLabel(frame, text="Custom Prompt (Hỗ trợ biến {author} và {text}):", font=ctk.CTkFont(weight="bold"), text_color="#1e293b")
        lbl_prompt.pack(anchor="w", pady=(5, 2))

        self.txt_prompt = ctk.CTkTextbox(frame, height=140, width=680, fg_color="#f8fafc")
        self.txt_prompt.pack(anchor="w", pady=(0, 10))

        btn_test_gemini = ctk.CTkButton(frame, text="🧪 Kiểm tra kết nối Gemini API", command=self.test_gemini, fg_color="#7c3aed", hover_color="#6d28d9")
        btn_test_gemini.pack(anchor="w", pady=10)

        btn_save_gemini = ctk.CTkButton(frame, text="💾 Lưu Cấu hình Gemini", command=self.save_gemini_settings, fg_color="#059669", hover_color="#047857")
        btn_save_gemini.pack(anchor="w", pady=5)

    # --- Telegram Tab ---
    def _build_telegram_tab(self):
        frame = ctk.CTkScrollableFrame(self.tab_telegram, fg_color="#ffffff")
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        lbl_token = ctk.CTkLabel(frame, text="Telegram Bot Token:", font=ctk.CTkFont(weight="bold"), text_color="#1e293b")
        lbl_token.pack(anchor="w", pady=(5, 2))

        self.entry_tg_token = ctk.CTkEntry(frame, placeholder_text="Nhập Telegram Bot Token...", show="*", width=500)
        self.entry_tg_token.pack(anchor="w", pady=(0, 10))

        lbl_chat_id = ctk.CTkLabel(frame, text="Telegram Group Chat ID (Hỗ trợ ID nhóm như -100xxx):", font=ctk.CTkFont(weight="bold"), text_color="#1e293b")
        lbl_chat_id.pack(anchor="w", pady=(5, 2))

        self.entry_tg_chat_id = ctk.CTkEntry(frame, placeholder_text="Nhập Group Chat ID...", width=350)
        self.entry_tg_chat_id.pack(anchor="w", pady=(0, 15))

        btn_test_tg = ctk.CTkButton(frame, text="🧪 Gửi tin nhắn thử nghiệm Telegram", command=self.test_telegram, fg_color="#2563eb", hover_color="#1d4ed8")
        btn_test_tg.pack(anchor="w", pady=10)

        btn_save_tg = ctk.CTkButton(frame, text="💾 Lưu Cấu hình Telegram", command=self.save_telegram_settings, fg_color="#059669", hover_color="#047857")
        btn_save_tg.pack(anchor="w", pady=5)

    # --- History Tab ---
    def _build_history_tab(self):
        top_frame = ctk.CTkFrame(self.tab_history, fg_color="#f8fafc")
        top_frame.pack(fill="x", pady=5, padx=5)

        lbl = ctk.CTkLabel(top_frame, text="Lịch sử Tóm tắt Bài đăng Phân loại theo Nguồn tin:", font=ctk.CTkFont(size=14, weight="bold"), text_color="#1e293b")
        lbl.pack(side="left", padx=10, pady=10)

        # Source Filter for History
        self.combo_hist_filter = ctk.CTkComboBox(
            top_frame,
            values=["Tất cả nguồn tin"],
            command=lambda val: self._refresh_history_list(),
            width=200
        )
        self.combo_hist_filter.set("Tất cả nguồn tin")
        self.combo_hist_filter.pack(side="right", padx=10, pady=10)

        lbl_f = ctk.CTkLabel(top_frame, text="Lọc theo nguồn:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#475569")
        lbl_f.pack(side="right", padx=(5, 2))

        self.hist_scroll = ctk.CTkScrollableFrame(self.tab_history, height=450, fg_color="#ffffff")
        self.hist_scroll.pack(fill="both", expand=True, padx=5, pady=5)

    # --- Settings Tab ---
    def _build_settings_tab(self):
        frame = ctk.CTkScrollableFrame(self.tab_settings, fg_color="#ffffff")
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        lbl_sec1 = ctk.CTkLabel(frame, text="1. Tần suất & Cấu hình Thu thập", font=ctk.CTkFont(size=15, weight="bold"), text_color="#1e293b")
        lbl_sec1.pack(anchor="w", pady=(5, 5))

        lbl_interval = ctk.CTkLabel(frame, text="Tần suất quét tin mới (Giây):")
        lbl_interval.pack(anchor="w", pady=(2, 2))
        self.entry_interval = ctk.CTkEntry(frame, width=150)
        self.entry_interval.pack(anchor="w", pady=(0, 10))

        lbl_limit = ctk.CTkLabel(frame, text="Giới hạn ký tự bài quá ngắn (Bỏ qua Gemini API nếu < N ký tự):")
        lbl_limit.pack(anchor="w", pady=(2, 2))
        self.entry_short_limit = ctk.CTkEntry(frame, width=150)
        self.entry_short_limit.pack(anchor="w", pady=(0, 10))

        lbl_max_age = ctk.CTkLabel(frame, text="Giới hạn thời gian tối đa để nhận tin mới (Giờ): (Ví dụ: 6 giờ)")
        lbl_max_age.pack(anchor="w", pady=(2, 2))
        self.entry_max_age = ctk.CTkEntry(frame, width=150)
        self.entry_max_age.pack(anchor="w", pady=(0, 10))

        self.switch_skip_existing = ctk.CTkSwitch(frame, text="🛡 Bỏ qua toàn bộ bài viết cũ khi mới chạy/mới thêm tài khoản (Chống Spam)")
        self.switch_skip_existing.pack(anchor="w", pady=(5, 10))

        self.switch_media = ctk.CTkSwitch(frame, text="Bật thu thập Media (Hình ảnh) phòng khi cần")
        self.switch_media.pack(anchor="w", pady=(5, 15))

        lbl_sec2 = ctk.CTkLabel(frame, text="2. Sao lưu & Phục hồi Cấu hình (Export / Import JSON)", font=ctk.CTkFont(size=15, weight="bold"), text_color="#1e293b")
        lbl_sec2.pack(anchor="w", pady=(10, 5))

        ex_frame = ctk.CTkFrame(frame, fg_color="transparent")
        ex_frame.pack(anchor="w", pady=5)
        btn_export = ctk.CTkButton(ex_frame, text="📤 Export Cấu hình (JSON)", command=self.export_config, fg_color="#2563eb")
        btn_export.pack(side="left", padx=5, pady=5)
        btn_import = ctk.CTkButton(ex_frame, text="📥 Import Cấu hình (JSON)", command=self.import_config, fg_color="#7c3aed")
        btn_import.pack(side="left", padx=5, pady=5)

        lbl_sec3 = ctk.CTkLabel(frame, text="3. Dọn dẹp Dữ liệu & Clear Cache", font=ctk.CTkFont(size=15, weight="bold"), text_color="#1e293b")
        lbl_sec3.pack(anchor="w", pady=(15, 5))

        cl_frame = ctk.CTkFrame(frame, fg_color="transparent")
        cl_frame.pack(anchor="w", pady=5)
        btn_clean_cache = ctk.CTkButton(cl_frame, text="🧹 Xóa Gemini Cache", command=self.clear_cache, fg_color="#dc2626", hover_color="#b91c1c")
        btn_clean_cache.pack(side="left", padx=5, pady=5)
        btn_clean_all = ctk.CTkButton(cl_frame, text="🗑 Xóa Toàn bộ Nhật ký & Lịch sử", command=self.cleanup_all_data, fg_color="#dc2626", hover_color="#b91c1c")
        btn_clean_all.pack(side="left", padx=5, pady=5)

        btn_save_all = ctk.CTkButton(frame, text="💾 Lưu Tất cả Cài đặt", command=self.save_general_settings, fg_color="#059669", hover_color="#047857", font=ctk.CTkFont(weight="bold"))
        btn_save_all.pack(anchor="w", pady=20)

    # --- About Tab ---
    def _build_about_tab(self):
        from PIL import Image
        frame = ctk.CTkScrollableFrame(self.tab_about, fg_color="#ffffff")
        frame.pack(fill="both", expand=True, padx=15, pady=15)

        # Title Card
        title_box = ctk.CTkFrame(frame, corner_radius=12, fg_color="#e0f2fe", border_width=1, border_color="#0284c7")
        title_box.pack(fill="x", pady=10, padx=5)

        img_path = get_resource_path(os.path.join("assets", "app_icon.png"))
        if os.path.exists(img_path):
            try:
                pil_img = Image.open(img_path)
                icon_ctk = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(80, 80))
                lbl_img = ctk.CTkLabel(title_box, image=icon_ctk, text="")
                lbl_img.pack(side="left", padx=(20, 5), pady=15)
            except Exception:
                pass

        txt_frame = ctk.CTkFrame(title_box, fg_color="transparent")
        txt_frame.pack(side="left", fill="both", expand=True, padx=10, pady=15)

        app_title = ctk.CTkLabel(txt_frame, text="⚡ Social News Monitor AI", font=ctk.CTkFont(size=22, weight="bold"), text_color="#0369a1", anchor="w")
        app_title.pack(anchor="w", pady=(0, 2))

        app_subtitle = ctk.CTkLabel(txt_frame, text="Hệ thống Theo dõi Mạng xã hội, Biên tập Gemini AI & Tự động Thông báo Telegram", font=ctk.CTkFont(size=13), text_color="#0c4a6e", anchor="w")
        app_subtitle.pack(anchor="w", pady=0)

        meta_box = ctk.CTkFrame(frame, corner_radius=10, fg_color="#f8fafc", border_width=1, border_color="#e2e8f0")
        meta_box.pack(fill="x", pady=10, padx=5)

        lbl_meta_hdr = ctk.CTkLabel(meta_box, text="📌 THÔNG TIN PHẦN MỀM & BẢN QUYỀN", font=ctk.CTkFont(size=14, weight="bold"), text_color="#1e293b")
        lbl_meta_hdr.pack(anchor="w", padx=15, pady=(12, 8))

        items = [
            ("👤 Tác giả (Author)", "Mindz"),
            ("🚀 Phiên bản (Version)", "v2.5.0 (Release 2026)"),
            ("© Bản quyền (Copyright)", "© 2026 Mindz. All Rights Reserved."),
            ("🖥 Hệ điều hành hỗ trợ", "Windows 10 / 11 & Google Cloud VPS (Headless Mode)")
        ]
        for label, val in items:
            row = ctk.CTkFrame(meta_box, fg_color="transparent")
            row.pack(fill="x", padx=15, pady=3)
            l_lbl = ctk.CTkLabel(row, text=label, font=ctk.CTkFont(weight="bold", size=12), text_color="#475569", width=220, anchor="w")
            l_lbl.pack(side="left")
            r_lbl = ctk.CTkLabel(row, text=val, font=ctk.CTkFont(size=12, weight="bold" if label.startswith("👤") else "normal"), text_color="#0f172a", anchor="w")
            r_lbl.pack(side="left")

        tech_box = ctk.CTkFrame(frame, corner_radius=10, fg_color="#f8fafc", border_width=1, border_color="#e2e8f0")
        tech_box.pack(fill="x", pady=10, padx=5)

        lbl_tech_hdr = ctk.CTkLabel(tech_box, text="🛠 CÁC THÀNH PHẦN & CÔNG NGHỆ TÍCH HỢP", font=ctk.CTkFont(size=14, weight="bold"), text_color="#1e293b")
        lbl_tech_hdr.pack(anchor="w", padx=15, pady=(12, 8))

        tech_items = [
            ("Core Programming", "Python 3.12 (CPython Engine)"),
            ("Desktop UI Framework", "CustomTkinter Framework (Light Theme Edition)"),
            ("Artificial Intelligence (AI)", "Google Gemini API (SDK `google-genai` - Gemini 3.6 Flash)"),
            ("Crawler Engine", "Multi-Instance Nitter / RSS Parser Engine với Anti-Rate Limit & Jitter"),
            ("Notification System", "Telegram Bot API (Group Markdown Format) & Windows Toast Notification (`plyer`)"),
            ("Storage & Cache", "JSON Flat Database Engine (`data/*.json` - Baseline Seeding & Cache)")
        ]
        for label, val in tech_items:
            row = ctk.CTkFrame(tech_box, fg_color="transparent")
            row.pack(fill="x", padx=15, pady=3)
            l_lbl = ctk.CTkLabel(row, text=f"• {label}:", font=ctk.CTkFont(weight="bold", size=12), text_color="#475569", width=220, anchor="w")
            l_lbl.pack(side="left")
            r_lbl = ctk.CTkLabel(row, text=val, font=ctk.CTkFont(size=12), text_color="#0f172a", anchor="w")
            r_lbl.pack(side="left")

    def _copy_to_clipboard(self, text: str, button_widget=None):
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.update()
            if button_widget:
                original_text = button_widget.cget("text")
                button_widget.configure(text="✅ Đã Copy!", fg_color="#059669")
                self.after(1800, lambda: button_widget.configure(text=original_text, fg_color="#7c3aed"))
            self.on_service_log("INFO", "📋 Đã sao chép nội dung bài đăng vào Clipboard.")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể sao chép: {e}")

    def _format_to_gmt7(self, time_str: str) -> str:
        if not time_str:
            return time.strftime("%H:%M:%S %d/%m/%Y (GMT+7)")
        if "(GMT+7)" in time_str:
            return time_str
        try:
            import email.utils
            from datetime import timezone, timedelta
            dt = email.utils.parsedate_to_datetime(time_str)
            if dt:
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                gmt7_dt = dt.astimezone(timezone(timedelta(hours=7)))
                return gmt7_dt.strftime("%H:%M:%S %d/%m/%Y (GMT+7)")
        except Exception:
            pass
        return time_str

    # --- Render Post Cards for Dashboard & History ---
    def _create_post_card(self, parent, post_data: dict):
        account = post_data.get("account", "Unkown")
        summary = post_data.get("summary", "")
        raw_text = post_data.get("raw_text", "")
        url = post_data.get("url", "")
        raw_ts = post_data.get("timestamp") or post_data.get("published_at") or ""
        gmt7_time = self._format_to_gmt7(raw_ts)

        card = ctk.CTkFrame(parent, corner_radius=8, fg_color="#f8fafc", border_width=1, border_color="#e2e8f0")
        card.pack(fill="x", pady=6, padx=4)

        top_row = ctk.CTkFrame(card, fg_color="transparent")
        top_row.pack(fill="x", padx=10, pady=(8, 4))

        # Account Badge Tag
        badge = ctk.CTkLabel(top_row, text=f" @{account} ", font=ctk.CTkFont(size=12, weight="bold"), text_color="#ffffff", fg_color="#2563eb", corner_radius=6)
        badge.pack(side="left")

        time_lbl = ctk.CTkLabel(top_row, text=f"⏰ {gmt7_time}", font=ctk.CTkFont(size=11), text_color="#64748b")
        time_lbl.pack(side="left", padx=10)

        # Action Buttons on Right (Copy & Original Link)
        display_text = summary if summary else raw_text

        btn_copy = ctk.CTkButton(
            top_row,
            text="📋 Copy",
            font=ctk.CTkFont(size=11, weight="bold"),
            width=70,
            height=24,
            fg_color="#7c3aed",
            hover_color="#6d28d9",
            command=lambda t=display_text: self._copy_to_clipboard(t, btn_copy)
        )
        btn_copy.pack(side="right", padx=(5, 0))

        if url:
            btn_link = ctk.CTkButton(
                top_row,
                text="🔗 Bài gốc",
                font=ctk.CTkFont(size=11),
                width=80,
                height=24,
                fg_color="#0284c7",
                hover_color="#0369a1",
                command=lambda u=url: webbrowser.open(u)
            )
            btn_link.pack(side="right", padx=(0, 5))

        # Content Summary Body with Selectable & Copyable Textbox
        lines_count = max(2, len(display_text.split('\n')) + len(display_text) // 60)
        box_height = min(220, max(50, lines_count * 20))

        txt_content = ctk.CTkTextbox(
            card,
            font=ctk.CTkFont(size=12),
            fg_color="#ffffff",
            text_color="#1e293b",
            height=box_height,
            wrap="word",
            border_width=1,
            border_color="#cbd5e1"
        )
        txt_content.insert("1.0", display_text)
        txt_content.pack(fill="x", padx=10, pady=(2, 10))

    def _refresh_source_filter_dropdown(self):
        accounts = self.db.get_accounts()
        options = ["Tất cả nguồn tin"] + [f"@{a['identifier']}" for a in accounts]
        self.combo_source_filter.configure(values=options)
        self.combo_hist_filter.configure(values=options)

    def _refresh_dashboard_feed(self):
        for widget in self.feed_scroll.winfo_children():
            widget.destroy()

        selected_filter = self.combo_source_filter.get()
        posts = self.db.get_history(account_filter=selected_filter, limit=50)

        if not posts:
            lbl_empty = ctk.CTkLabel(self.feed_scroll, text="Chưa có bài đăng nào từ nguồn tin này.", text_color="#94a3b8")
            lbl_empty.pack(pady=30)
            return

        for post in posts:
            self._create_post_card(self.feed_scroll, post)

    def _refresh_history_list(self):
        for widget in self.hist_scroll.winfo_children():
            widget.destroy()

        selected_filter = self.combo_hist_filter.get()
        history = self.db.get_history(account_filter=selected_filter, limit=100)

        if not history:
            lbl_empty = ctk.CTkLabel(self.hist_scroll, text="Chưa có lịch sử bài đăng nào từ nguồn tin đã chọn.", text_color="#94a3b8")
            lbl_empty.pack(pady=30)
            return

        for h in history:
            self._create_post_card(self.hist_scroll, h)

    def on_service_post_received(self, post_data: dict):
        def _update():
            self._refresh_dashboard_feed()
            self._refresh_history_list()

        self.after(0, _update)

    # --- Logic & Handlers ---
    def _load_saved_settings(self):
        use_gemini = self.db.get_setting("use_gemini", True)
        key = self.db.get_setting("gemini_api_key", "")
        model = self.db.get_setting("gemini_model", "gemini-3.6-flash")
        style = self.db.get_setting("style_preset", "bilingual")
        prompt = self.db.get_setting("custom_prompt", "")

        if use_gemini:
            self.switch_use_gemini.select()
        else:
            self.switch_use_gemini.deselect()

        bot_token = self.db.get_setting("telegram_bot_token", "")
        chat_id = self.db.get_setting("telegram_chat_id", "")
        interval = self.db.get_setting("poll_interval", 60)
        short_limit = self.db.get_setting("short_post_limit", 40)
        max_age = self.db.get_setting("max_post_age_hours", 6)
        skip_existing = self.db.get_setting("skip_existing_on_start", True)
        collect_media = self.db.get_setting("collect_media", False)

        if key:
            self.entry_gemini_key.delete(0, "end")
            self.entry_gemini_key.insert(0, key)
        self.combo_gemini_model.set(model)
        self.combo_style.set("Song ngữ Anh - Việt" if style == "bilingual" else "Phong cách Báo chí")
        
        if prompt:
            self.txt_prompt.delete("1.0", "end")
            self.txt_prompt.insert("1.0", prompt)

        if bot_token:
            self.entry_tg_token.delete(0, "end")
            self.entry_tg_token.insert(0, bot_token)
        if chat_id:
            self.entry_tg_chat_id.delete(0, "end")
            self.entry_tg_chat_id.insert(0, chat_id)

        self.entry_interval.delete(0, "end")
        self.entry_interval.insert(0, str(interval))

        self.entry_short_limit.delete(0, "end")
        self.entry_short_limit.insert(0, str(short_limit))

        self.entry_max_age.delete(0, "end")
        self.entry_max_age.insert(0, str(max_age))

        if skip_existing:
            self.switch_skip_existing.select()
        else:
            self.switch_skip_existing.deselect()

        if collect_media:
            self.switch_media.select()
        else:
            self.switch_media.deselect()

    def _refresh_accounts_list(self):
        for widget in self.acc_scroll.winfo_children():
            widget.destroy()

        accounts = self.db.get_accounts()
        active_count = sum(1 for a in accounts if a.get("is_active", True))
        self.card_accounts.configure(text=str(active_count))

        if not accounts:
            lbl_empty = ctk.CTkLabel(self.acc_scroll, text="Chưa có tài khoản nào. Vui lòng thêm tài khoản ở trên.", text_color="gray")
            lbl_empty.pack(pady=20)
            return

        for acc in accounts:
            row = ctk.CTkFrame(self.acc_scroll, fg_color="#f8fafc")
            row.pack(fill="x", pady=4, padx=5)

            lbl_name = ctk.CTkLabel(row, text=f"@{acc['identifier']}", font=ctk.CTkFont(weight="bold"), text_color="#1e293b", width=200, anchor="w")
            lbl_name.pack(side="left", padx=10)

            switch_var = ctk.BooleanVar(value=bool(acc.get("is_active", True)))
            switch = ctk.CTkSwitch(row, text="Bật" if acc.get("is_active", True) else "Tắt", variable=switch_var,
                                   command=lambda a_id=acc["id"], v=switch_var: self._toggle_account(a_id, v))
            switch.pack(side="left", padx=20)

            btn_test = ctk.CTkButton(row, text="🧪 Test", width=65, fg_color="#7c3aed", hover_color="#6d28d9",
                                    command=lambda a_name=acc["identifier"]: self.send_test_latest(a_name))
            btn_test.pack(side="right", padx=5)

            btn_del = ctk.CTkButton(row, text="🗑 Xóa", width=60, fg_color="#dc2626", hover_color="#b91c1c",
                                    command=lambda a_id=acc["id"]: self._delete_account(a_id))
            btn_del.pack(side="right", padx=5)

        self._refresh_source_filter_dropdown()

    def _toggle_account(self, acc_id: int, var: ctk.BooleanVar):
        self.db.toggle_account(acc_id, var.get())
        self._refresh_accounts_list()

    def _delete_account(self, acc_id: int):
        self.db.delete_account(acc_id)
        self._refresh_accounts_list()

    def add_account(self):
        val = self.entry_account.get().strip()
        if not val:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập tên tài khoản!")
            return
        success = self.db.add_account(val)
        if success:
            self.entry_account.delete(0, "end")
            self._refresh_accounts_list()
            self.on_service_log("INFO", f"Đã thêm tài khoản @{val}")
        else:
            messagebox.showerror("Lỗi", "Tài khoản đã tồn tại!")

    def save_gemini_settings(self):
        use_gemini = bool(self.switch_use_gemini.get())
        key = self.entry_gemini_key.get().strip()
        model = self.combo_gemini_model.get().strip()
        style = "bilingual" if self.combo_style.get() == "Song ngữ Anh - Việt" else "journalistic"
        prompt = self.txt_prompt.get("1.0", "end-1c").strip()

        self.db.set_setting("use_gemini", use_gemini)
        self.db.set_setting("gemini_api_key", key)
        self.db.set_setting("gemini_model", model)
        self.db.set_setting("style_preset", style)
        self.db.set_setting("custom_prompt", prompt)
        self.service._reload_config()
        messagebox.showinfo("Thành công", "Đã lưu cấu hình Gemini API!")

    def save_telegram_settings(self):
        bot_token = self.entry_tg_token.get().strip()
        chat_id = self.entry_tg_chat_id.get().strip()

        self.db.set_setting("telegram_bot_token", bot_token)
        self.db.set_setting("telegram_chat_id", chat_id)
        self.service._reload_config()
        messagebox.showinfo("Thành công", "Đã lưu cấu hình Telegram Bot!")

    def save_general_settings(self):
        interval = self.entry_interval.get().strip()
        short_limit = self.entry_short_limit.get().strip()
        max_age = self.entry_max_age.get().strip()
        skip_existing = bool(self.switch_skip_existing.get())
        collect_media = bool(self.switch_media.get())

        if not interval.isdigit() or int(interval) < 10:
            messagebox.showwarning("Cảnh báo", "Tần suất quét phải từ 10 giây trở lên!")
            return

        self.db.set_setting("poll_interval", int(interval))
        self.db.set_setting("short_post_limit", int(short_limit) if short_limit.isdigit() else 40)
        self.db.set_setting("max_post_age_hours", float(max_age) if max_age.replace('.', '', 1).isdigit() else 6.0)
        self.db.set_setting("skip_existing_on_start", skip_existing)
        self.db.set_setting("collect_media", collect_media)
        self.service._reload_config()
        messagebox.showinfo("Thành công", "Đã lưu cài đặt chung & Chống Spam!")

    def export_config(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Files", "*.json")])
        if file_path:
            ok = self.db.export_config(file_path)
            if ok:
                messagebox.showinfo("Thành công", f"Đã export cấu hình ra: {file_path}")
            else:
                messagebox.showerror("Lỗi", "Không thể export tệp cấu hình!")

    def import_config(self):
        file_path = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
        if file_path:
            ok = self.db.import_config(file_path)
            if ok:
                self._load_saved_settings()
                self._refresh_accounts_list()
                self._refresh_dashboard_feed()
                messagebox.showinfo("Thành công", "Đã import cấu hình thành công!")
            else:
                messagebox.showerror("Lỗi", "Không thể import tệp cấu hình!")

    def clear_cache(self):
        self.db.clear_cache()
        messagebox.showinfo("Thành công", "Đã xóa toàn bộ Gemini Cache!")

    def cleanup_all_data(self):
        if messagebox.askyesno("Xác nhận", "Bạn có chắc muốn xóa toàn bộ lịch sử và nhật ký hoạt động?"):
            self.db.cleanup_old_data()
            self._refresh_dashboard_feed()
            self._refresh_history_list()
            self._load_recent_logs()
            messagebox.showinfo("Thành công", "Đã dọn dẹp toàn bộ dữ liệu!")

    def test_gemini(self):
        key = self.entry_gemini_key.get().strip()
        model = self.combo_gemini_model.get().strip()
        if not key:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập Gemini API Key trước.")
            return

        def run():
            ai = AIProcessor(api_key=key, model_name=model)
            ok, msg = ai.test_connection()
            if ok:
                messagebox.showinfo("Thành công", msg)
            else:
                messagebox.showerror("Lỗi", msg)

        threading.Thread(target=run, daemon=True).start()

    def test_telegram(self):
        token = self.entry_tg_token.get().strip()
        chat_id = self.entry_tg_chat_id.get().strip()
        if not token or not chat_id:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập Bot Token và Chat ID trước.")
            return

        def run():
            notifier = TelegramNotifier(bot_token=token, default_chat_id=chat_id)
            ok, msg = notifier.test_connection()
            if ok:
                messagebox.showinfo("Thành công", msg)
            else:
                messagebox.showerror("Lỗi", msg)

        threading.Thread(target=run, daemon=True).start()

    def start_monitoring(self):
        self.service.start()
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.status_badge.configure(text="● Đang chạy theo dõi", text_color="#059669")

    def stop_monitoring(self):
        self.service.stop()
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.status_badge.configure(text="● Đang tạm dừng", text_color="#dc2626")

    def check_now(self):
        self.service.check_now()

    def send_test_latest(self, account_identifier: str = None):
        selected_filter = self.combo_source_filter.get()
        if not account_identifier and selected_filter != "Tất cả nguồn tin":
            account_identifier = selected_filter

        def run():
            ok, msg = self.service.send_test_latest_post(account_identifier)
            if ok:
                messagebox.showinfo("Thành công", msg)
            else:
                messagebox.showerror("Thông báo / Lỗi", msg)

        threading.Thread(target=run, daemon=True).start()

    def on_service_log(self, level: str, message: str):
        def _update():
            timestamp = time.strftime("%H:%M:%S")
            prefix = "[INFO]"
            if level == "SUCCESS":
                prefix = "✅ [SUCCESS]"
            elif level == "ERROR":
                prefix = "❌ [ERROR]"
            elif level == "WARNING":
                prefix = "⚠️ [WARN]"

            log_line = f"[{timestamp}] {prefix} {message}\n"
            self.log_box.insert("end", log_line)
            self.log_box.see("end")

        self.after(0, _update)

    def on_service_stats(self, checked: int, sent: int, errors: int):
        def _update():
            self.card_checked.configure(text=str(checked))
            self.card_sent.configure(text=str(sent))
            self.card_errors.configure(text=str(errors))

        self.after(0, _update)

    def _load_recent_logs(self):
        logs = self.db.get_logs(50)
        for log in reversed(logs):
            msg = log["message"]
            lvl = log["level"]
            t = log["timestamp"]
            self.log_box.insert("end", f"[{t}] [{lvl}] {msg}\n")
        self.log_box.see("end")

    def on_close_window(self):
        if self.service.is_running:
            if messagebox.askyesno("Thoát", "Phần mềm đang chạy theo dõi. Bạn có muốn tạm dừng và thoát hoàn toàn không?"):
                self.service.stop()
                self.destroy()
        else:
            self.destroy()

if __name__ == "__main__":
    app = NewsMonitorApp()
    app.mainloop()
