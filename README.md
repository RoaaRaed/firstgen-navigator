# FirstGen Navigator AI

A bilingual (English and Arabic) advising assistant for first-generation and immigrant college students. It answers only from an institution's own documents, cites its sources, shows a confidence label, and says "Not found" when it does not know.

Built for the Chicago Education Advocacy Cooperative (ChiEAC).
Author: Roaa Abu Arra.

> **Status:** work in progress (fellowship project, October to December 2026).

## Quick start (Windows PowerShell)

```powershell
git clone https://github.com/RoaaRaed/firstgen-navigator.git
cd firstgen-navigator
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env   # then add your own API key to .env
```

Requires Python 3.11 or later.

## Run it

```powershell
python -m core.ingest            # builds the search index (chroma_db/) the first time
streamlit run app/main.py
```

On a machine without `chroma_db/` (for example Streamlit Community Cloud) the app builds the
index by itself on start-up; this takes about a minute.

## Deploy to Streamlit Community Cloud

1. Push to GitHub, then on share.streamlit.io choose **Create app**: repository
   `RoaaRaed/firstgen-navigator`, branch `main`, main file `app/main.py`.
2. In **Advanced settings** pick **Python 3.11** (the version `requirements.txt` was tested with), and paste
   the contents of `.streamlit/secrets.toml.example` into **Secrets** with your real `GROQ_API_KEY`.
   Never commit the key.
3. Deploy. The first start downloads the embedding model and builds the index (a few minutes).
   After a day without visitors the app sleeps and wakes with a short delay.
4. In the app's **Settings > Sharing** restrict viewing to the people who should see the demo.
   Every question uses the project's Groq quota (about 200,000 tokens a day on the free plan,
   roughly 20 conversations), so the link should not be public.

Privacy: the questionnaire answers and the free-text note are sent to the Groq API together with
the question. The questionnaire never asks about immigration status.

## Project structure

| Folder | Purpose |
|---|---|
| `app/` | Streamlit interface (pages, translations, styles) |
| `core/` | Retrieval, agent, tools, prompts |
| `institutions/` | One folder per institution: config, documents, tables |
| `evals/` | Evaluation scripts and reports |
| `tests/` | Automated tests |
| `docs/` | Architecture notes, cost model, transcripts |
| `experiments/` | Early prototypes and setup checks |

## License

See [LICENSE](LICENSE).