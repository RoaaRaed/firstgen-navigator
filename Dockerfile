# FirstGen Navigator AI: one container serves one institution.
#
#   docker build -t firstgen-navigator .
#   docker run --rm -p 8501:8501 --env-file .env firstgen-navigator
#   open http://localhost:8501
#
# Another institution: add  -e INSTITUTION=uic  to the run command.
# The Groq key is NOT in the image. It comes from the environment at run time (see docs/docker.md).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/opt/hf \
    INSTITUTION=demo-ccc

WORKDIR /app

# 1. Python packages (this layer is cached until requirements.txt changes).
COPY requirements.txt .
RUN pip install -r requirements.txt

# 2. The search model, downloaded once at build time so the container starts without the internet.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-small')"

# 3. The app. .dockerignore keeps .env, secrets, tests and local databases out of the image.
COPY . .

# 4. Run as a normal user, not root. The app writes chroma_db/ and Admin uploads under /app.
RUN useradd --create-home app && chown -R app:app /app /opt/hf
USER app

# From here on the model is already on disk: never try to reach Hugging Face.
ENV HF_HUB_OFFLINE=1

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health', timeout=4)"

# Build (or refresh) this institution's search index, then start the app. The index step is fast
# when the documents have not changed, and it is how documents added on the Admin page are picked up
# after a restart.
CMD ["sh", "-c", "python -m core.ingest --kb institutions/${INSTITUTION}/kb && exec streamlit run app/main.py --server.port=8501 --server.address=0.0.0.0"]
