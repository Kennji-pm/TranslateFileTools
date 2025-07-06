import os
import sys
from typing import List, Optional
from google import genai
from colorama import Fore

class APIManager:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.model: Optional[genai.Client] = None
        self._configure_genai_with_primary_key()

    def _configure_genai_with_primary_key(self):
        """Configures the global genai object with the primary API key."""
        api_keys = self.config_manager.get_api_keys()
        if not api_keys:
            self.model = None
            print("⚠️ Không có API key nào được cung cấp để cấu hình.")
            return

        primary_key = api_keys[0]
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

    def get_model(self):
        return self.model

    def _display_api_keys(self):
        """Hiển thị danh sách các API key hiện có."""
        api_keys = self.config_manager.get_api_keys()
        if api_keys:
            print(f"🔑 Các API key hiện có:")
            for i, key in enumerate(api_keys):
                key_display = f"...{key[-4:]}" if len(key) > 4 else key
                status = f" (Đang sử dụng)" if i == 0 else ""
                print(f"  [{i+1}] {key_display}{status}")
        else:
            print(f"🔑 Chưa có API key nào được cấu hình.")

    def configure_api_interactively(self, ui_manager):
        while True:
            ui_manager.print_header("Cấu Hình API Key")
            self._display_api_keys()

            print(f"\nChọn hành động:")
            print(f"  [1] Thêm API key mới")
            if self.config_manager.get_api_keys():
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
                    current_keys = self.config_manager.get_api_keys()
                    added_count = 0
                    for nk in new_keys:
                        if nk not in current_keys:
                            current_keys.append(nk)
                            added_count += 1
                    if added_count > 0:
                        self.config_manager.set_api_keys(current_keys)
                        print(f"✅ Đã thêm {added_count} API key mới.")
                        self._configure_genai_with_primary_key()
                    else:
                        print(f"ℹ️ Không có key mới nào được thêm (có thể đã tồn tại).")
                else:
                    print(f"⚠️ Không có key nào được nhập.")
                input(f"\nNhấn Enter để tiếp tục...")
                
            elif choice == '2' and self.config_manager.get_api_keys():
                if len(self.config_manager.get_api_keys()) == 1:
                    print(f"ℹ️ Chỉ có một API key, không cần chọn lại.")
                    input(f"\nNhấn Enter để tiếp tục...")
                    continue
                
                try:
                    ui_manager.print_header("Chọn API Key Chính")
                    self._display_api_keys()
                    key_index_str = input(f"\nNhập số thứ tự của API key muốn sử dụng làm chính (1-{len(self.config_manager.get_api_keys())}): ").strip()
                    selected_idx = int(key_index_str) - 1
                    current_keys = self.config_manager.get_api_keys()
                    if 0 <= selected_idx < len(current_keys):
                        selected_key = current_keys.pop(selected_idx)
                        current_keys.insert(0, selected_key)
                        self.config_manager.set_api_keys(current_keys)
                        print(f"✅ Đã đặt key '{f'...{selected_key[-4:]}' if len(selected_key) > 4 else selected_key}' làm key chính.")
                        self._configure_genai_with_primary_key()
                    else:
                        print(f"⚠️ Lựa chọn không hợp lệ. Vui lòng nhập số trong danh sách.")
                except ValueError:
                    print(f"❌ Đầu vào không hợp lệ. Vui lòng nhập một số.")
                input(f"\nNhấn Enter để tiếp tục...")

            elif choice == '3' and self.config_manager.get_api_keys():
                if not self.config_manager.get_api_keys():
                    print(f"ℹ️ Không có API key nào để xóa.")
                    input(f"\nNhấn Enter để tiếp tục...")
                    continue

                while True:
                    ui_manager.print_header("Xóa API Key")
                    self._display_api_keys()
                    print(f"\n💡 Nhập số thứ tự của API key muốn xóa (có thể nhập nhiều, cách nhau bằng dấu phẩy ',').")
                    print(f"   CẢNH BÁO: Không thể hoàn tác.")
                    delete_choice = input(f"Nhập lựa chọn của bạn (hoặc 'q' để quay lại): ").strip().lower()

                    if delete_choice == 'q':
                        break

                    try:
                        indices_to_delete = []
                        valid_input = True
                        current_keys = self.config_manager.get_api_keys()
                        for x in delete_choice.split(','):
                            x_strip = x.strip()
                            if x_strip:
                                num = int(x_strip) - 1
                                if 0 <= num < len(current_keys):
                                    indices_to_delete.append(num)
                                else:
                                    print(f"⚠️ Bỏ qua số thứ tự không hợp lệ: {num + 1}.")
                                    valid_input = False
                        
                        if not indices_to_delete:
                            if valid_input:
                                print(f"ℹ️ Không có key nào được chọn để xóa.")
                            input(f"\nNhấn Enter để tiếp tục...")
                            continue

                        indices_to_delete = sorted(list(set(indices_to_delete)), reverse=True)

                        print(f"\n⚠️ Bạn sắp xóa các API key sau:")
                        for idx in indices_to_delete:
                            key_display = f"...{current_keys[idx][-4:]}" if len(current_keys[idx]) > 4 else current_keys[idx]
                            print(f"  - [{idx+1}] {key_display}")
                        
                        confirm_delete = input(f"\n🛑 XÁC NHẬN XÓA (y/n)? ").strip().lower()
                        if confirm_delete == 'y':
                            deleted_count = 0
                            for idx in indices_to_delete:
                                deleted_key = current_keys.pop(idx)
                                print(f"✅ Đã xóa key: ...{deleted_key[-4:]}")
                                deleted_count += 1
                            
                            if deleted_count > 0:
                                self.config_manager.set_api_keys(current_keys)
                                self._configure_genai_with_primary_key()
                                print(f"🎉 Hoàn tất xóa key.")
                            else:
                                print(f"ℹ️ Không có key nào được xóa.")
                            input(f"\nNhấn Enter để tiếp tục...")
                            break
                        else:
                            print(f"❌ Đã hủy thao tác xóa.")
                            input(f"\nNhấn Enter để tiếp tục...")
                            break

                    except ValueError:
                        print(f"❌ Đầu vào không hợp lệ. Vui lòng nhập các số cách nhau bằng dấu phẩy.")
                        input(f"\nNhấn Enter để tiếp tục...")
            else:
                print(f"❌ Lựa chọn không hợp lệ. Vui lòng thử lại.")
                input(f"\nNhấn Enter để tiếp tục...")

        if not self.model:
            print(f"\n❌ Cấu hình API key không thành công hoặc không có key.")
            if input(f"Thử lại cấu hình API key? (y/n): ").lower() == 'y':
                return self.configure_api_interactively(ui_manager)
            else:
                print(f"⛔ Chương trình không thể hoạt động mà không có API key hợp lệ.")
                sys.exit(1)
