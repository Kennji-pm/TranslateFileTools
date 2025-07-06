import sys
import signal
import atexit
import traceback
import os

from src.managers.config_manager import ConfigManager
from src.managers.api_manager import APIManager
from src.managers.project_manager import ProjectManager
from src.handlers.file_handler import FileHandler
from src.core.translation_core import TranslationCore
from src.ui.ui_manager import UIManager
from src.utils.utils import clear_screen

class MainApplication:
    def __init__(self):
        self.translation_errors = []
        self.translation_warnings = []

        self.config_manager = ConfigManager()
        self.api_manager = APIManager(self.config_manager)
        self.file_handler = FileHandler(self.translation_errors, self.translation_warnings)
        self.project_manager = ProjectManager(self.config_manager)
        self.translation_core = TranslationCore(self.config_manager, self.api_manager, self.file_handler)
        self.ui_manager = UIManager(self.config_manager, self.project_manager, self.translation_errors, self.translation_warnings)

        atexit.register(self._cleanup_on_exit)
        signal.signal(signal.SIGINT, self._signal_handler)

        self._initial_setup()

    def _signal_handler(self, sig, frame):
        print("\n\n🛑 Đang dừng chương trình và dọn dẹp...")
        self._cleanup_on_exit()
        sys.exit(0)

    def _cleanup_on_exit(self):
        self.project_manager.cleanup_temp_folders()

    def _initial_setup(self):
        self.ui_manager.print_header("Khởi Chạy")
        print("Đang kiểm tra cấu hình và API...")
        
        # Ensure necessary directories exist
        os.makedirs(self.config_manager.get_input_folder(), exist_ok=True)
        os.makedirs(self.config_manager.get_output_folder(), exist_ok=True)
        os.makedirs(self.config_manager.get_projects_folder(), exist_ok=True)

        # Configure API if not already done or if model is not set
        if not self.api_manager.get_model():
            self.api_manager.configure_api_interactively(self.ui_manager)

    def run(self):
        try:
            self.ui_manager.main_menu(self.api_manager, self.translation_core)
        except KeyboardInterrupt:
            clear_screen()
            print("\n\n🛑 Chương trình bị ngắt bởi người dùng...")
            self._cleanup_on_exit()
            print("👋 Cảm ơn đã sử dụng công cụ Dịch File!")
        except Exception as e:
            clear_screen()
            print(f"\n❌ Đã xảy ra lỗi không mong muốn: {str(e)}")
            traceback.print_exc()
            print("Vui lòng báo lỗi này cho nhà phát triển nếu cần thiết.")
            self._cleanup_on_exit()
            input("\nNhấn Enter để thoát.")
        finally:
            print("\nĐóng chương trình.")

if __name__ == "__main__":
    app = MainApplication()
    app.run()
