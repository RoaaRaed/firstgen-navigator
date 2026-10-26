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