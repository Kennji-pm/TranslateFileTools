import os
import shutil
import datetime
from typing import List, Optional

class ProjectManager:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.temp_folders = []

        # Ensure project root and projects folder exist
        os.makedirs(self.config_manager.project_root, exist_ok=True)
        os.makedirs(self.config_manager.projects_folder, exist_ok=True)

    def create_project_folder(self, base_name: str) -> str:
        """Tạo thư mục dự án mới dựa trên tên file và thời gian"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        project_name = f"{base_name}_{timestamp}"
        project_path = os.path.join(self.config_manager.projects_folder, project_name)

        for subfolder in ["original", "chunks", "translated"]:
            os.makedirs(os.path.join(project_path, subfolder), exist_ok=True)

        return project_path

    def list_translatable_files(self, directory: str, translation_errors: List[str]) -> List[str]:
        """Liệt kê các file YAML và JSON trong thư mục"""
        if not os.path.exists(directory):
            return []
        try:
            files = [f for f in os.listdir(directory)
                       if os.path.isfile(os.path.join(directory, f)) and f.endswith((".yml", ".yaml", ".json"))]
            return sorted(files)
        except OSError as e:
            translation_errors.append(f"❌ Không thể truy cập thư mục {directory}: {e}")
            return []

    def view_projects(self, ui_manager):
        """Xem danh sách các dự án đã tạo"""
        ui_manager.print_header("Danh sách thư mục dự án")

        if not os.path.exists(self.config_manager.projects_folder):
            print("📂 Chưa có thư mục dự án nào được tạo.")
            input("\nNhấn Enter để tiếp tục...")
            return

        try:
            projects = [d for d in os.listdir(self.config_manager.projects_folder)
                        if os.path.isdir(os.path.join(self.config_manager.projects_folder, d))]
        except OSError as e:
            print(f"❌ Không thể truy cập thư mục dự án tại '{self.config_manager.projects_folder}': {e}")
            input("\nNhấn Enter để tiếp tục...")
            return

        if not projects:
            print("📂 Chưa có thư mục dự án nào được tạo.")
            input("\nNhấn Enter để tiếp tục...")
            return

        try:
            projects.sort(key=lambda x: os.path.getmtime(os.path.join(self.config_manager.projects_folder, x)), reverse=True)
        except OSError:
            print("⚠️ Lỗi khi sắp xếp dự án theo thời gian, hiển thị theo thứ tự mặc định.")

        print(f"🔍 Tìm thấy {len(projects)} thư mục dự án trong '{self.config_manager.projects_folder}':")
        for i, project_name in enumerate(projects):
            project_path = os.path.join(self.config_manager.projects_folder, project_name)
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

    def delete_projects(self, ui_manager):
        """Xóa một hoặc nhiều thư mục dự án"""
        ui_manager.print_header("Xóa thư mục dự án")

        if not os.path.exists(self.config_manager.projects_folder):
            print("📂 Chưa có thư mục dự án nào được tạo để xóa.")
            input("\nNhấn Enter để tiếp tục...")
            return

        try:
            projects = [d for d in os.listdir(self.config_manager.projects_folder)
                        if os.path.isdir(os.path.join(self.config_manager.projects_folder, d))]
            if not projects:
                print(f"📂 Không tìm thấy thư mục dự án nào trong '{self.config_manager.projects_folder}'.")
                input("\nNhấn Enter để tiếp tục...")
                return
            projects.sort(key=lambda x: os.path.getmtime(os.path.join(self.config_manager.projects_folder, x)), reverse=True)
        except OSError as e:
            print(f"❌ Không thể truy cập thư mục dự án tại '{self.config_manager.projects_folder}': {e}")
            input("\nNhấn Enter để tiếp tục...")
            return

        max_display_project_count = self.config_manager.get_max_display_project_count()
        num_total_projects = len(projects)
        print(f"\n📋 DANH SÁCH THƯ MỤC DỰ ÁN trong '{self.config_manager.projects_folder}':")
        for i in range(min(num_total_projects, max_display_project_count)):
            project = projects[i]
            project_path_full = os.path.join(self.config_manager.projects_folder, project) 
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
                projects_to_delete_names = projects
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
            for project_name_del in projects_to_delete_names: print(f"  - {project_name_del} (trong {self.config_manager.projects_folder})")

            confirm = input("\n🛑 CẢNH BÁO: Thao tác này KHÔNG THỂ HOÀN TÁC! Bạn có chắc chắn muốn xóa? (y/n): ").lower()
            if confirm != 'y':
                print("❌ Hủy thao tác xóa.")
                input("\nNhấn Enter để tiếp tục...")
                return

            deleted_count = 0
            error_count = 0
            print("\n🗑️  Đang tiến hành xóa...")
            for project_name_final_del in projects_to_delete_names:
                project_path_to_delete = os.path.join(self.config_manager.projects_folder, project_name_final_del)
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

    def cleanup_temp_folders(self):
        """Dọn dẹp các thư mục tạm thời (chunks are now in project folders, this might be less used or repurposed)"""
        cleaned_count = 0
        for folder in self.temp_folders:
            if os.path.exists(folder):
                try:
                    shutil.rmtree(folder)
                    cleaned_count +=1
                except Exception as e:
                    print(f"⚠️ Không thể xóa thư mục tạm {folder}: {str(e)}")
        if cleaned_count > 0:
            print(f"🧹 Đã dọn dẹp {cleaned_count} thư mục tạm thời.")
        self.temp_folders = []
