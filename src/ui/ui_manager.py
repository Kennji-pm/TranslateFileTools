import os
from typing import List, Tuple, Optional
from colorama import Fore

class UIManager:
    def __init__(self, config_manager, project_manager, translation_errors: List[str], translation_warnings: List[str]):
        self.config_manager = config_manager
        self.project_manager = project_manager
        self.translation_errors = translation_errors
        self.translation_warnings = translation_warnings

    def print_header(self, title: str):
        os.system('cls' if os.name == 'nt' else 'clear')
        print("=" * 70)
        print(f"🎨 CÔNG CỤ DỊCH FILE V3 - {title.upper()} 🎨".center(70))
        print("=" * 70)

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
                            else:
                                print(f"⚠️ Khoảng chọn '{token}' không hợp lệ. Hãy đảm bảo các số nằm trong khoảng 1-{files_count} và số đầu không lớn hơn số cuối.")
                    except ValueError:
                        print(f"⚠️ Số không hợp lệ trong khoảng chọn: {token}. Mong đợi dạng '<số>-<số>'.")
                else:
                    print(f"⚠️ Định dạng khoảng chọn không hợp lệ: {token}. Sử dụng dạng '<số>-<số>' (ví dụ: 1-5).")
            else:
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

    def select_file_from_directory(self, directory: str) -> Optional[str]:
        self.print_header("Chọn file")
        files = self.project_manager.list_translatable_files(directory, self.translation_errors)

        if not files:
            print(f"❌ Không tìm thấy file YAML hoặc JSON nào trong thư mục '{directory}'")
            print("💡 Hãy đặt các file YAML/JSON vào thư mục và thử lại hoặc làm mới danh sách.")
            input("\nNhấn Enter để tiếp tục...")
            return []

        print(f"\n📋 Các file YAML/JSON có sẵn trong '{directory}':")
        for i, file_name_display in enumerate(files):
            print(f"  [{i+1}] {file_name_display}")

        while True:
            prompt_message = (
                f"\n🔢 Nhập STT file, khoảng chọn (vd: 1-3, ^4), 'all' "
                f"(hoặc 'q' để quay lại, 'r' để làm mới): "
            )
            choice = input(prompt_message).strip().lower()

            if choice == 'q':
                return []
            elif choice == 'r':
                print(f"🔄 Đang làm mới danh sách file từ '{directory}'...")
                files = self.project_manager.list_translatable_files(directory, self.translation_errors)
                if not files:
                    print(f"❌ Không tìm thấy file YAML hoặc JSON nào trong '{directory}' sau khi làm mới.")
                    return []
                print(f"\n📋 Các file YAML/JSON có sẵn trong '{directory}':")
                for i, file_name_display_refreshed in enumerate(files):
                    print(f"  [{i+1}] {file_name_display_refreshed}")
                continue

            raw_tokens = [t.strip() for t in choice.split(',') if t.strip()]

            if not raw_tokens:
                if choice:
                    print("⚠️ Lựa chọn không hợp lệ. Vui lòng nhập số, khoảng chọn, 'all', 'q', hoặc 'r'.")
                else:
                    print("⚠️ Lựa chọn không được để trống.")
                continue

            selected_indices, all_valid = self._parse_file_selection_tokens(raw_tokens, len(files), os.path.basename(directory))

            if not selected_indices and choice:
                if all_valid:
                     print(f"ℹ️ Các chỉ số bạn nhập không tương ứng với file nào hiện có (1-{len(files)}).")
                continue

            if selected_indices:
                return [os.path.join(directory, files[i]) for i in selected_indices]

    def select_multiple_files_from_directory(self, directory: str, header_override: Optional[str] = None) -> List[str]:
        effective_header = header_override if header_override else f"Chọn nhiều file từ '{os.path.basename(directory)}'"
        
        files = self.project_manager.list_translatable_files(directory, self.translation_errors)

        if not files:
            print(f"❌ Không tìm thấy file YAML hoặc JSON nào trong thư mục '{directory}'")
            print("💡 Hãy đặt các file YAML/JSON vào thư mục và thử lại hoặc làm mới danh sách.")
            input("\nNhấn Enter để tiếp tục...")
            return []

        print(f"\n📋 Các file YAML/JSON có sẵn trong '{directory}':")
        for i, file_name_display in enumerate(files):
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
                print(f"🔄 Đang làm mới danh sách file từ '{directory}'...")
                files = self.project_manager.list_translatable_files(directory, self.translation_errors)
                if not files:
                    print(f"❌ Không tìm thấy file YAML hoặc JSON nào trong '{directory}' sau khi làm mới.")
                    return []
                print(f"\n📋 Các file YAML/JSON có sẵn trong '{directory}':")
                for i, file_name_display_refreshed in enumerate(files):
                    print(f"  [{i+1}] {file_name_display_refreshed}")
                continue
            
            raw_tokens = [t.strip() for t in choice.split(',') if t.strip()]
            
            if not raw_tokens:
                if choice:
                     print("⚠️ Lựa chọn không hợp lệ. Vui lòng nhập STT, khoảng chọn, 'all', 'q', hoặc 'r'.")
                else:
                     print("⚠️ Lựa chọn không được để trống.")
                continue

            selected_indices, all_valid = self._parse_file_selection_tokens(raw_tokens, len(files), os.path.basename(directory))

            if not selected_indices and choice:
                if all_valid:
                    print(f"ℹ️ Các chỉ số bạn nhập không tương ứng với file nào hiện có (1-{len(files)}).")
                continue
            
            if selected_indices:
                return [os.path.join(directory, files[i]) for i in selected_indices]

    def display_and_clear_messages(self):
        """Displays accumulated errors and warnings, then clears them."""
        if self.translation_warnings:
            print(f"\n--- Cảnh báo dịch ({len(self.translation_warnings)} cảnh báo) ---")
            for warning_msg in self.translation_warnings:
                print(Fore.YELLOW + warning_msg + Fore.RESET)
            self.translation_warnings.clear()
        
        if self.translation_errors:
            print(f"\n--- LỖI DỊCH ({len(self.translation_errors)} lỗi) ---")
            for error_msg in self.translation_errors:
                print(Fore.RED + error_msg + Fore.RESET)
            self.translation_errors.clear()

    def main_menu(self, api_manager, translation_core):
        while True:
            self.print_header("Menu Chính")
            print(" Lựa chọn chức năng dịch:")
            print(f"  [1] Dịch file từ thư mục đầu vào mặc định ('{os.path.basename(self.config_manager.get_input_folder())}')")
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
            print(f" 👤 Cấu hình hiện tại ({self.config_manager.config_file}):")
            lang_display = self.config_manager.get_target_lang()
            api_keys = self.config_manager.get_api_keys()
            active_key_info = f"API key chính: {Fore.GREEN}...{api_keys[0][-4:]}{Fore.RESET}" if api_keys and api_keys[0] else f"{Fore.RED}Chưa có key{Fore.RESET}"
            filename_option_display = "Giữ nguyên" if self.config_manager.get_keep_original_filename() else "Thêm mã ngôn ngữ"
            print(f"    🌐 Ngôn ngữ đích: {lang_display}  🧵 Số luồng: {self.config_manager.get_max_workers()}  📦 Model: gemini-2.0-flash")
            print(f"    🔑 {active_key_info} ({len(api_keys)} key(s)) 🏷️ Tên file: {filename_option_display}")
            print(f"    📂 Input: '{self.config_manager.get_input_folder()}' | Output: '{self.config_manager.get_output_folder()}'")
            print("=" * 70)

            choice = input("Nhập lựa chọn của bạn: ").strip()

            if choice == "1":
                self.print_header(f"Dịch nhiều file từ '{self.config_manager.get_input_folder()}'")
                file_paths = self.select_multiple_files_from_directory(self.config_manager.get_input_folder())
                if file_paths:
                    print(f"\n📋 Đã chọn {len(file_paths)} file để dịch từ '{self.config_manager.get_input_folder()}':")
                    for i, path_item in enumerate(file_paths):
                        print(f"  {i+1}. {os.path.basename(path_item)}")
                    
                    print(f"Các file dịch (bản sao chung) sẽ được lưu trực tiếp vào: '{self.config_manager.get_output_folder()}'")

                    confirm = input("\nTiếp tục dịch các file này? (y/n): ").lower()
                    if confirm == 'y':
                        translation_core.batch_translate_files(file_paths, output_subdir_for_common_copy=None, project_manager=self.project_manager, ui_manager=self)
                        print(f"\n🏁 Hoàn tất dịch file từ '{self.config_manager.get_input_folder()}'.")
                    else:
                        print("🚫 Đã hủy dịch file.")
                    input("\nNhấn Enter để tiếp tục...")

            elif choice == "2":
                self.print_header("Dịch từ đường dẫn tùy chọn")
                custom_path = input("Nhập đường dẫn đầy đủ đến file (YAML/JSON) hoặc thư mục chứa file: ").strip()

                if not custom_path:
                    print("⚠️ Đường dẫn không được để trống.")
                    input("\nNhấn Enter để tiếp tục...")
                    continue

                if os.path.isfile(custom_path):
                    if custom_path.endswith((".yml", ".yaml", ".json")):
                        translation_core.translate_file(custom_path, output_subdirectory_name=None, project_manager=self.project_manager)
                        self.display_and_clear_messages()
                    else:
                        self.translation_errors.append("❌ File không phải là file YAML/JSON hợp lệ.")
                        self.display_and_clear_messages()
                        input("\nNhấn Enter để tiếp tục...")
                
                elif os.path.isdir(custom_path):
                    print(f"🔎 Đang tìm các file YAML/JSON trong thư mục: '{custom_path}'")
                    selected_file_paths_for_dir = self.select_multiple_files_from_directory(custom_path)

                    if selected_file_paths_for_dir:
                        original_dir_basename = os.path.basename(custom_path) if custom_path else "selected_files"
                        self.print_header(f"Xác nhận dịch từ '{original_dir_basename}'")
                        print(f"\n📋 Sẽ dịch {len(selected_file_paths_for_dir)} file đã chọn từ thư mục '{original_dir_basename}'.")
                        for i, path_item in enumerate(selected_file_paths_for_dir):
                            print(f"  {i+1}. {os.path.basename(path_item)}")
                        print(f"Các file dịch (bản sao chung) sẽ được lưu vào: '{os.path.join(self.config_manager.get_output_folder(), original_dir_basename)}'")
                        
                        confirm_dir_translate = input("\nTiếp tục? (y/n): ").lower()
                        if confirm_dir_translate == 'y':
                            print(f"\n🚀 Bắt đầu dịch {len(selected_file_paths_for_dir)} file từ '{original_dir_basename}'...")
                            translation_core.batch_translate_files(selected_file_paths_for_dir, output_subdir_for_common_copy=original_dir_basename, project_manager=self.project_manager, ui_manager=self)
                            print(f"\n🏁 Hoàn tất dịch các file từ thư mục '{original_dir_basename}'.")
                        else:
                            print("🚫 Đã hủy dịch các file từ thư mục.")
                        input("\nNhấn Enter để tiếp tục...")

                else:
                    self.translation_errors.append(f"❌ Đường dẫn không tồn tại hoặc không hợp lệ: '{custom_path}'")
                    self.display_and_clear_messages()
                    input("\nNhấn Enter để tiếp tục...")


            elif choice == "3": self.project_manager.view_projects(self)
            elif choice == "4": self.project_manager.delete_projects(self)
            elif choice == "5":
                self.print_header("Cấu hình thư mục mặc định")
                print(f"Thư mục đầu vào (input) mặc định hiện tại: {self.config_manager.get_input_folder()}")
                print(f"Thư mục đầu ra (output) chung cho file dịch hiện tại: {self.config_manager.get_output_folder()}")
                print(f"Thư mục gốc cho các dự án hiện tại: {self.config_manager.get_projects_folder()} (thường là {os.path.join(self.config_manager.project_root, 'projects')})")

                new_input_str = input("\nThư mục đầu vào mặc định MỚI (Enter để giữ nguyên): ").strip()
                if new_input_str:
                    self.config_manager.set_input_folder(new_input_str)
                    print(f"✅ Thư mục đầu vào mặc định được cập nhật thành: {self.config_manager.get_input_folder()}")
                
                new_output_str = input("Thư mục đầu ra chung MỚI (Enter để giữ nguyên): ").strip()
                if new_output_str:
                    self.config_manager.set_output_folder(new_output_str)
                    print(f"✅ Thư mục đầu ra chung được cập nhật thành: {self.config_manager.get_output_folder()}")
                
                print(f"\n✅ Đã cập nhật và lưu cấu hình thư mục.")
                input("\nNhấn Enter để tiếp tục...")
            elif choice == "6":
                self.print_header("Cấu hình ngôn ngữ đích")
                languages = {
                    "vi": "Tiếng Việt", "en": "Tiếng Anh", "zh": "Tiếng Trung",
                    "ja": "Tiếng Nhật", "ko": "Tiếng Hàn", "fr": "Tiếng Pháp",
                    "de": "Tiếng Đức", "es": "Tiếng Tây Ban Nha", "ru": "Tiếng Nga"
                }

                print("Các ngôn ngữ có sẵn:")
                for code, name in languages.items():
                    print(f"  {code}: {name}")

                choice_lang = input(f"Chọn ngôn ngữ đích (mặc định: {self.config_manager.get_target_lang()}): ").strip()
                if choice_lang in languages:
                    self.config_manager.set_target_lang(choice_lang)
                    print(f"✅ Đã chọn ngôn ngữ đích: {languages[self.config_manager.get_target_lang()]}")
                else:
                    print(f"⚠️ Không nhận dạng được ngôn ngữ, sử dụng mặc định: {languages[self.config_manager.get_target_lang()]}")

                input("\nNhấn Enter để tiếp tục...")
            elif choice == "7":
                self.print_header("Cấu hình đa luồng")
                print(f"Số luồng hiện tại: {self.config_manager.get_max_workers()}")

                try:
                    new_workers = input(f"Nhập số luồng mới (1-16, mặc định: {self.config_manager.get_max_workers()}): ").strip()
                    if new_workers:
                        new_workers = int(new_workers)
                        if 1 <= new_workers <= 16:
                            self.config_manager.set_max_workers(new_workers)
                            print(f"✅ Đã cập nhật số luồng thành: {self.config_manager.get_max_workers()}")
                        else:
                            print("⚠️ Số luồng phải từ 1-16, giữ nguyên giá trị hiện tại.")
                    else:
                        print(f"✅ Giữ nguyên số luồng: {self.config_manager.get_max_workers()}")
                except ValueError:
                    print("⚠️ Giá trị không hợp lệ, giữ nguyên số luồng hiện tại.")

                input("\nNhấn Enter để tiếp tục...")
            elif choice == "8": api_manager.configure_api_interactively(self)
            elif choice == "9":
                self.print_header("Cấu hình Rate Limit & Retry")
                print(f"Cấu hình hiện tại:")
                print(f"- Khoảng cách tối thiểu giữa các request API (giây): {self.config_manager.get_min_request_interval()}")
                print(f"- Số lần thử lại tối đa cho mỗi chunk: {self.config_manager.get_max_retries()}")
                print(f"- Hệ số tăng thời gian chờ (backoff factor): {self.config_manager.get_backoff_factor()}")

                update = input("\nBạn muốn cập nhật cấu hình này? (y/n): ").lower()
                if update == 'y':
                    try:
                        interval_str = input(f"Khoảng cách tối thiểu mới (giây, hiện tại: {self.config_manager.get_min_request_interval()}, Enter để giữ): ").strip()
                        if interval_str: self.config_manager.set_min_request_interval(max(0.1, float(interval_str)))

                        retries_str = input(f"Số lần thử lại tối đa mới (hiện tại: {self.config_manager.get_max_retries()}, Enter để giữ): ").strip()
                        if retries_str: self.config_manager.set_max_retries(max(1, int(retries_str)))

                        factor_str = input(f"Hệ số tăng thời gian chờ mới (hiện tại: {self.config_manager.get_backoff_factor()}, Enter để giữ): ").strip()
                        if factor_str: self.config_manager.set_backoff_factor(max(1.1, float(factor_str))) 

                        print("\n✅ Đã cập nhật cấu hình rate limit & retry.")
                    except ValueError:
                        print("\n⚠️ Giá trị không hợp lệ, giữ nguyên cấu hình cũ.")
                else:
                    print("\nℹ️ Không thay đổi cấu hình.")
                input("\nNhấn Enter để tiếp tục...")
            elif choice == "10":
                self.print_header("Tùy chọn tên file đầu ra")
                current_status = "Giữ nguyên tên file gốc" if self.config_manager.get_keep_original_filename() else f"Thêm mã ngôn ngữ (_{self.config_manager.get_target_lang()}) vào tên file"
                print(f"Trạng thái hiện tại: {current_status}")
                
                choice_filename = input(f"Bạn có muốn giữ nguyên tên file gốc khi dịch không? (y/n, mặc định là '{'y' if self.config_manager.get_keep_original_filename() else 'n'}'): ").lower()
                if choice_filename == 'y':
                    self.config_manager.set_keep_original_filename(True)
                    print("✅ Tên file đầu ra sẽ được giữ nguyên (ví dụ: 'filename.ext').")
                elif choice_filename == 'n':
                    self.config_manager.set_keep_original_filename(False)
                    print(f"✅ Mã ngôn ngữ '_{self.config_manager.get_target_lang()}' sẽ được thêm vào tên file đầu ra (ví dụ: 'filename_{self.config_manager.get_target_lang()}.ext').")
                else:
                    print(f"⚠️ Lựa chọn không hợp lệ. Giữ nguyên cài đặt hiện tại: {current_status}")
                    
                input("\nNhấn Enter để tiếp tục...")
            elif choice == "0":
                os.system('cls' if os.name == 'nt' else 'clear')
                print("\n🛑 Đang thoát chương trình và dọn dọn dẹp...")
                self.project_manager.cleanup_temp_folders()
                print("👋 Cảm ơn đã sử dụng công cụ Dịch File!")
                return
            else:
                print("❌ Lựa chọn không hợp lệ. Vui lòng thử lại.")
                input("\nNhấn Enter để tiếp tục...")
