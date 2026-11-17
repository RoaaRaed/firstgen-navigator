"""Streamlit runs app/main.py with the app/ folder first on sys.path, so a file there named
like a standard-library module (app/profile.py once hid `profile`, which cProfile needs, which
torch imports) breaks unrelated libraries. This test stops that from happening again."""
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"


def test_no_app_file_or_folder_has_a_standard_library_name():
    names = {p.stem for p in APP.iterdir() if p.suffix == ".py" or p.is_dir()}
    names -= {"__init__", "__pycache__", "i18n", "assets"}
    clash = sorted(names & set(sys.stdlib_module_names))
    assert clash == [], f"these app/ names hide standard-library modules: {clash}"
