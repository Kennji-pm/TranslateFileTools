import os
import time
import json
import shutil
import random
import threading
import concurrent.futures
from typing import Dict, List, Optional, Tuple

from tqdm import tqdm

from src.utils.utils import ExponentialBackoff, extract_json_from_response
from src.handlers.file_handler import FileHandler
from src.managers.api_manager import APIManager
from src.managers.config_manager import ConfigManager

class TranslationCore:
    def __init__(self, config_manager: ConfigManager, api_manager: APIManager, file_handler: FileHandler):
        self.config_manager = config_manager
        self.api_manager = api_manager
        self.file_handler = file_handler
        self.translation_errors = file_handler.translation_errors
        self.translation_warnings = file_handler.translation_warnings
        self.progress = None # For tqdm

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
        target_name = lang_names.get(self.config_manager.get_target_lang(), self.config_manager.get_target_lang())
        model = self.api_manager.get_model()

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

        for attempt in range(self.config_manager.get_max_retries()):
            try:
                response = model.models.generate_content(
                    model="gemini-2.0-flash", contents=prompt
                )
                translated_json = extract_json_from_response(response.text, self.translation_warnings)
                
                if translated_json and isinstance(translated_json, dict):
                    missing_keys = [k for k in text_chunk if k not in translated_json]
                    if not missing_keys:
                        extra_keys = [k for k in translated_json if k not in text_chunk]
                        if extra_keys:
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
                        if attempt < self.config_manager.get_max_retries() - 1:
                            time.sleep(2)
                        else:
                            self.translation_errors.append(
                                f"❌ Trích xuất JSON thất bại sau nhiều lần thử, trả về chunk gốc do thiếu key."
                                f"Input chunk: {json.dumps(text_chunk)}"
                            )
                            return text_chunk
                else:
                    self.translation_warnings.append(f"⚠️ Lần thử {attempt + 1}: Trích xuất JSON thất bại hoặc không phải dạng dict. Thử lại...")
                    if attempt < self.config_manager.get_max_retries() - 1:
                         time.sleep(2)
                    else:
                        self.translation_errors.append(f"❌ Trích xuất JSON thất bại sau nhiều lần thử, trả về chunk gốc.")
                        return text_chunk

            except Exception as e:
                self.translation_warnings.append(f"⚠️ Lỗi khi dịch với Gemini (lần {attempt + 1}): {str(e)}")
                if attempt < self.config_manager.get_max_retries() - 1:
                    time.sleep(2 * (attempt + 1))
                else:
                    self.translation_errors.append(f"❌ Lỗi khi dịch với Gemini sau {self.config_manager.get_max_retries()} lần thử: {str(e)}. Trả về chunk gốc.")
                    return text_chunk

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
                factor=self.config_manager.get_backoff_factor(),
                jitter=True
            )

            for attempt in range(1, self.config_manager.get_max_retries() + 1):
                try:
                    translated_data = self.translate_with_gemini(original_chunk_data)

                    if translated_data and isinstance(translated_data, dict) and all(key in translated_data for key in original_chunk_data.keys()):
                        if translated_data != original_chunk_data or (translated_data == original_chunk_data and attempt >= self.config_manager.get_max_retries()):
                            if lock:
                                with lock:
                                    self.progress.update(1)
                            return translated_data
                        else:
                            self.translation_warnings.append(
                                f"🔎 Chunk {os.path.basename(chunk_path)} ({basename}): "
                                f"Dịch không thay đổi, có thể do toàn ID hoặc lỗi tạm thời. Thử lại (lần {attempt}/{self.config_manager.get_max_retries()})."
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
                        # sys.exit(1) # Do not exit here, let main handle it

                    if attempt < self.config_manager.get_max_retries():
                        delay_time = backoff.wait()
                        error_type_msg = "Rate limit/Server busy" if is_rate_limit else "Lỗi API/JSON"
                        self.translation_warnings.append(
                            f"⚠️ {error_type_msg} (chunk {os.path.basename(chunk_path)}), "
                            f"thử lại sau {delay_time:.2f}s (lần {attempt+1}/{self.config_manager.get_max_retries()}). Lỗi: {str(e)[:100]}"
                        )
                    else:
                        self.translation_errors.append(
                            f"❌ Chunk {os.path.basename(chunk_path)}: Thất bại sau {self.config_manager.get_max_retries()} lần. Lỗi: {str(e)}. Trả về chunk gốc."
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

    def translate_file(self, input_path: str, output_path: Optional[str] = None, silent: bool = False, existing_project_path: Optional[str] = None, output_subdirectory_name: Optional[str] = None, project_manager=None):
        if not silent:
            # self._print_header(f"Dịch File: {os.path.basename(input_path)}") # UI Manager handles headers
            pass
        
        if not os.path.exists(input_path):
            self.translation_errors.append(f"❌ Không tìm thấy file: {input_path}")
            if not silent: input("\nNhấn Enter để tiếp tục...")
            return False

        base_name, ext = os.path.splitext(os.path.basename(input_path))

        project_to_use_for_artifacts = existing_project_path
        if not project_to_use_for_artifacts:
            if project_manager:
                project_to_use_for_artifacts = project_manager.create_project_folder(base_name)
            else:
                self.translation_errors.append("❌ ProjectManager không được cung cấp để tạo thư mục dự án.")
                return False
        else:
            for subfolder in ["original", "chunks", "translated"]:
                os.makedirs(os.path.join(project_to_use_for_artifacts, subfolder), exist_ok=True)
        
        translated_filename_only = f"{base_name}{ext}" if self.config_manager.get_keep_original_filename() else f"{base_name}_{self.config_manager.get_target_lang()}{ext}"

        final_translated_file_destination = output_path
        if not final_translated_file_destination:
            final_translated_file_destination = os.path.join(project_to_use_for_artifacts, "translated", translated_filename_only)
        
        os.makedirs(os.path.dirname(final_translated_file_destination), exist_ok=True)

        if not silent:
            print(f"\n📂 Đang dịch file: {input_path}")
            print(f"🗂️ Thư mục dự án (chứa file gốc, chunks): {project_to_use_for_artifacts}")
            print(f"💾 File dịch chính sẽ được lưu tại: {final_translated_file_destination}")

        original_copy_path = os.path.join(project_to_use_for_artifacts, "original", os.path.basename(input_path))
        shutil.copy2(input_path, original_copy_path)
        chunks_folder = os.path.join(project_to_use_for_artifacts, "chunks")

        original_data = self.file_handler.load_file(input_path)
        if not original_data:
            if not silent:
                # self.display_and_clear_messages() # UI Manager handles this
                input("\nNhấn Enter để tiếp tục...")
            return False

        texts_to_translate = self.file_handler.extract_text(original_data)
        if not texts_to_translate:
            if not silent: self.translation_warnings.append("⚠️ Không tìm thấy nội dung để dịch trong file.")
            if self.file_handler.save_file(original_data, final_translated_file_destination):
                if not silent: print(f"✅ File gốc không có nội dung dịch, đã sao chép tới: {final_translated_file_destination}")
                
                common_output_dir_final = self.config_manager.get_output_folder()
                if output_subdirectory_name:
                    common_output_dir_final = os.path.join(common_output_dir_final, output_subdirectory_name)
                os.makedirs(common_output_dir_final, exist_ok=True)
                common_output_path_final = os.path.join(common_output_dir_final, translated_filename_only)
                self.file_handler.save_file(original_data, common_output_path_final)
                if not silent: print(f"✅ Đã lưu bản sao tại: {common_output_path_final}")

            else:
                if not silent: self.translation_errors.append(f"❌ Lỗi khi sao chép file gốc (không có nội dung dịch).")
            if not silent: 
                # self.display_and_clear_messages() # UI Manager handles this
                input("\nNhấn Enter để tiếp tục...")
            return True

        if not silent: print(f"✂️ Trích xuất {len(texts_to_translate)} đoạn văn bản, đang chia nhỏ...")
        chunks = self.file_handler.chunk_texts(texts_to_translate, max_chars=1800)
        self.file_handler.save_chunks_to_folder(chunks, chunks_folder)

        if not silent: print(f"🌐 Đang dịch ({len(chunks)} phần) với {self.config_manager.get_max_workers()} luồng...")
        translated_texts_combined = {}
        chunk_files = sorted([os.path.join(chunks_folder, f) for f in os.listdir(chunks_folder) if f.endswith('.json')])

        self.progress = tqdm(total=len(chunk_files), 
                             desc=f"Dịch {os.path.basename(input_path)}" if not silent else None, 
                             disable=silent, 
                             leave=False)
        
        progress_lock = threading.Lock()
        last_request_time = [time.time() - self.config_manager.get_min_request_interval()]
        rate_limit_lock = threading.Lock()

        def rate_limited_translate_task(chunk_file_path):
            with rate_limit_lock:
                current_time = time.time()
                time_since_last = current_time - last_request_time[0]
                actual_min_interval = self.config_manager.get_min_request_interval() + random.uniform(0, self.config_manager.get_min_request_interval() * 0.1)

                if time_since_last < actual_min_interval:
                    sleep_time = actual_min_interval - time_since_last
                    time.sleep(sleep_time)
                last_request_time[0] = time.time()
            
            return self.translate_chunk(chunk_file_path, basename=f"{base_name}{ext}", lock=progress_lock)

        try:
            actual_workers_for_pool = max(1, self.config_manager.get_max_workers()) 

            with concurrent.futures.ThreadPoolExecutor(max_workers=actual_workers_for_pool) as executor:
                futures = [executor.submit(rate_limited_translate_task, chunk_path) for chunk_path in chunk_files]
                
                for future in concurrent.futures.as_completed(futures):
                    try:
                        result = future.result()
                        if result and isinstance(result, dict):
                            translated_texts_combined.update(result)
                    except Exception as exc_inner:
                        self.translation_errors.append(f"❌ Lỗi khi xử lý một future cho file {os.path.basename(input_path)}: {exc_inner}")

            if not silent : self.progress.close()

            translated_data_structure = self.file_handler.apply_translations(original_data, translated_texts_combined)
            
            if self.file_handler.save_file(translated_data_structure, final_translated_file_destination):
                if not silent: print(f"\n✅ Đã lưu file dịch chính tại: {final_translated_file_destination}")
                
                common_output_dir_final = self.config_manager.get_output_folder()
                if output_subdirectory_name:
                    common_output_dir_final = os.path.join(common_output_dir_final, output_subdirectory_name)
                
                os.makedirs(common_output_dir_final, exist_ok=True)
                common_output_path_final = os.path.join(common_output_dir_final, translated_filename_only)
                
                if self.file_handler.save_file(translated_data_structure, common_output_path_final):
                    if not silent: print(f"✅ Đã lưu bản sao tại: {common_output_path_final}")
                else:
                    if not silent: self.translation_errors.append(f"❌ Lỗi khi lưu bản sao tại: {common_output_path_final}")

                if not silent: 
                    # self.display_and_clear_messages() # UI Manager handles this
                    input("\nNhấn Enter để tiếp tục...")
                return True
            else:
                if not silent:
                    self.translation_errors.append(f"❌ Lỗi khi lưu file dịch chính tại: {final_translated_file_destination}")
                    # self.display_and_clear_messages() # UI Manager handles this
                    input("\nNhấn Enter để tiếp tục...")
                return False

        except Exception as e:
            if not silent and hasattr(self, 'progress') and self.progress and not self.progress.disable:
                self.progress.close()
            
            self.translation_errors.append(f"\n❌ Lỗi trong quá trình dịch file {os.path.basename(input_path)}: {str(e)}")
            
            if not silent:
                # self.display_and_clear_messages() # UI Manager handles this
                input("\nNhấn Enter để tiếp tục...")
            return False
        finally:
            pass

    def batch_translate_files(self, file_paths: List[str], output_subdir_for_common_copy: Optional[str] = None, project_manager=None, ui_manager=None):
        if not file_paths:
            print("ℹ️ Không có file nào được chọn để dịch.")
            input("\nNhấn Enter để tiếp tục...")
            return
        
        self.translation_errors = []
        self.translation_warnings = []

        header_message = f"Dịch hàng loạt ({len(file_paths)} file)"
        if output_subdir_for_common_copy:
            header_message = f"Dịch thư mục '{output_subdir_for_common_copy}' ({len(file_paths)} file)"
        if ui_manager:
            ui_manager.print_header(header_message)

        num_workers = min(len(file_paths), self.config_manager.get_max_workers(), 8) 
        print(f"📊 Sử dụng tối đa {num_workers} luồng để dịch {len(file_paths)} file.")
        
        start_time = time.time()
        results_summary = []
        with tqdm(total=len(file_paths), desc=f"Tiến độ dịch các file", unit="file", bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}]") as batch_progress:
            with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
                futures_to_path = {
                    executor.submit(self._translate_file_with_project_wrapper, file_path, output_subdir_for_common_copy, project_manager): file_path 
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
        if ui_manager:
            ui_manager.print_header(f"Kết quả dịch {len(file_paths)} file")
        print("\n--- Kết quả dịch hàng loạt ---")
        print(f"📊 Tổng số file đã xử lý: {len(file_paths)}")
        print(f"✅ Thành công: {successful_translations}")
        print(f"❌ Thất bại: {failed_translations}")
        print(f"⏱️ Tổng thời gian: {duration:.2f} giây")

        if len(results_summary) < 10:
            if any(s for _,s,_ in results_summary):
                print("\n📁 Chi tiết các bản dịch thành công:")
                for fname, success, proj_path in results_summary:
                    if success:
                        print(f"  ✓ {fname} (Thư mục dự án: {proj_path if proj_path else 'N/A'})")
        
        if ui_manager:
            ui_manager.display_and_clear_messages()
        
        print(f"\nℹ️ Bản sao của các file dịch thành công (nếu có) được lưu tại: {self.config_manager.get_output_folder()}" + (f"/{output_subdir_for_common_copy}" if output_subdir_for_common_copy else ""))

    def _translate_file_with_project_wrapper(self, input_path: str, output_subdirectory_name: Optional[str] = None, project_manager=None):
        """
        Wrapper for translate_file to be used in ThreadPoolExecutor.
        Creates a project folder for the file and calls translate_file.
        Ensures `translate_file` is called in silent mode for batch operations.
        Returns a tuple: (success_status: bool, project_artifact_path: Optional[str])
        """
        try:
            base_name, ext = os.path.splitext(os.path.basename(input_path))
            project_path_for_this_file_artifacts = project_manager.create_project_folder(base_name)
            translated_filename_in_project = f"{base_name}{ext}" if self.config_manager.get_keep_original_filename() else f"{base_name}_{self.config_manager.get_target_lang()}{ext}"
            output_path_within_project_artifacts = os.path.join(project_path_for_this_file_artifacts, "translated", translated_filename_in_project)
            success_status = self.translate_file(
                input_path=input_path,
                output_path=output_path_within_project_artifacts,
                silent=True,
                existing_project_path=project_path_for_this_file_artifacts,
                output_subdirectory_name=output_subdirectory_name,
                project_manager=project_manager
            )
            return success_status, project_path_for_this_file_artifacts
        except Exception as e:
            self.translation_errors.append(f"❌ Lỗi không mong muốn khi thiết lập dịch file {os.path.basename(input_path)} trong batch: {str(e)}")
            return False, None
