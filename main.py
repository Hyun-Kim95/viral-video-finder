"""Viral Video Finder - 진입점."""
import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ui.main_window import run_app

if __name__ == "__main__":
    try:
        run_app()
    except KeyboardInterrupt:
        sys.exit(0)
