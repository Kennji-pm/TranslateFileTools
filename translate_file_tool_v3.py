import yaml
import time
import json
import re
import os
import shutil
import sys
import signal
import atexit
import threading
import concurrent.futures
import datetime
import random
import traceback

from colorama import Fore
from tqdm import tqdm
from google import genai
from dotenv import load_dotenv
from typing import Any, Dict, List, Optional, Tuple

def clear_screen():
    """Xóa màn hình console"""
    os.system('cls' if os.name == 'nt' else 'clear')

class ExponentialBackoff:
    """Lớp quản lý backoff theo cấp số nhân cho các API request"""

    def __init__(self, initial_delay=1.0, max_delay=60.0, factor=2.0, jitter=True):
        """
        Khởi tạo backoff manager

        initial_delay: Thời gian chờ ban đầu (giây)
        max_delay: Thời gian chờ tối đa (giây)
        factor: Hệ số nhân cho mỗi lần thử lại
        jitter: Thêm yếu tố ngẫu nhiên để tránh thundering herd
        """
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.factor = factor
        self.jitter = jitter
        self.attempt = 0

    def reset(self):
        """Reset số lần thử về 0"""
        self.attempt = 0

    def delay(self):
        """Tính toán thời gian chờ cho lần thử hiện tại"""
        self.attempt += 1
        delay = min(self.initial_delay * (self.factor ** (self.attempt - 1)), self.max_delay)

        if self.jitter:
            # Thêm jitter từ 0% đến 25% của delay
            jitter_amount = random.uniform(0, delay * 0.25)
            delay += jitter_amount

        return delay

    def wait(self):
        """Chờ theo thời gian được tính toán"""
        delay_time = self.delay()
        time.sleep(delay_time)
        return delay_time

class FileTranslator:
    def __init__(self):
        self.api_keys: List[str] = []
        self.model: Optional[genai.Client] = None
        self.temp_folders = []
        self.target_lang = "vi"
        self.project_root = "translator_projects" # Changed for clarity
        self.projects_folder = os.path.join(self.project_root, "projects")
        self.input_folder = os.path.join(self.project_root, "input_files") # Changed to handle both
        self.output_folder = os.path.join(self.project_root, "translated_files") # Changed to handle both
        self.max_workers = 4
        self.min_request_interval = 0.5  # Khoảng cách tối thiểu giữa các request (giây)
        self.max_retries = 5  # Số lần thử lại tối đa khi gặp lỗi
        self.backoff_factor = 2.0  # Hệ số tăng thời gian chờ
        self.config_file = os.path.join(self.project_root, "config.json")
        self.keep_original_filename = False

        self.translation_errors: List[str] = []
        self.translation_warnings: List[str] = []

        # Misc
        self.max_display_project_count = 5
        load_dotenv()

        # Đăng ký hàm dọn dẹp khi thoát
        atexit.register(self.cleanup_temp_folders)
        signal.signal(signal.SIGINT, self.signal_handler)

        # Tạo thư mục projects nếu chưa có
        os.makedirs(self.projects_folder, exist_ok=True)

        # Tải cấu hình nếu có
        self.load_config()

    def signal_handler(self, sig, frame):
        print("\n\n🛑 Đang dừng chương trình và dọn dẹp...")
        self.cleanup_temp_folders()
        sys.exit(0)

    def load_config(self):
        """Tải cấu hình từ file config.json nếu có"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                # Get api key
                api_key_data = config.get('api_keys') or config.get('api_key')
                if isinstance(api_key_data, list):
                    self.api_keys = [str(key) for key in api_key_data if isinstance(key, str) and key.strip()]
                elif isinstance(api_key_data, str) and api_key_data.strip():
                    self.api_keys = [k.strip() for k in api_key_data.split(',') if k.strip()]

                # Cập nhật các thuộc tính từ config
                self.target_lang = config.get('target_lang', self.target_lang)
                self.max_workers = config.get('max_workers', self.max_workers)
                self.input_folder = config.get('input_folder', self.input_folder)
                self.output_folder = config.get('output_folder', self.output_folder)
                self.min_request_interval = config.get('min_request_interval', self.min_request_interval)
                self.max_retries = config.get('max_retries', self.max_retries)
                self.backoff_factor = config.get('backoff_factor', self.backoff_factor)
                self.keep_original_filename = config.get('keep_original_filename', self.keep_original_filename)

                # Misc
                self.max_display_project_count = config.get('max_display_project_count', self.max_display_project_count)

                print(f"✅ Đã tải cấu hình từ {self.config_file}")
        except Exception as e:
            print(f"⚠️ Không thể đọc file cấu hình: {str(e)}")

    def save_config(self):
        """Lưu cấu hình vào file config.json"""
        try:
            config = {
                'api_keys': self.api_keys,
                'target_lang': self.target_lang,
                'max_workers': self.max_workers,
                'input_folder': self.input_folder,
                'output_folder': self.output_folder,
                'min_request_interval': self.min_request_interval,
                'max_retries': self.max_retries,
                'backoff_factor': self.backoff_factor,
                'keep_original_filename': self.keep_original_filename
            }

            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)

            print(f"✅ Đã lưu cấu hình vào {self.config_file}")
        except Exception as e:
            print(f"⚠️ Không thể lưu file cấu hình: {str(e)}")

    def setup(self):
        """Thiết lập ban đầu và cấu hình API"""
        for folder in [self.input_folder, self.output_folder, self.projects_folder]:
            os.makedirs(folder, exist_ok=True)

        if not self.api_keys:
            env_keys_str = os.getenv("GEMINI_API_KEYS")
            if env_keys_str:
                print("🔎 Tìm thấy API keys từ biến môi trường GEMINI_API_KEYS.")
                self.api_keys = [k.strip() for k in env_keys_str.split(',') if k.strip()]
            else:
                env_key_singular = os.getenv("GEMINI_API_KEY")
                if env_key_singular:
                    print("🔎 Tìm thấy API key từ biến môi trường GEMINI_API_KEY.")
                    self.api_keys = [env_key_singular.strip()]
        if self.api_keys:
            self._configure_genai_with_primary_key()
        else:
            print("🔑 Không tìm thấy API key trong cấu hình hoặc biến môi trường.")
            self.configure_api_interactively()

        self.save_config()

    def _print_header(self, title: str):
        clear_screen()
        print("=" * 70)
        print(f"🎨 CÔNG CỤ DỊCH FILE V3 - {title.upper()} 🎨".center(70))
        print("=" * 70)

    def _configure_genai_with_primary_key(self):
        """Configures the global genai object with the primary API key."""
        if not self.api_keys:
            self.model = None
            print("⚠️ Không có API key nào được cung cấp để cấu hình.")
            return

        primary_key = self.api_keys[0]
        try:
            self.model = genai.Client(api_key=primary_key)
            key_display = f"...{primary_key[-4:]}" if len(primary_key) > 4 else primary_key
            print(f"⚙️  Gemini API được cấu hình để sử dụng key chính kết thúc bằng: {key_display}")
            print(f"   Model sử dụng: gemini-2.0-flash")
        except Exception as e:
            self.model = None
            key_display = f"...{primary_key[-4:]}" if len(primary_key) > 4 else primary_key
            print(f"❌ Lỗi khi cấu hình Gemini API với key {key_display}: {str(e)}")
            print("   Vui lòng kiểm tra API key và thử lại.")

    def _display_api_keys(self):
        """Hiển thị danh sách các API key hiện có."""
        if self.api_keys:
            print(f"🔑 Các API key hiện có:")
            for i, key in enumerate(self.api_keys):
                key_display = f"...{key[-4:]}" if len(key) > 4 else key
                status = f" (Đang sử dụng)" if i == 0 else ""
                print(f"  [{i+1}] {key_display}{status}")
        else:
            print(f"🔑 Chưa có API key nào được cấu hình.")

    def _parse_file_selection_tokens(self, tokens: List[str], files_count: int, directory_name_for_messages: str) -> Tuple[List[int], bool]:
        """
        Parses selection tokens (like "1", "^3", "5-7", "all") into a list of 0-based indices.
        Returns a tuple: (list of 0-based indices, all_tokens_were_valid_and_processed_successfully).
        """
        selected_indices_set = set()
        all_tokens_valid_and_processed = True

        if not tokens:
            return [], True 

        for token in tokens:
            token_processed_successfully_this_iteration = False
            if token == 'all':
                selected_indices_set.update(range(files_count))
                token_processed_successfully_this_iteration = True
            elif token.startswith('^'):
                try:
                    start_num_1_based = int(token[1:])
                    if 1 <= start_num_1_based <= files_count:
                        start_idx_0_based = start_num_1_based - 1
                        selected_indices_set.update(range(start_idx_0_based, files_count))
                        token_processed_successfully_this_iteration = True
                    else:
                        print(f"⚠️ Số bắt đầu '{start_num_1_based}' cho ký hiệu '^' không hợp lệ. Phải nằm trong khoảng 1-{files_count}.")
                except ValueError:
                    print(f"⚠️ Định dạng không hợp lệ cho ký hiệu '^': {token}. Mong đợi dạng '^<số>'.")
            elif '-' in token:
                parts = token.split('-', 1)
                if len(parts) == 2:
                    try:
                        start_num_1_based = int(parts[0])
                        end_num_1_based = int(parts[1])
                        
                        start_idx_0_based = start_num_1_based - 1
                        end_idx_0_based = end_num_1_based - 1

                        if 0 <= start_idx_0_based < files_count and \
                           0 <= end_idx_0_based < files_count and \
                           start_idx_0_based <= end_idx_0_based:
                            selected_indices_set.update(range(start_idx_0_based, end_idx_0_based + 1))
                            token_processed_successfully_this_iteration = True
                        else:
                            if not (0 <= start_idx_0_based < files_count):
                                print(f"⚠️ Số bắt đầu '{start_num_1_based}' trong khoảng chọn '{token}' không hợp lệ. Phải nằm trong khoảng 1-{files_count}.")
                            elif not (0 <= end_idx_0_based < files_count):
                                print(f"⚠️ Số kết thúc '{end_num_1_based}' trong khoảng chọn '{token}' không hợp lệ. Phải nằm trong khoảng 1-{files_count}.")
                            elif start_idx_0_based > end_idx_0_based:
                                print(f"⚠️ Số bắt đầu '{start_num_1_based}' phải nhỏ hơn hoặc bằng số kết thúc '{end_num_1_based}' trong khoảng chọn '{token}'.")
                            else: # General fallback for invalid range
                                print(f"⚠️ Khoảng chọn '{token}' không hợp lệ. Hãy đảm bảo các số nằm trong khoảng 1-{files_count} và số đầu không lớn hơn số cuối.")
                    except ValueError:
                        print(f"⚠️ Số không hợp lệ trong khoảng chọn: {token}. Mong đợi dạng '<số>-<số>'.")
                else: # More or less than one '-'
                    print(f"⚠️ Định dạng khoảng chọn không hợp lệ: {token}. Sử dụng dạng '<số>-<số>' (ví dụ: 1-5).")
            else: # Assumed to be a single number
                try:
                    num_1_based = int(token)
                    idx_0_based = num_1_based - 1
                    if 0 <= idx_0_based < files_count:
                        selected_indices_set.add(idx_0_based)
                        token_processed_successfully_this_iteration = True
                    else:
                        print(f"⚠️ Số thứ tự file '{num_1_based}' không hợp lệ. Phải nằm trong khoảng 1-{files_count}.")
                except ValueError:
                    print(f"⚠️ Lựa chọn không nhận dạng được: '{token}'. Vui lòng nhập số, khoảng chọn (vd: 1-5), ^<số>, 'all'.")
            
            if not token_processed_successfully_this_iteration:
                all_tokens_valid_and_processed = False

        return sorted(list(selected_indices_set)), all_tokens_valid_and_processed

    def configure_api_interactively(self):
        while True:
            self._print_header("Cấu Hình API Key")
            self._display_api_keys()

            print(f"\nChọn hành động:")
            print(f"  [1] Thêm API key mới")
            if self.api_keys:
                print(f"  [2] Chọn một API key hiện có để sử dụng chính")
                print(f"  [3] Xóa API key")
            print(f"  [0] Quay lại menu chính")
            print(f"{'-' * 30}")

            choice = input(f"Nhập lựa chọn của bạn: ").strip().lower()

            if choice == '0':
                break
            elif choice == '1':
                new_keys_str = input(f"Nhập API key mới (có thể nhập nhiều, cách nhau bằng dấu phẩy ','):\n> ").strip()
                if new_keys_str:
                    new_keys = [k.strip() for k in new_keys_str.split(',') if k.strip()]
                    added_count = 0
                    for nk in new_keys:
                        if nk not in self.api_keys:
                            self.api_keys.append(nk)
                            added_count += 1
                    if added_count > 0:
                        print(f"✅ Đã thêm {added_count} API key mới.")
                        self._configure_genai_with_primary_key()
                        self.save_config()
                    else:
                        print(f"ℹ️ Không có key mới nào được thêm (có thể đã tồn tại).")
                else:
                    print(f"⚠️ Không có key nào được nhập.")
                input(f"\nNhấn Enter để tiếp tục...")
                
            elif choice == '2' and self.api_keys:
                if len(self.api_keys) == 1:
                    print(f"ℹ️ Chỉ có một API key, không cần chọn lại.")
                    input(f"\nNhấn Enter để tiếp tục...")
                    continue
                
                try:
                    self._print_header("Chọn API Key Chính")
                    self._display_api_keys()
                    key_index_str = input(f"\nNhập số thứ tự của API key muốn sử dụng làm chính (1-{len(self.api_keys)}): ").strip()
                    selected_idx = int(key_index_str) - 1
                    if 0 <= selected_idx < len(self.api_keys):
                        selected_key = self.api_keys.pop(selected_idx)
                        self.api_keys.insert(0, selected_key)
                        print(f"✅ Đã đặt key '{f'...{selected_key[-4:]}' if len(selected_key) > 4 else selected_key}' làm key chính.")
                        self._configure_genai_with_primary_key()
                        self.save_config()
                    else:
                        print(f"⚠️ Lựa chọn không hợp lệ. Vui lòng nhập số trong danh sách.")
                except ValueError:
                    print(f"❌ Đầu vào không hợp lệ. Vui lòng nhập một số.")
                input(f"\nNhấn Enter để tiếp tục...")

            elif choice == '3' and self.api_keys:
                if not self.api_keys:
                    print(f"ℹ️ Không có API key nào để xóa.")
                    input(f"\nNhấn Enter để tiếp tục...")
                    continue

                while True: # Loop for deletion confirmation
                    self._print_header("Xóa API Key")
                    self._display_api_keys()
                    print(f"\n💡 Nhập số thứ tự của API key muốn xóa (có thể nhập nhiều, cách nhau bằng dấu phẩy ',').")
                    print(f"   CẢNH BÁO: Không thể hoàn tác.")
                    delete_choice = input(f"Nhập lựa chọn của bạn (hoặc 'q' để quay lại): ").strip().lower()

                    if delete_choice == 'q':
                        break

                    try:
                        indices_to_delete = []
                        valid_input = True
                        for x in delete_choice.split(','):
                            x_strip = x.strip()
                            if x_strip:
                                num = int(x_strip) - 1
                                if 0 <= num < len(self.api_keys):
                                    indices_to_delete.append(num)
                                else:
                                    print(f"⚠️ Bỏ qua số thứ tự không hợp lệ: {num + 1}.")
                                    valid_input = False
                        
                        if not indices_to_delete:
                            if valid_input: # If input was valid but no keys selected
                                print(f"ℹ️ Không có key nào được chọn để xóa.")
                            input(f"\nNhấn Enter để tiếp tục...")
                            continue # Re-prompt for deletion if nothing was selected

                        # Remove duplicates and sort in reverse to delete correctly
                        indices_to_delete = sorted(list(set(indices_to_delete)), reverse=True)

                        print(f"\n⚠️ Bạn sắp xóa các API key sau:")
                        for idx in indices_to_delete:
                            key_display = f"...{self.api_keys[idx][-4:]}" if len(self.api_keys[idx]) > 4 else self.api_keys[idx]
                            print(f"  - [{idx+1}] {key_display}")
                        
                        confirm_delete = input(f"\n🛑 XÁC NHẬN XÓA (y/n)? ").strip().lower()
                        if confirm_delete == 'y':
                            deleted_count = 0
                            for idx in indices_to_delete:
                                deleted_key = self.api_keys.pop(idx)
                                print(f"✅ Đã xóa key: ...{deleted_key[-4:]}")
                                deleted_count += 1
                            
                            if deleted_count > 0:
                                self._configure_genai_with_primary_key() # Re-configure in case the primary key was deleted
                                self.save_config()
                                print(f"🎉 Hoàn tất xóa key.")
                            else:
                                print(f"ℹ️ Không có key nào được xóa.")
                            input(f"\nNhấn Enter để tiếp tục...")
                            break # Exit deletion loop after successful deletion
                        else:
                            print(f"❌ Đã hủy thao tác xóa.")
                            input(f"\nNhấn Enter để tiếp tục...")
                            break # Exit deletion loop if canceled

                    except ValueError:
                        print(f"❌ Đầu vào không hợp lệ. Vui lòng nhập các số cách nhau bằng dấu phẩy.")
                        input(f"\nNhấn Enter để tiếp tục...")
            else:
                print(f"❌ Lựa chọn không hợp lệ. Vui lòng thử lại.")
                input(f"\nNhấn Enter để tiếp tục...")

        if not self.model:
            print(f"\n❌ Cấu hình API key không thành công hoặc không có key.")
            if input(f"Thử lại cấu hình API key? (y/n): ").lower() == 'y':
                return self.configure_api_interactively()
            else:
                print(f"⛔ Chương trình không thể hoạt động mà không có API key hợp lệ.")
                sys.exit(1)

    def configure_language(self):
        """Cấu hình ngôn ngữ đích"""
        self._print_header("Cấu hình ngôn ngữ đích")
        languages = {
            "vi": "Tiếng Việt", "en": "Tiếng Anh", "zh": "Tiếng Trung",
            "ja": "Tiếng Nhật", "ko": "Tiếng Hàn", "fr": "Tiếng Pháp",
            "de": "Tiếng Đức", "es": "Tiếng Tây Ban Nha", "ru": "Tiếng Nga"
        }

        print("Các ngôn ngữ có sẵn:")
        for code, name in languages.items():
            print(f"  {code}: {name}")

        choice = input(f"Chọn ngôn ngữ đích (mặc định: {self.target_lang}): ").strip()
        if choice in languages:
            self.target_lang = choice
            print(f"✅ Đã chọn ngôn ngữ đích: {languages[self.target_lang]}")
        else:
            print(f"⚠️ Không nhận dạng được ngôn ngữ, sử dụng mặc định: {languages[self.target_lang]}")

        self.save_config()
        input("\nNhấn Enter để tiếp tục...")

    def configure_threading(self):
        """Cấu hình số luồng tối đa"""
        self._print_header("Cấu hình đa luồng")
        print(f"Số luồng hiện tại: {self.max_workers}")

        try:
            new_workers = input(f"Nhập số luồng mới (1-16, mặc định: {self.max_workers}): ").strip()
            if new_workers:
                new_workers = int(new_workers)
                if 1 <= new_workers <= 16:
                    self.max_workers = new_workers
                    print(f"✅ Đã cập nhật số luồng thành: {self.max_workers}")
                else:
                    print("⚠️ Số luồng phải từ 1-16, giữ nguyên giá trị hiện tại.")
            else:
                print(f"✅ Giữ nguyên số luồng: {self.max_workers}")
        except ValueError:
            print("⚠️ Giá trị không hợp lệ, giữ nguyên số luồng hiện tại.")

        self.save_config()
        input("\nNhấn Enter để tiếp tục...")

    def configure_rate_limit(self):
        """Cấu hình cho rate limiting"""
        self._print_header("Cấu hình Rate Limit & Retry")
        print(f"Cấu hình hiện tại:")
        print(f"- Khoảng cách tối thiểu giữa các request API (giây): {self.min_request_interval}")
        print(f"- Số lần thử lại tối đa cho mỗi chunk: {self.max_retries}")
        print(f"- Hệ số tăng thời gian chờ (backoff factor): {self.backoff_factor}")

        update = input("\nBạn muốn cập nhật cấu hình này? (y/n): ").lower()
        if update == 'y':
            try:
                interval_str = input(f"Khoảng cách tối thiểu mới (giây, hiện tại: {self.min_request_interval}, Enter để giữ): ").strip()
                if interval_str: self.min_request_interval = max(0.1, float(interval_str))

                retries_str = input(f"Số lần thử lại tối đa mới (hiện tại: {self.max_retries}, Enter để giữ): ").strip()
                if retries_str: self.max_retries = max(1, int(retries_str))

                factor_str = input(f"Hệ số tăng thời gian chờ mới (hiện tại: {self.backoff_factor}, Enter để giữ): ").strip()
                if factor_str: self.backoff_factor = max(1.1, float(factor_str)) 

                print("\n✅ Đã cập nhật cấu hình rate limit & retry.")
                self.save_config()
            except ValueError:
                print("\n⚠️ Giá trị không hợp lệ, giữ nguyên cấu hình cũ.")
        else:
            print("\nℹ️ Không thay đổi cấu hình.")
        input("\nNhấn Enter để tiếp tục...")
    
    def configure_output_filename_option(self):
        self._print_header("Tùy chọn tên file đầu ra")
        current_status = "Giữ nguyên tên file gốc" if self.keep_original_filename else f"Thêm mã ngôn ngữ (_{self.target_lang}) vào tên file"
        print(f"Trạng thái hiện tại: {current_status}")
        
        choice = input(f"Bạn có muốn giữ nguyên tên file gốc khi dịch không? (y/n, mặc định là '{'y' if self.keep_original_filename else 'n'}'): ").lower()
        if choice == 'y':
            self.keep_original_filename = True
            print("✅ Tên file đầu ra sẽ được giữ nguyên (ví dụ: 'filename.ext').")
        elif choice == 'n':
            self.keep_original_filename = False
            print(f"✅ Mã ngôn ngữ '_{self.target_lang}' sẽ được thêm vào tên file đầu ra (ví dụ: 'filename_{self.target_lang}.ext').")
        else:
            print(f"⚠️ Lựa chọn không hợp lệ. Giữ nguyên cài đặt hiện tại: {current_status}")
            
        self.save_config()
        input("\nNhấn Enter để tiếp tục...")

    def load_file(self, filepath: str) -> Optional[Dict]:
        """Đọc file YAML hoặc JSON"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                if filepath.endswith((".yml", ".yaml")):
                    return yaml.safe_load(f)
                elif filepath.endswith(".json"):
                    return json.load(f)
                else:
                    self.translation_errors.append(f"❌ Định dạng file không được hỗ trợ: {filepath}")
                    return None
        except Exception as e:
            self.translation_errors.append(f"❌ Lỗi khi đọc file {filepath}: {str(e)}")
            return None

    def save_file(self, data: Dict, filepath: str):
        """Lưu dữ liệu vào file YAML hoặc JSON (dựa trên đuôi file)"""
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                if filepath.endswith((".yml", ".yaml")):
                    yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
                elif filepath.endswith(".json"):
                    json.dump(data, f, indent=4, ensure_ascii=False)
                else:
                    self.translation_errors.append(f"❌ Không thể lưu, định dạng file không được hỗ trợ: {filepath}")
                    return False
            return True
        except Exception as e:
            self.translation_errors.append(f"❌ Lỗi khi lưu file {filepath}: {str(e)}")
            return False

    def extract_text(self, data: Any, prefix="") -> Dict[str, str]:
        """Trích xuất văn bản cần dịch từ cấu trúc dữ liệu"""
        texts = {}
        if isinstance(data, dict):
            for key, value in data.items():
                full_key = f"{prefix}.{key}" if prefix else key
                texts.update(self.extract_text(value, full_key))
        elif isinstance(data, list):
            for idx, item in enumerate(data):
                full_key = f"{prefix}[{idx}]"
                texts.update(self.extract_text(item, full_key))
        elif isinstance(data, str):
            if re.fullmatch(r"[A-Za-z0-9_\-\.\/]+", data) and not re.search(r"\s", data): # if it has no spaces and is typical ID like
                 if not any(c.isalpha() for c in data if c.lower() > 'f'): # Heuristic: if it has letters beyond 'f', it might be text
                    if len(re.findall(r'[A-Za-z]', data)) < 3 and len(data) < 30 : # if very few letters and short, likely an ID
                        return {}
            if len(data.strip()) > 0: # Ensure non-empty after strip
                texts[prefix] = data
        return texts

    def apply_translations(self, data: Any, translations: Dict[str, str], prefix="") -> Any:
        """Áp dụng bản dịch vào cấu trúc dữ liệu gốc"""
        if isinstance(data, dict):
            return {k: self.apply_translations(v, translations, f"{prefix}.{k}" if prefix else k) for k, v in data.items()}
        elif isinstance(data, list):
            return [self.apply_translations(v, translations, f"{prefix}[{i}]") for i, v in enumerate(data)]
        elif isinstance(data, str):
            return translations.get(prefix, data)
        return data

    def chunk_texts(self, texts: Dict[str, str], max_chars=1000) -> List[Dict[str, str]]:
        """Chia nhỏ văn bản thành các phần để xử lý"""
        chunks = []
        current_chunk = {}
        current_chars = 0
        sorted_items = sorted(texts.items())

        for key, text in sorted_items:
            text_len = len(text)
            if text_len > max_chars:
                if current_chunk: # Add the pending chunk first
                    chunks.append(current_chunk)
                    current_chunk = {}
                    current_chars = 0
                chunks.append({key: text}) # This large item is its own chunk
                continue

            if current_chars + text_len > max_chars and current_chunk:
                chunks.append(current_chunk)
                current_chunk = {}
                current_chars = 0
            
            current_chunk[key] = text
            current_chars += text_len

        if current_chunk:
            chunks.append(current_chunk)
        return chunks

    def extract_json_from_response(self, text):
        """Trích xuất JSON từ phản hồi của Gemini"""
        try:
            # Prioritize finding JSON within markdown-like code blocks
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
            if match:
                json_text = match.group(1)
            else:
                first_brace = text.find('{')
                last_brace = text.rfind('}')
                if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                    json_text = text[first_brace : last_brace+1]
                else:
                    json_text = text
            json_text = json_text.strip()
            if json_text.lower().startswith("json"):
                json_text = json_text[4:].lstrip()

            return json.loads(json_text)

        except json.JSONDecodeError as e:
            self.translation_warnings.append(f"⚠️ Lỗi giải mã JSON: {str(e)}. Phản hồi gốc (hoặc phần được cho là JSON): {text[:500]}...")
            return None

        except Exception as e: # Catch other potential errors like regex not matching
            self.translation_warnings.append(f"⚠️ Không thể trích xuất JSON từ phản hồi Gemini (lỗi chung): {str(e)}. Phản hồi gốc: {text[:200]}...")
            return None

    def translate_with_gemini(self, text_chunk: Dict[str, str]) -> Dict[str, str]:
        """
        Dịch văn bản sử dụng Gemini API. 
        Cố gắng đảm bảo cấu trúc key của chunk được duy trì.
        """
        lang_names = {
            "vi": "tiếng Việt", "en": "tiếng Anh", "zh": "tiếng Trung",
            "ja": "tiếng Nhật", "ko": "tiếng Hàn", "fr": "tiếng Pháp",
            "de": "tiếng Đức", "es": "tiếng Tây Ban Nha", "ru": "tiếng Nga"
        }
        target_name = lang_names.get(self.target_lang, self.target_lang)

        prompt = (
            f"You are an expert translation service. Translate the JSON values in the following JSON object into {target_name}. "
            "IMPORTANT RULES:\n"
            "1. ONLY translate the string values. DO NOT translate the keys.\n"
            "2. If a string value appears to be an identifier, a path, a placeholder (like '%s', '{{variable}}'), a version number (e.g., '1.0.0'), "
            "   a URL, an email address, or a sequence of random-looking characters, KEEP IT UNCHANGED.\n"
            "3. Maintain the original JSON structure EXACTLY.\n"
            "4. Ensure the output is a valid JSON object, starting with `{` and ending with `}`.\n"
            "5. Do not add any explanatory text, comments, or markdown formatting (like ```json) around the JSON output. "
            "   The response MUST be only the translated JSON object itself.\n\n"
            "Input JSON to translate:\n"
            f"{json.dumps(text_chunk, ensure_ascii=False, indent=2)}"
        )

        for attempt in range(self.max_retries): # Use configured retries
            try:
                response = self.model.models.generate_content(
                    model="gemini-2.0-flash", contents=prompt
                )
                translated_json = self.extract_json_from_response(response.text)
                
                # Check for structural integrity and key presence
                if translated_json and isinstance(translated_json, dict):
                    # Check if all original keys are present
                    missing_keys = [k for k in text_chunk if k not in translated_json]
                    if not missing_keys:
                        # Ensure no extra keys are added (robustness)
                        extra_keys = [k for k in translated_json if k not in text_chunk]
                        if extra_keys:
                            # Remove extra keys if they appear (model hallucination)
                            for ek in extra_keys:
                                del translated_json[ek]
                            self.translation_warnings.append(
                                f"⚠️ Loại bỏ các key không mong muốn trong bản dịch chunk (lần {attempt + 1}): {extra_keys}. "
                                f"Input chunk: {json.dumps(text_chunk)}"
                            )
                        return translated_json
                    else:
                        self.translation_warnings.append(
                            f"⚠️ Lần thử {attempt + 1}: Trích xuất JSON thành công nhưng thiếu key gốc: {missing_keys}. "
                            f"Output JSON: {json.dumps(translated_json)}. Thử lại..."
                        )
                        if attempt < self.max_retries - 1:
                            time.sleep(2) # Wait before retry
                        else:
                            self.translation_errors.append(
                                f"❌ Trích xuất JSON thất bại sau nhiều lần thử, trả về chunk gốc do thiếu key."
                                f"Input chunk: {json.dumps(text_chunk)}"
                            )
                            return text_chunk # Return original if all retries fail
                else:
                    self.translation_warnings.append(f"⚠️ Lần thử {attempt + 1}: Trích xuất JSON thất bại hoặc không phải dạng dict. Thử lại...")
                    if attempt < self.max_retries - 1:
                         time.sleep(2) # Wait before retry
                    else:
                        self.translation_errors.append(f"❌ Trích xuất JSON thất bại sau nhiều lần thử, trả về chunk gốc.")
                        return text_chunk # Return original if all retries fail

            except Exception as e:
                self.translation_warnings.append(f"⚠️ Lỗi khi dịch với Gemini (lần {attempt + 1}): {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 * (attempt + 1))  # Simple backoff within this function
                else:
                    self.translation_errors.append(f"❌ Lỗi khi dịch với Gemini sau {self.max_retries} lần thử: {str(e)}. Trả về chunk gốc.")
                    return text_chunk # Return original if all retries fail

    def save_chunks_to_folder(self, chunks: List[Dict[str, str]], folder: str):
        """Lưu các phần nhỏ vào thư mục tạm (sử dụng JSON)"""
        os.makedirs(folder, exist_ok=True)
        self.temp_folders.append(folder) # Register for cleanup

        for i, chunk in enumerate(chunks):
            path = os.path.join(folder, f"chunk_{i:03d}.json") # Save as JSON
            with open(path, "w", encoding="utf-8") as f:
                json.dump(chunk, f, ensure_ascii=False, indent=2) 

    def translate_chunk(self, chunk_path: str, basename: str, lock=None):
        """
        Dịch một phần nhỏ với exponential backoff (đọc JSON).
        Lỗi API sẽ được in ra ngay lập tức, các lỗi khác được thu thập.
        """
        original_chunk_data = {}
        try:
            with open(chunk_path, 'r', encoding="utf-8") as f:
                original_chunk_data = json.load(f)

            if not original_chunk_data:
                if lock:
                    with lock:
                        self.progress.update(1)
                return {}

            backoff = ExponentialBackoff(
                initial_delay=1.0,
                max_delay=45.0,
                factor=self.backoff_factor,
                jitter=True
            )

            for attempt in range(1, self.max_retries + 1):
                try:
                    translated_data = self.translate_with_gemini(original_chunk_data)

                    if translated_data and isinstance(translated_data, dict) and all(key in translated_data for key in original_chunk_data.keys()):
                        if translated_data != original_chunk_data or (translated_data == original_chunk_data and attempt >= self.max_retries):
                            if lock:
                                with lock:
                                    self.progress.update(1)
                            return translated_data
                        else:
                            self.translation_warnings.append(
                                f"🔎 Chunk {os.path.basename(chunk_path)} ({basename}): "
                                f"Dịch không thay đổi, có thể do toàn ID hoặc lỗi tạm thời. Thử lại (lần {attempt}/{self.max_retries})."
                            )
                    else:
                        raise ValueError("Dịch thất bại hoặc trả về cấu trúc không hợp lệ.")

                except Exception as e:
                    error_message = str(e).lower()
                    is_api_error = "400" in error_message or \
                                   "401" in error_message or \
                                   "403" in error_message or \
                                   "404" in error_message or \
                                   "500" in error_message or \
                                   "api key not valid. please pass a valid api key." in error_message or \
                                   "authentication" in error_message or \
                                   "unauthorized" in error_message

                    is_rate_limit = "rate" in error_message or \
                                    "limit" in error_message or \
                                    "quota" in error_message or \
                                    "resource_exhausted" in error_message or \
                                    "429" in error_message or \
                                    "503" in error_message

                    if is_api_error and not is_rate_limit:
                        if lock:
                            with lock:
                                print(f"\n❌ LỖI API NGHIÊM TRỌNG (chunk {os.path.basename(chunk_path)}): {str(e)}")
                                print(f"   Vui lòng kiểm tra API key hoặc trạng thái dịch vụ.")
                                if hasattr(self, 'progress') and self.progress:
                                    self.progress.close()
                        sys.exit(1)

                    if attempt < self.max_retries:
                        delay_time = backoff.wait()
                        error_type_msg = "Rate limit/Server busy" if is_rate_limit else "Lỗi API/JSON"
                        self.translation_warnings.append(
                            f"⚠️ {error_type_msg} (chunk {os.path.basename(chunk_path)}), "
                            f"thử lại sau {delay_time:.2f}s (lần {attempt+1}/{self.max_retries}). Lỗi: {str(e)[:100]}"
                        )
                    else:
                        self.translation_errors.append(
                            f"❌ Chunk {os.path.basename(chunk_path)}: Thất bại sau {self.max_retries} lần. Lỗi: {str(e)}. Trả về chunk gốc."
                        )
                        if lock:
                            with lock:
                                self.progress.update(1)
                        return original_chunk_data

        except Exception as e:
            self.translation_errors.append(f"❌ Lỗi nghiêm trọng khi xử lý chunk {os.path.basename(chunk_path)}: {str(e)}")
            if lock:
                with lock:
                    if hasattr(self, 'progress') and self.progress:
                        self.progress.update(1)
            return original_chunk_data if original_chunk_data else {}

    def create_project_folder(self, base_name: str) -> str:
        """Tạo thư mục dự án mới dựa trên tên file và thời gian"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        project_name = f"{base_name}_{timestamp}"
        project_path = os.path.join(self.projects_folder, project_name)

        for subfolder in ["original", "chunks", "translated"]:
            os.makedirs(os.path.join(project_path, subfolder), exist_ok=True)

        return project_path

    def translate_file(self, input_path: str, output_path: Optional[str] = None, silent: bool = False, existing_project_path: Optional[str] = None, output_subdirectory_name: Optional[str] = None):
        if not silent:
            self._print_header(f"Dịch File: {os.path.basename(input_path)}")
        
        # Clear errors/warnings for this single file translation if not part of a batch
        if not silent:
            self.translation_errors = []
            self.translation_warnings = []

        if not os.path.exists(input_path):
            self.translation_errors.append(f"❌ Không tìm thấy file: {input_path}")
            if not silent: input("\nNhấn Enter để tiếp tục...")
            return False

        base_name, ext = os.path.splitext(os.path.basename(input_path))

        project_to_use_for_artifacts = existing_project_path
        if not project_to_use_for_artifacts:
            project_to_use_for_artifacts = self.create_project_folder(base_name)
        else: # Ensure subfolders exist if project path is provided
            for subfolder in ["original", "chunks", "translated"]:
                os.makedirs(os.path.join(project_to_use_for_artifacts, subfolder), exist_ok=True)
        
        translated_filename_only = f"{base_name}{ext}" if self.keep_original_filename else f"{base_name}_{self.target_lang}{ext}"

        # final_translated_file_destination is where the primary translated file (in its project) is saved.
        # If output_path is given, it's that. Otherwise, it's in the project's "translated" folder.
        final_translated_file_destination = output_path
        if not final_translated_file_destination: # Default if no specific output_path given
            final_translated_file_destination = os.path.join(project_to_use_for_artifacts, "translated", translated_filename_only)
        
        # Ensure the directory for final_translated_file_destination exists
        os.makedirs(os.path.dirname(final_translated_file_destination), exist_ok=True)


        if not silent:
            print(f"\n📂 Đang dịch file: {input_path}")
            print(f"🗂️ Thư mục dự án (chứa file gốc, chunks): {project_to_use_for_artifacts}")
            print(f"💾 File dịch chính sẽ được lưu tại: {final_translated_file_destination}")

        original_copy_path = os.path.join(project_to_use_for_artifacts, "original", os.path.basename(input_path))
        shutil.copy2(input_path, original_copy_path)
        chunks_folder = os.path.join(project_to_use_for_artifacts, "chunks")

        original_data = self.load_file(input_path)
        if not original_data:
            if not silent:
                self.display_and_clear_messages()
                input("\nNhấn Enter để tiếp tục...")
            return False

        texts_to_translate = self.extract_text(original_data)
        if not texts_to_translate:
            if not silent: self.translation_warnings.append("⚠️ Không tìm thấy nội dung để dịch trong file.")
            # Still save the original data to the target location as if it was "translated" (i.e., copied)
            if self.save_file(original_data, final_translated_file_destination):
                if not silent: self.translation_warnings.append(f"✅ File gốc không có nội dung dịch, đã sao chép tới: {final_translated_file_destination}")
                
                # Also save to common output folder (potentially in a subdirectory)
                common_output_dir_final = self.output_folder
                if output_subdirectory_name:
                    common_output_dir_final = os.path.join(self.output_folder, output_subdirectory_name)
                os.makedirs(common_output_dir_final, exist_ok=True)
                common_output_path_final = os.path.join(common_output_dir_final, translated_filename_only)
                self.save_file(original_data, common_output_path_final)
                if not silent: self.translation_warnings.append(f"✅ Đã lưu bản sao tại: {common_output_path_final}")

            else:
                if not silent: self.translation_errors.append(f"❌ Lỗi khi sao chép file gốc (không có nội dung dịch).")
            if not silent: 
                self.display_and_clear_messages()
                input("\nNhấn Enter để tiếp tục...")
            return True # Considered success as file was processed and copied

        if not silent: print(f"✂️ Trích xuất {len(texts_to_translate)} đoạn văn bản, đang chia nhỏ...")
        chunks = self.chunk_texts(texts_to_translate, max_chars=1800) # Increased max_chars slightly
        self.save_chunks_to_folder(chunks, chunks_folder)

        if not silent: print(f"🌐 Đang dịch ({len(chunks)} phần) với {self.max_workers} luồng...")
        translated_texts_combined = {} # Renamed for clarity
        chunk_files = sorted([os.path.join(chunks_folder, f) for f in os.listdir(chunks_folder) if f.endswith('.json')])

        # Initialize progress bar
        # Ensure self.progress is an instance variable for access in finally
        self.progress = tqdm(total=len(chunk_files), 
                             desc=f"Dịch {os.path.basename(input_path)}" if not silent else None, 
                             disable=silent, 
                             leave=False) # Leave=False if it's per file and there's an outer loop
        
        progress_lock = threading.Lock()
        last_request_time = [time.time() - self.min_request_interval] # Store as a list to modify in nested func
        rate_limit_lock = threading.Lock() # Ensures atomic check-and-update of last_request_time

        def rate_limited_translate_task(chunk_file_path):
            with rate_limit_lock:
                current_time = time.time()
                time_since_last = current_time - last_request_time[0]
                actual_min_interval = self.min_request_interval + random.uniform(0, self.min_request_interval * 0.1)

                if time_since_last < actual_min_interval:
                    sleep_time = actual_min_interval - time_since_last
                    time.sleep(sleep_time)
                last_request_time[0] = time.time() # Update the time of the last request start
            
            # The actual translation of the chunk
            return self.translate_chunk(chunk_file_path, basename=f"{base_name}{ext}", lock=progress_lock)


        try:
            actual_workers_for_pool = max(1, self.max_workers) 

            with concurrent.futures.ThreadPoolExecutor(max_workers=actual_workers_for_pool) as executor:
                # Submit all tasks and collect futures
                futures = [executor.submit(rate_limited_translate_task, chunk_path) for chunk_path in chunk_files]
                
                for future in concurrent.futures.as_completed(futures):
                    try:
                        result = future.result()
                        if result and isinstance(result, dict):
                            translated_texts_combined.update(result)
                        # Progress bar is updated within translate_chunk via lock
                    except Exception as exc_inner: # Catch exceptions from the task itself
                        self.translation_errors.append(f"❌ Lỗi khi xử lý một future cho file {os.path.basename(input_path)}: {exc_inner}")

            if not silent : self.progress.close() # Close progress bar on success

            translated_data_structure = self.apply_translations(original_data, translated_texts_combined)
            
            if self.save_file(translated_data_structure, final_translated_file_destination):
                if not silent: print(f"\n✅ Đã lưu file dịch chính tại: {final_translated_file_destination}")
                
                # Determine common output path (potentially in a subdirectory)
                common_output_dir_final = self.output_folder
                if output_subdirectory_name:
                    common_output_dir_final = os.path.join(self.output_folder, output_subdirectory_name)
                
                os.makedirs(common_output_dir_final, exist_ok=True) # Ensure dir exists
                common_output_path_final = os.path.join(common_output_dir_final, translated_filename_only)
                
                if self.save_file(translated_data_structure, common_output_path_final):
                    if not silent: print(f"✅ Đã lưu bản sao tại: {common_output_path_final}")
                else:
                    if not silent: self.translation_errors.append(f"❌ Lỗi khi lưu bản sao tại: {common_output_path_final}")

                if not silent: 
                    self.display_and_clear_messages()
                    input("\nNhấn Enter để tiếp tục...")
                return True
            else: # Failed to save the main translated file
                if not silent:
                    self.translation_errors.append(f"❌ Lỗi khi lưu file dịch chính tại: {final_translated_file_destination}")
                    self.display_and_clear_messages()
                    input("\nNhấn Enter để tiếp tục...")
                return False

        except Exception as e:
            if not silent and hasattr(self, 'progress') and self.progress and not self.progress.disable:
                self.progress.close() # Ensure progress bar is closed on error
            
            self.translation_errors.append(f"\n❌ Lỗi trong quá trình dịch file {os.path.basename(input_path)}: {str(e)}")
            # traceback.print_exc() # For debug, keep disabled in normal operation
            
            if not silent:
                self.display_and_clear_messages()
                input("\nNhấn Enter để tiếp tục...")
            return False
        finally:
            pass

    def list_translatable_files(self, directory: str) -> List[str]:
        """Liệt kê các file YAML và JSON trong thư mục"""
        if not os.path.exists(directory):
            # self.translation_errors.append(f"❌ Thư mục {directory} không tồn tại") # Not an error, just no files
            return []
        try:
            files = [f for f in os.listdir(directory)
                       if os.path.isfile(os.path.join(directory, f)) and f.endswith((".yml", ".yaml", ".json"))]
            return sorted(files)
        except OSError as e:
            self.translation_errors.append(f"❌ Không thể truy cập thư mục {directory}: {e}")
            return []

    def refresh_file_list(self, directory: str):
        """Làm mới danh sách file YAML/JSON trong thư mục"""
        self._print_header("Làm mới danh sách file")
        files = self.list_translatable_files(directory)
        if files:
            print(f"✅ Đã tìm thấy {len(files)} file YAML/JSON trong thư mục {directory}")
        else:
            print(f"⚠️ Không tìm thấy file YAML hoặc JSON nào trong thư mục {directory}")

        input("\nNhấn Enter để tiếp tục...")
        return files

    def select_file_from_directory(self, directory: str) -> Optional[str]:
        """
        Cho phép người dùng chọn một hoặc nhiều file từ thư mục bằng số thứ tự, khoảng chọn, hoặc '^' notation.
        Returns a list of full file paths.
        """
        self._print_header("Chọn file") # Header might be redundant if called from other menus
        files = self.list_translatable_files(directory)

        if not files:
            print(f"❌ Không tìm thấy file YAML hoặc JSON nào trong thư mục '{directory}'")
            print("💡 Hãy đặt các file YAML/JSON vào thư mục và thử lại hoặc làm mới danh sách.")
            input("\nNhấn Enter để tiếp tục...") # Allow caller to decide
            return []

        print(f"\n📋 Các file YAML/JSON có sẵn trong '{directory}':")
        for i, file_name_display in enumerate(files): # Renamed variable
            print(f"  [{i+1}] {file_name_display}")

        while True:
            prompt_message = (
                f"\n🔢 Nhập STT file, khoảng chọn (vd: 1-3, ^4), 'all' "
                f"(hoặc 'q' để quay lại, 'r' để làm mới): "
            )
            choice = input(prompt_message).strip().lower()

            if choice == 'q':
                return [] # Return empty list for 'q'
            elif choice == 'r':
                # clear_screen() # Optional: depends on desired UX
                print(f"🔄 Đang làm mới danh sách file từ '{directory}'...")
                files = self.list_translatable_files(directory)
                if not files:
                    print(f"❌ Không tìm thấy file YAML hoặc JSON nào trong '{directory}' sau khi làm mới.")
                    return [] # Return empty list if refresh yields no files
                print(f"\n📋 Các file YAML/JSON có sẵn trong '{directory}':")
                for i, file_name_display_refreshed in enumerate(files): # Renamed variable
                    print(f"  [{i+1}] {file_name_display_refreshed}")
                continue # Re-prompt for selection

            raw_tokens = [t.strip() for t in choice.split(',') if t.strip()]

            if not raw_tokens: # Input was empty or just commas
                if choice: # Contained only commas/spaces, not 'q' or 'r'
                    print("⚠️ Lựa chọn không hợp lệ. Vui lòng nhập số, khoảng chọn, 'all', 'q', hoặc 'r'.")
                else: # Truly empty input by just pressing Enter
                    print("⚠️ Lựa chọn không được để trống.")
                continue

            selected_indices, all_valid = self._parse_file_selection_tokens(raw_tokens, len(files), os.path.basename(directory))

            # if not all_valid:
            #     print("❌ Một hoặc nhiều phần trong lựa chọn của bạn không hợp lệ. Hãy thử lại.")
            #     continue

            if not selected_indices and choice:
                if all_valid:
                     print(f"ℹ️ Các chỉ số bạn nhập không tương ứng với file nào hiện có (1-{len(files)}).")
                continue


            if selected_indices:
                return [os.path.join(directory, files[i]) for i in selected_indices]

    def select_multiple_files_from_directory(self, directory: str, header_override: Optional[str] = None) -> List[str]:
        """Cho phép người dùng chọn nhiều file từ thư mục để dịch hàng loạt"""
        effective_header = header_override if header_override else f"Chọn nhiều file từ '{os.path.basename(directory)}'"
        # self._print_header(effective_header) # Header management can be tricky if called nestedly
        
        files = self.list_translatable_files(directory)

        if not files:
            print(f"❌ Không tìm thấy file YAML hoặc JSON nào trong thư mục '{directory}'")
            print("💡 Hãy đặt các file YAML/JSON vào thư mục và thử lại hoặc làm mới danh sách.")
            input("\nNhấn Enter để tiếp tục...") # Allow caller to decide
            return [] # Return empty list

        print(f"\n📋 Các file YAML/JSON có sẵn trong '{directory}':")
        for i, file_name_display in enumerate(files): # Renamed variable
            print(f"  [{i+1}] {file_name_display}")

        print("\n💡 Chọn file/nhiều file bằng cách nhập STT (ví dụ: 1), danh sách STT (1,3,5),")
        print("   khoảng chọn (6-10), chọn từ vị trí đến hết (^4), hoặc 'all' để chọn tất cả.")

        while True:
            prompt_message = (
                f"\n🔢 Nhập lựa chọn (hoặc 'q' để quay lại, 'r' để làm mới): "
            )
            choice = input(prompt_message).strip().lower()

            if choice == 'q':
                return []
            elif choice == 'r':
                # clear_screen() # Optional
                # self._print_header(effective_header) # Re-print header if screen cleared
                print(f"🔄 Đang làm mới danh sách file từ '{directory}'...")
                files = self.list_translatable_files(directory)
                if not files:
                    print(f"❌ Không tìm thấy file YAML hoặc JSON nào trong '{directory}' sau khi làm mới.")
                    return []
                print(f"\n📋 Các file YAML/JSON có sẵn trong '{directory}':")
                for i, file_name_display_refreshed in enumerate(files): # Renamed variable
                    print(f"  [{i+1}] {file_name_display_refreshed}")
                continue
            
            raw_tokens = [t.strip() for t in choice.split(',') if t.strip()]
            
            if not raw_tokens: # Input was empty or just commas
                if choice: # Contained only commas/spaces, not 'q' or 'r'
                     print("⚠️ Lựa chọn không hợp lệ. Vui lòng nhập STT, khoảng chọn, 'all', 'q', hoặc 'r'.")
                else: # Truly empty input
                     print("⚠️ Lựa chọn không được để trống.")
                continue

            selected_indices, all_valid = self._parse_file_selection_tokens(raw_tokens, len(files), os.path.basename(directory))

            # if not all_valid:
            #     print("❌ Một hoặc nhiều phần trong lựa chọn của bạn không hợp lệ. Xin hãy thử lại.")
            #     continue # Re-prompt

            if not selected_indices and choice:
                if all_valid: # Valid tokens but selected nothing
                    print(f"ℹ️ Các chỉ số bạn nhập không tương ứng với file nào hiện có (1-{len(files)}).")
                # If not all_valid, message already printed by parser or above.
                continue
            
            if selected_indices:
                return [os.path.join(directory, files[i]) for i in selected_indices]

            # Fallback, though ideally not reached.
            # print("❌ Lựa chọn không hợp lệ hoặc không có file nào được chọn. Vui lòng thử lại.")

    def batch_translate_files(self, file_paths: List[str], output_subdir_for_common_copy: Optional[str] = None):
        if not file_paths:
            print("ℹ️ Không có file nào được chọn để dịch.")
            input("\nNhấn Enter để tiếp tục...")
            return
        
        # Clear global errors/warnings at the start of a new batch operation
        self.translation_errors = []
        self.translation_warnings = []

        header_message = f"Dịch hàng loạt ({len(file_paths)} file)"
        if output_subdir_for_common_copy:
            header_message = f"Dịch thư mục '{output_subdir_for_common_copy}' ({len(file_paths)} file)"
        self._print_header(header_message)

        num_workers = min(len(file_paths), self.max_workers, 8) 
        print(f"📊 Sử dụng tối đa {num_workers} luồng để dịch {len(file_paths)} file.")
        
        start_time = time.time()
        results_summary = []
        with tqdm(total=len(file_paths), desc=f"Tiến độ dịch các file", unit="file", bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}]") as batch_progress:
            with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
                futures_to_path = {
                    executor.submit(self.translate_file_with_project_wrapper, file_path, output_subdir_for_common_copy): file_path 
                    for file_path in file_paths
                }
                for future in concurrent.futures.as_completed(futures_to_path):
                    original_file_path = futures_to_path[future]
                    try:
                        success_status, project_artifact_path = future.result()
                        results_summary.append((os.path.basename(original_file_path), success_status, project_artifact_path))
                    except Exception as exc:
                        self.translation_errors.append(f"❌ Lỗi nghiêm trọng khi xử lý file {os.path.basename(original_file_path)} trong batch: {exc}")
                        results_summary.append((os.path.basename(original_file_path), False, None))
                    finally:
                        batch_progress.update(1)

        end_time = time.time()
        duration = end_time - start_time
        
        successful_translations = sum(1 for _, success, _ in results_summary if success)
        failed_translations = len(results_summary) - successful_translations
        self._print_header(f"Kết quả dịch {len(file_paths)} file")
        print("\n--- Kết quả dịch hàng loạt ---")
        print(f"📊 Tổng số file đã xử lý: {len(file_paths)}")
        print(f"✅ Thành công: {successful_translations}")
        print(f"❌ Thất bại: {failed_translations}")
        print(f"⏱️ Tổng thời gian: {duration:.2f} giây")

        # List successful translations and their project artifact paths
        if len(results_summary) < 10: # Only show details if not too many files
            if any(s for _,s,_ in results_summary):
                print("\n📁 Chi tiết các bản dịch thành công:")
                for fname, success, proj_path in results_summary:
                    if success:
                        print(f"  ✓ {fname} (Thư mục dự án: {proj_path if proj_path else 'N/A'})")
        
        # Display collected errors and warnings
        self.display_and_clear_messages()
        
        print(f"\nℹ️ Bản sao của các file dịch thành công (nếu có) được lưu tại: {self.output_folder}" + (f"/{output_subdir_for_common_copy}" if output_subdir_for_common_copy else ""))
        # input("\nNhấn Enter để tiếp tục...") # Handled by caller

    def display_and_clear_messages(self):
        """Displays accumulated errors and warnings, then clears them."""
        if self.translation_warnings:
            print(f"\n--- Cảnh báo dịch ({len(self.translation_warnings)} cảnh báo) ---")
            for warning_msg in self.translation_warnings:
                print(Fore.YELLOW + warning_msg + Fore.RESET)
            self.translation_warnings = [] # Clear after display
        
        if self.translation_errors:
            print(f"\n--- LỖI DỊCH ({len(self.translation_errors)} lỗi) ---")
            for error_msg in self.translation_errors:
                print(Fore.RED + error_msg + Fore.RESET)
            self.translation_errors = [] # Clear after display

    def translate_file_with_project_wrapper(self, input_path: str, output_subdirectory_name: Optional[str] = None):
        """
        Wrapper for translate_file to be used in ThreadPoolExecutor.
        Creates a project folder for the file and calls translate_file.
        Ensures `translate_file` is called in silent mode for batch operations.
        Returns a tuple: (success_status: bool, project_artifact_path: Optional[str])
        """
        try:
            base_name, ext = os.path.splitext(os.path.basename(input_path))
            project_path_for_this_file_artifacts = self.create_project_folder(base_name)
            translated_filename_in_project = f"{base_name}{ext}" if self.keep_original_filename else f"{base_name}_{self.target_lang}{ext}"
            output_path_within_project_artifacts = os.path.join(project_path_for_this_file_artifacts, "translated", translated_filename_in_project)
            success_status = self.translate_file(
                input_path=input_path,
                output_path=output_path_within_project_artifacts,
                silent=True,
                existing_project_path=project_path_for_this_file_artifacts,
                output_subdirectory_name=output_subdirectory_name
            )
            return success_status, project_path_for_this_file_artifacts
        except Exception as e:
            self.translation_errors.append(f"❌ Lỗi không mong muốn khi thiết lập dịch file {os.path.basename(input_path)} trong batch: {str(e)}")
            return False, None

    def cleanup_temp_folders(self):
        """Dọn dẹp các thư mục tạm thời (chunks are now in project folders, this might be less used or repurposed)"""
        cleaned_count = 0
        for folder in self.temp_folders:
            if os.path.exists(folder):
                try:
                    shutil.rmtree(folder)
                    # print(f"🧹 Đã xóa thư mục tạm: {folder}") # Can be noisy
                    cleaned_count +=1
                except Exception as e:
                    print(f"⚠️ Không thể xóa thư mục tạm {folder}: {str(e)}")
        if cleaned_count > 0:
            print(f"🧹 Đã dọn dẹp {cleaned_count} thư mục tạm thời.")
        self.temp_folders = [] # Clear the list

    def view_projects(self):
        """Xem danh sách các dự án đã tạo"""
        self._print_header("Danh sách thư mục dự án")

        if not os.path.exists(self.projects_folder):
            print("📂 Chưa có thư mục dự án nào được tạo.")
            input("\nNhấn Enter để tiếp tục...")
            return

        try:
            projects = [d for d in os.listdir(self.projects_folder)
                        if os.path.isdir(os.path.join(self.projects_folder, d))]
        except OSError as e:
            print(f"❌ Không thể truy cập thư mục dự án tại '{self.projects_folder}': {e}")
            input("\nNhấn Enter để tiếp tục...")
            return

        if not projects:
            print("📂 Chưa có thư mục dự án nào được tạo.")
            input("\nNhấn Enter để tiếp tục...")
            return

        try:
            projects.sort(key=lambda x: os.path.getmtime(os.path.join(self.projects_folder, x)), reverse=True)
        except OSError:
            print("⚠️ Lỗi khi sắp xếp dự án theo thời gian, hiển thị theo thứ tự mặc định.")

        print(f"🔍 Tìm thấy {len(projects)} thư mục dự án trong '{self.projects_folder}':")
        for i, project_name in enumerate(projects):
            project_path = os.path.join(self.projects_folder, project_name)
            try:
                created_time = datetime.datetime.fromtimestamp(os.path.getmtime(project_path))
                
                original_dir = os.path.join(project_path, "original")
                translated_dir = os.path.join(project_path, "translated")
                
                original_files_count = len(os.listdir(original_dir)) if os.path.exists(original_dir) and os.path.isdir(original_dir) else 0
                translated_files_count = len(os.listdir(translated_dir)) if os.path.exists(translated_dir) and os.path.isdir(translated_dir) else 0

                print(f"\n[{i+1}] {project_name}")
                print(f"    📅 Lần sửa đổi cuối: {created_time.strftime('%d/%m/%Y %H:%M:%S')}")
                print(f"    📄 File gốc: {original_files_count}, File dịch: {translated_files_count}")
            except OSError:
                print(f"\n[{i+1}] {project_name} (không thể truy cập chi tiết)")
            print("-" * 50)

        input("\nNhấn Enter để tiếp tục...")

    def delete_projects(self):
        """Xóa một hoặc nhiều thư mục dự án"""
        self._print_header("Xóa thư mục dự án")

        if not os.path.exists(self.projects_folder):
            print("📂 Chưa có thư mục dự án nào được tạo để xóa.")
            input("\nNhấn Enter để tiếp tục...")
            return

        try:
            projects = [d for d in os.listdir(self.projects_folder)
                        if os.path.isdir(os.path.join(self.projects_folder, d))]
            if not projects:
                print(f"📂 Không tìm thấy thư mục dự án nào trong '{self.projects_folder}'.")
                input("\nNhấn Enter để tiếp tục...")
                return
            projects.sort(key=lambda x: os.path.getmtime(os.path.join(self.projects_folder, x)), reverse=True)
        except OSError as e:
            print(f"❌ Không thể truy cập thư mục dự án tại '{self.projects_folder}': {e}")
            input("\nNhấn Enter để tiếp tục...")
            return

        max_display_project_count = self.max_display_project_count
        num_total_projects = len(projects)
        print(f"\n📋 DANH SÁCH THƯ MỤC DỰ ÁN trong '{self.projects_folder}':")
        for i in range(min(num_total_projects, max_display_project_count)):
            project = projects[i]
            project_path_full = os.path.join(self.projects_folder, project) 
            try:
                created_time = datetime.datetime.fromtimestamp(os.path.getmtime(project_path_full))
                print(f"[{i+1}] {project} - (Sửa đổi lần cuối: {created_time.strftime('%d/%m/%Y %H:%M:%S')})")
            except OSError:
                 print(f"[{i+1}] {project} - (Không thể đọc thời gian)")
        
        if num_total_projects > max_display_project_count:
            remaining_count = num_total_projects - max_display_project_count
            print(f"...còn {remaining_count} dự án khác.")

        print("\n💡 Chọn nhiều thư mục dự án bằng cách nhập các số, cách nhau bởi dấu phẩy (,)")
        print("   Ví dụ: 1,3,5 sẽ chọn mục 1, 3 và 5.")
        print("   Nhập 'all' để chọn tất cả các thư mục dự án được liệt kê.")

        try:
            choice_str = input("\n🔢 Nhập lựa chọn của bạn (hoặc 'q' để quay lại): ").strip().lower()
            if choice_str == 'q': return

            projects_to_delete_names = []
            if choice_str == 'all':
                projects_to_delete_names = projects # List of names
            else:
                selected_indices = [int(idx.strip()) - 1 for idx in choice_str.split(',') if idx.strip()]
                for idx in selected_indices:
                    if 0 <= idx < len(projects):
                        projects_to_delete_names.append(projects[idx])
                    else:
                        print(f"⚠️ Bỏ qua số không hợp lệ trong lựa chọn: {idx+1}")

            if not projects_to_delete_names:
                print("❌ Không có thư mục dự án nào được chọn hợp lệ để xóa.")
                input("\nNhấn Enter để tiếp tục...")
                return

            print("\n⚠️ Các thư mục dự án sau và TOÀN BỘ NỘI DUNG BÊN TRONG sẽ bị xóa vĩnh viễn:")
            for project_name_del in projects_to_delete_names: print(f"  - {project_name_del} (trong {self.projects_folder})")

            confirm = input("\n🛑 CẢNH BÁO: Thao tác này KHÔNG THỂ HOÀN TÁC! Bạn có chắc chắn muốn xóa? (y/n): ").lower()
            if confirm != 'y':
                print("❌ Hủy thao tác xóa.")
                input("\nNhấn Enter để tiếp tục...")
                return

            deleted_count = 0
            error_count = 0
            print("\n🗑️  Đang tiến hành xóa...")
            for project_name_final_del in projects_to_delete_names:
                project_path_to_delete = os.path.join(self.projects_folder, project_name_final_del)
                try:
                    shutil.rmtree(project_path_to_delete)
                    print(f"  ✅ Đã xóa thư mục dự án: {project_name_final_del}")
                    deleted_count += 1
                except Exception as e:
                    print(f"  ❌ Lỗi khi xóa thư mục dự án {project_name_final_del}: {str(e)}")
                    error_count += 1

            print(f"\n🧹 Hoàn tất: Đã xóa {deleted_count} thư mục dự án, {error_count} lỗi.")
            input("\nNhấn Enter để tiếp tục...")

        except ValueError:
            print("❌ Vui lòng nhập danh sách số hợp lệ hoặc 'all'/'q'.")
            input("\nNhấn Enter để thử lại...")
        except Exception as e_outer:
            print(f"❌ Đã xảy ra lỗi không mong muốn trong quá trình xóa: {e_outer}")
            input("\nNhấn Enter để tiếp tục...")

    def main_menu(self):
        """Menu chính của chương trình"""
        while True:
            self._print_header("Menu Chính")
            print(" Lựa chọn chức năng dịch:")
            print(f"  [1] Dịch file từ thư mục đầu vào mặc định ('{os.path.basename(self.input_folder)}')")
            print("  [2] Dịch file hoặc thư mục từ đường dẫn tùy chọn")
            print("-" * 70)
            print(" Quản lý & Cấu hình:")
            print("  [3] Xem các thư mục dự án")
            print("  [4] Xóa thư mục dự án")
            print("  [5] Thay đổi thư mục đầu vào/đầu ra mặc định")
            print("  [6] Thay đổi ngôn ngữ đích")
            print("  [7] Cấu hình đa luồng (max_workers)")
            print("  [8] Cấu hình lại API key(s)")
            print("  [9] Cấu hình rate limit & retry")
            print("  [10] Tùy chọn tên file đầu ra (giữ tên gốc / thêm mã ngôn ngữ)")
            print("  [0] Thoát chương trình")
            print("=" * 70)
            print(f" 👤 Cấu hình hiện tại ({self.config_file}):")
            lang_display = self.target_lang
            active_key_info = f"API key chính: {Fore.GREEN}...{self.api_keys[0][-4:]}{Fore.RESET}" if self.api_keys and self.api_keys[0] else f"{Fore.RED}Chưa có key{Fore.RESET}"
            filename_option_display = "Giữ nguyên" if self.keep_original_filename else "Thêm mã ngôn ngữ"
            print(f"    🌐 Ngôn ngữ đích: {lang_display}  🧵 Số luồng: {self.max_workers}  📦 Model: gemini-2.0-flash")
            print(f"    🔑 {active_key_info} ({len(self.api_keys)} key(s)) 🏷️ Tên file: {filename_option_display}")
            print(f"    📂 Input: '{self.input_folder}' | Output: '{self.output_folder}'")
            print("=" * 70)

            choice = input("Nhập lựa chọn của bạn: ").strip()

            if choice == "1":
                self._print_header(f"Dịch nhiều file từ '{self.input_folder}'")
                # Files selected from default input_folder
                file_paths = self.select_multiple_files_from_directory(self.input_folder)
                if file_paths:
                    # self._print_header("Xác nhận dịch hàng loạt") # Already handled by batch_translate_files header
                    print(f"\n📋 Đã chọn {len(file_paths)} file để dịch từ '{self.input_folder}':")
                    for i, path_item in enumerate(file_paths): # Renamed variable
                        print(f"  {i+1}. {os.path.basename(path_item)}")
                    
                    print(f"Các file dịch (bản sao chung) sẽ được lưu trực tiếp vào: '{self.output_folder}'")

                    confirm = input("\nTiếp tục dịch các file này? (y/n): ").lower()
                    if confirm == 'y':
                        self.batch_translate_files(file_paths, output_subdir_for_common_copy=None)
                        print(f"\n🏁 Hoàn tất dịch file từ '{self.input_folder}'.")
                    else:
                        print("🚫 Đã hủy dịch file.")
                    input("\nNhấn Enter để tiếp tục...")
                # else:
                #     print(f"ℹ️ Không có file nào được chọn từ '{self.input_folder}'.")
                #     input("\nNhấn Enter để tiếp tục...")

            elif choice == "2":
                self._print_header("Dịch từ đường dẫn tùy chọn")
                custom_path = input("Nhập đường dẫn đầy đủ đến file (YAML/JSON) hoặc thư mục chứa file: ").strip()

                if not custom_path:
                    print("⚠️ Đường dẫn không được để trống.")
                    input("\nNhấn Enter để tiếp tục...")
                    continue

                if os.path.isfile(custom_path):
                    if custom_path.endswith((".yml", ".yaml", ".json")):
                        self.translate_file(custom_path, output_subdirectory_name=None)
                    else:
                        self.translation_errors.append("❌ File không phải là file YAML/JSON hợp lệ.")
                        self.display_and_clear_messages()
                        input("\nNhấn Enter để tiếp tục...")
                
                elif os.path.isdir(custom_path):
                    print(f"🔎 Đang tìm các file YAML/JSON trong thư mục: '{custom_path}'")
                    selected_file_paths_for_dir = []
                    selected_file_paths_for_dir = self.select_multiple_files_from_directory(custom_path)

                    if selected_file_paths_for_dir:
                        original_dir_basename = os.path.basename(custom_path) if custom_path else "selected_files"
                        self._print_header(f"Xác nhận dịch từ '{original_dir_basename}'")
                        print(f"\n📋 Sẽ dịch {len(selected_file_paths_for_dir)} file đã chọn từ thư mục '{original_dir_basename}'.")
                        for i, path_item in enumerate(selected_file_paths_for_dir):
                            print(f"  {i+1}. {os.path.basename(path_item)}")
                        print(f"Các file dịch (bản sao chung) sẽ được lưu vào: '{os.path.join(self.output_folder, original_dir_basename)}'")
                        
                        confirm_dir_translate = input("\nTiếp tục? (y/n): ").lower()
                        if confirm_dir_translate == 'y':
                            print(f"\n🚀 Bắt đầu dịch {len(selected_file_paths_for_dir)} file từ '{original_dir_basename}'...")
                            self.batch_translate_files(selected_file_paths_for_dir, output_subdir_for_common_copy=original_dir_basename)
                            print(f"\n🏁 Hoàn tất dịch các file từ thư mục '{original_dir_basename}'.")
                        else:
                            print("🚫 Đã hủy dịch các file từ thư mục.")
                        input("\nNhấn Enter để tiếp tục...")

                else:
                    self.translation_errors.append(f"❌ Đường dẫn không tồn tại hoặc không hợp lệ: '{custom_path}'")
                    self.display_and_clear_messages()
                    input("\nNhấn Enter để tiếp tục...")


            elif choice == "3": self.view_projects()
            elif choice == "4": self.delete_projects()
            elif choice == "5":
                self._print_header("Cấu hình thư mục mặc định")
                print(f"Thư mục đầu vào (input) mặc định hiện tại: {self.input_folder}")
                print(f"Thư mục đầu ra (output) chung cho file dịch hiện tại: {self.output_folder}")
                print(f"Thư mục gốc cho các dự án hiện tại: {self.projects_folder} (thường là {os.path.join(self.project_root, 'projects')})")

                new_input_str = input("\nThư mục đầu vào mặc định MỚI (Enter để giữ nguyên): ").strip()
                if new_input_str:
                    self.input_folder = new_input_str
                    os.makedirs(self.input_folder, exist_ok=True) # Ensure it exists after setting
                    print(f"✅ Thư mục đầu vào mặc định được cập nhật thành: {self.input_folder}")
                
                new_output_str = input("Thư mục đầu ra chung MỚI (Enter để giữ nguyên): ").strip()
                if new_output_str:
                    self.output_folder = new_output_str
                    os.makedirs(self.output_folder, exist_ok=True)
                    print(f"✅ Thư mục đầu ra chung được cập nhật thành: {self.output_folder}")
                
                os.makedirs(self.input_folder, exist_ok=True)
                os.makedirs(self.output_folder, exist_ok=True)
                os.makedirs(self.projects_folder, exist_ok=True)

                print(f"\n✅ Đã cập nhật và lưu cấu hình thư mục.")
                self.save_config()
                input("\nNhấn Enter để tiếp tục...")
            elif choice == "6": self.configure_language()
            elif choice == "7": self.configure_threading()
            elif choice == "8": self.configure_api_interactively()
            elif choice == "9": self.configure_rate_limit()
            elif choice == "10": self.configure_output_filename_option()
            elif choice == "0":
                clear_screen()
                print("\n🛑 Đang thoát chương trình và dọn dọn dẹp...")
                self.cleanup_temp_folders()
                print("👋 Cảm ơn đã sử dụng công cụ Dịch File!")
                return
            else:
                print("❌ Lựa chọn không hợp lệ. Vui lòng thử lại.")
                input("\nNhấn Enter để tiếp tục...")

    def run(self):
        """Khởi chạy ứng dụng"""
        try:
            self._print_header("Khởi Chạy")
            print("Đang kiểm tra cấu hình và API...")
            self.setup()
            self.main_menu()
        except KeyboardInterrupt:
            clear_screen()
            print("\n\n🛑 Chương trình bị ngắt bởi người dùng...")
            self.cleanup_temp_folders()
            print("👋 Cảm ơn đã sử dụng công cụ Dịch File!")
        except Exception as e:
            clear_screen()
            print(f"\n❌ Đã xảy ra lỗi không mong muốn: {str(e)}")
            traceback.print_exc()
            print("Vui lòng báo lỗi này cho nhà phát triển nếu cần thiết.")
            self.cleanup_temp_folders()
            input("\nNhấn Enter để thoát.")
        finally:
            print("\nĐóng chương trình.")

if __name__ == "__main__":
    translator = FileTranslator()
    translator.run()
