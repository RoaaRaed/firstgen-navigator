"""The Dockerfile cannot be built inside the test run (no Docker, no network), so these tests check that
it is safe and consistent with the rest of the project."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCKERFILE = (ROOT / "Dockerfile").read_text(encoding="utf-8")
IGNORE = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()


def test_secrets_and_local_data_stay_out_of_the_image():
    for pattern in (".env", ".streamlit/secrets.toml", "chroma_db/", ".git/"):
        assert pattern in IGNORE
    assert not re.search(r"GROQ_API_KEY\s*=\s*\S|ADMIN_PASSWORD\s*=\s*\S", DOCKERFILE)


def test_the_container_does_not_run_as_root():
    assert re.search(r"^USER\s+(?!root)\S+", DOCKERFILE, re.M)


def test_it_starts_the_streamlit_app_on_the_exposed_port():
    assert "app/main.py" in DOCKERFILE
    assert "EXPOSE 8501" in DOCKERFILE and "--server.port=8501" in DOCKERFILE
    assert "--server.address=0.0.0.0" in DOCKERFILE


def test_the_search_model_in_the_image_is_the_one_the_code_uses():
    from core.embeddings import E5Embedder

    assert E5Embedder.name in DOCKERFILE


def test_the_institution_setting_is_the_one_the_app_reads():
    assert re.search(r"^\s*INSTITUTION=demo-ccc", DOCKERFILE, re.M)
    assert "institutions/${INSTITUTION}/kb" in DOCKERFILE


def test_the_python_version_matches_the_tested_one():
    assert "python:3.11" in DOCKERFILE


def test_the_requirements_file_is_copied_before_the_code_so_the_install_layer_is_cached():
    assert DOCKERFILE.index("COPY requirements.txt") < DOCKERFILE.index("COPY . .")


def test_the_docs_page_exists():
    assert (ROOT / "docs" / "docker.md").exists()


def test_the_github_workflow_builds_and_starts_the_image_without_real_keys():
    wf = (ROOT / ".github" / "workflows" / "docker.yml").read_text(encoding="utf-8")
    assert "docker build" in wf and "/_stcore/health" in wf
    assert "GROQ_API_KEY=dummy" in wf
    assert "${{ secrets" not in wf  # it must not touch the repository's real secrets
