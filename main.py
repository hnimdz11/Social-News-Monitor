import os
import sys
import time
import argparse
import logging

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def run_headless_cli():
    """Chế độ Headless CLI cho Google Cloud VPS hoặc Server 24/7."""
    print("=" * 60)
    print("⚡ Social News Monitor - Chế độ Headless Server (Google Cloud VPS)")
    print("=" * 60)
    
    from json_db import JsonDatabase
    from service import MonitorService

    db = JsonDatabase()
    service = MonitorService(db)

    def log_listener(level, message):
        print(f"[{level}] {message}")

    service.on_log_callback = log_listener
    service.start()

    print("Phần mềm đang chạy ngầm trên Server... Nhấn Ctrl+C để dừng.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nĐang dừng phần mềm...")
        service.stop()

def main():
    parser = argparse.ArgumentParser(description="Social News Monitor (X/Twitter, Gemini AI, Telegram Bot)")
    parser.add_argument("--cli", "--headless", action="store_true", help="Chạy ở chế độ dòng lệnh không cần GUI (phù hợp cho Server/Google Cloud VPS)")
    args = parser.parse_args()

    if args.cli:
        run_headless_cli()
    else:
        try:
            from gui import NewsMonitorApp
            app = NewsMonitorApp()
            app.mainloop()
        except Exception as e:
            logging.critical(f"Lỗi khởi chạy ứng dụng GUI: {e}", exc_info=True)

if __name__ == "__main__":
    main()
