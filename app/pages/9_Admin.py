"""Streamlit opens this file as the page /Admin. All the work is in app/admin_page.py."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import admin_page  # noqa: E402

admin_page.render()
