import time
import json
import re
import os
import random
from colorama import Fore

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

def clear_screen():
    """Xóa màn hình console"""
    os.system('cls' if os.name == 'nt' else 'clear')

def extract_json_from_response(text: str, translation_warnings: list) -> dict:
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
        translation_warnings.append(f"⚠️ Lỗi giải mã JSON: {str(e)}. Phản hồi gốc (hoặc phần được cho là JSON): {text[:500]}...")
        return None

    except Exception as e: # Catch other potential errors like regex not matching
        translation_warnings.append(f"⚠️ Không thể trích xuất JSON từ phản hồi Gemini (lỗi chung): {str(e)}. Phản hồi gốc: {text[:200]}...")
        return None
