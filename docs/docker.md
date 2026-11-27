# Run FirstGen Navigator in Docker

One container serves one institution. The image holds the code, the documents and the search model.
It does **not** hold any secret.

## Build

```bash
docker build -t firstgen-navigator .
```

The first build takes several minutes (it installs PyTorch and downloads the search model). Later builds are fast
unless `requirements.txt` changes.

## Run

Put your keys in a `.env` file next to the Dockerfile (never commit it; `.dockerignore` keeps it out of the image):

```
GROQ_API_KEY=your-key
ADMIN_PASSWORD=choose-a-long-password
```

Then:

```bash
docker run --rm -p 8501:8501 --env-file .env firstgen-navigator
```

Open <http://localhost:8501>. The Admin page is at <http://localhost:8501/Admin>.

## Another institution

```bash
docker run --rm -p 8502:8501 --env-file .env -e INSTITUTION=uic firstgen-navigator
```

`INSTITUTION` is the folder name under `institutions/`. See [white_label.md](white_label.md) for how to add one.

## What to know

- **Start-up:** the container builds the search index for its institution first (about a minute the first time),
  then starts the app. The healthcheck waits two minutes before it begins checking.
- **The index and Admin uploads live inside the container.** They are lost when the container is removed. To keep
  them, mount volumes:
  `-v fgn-db:/app/chroma_db -v fgn-docs:/app/institutions`. For uploads that should last, also add the file to the
  repository and rebuild the image.
- **No internet is needed for the search model** (it is in the image). The advisor still needs to reach Groq.
- **No student data is stored.** The app keeps no log of what students type (see `tests/test_privacy.py`).
- **Daily limit:** the free Groq tier has a daily token limit. When it is used up, the app says so and asks the student
  to try again tomorrow or contact an advisor.

## How it is checked

Every change to the Docker files runs the "Docker build" workflow on GitHub (`.github/workflows/docker.yml`). It builds
the image, checks that the image holds no secrets and does not run as root, starts the app with dummy keys, waits for
it to report healthy, and checks that the search index was built. The first run passed on 2026-11-27 (build and start
in under 4 minutes). It does not ask the AI a question, so it does not use any Groq quota.
