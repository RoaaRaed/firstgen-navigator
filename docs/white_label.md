# Adding a new institution (no code changes)

An institution is a folder under `institutions/` plus one setting. Target: under 4 hours.

1. **Create the folder and start the clock**
   `python scripts/new_institution.py start <slug> --name "Full Institution Name" --website https://...`
2. **Add documents.** Run the app, open `/Admin`, choose the institution, upload public PDF, Word,
   Markdown or HTML pages (give each its source URL), then press Re-index.
3. **Fill in the tables.** Edit `institutions/<slug>/programs.csv` (real offices) and `deadlines.csv`
   (real dates), then upload them on the Admin page, Tables tab, or put them in the folder.
4. **Point the hand-offs at real offices.** Edit `institutions/<slug>/handoffs.yaml`
   (each topic names a row of `programs.csv`).
5. **Write test questions.** Add rows to `institutions/<slug>/golden_questions.csv`, then run the
   Coverage Report on the Admin page.
6. **Serve it.** Set `INSTITUTION=<slug>` in `.env` (local) or in the app's Streamlit Secrets
   (a second deployment of the same repository). Nothing else changes.
7. **Stop the clock.** `python scripts/new_institution.py finish <slug>` writes `SETUP_TIME.md`.

Optional: `rules.yaml` (personalization rules) starts empty; copy ideas from `institutions/demo-ccc/rules.yaml`.
