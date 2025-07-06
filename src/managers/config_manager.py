import json
import os
from dotenv import load_dotenv
from typing import List

class ConfigManager:
    def __init__(self):
        load_dotenv()
        self.api_keys: List[str] = []
        self.target_lang = "vi"
        self.project_root = "translator_projects"
        self.projects_folder = os.path.join(self.project_root, "projects")
        self.input_folder = os.path.join(self.project_root, "input_files")
        self.output_folder = os.path.join(self.project_root, "translated_files")
        self.max_workers = 4
        self.min_request_interval = 0.5
        self.max_retries = 5
        self.backoff_factor = 2.0
        self.config_file = os.path.join(self.project_root, "config.json")
        self.keep_original_filename = False
        self.max_display_project_count = 5

        self._load_config()

    def _load_config(self):
        """Tải cấu hình từ file config.json nếu có"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                api_key_data = config.get('api_keys') or config.get('api_key')
                if isinstance(api_key_data, list):
                    self.api_keys = [str(key) for key in api_key_data if isinstance(key, str) and key.strip()]
                elif isinstance(api_key_data, str) and api_key_data.strip():
                    self.api_keys = [k.strip() for k in api_key_data.split(',') if k.strip()]

                self.target_lang = config.get('target_lang', self.target_lang)
                self.max_workers = config.get('max_workers', self.max_workers)
                self.input_folder = config.get('input_folder', self.input_folder)
                self.output_folder = config.get('output_folder', self.output_folder)
                self.min_request_interval = config.get('min_request_interval', self.min_request_interval)
                self.max_retries = config.get('max_retries', self.max_retries)
                self.backoff_factor = config.get('backoff_factor', self.backoff_factor)
                self.keep_original_filename = config.get('keep_original_filename', self.keep_original_filename)
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
                'keep_original_filename': self.keep_original_filename,
                'max_display_project_count': self.max_display_project_count
            }

            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)

            print(f"✅ Đã lưu cấu hình vào {self.config_file}")
        except Exception as e:
            print(f"⚠️ Không thể lưu file cấu hình: {str(e)}")

    def get_config(self) -> dict:
        return {
            "api_keys": self.api_keys,
            "target_lang": self.target_lang,
            "max_workers": self.max_workers,
            "input_folder": self.input_folder,
            "output_folder": self.output_folder,
            "min_request_interval": self.min_request_interval,
            "max_retries": self.max_retries,
            "backoff_factor": self.backoff_factor,
            "config_file": self.config_file,
            "keep_original_filename": self.keep_original_filename,
            "project_root": self.project_root,
            "projects_folder": self.projects_folder,
            "max_display_project_count": self.max_display_project_count
        }

    def update_config(self, key: str, value: any):
        if hasattr(self, key):
            setattr(self, key, value)
            self.save_config()
        else:
            print(f"⚠️ Cấu hình không hợp lệ: {key}")

    def get_api_keys(self) -> List[str]:
        return self.api_keys

    def set_api_keys(self, keys: List[str]):
        self.api_keys = keys
        self.save_config()

    def get_target_lang(self) -> str:
        return self.target_lang

    def set_target_lang(self, lang: str):
        self.target_lang = lang
        self.save_config()

    def get_max_workers(self) -> int:
        return self.max_workers

    def set_max_workers(self, workers: int):
        self.max_workers = workers
        self.save_config()

    def get_min_request_interval(self) -> float:
        return self.min_request_interval

    def set_min_request_interval(self, interval: float):
        self.min_request_interval = interval
        self.save_config()

    def get_max_retries(self) -> int:
        return self.max_retries

    def set_max_retries(self, retries: int):
        self.max_retries = retries
        self.save_config()

    def get_backoff_factor(self) -> float:
        return self.backoff_factor

    def set_backoff_factor(self, factor: float):
        self.backoff_factor = factor
        self.save_config()

    def get_keep_original_filename(self) -> bool:
        return self.keep_original_filename

    def set_keep_original_filename(self, keep: bool):
        self.keep_original_filename = keep
        self.save_config()

    def get_input_folder(self) -> str:
        return self.input_folder

    def set_input_folder(self, folder: str):
        self.input_folder = folder
        os.makedirs(self.input_folder, exist_ok=True)
        self.save_config()

    def get_output_folder(self) -> str:
        return self.output_folder

    def set_output_folder(self, folder: str):
        self.output_folder = folder
        os.makedirs(self.output_folder, exist_ok=True)
        self.save_config()

    def get_projects_folder(self) -> str:
        return self.projects_folder

    def get_max_display_project_count(self) -> int:
        return self.max_display_project_count

    def set_max_display_project_count(self, count: int):
        self.max_display_project_count = count
        self.save_config()
