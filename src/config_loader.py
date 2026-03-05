"""설정 로드 (API 키, 기본 옵션)."""
from pathlib import Path
import os

try:
    import yaml
except ImportError:
    yaml = None

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
SETTINGS_PATH = CONFIG_DIR / "settings.yaml"
EXAMPLE_PATH = CONFIG_DIR / "settings.example.yaml"


def load_settings():
    """settings.yaml 또는 환경변수 기반 설정 반환."""
    defaults = {
        "youtube": {"api_key": "", "use_api": True},
        "instagram": {"use_selenium": True},
        "crawling": {"request_delay_sec": 2, "max_retries": 3, "timeout_sec": 30},
        "schedule": {"default_interval_min": 10},
    }
    if yaml and SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
            for key, val in loaded.items():
                if isinstance(val, dict) and key in defaults:
                    defaults[key].update(val)
                else:
                    defaults[key] = val
        except Exception:
            pass
    # 환경변수 오버라이드
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if api_key:
        defaults["youtube"]["api_key"] = api_key
    return defaults
