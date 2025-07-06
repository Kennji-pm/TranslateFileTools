import yaml
import json
import re
import os
from typing import Any, Dict, List, Optional

class FileHandler:
    def __init__(self, translation_errors: List[str], translation_warnings: List[str]):
        self.translation_errors = translation_errors
        self.translation_warnings = translation_warnings

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
            if re.fullmatch(r"[A-Za-z0-9_\-\.\/]+", data) and not re.search(r"\s", data):
                 if not any(c.isalpha() for c in data if c.lower() > 'f'):
                    if len(re.findall(r'[A-Za-z]', data)) < 3 and len(data) < 30 :
                        return {}
            if len(data.strip()) > 0:
                texts[prefix] = data
        return texts

    def apply_translations(self, data: Any, translations: Dict[str, str], prefix="") -> Any:
        """Áp dụng bản dịch vào cấu trúc dữ liệu gốc"""
        if isinstance(data, dict):
            return {k: self.apply_translations(v, translations, f"{prefix}.{k}" if prefix else k) for k, v in data.items()}
        elif isinstance(data, list):
            return [self.apply_translations(v, translations, f"{prefix}[i]") for i, v in enumerate(data)]
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
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = {}
                    current_chars = 0
                chunks.append({key: text})
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

    def save_chunks_to_folder(self, chunks: List[Dict[str, str]], folder: str):
        """Lưu các phần nhỏ vào thư mục tạm (sử dụng JSON)"""
        os.makedirs(folder, exist_ok=True)

        for i, chunk in enumerate(chunks):
            path = os.path.join(folder, f"chunk_{i:03d}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(chunk, f, ensure_ascii=False, indent=2)
