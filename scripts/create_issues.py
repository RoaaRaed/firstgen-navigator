"""Create the GitHub Issues for every deliverable in the project brief.

Run from the project root, with GitHub CLI logged in:
    python scripts/create_issues.py            # preview only
    python scripts/create_issues.py --create   # really create them

Safe to run twice: issues whose title already exists are skipped.
"""
import json
import subprocess
import sys
import time

REPO = "RoaaRaed/firstgen-navigator"

LABELS = {
    "week-1": "0e8a16", "week-2": "1d76db", "week-3": "5319e7", "week-4": "d93f0b",
    "week-5": "fbca04", "week-6": "0052cc", "week-7": "b60205",
    "gate": "000000", "linkedin": "0a66c2", "kb": "1f5fd1", "evaluation": "0f7a52",
}

# (week, title, labels, benchmark/body, done)
ISSUES = [
    # ---------- Week 1: Oct 26-30 ----------
    (1, "Repository live with layout and README stub", [],
     "Benchmark: repository live with layout and README stub.", False),
    (1, "Decide the KB front matter schema and write the validator", ["kb"],
     "Seven-field front matter, validator in core/kb.py, template in docs/kb_template.md, 8 tests.", True),
    (1, "Write 25+ curated KB documents across federal, state, institution", ["kb"],
     "Benchmark: 25 or more documents in kb/ with complete front matter. Done: 25 documents, validated with python -m core.kb.", True),
    (1, "Fill deadlines.csv with 15+ rows and validate with Pydantic loader", ["kb"],
     "Benchmark: both CSVs validated by a Pydantic loader. Done: 22 rows.", True),
    (1, "Fill programs.csv with 15+ rows and validate with Pydantic loader", ["kb"],
     "Benchmark: both CSVs validated by a Pydantic loader. Done: 18 rows.", True),
    (1, "Close programs.csv coverage gap: food, immigrant services, child care", ["kb"],
     "Add rows backed by the new KB documents (food access/SNAP, undocumented student services). Validate with load_programs.", False),
    (1, "Draft golden_questions.csv v0 (40 questions)", ["evaluation"],
     "Benchmark: golden set v0 committed. 40 questions tagged by layer and expected behavior (Appendix B).", False),
    (1, "Write rules.yaml v0 with five personalization rules", [],
     "Five rules applied to next steps, based on questionnaire ids (not label text).", False),
    (1, "LinkedIn post 1 (kickoff)", ["linkedin"],
     "Tag Chicago Education Advocacy Cooperative and Benjamin Drury. Done: posted Oct 29.", True),
    (1, "Week 1 Friday update to benjamin@chieac.org", [],
     "Due Fri Oct 30, 12:00 pm Chicago (8:00 pm Palestine): what shipped, what is blocked, hours spent, next week's plan, link to LinkedIn post.", False),
    # ---------- Week 2: Nov 2-6 ----------
    (2, "Build ingest.py: load, split by heading, metadata, hash, embed, persist to Chroma", [],
     "Re-index touches only changed files.", False),
    (2, "Build retriever.py with language and layer filters and similarity threshold", [], "", False),
    (2, "Write retrieval_eval.py: expected source in top five for every golden question", ["evaluation"], "", False),
    (2, "Tune chunk size and threshold (BM25 hybrid only if Arabic falls short)", [], "", False),
    (2, "retrieval_report.md with the numbers", ["evaluation"], "", False),
    (2, "Gate 1: It retrieves (Nov 6)", ["gate"],
     "Top-5 hit rate at or above 80% for English questions and 70% for Arabic.", False),
    (2, "LinkedIn post 2", ["linkedin"], "Suggested: what a KB with metadata looks like, and the first hit-rate number.", False),
    # ---------- Week 3: Nov 9-13 ----------
    (3, "Implement the four tools with deterministic source identifiers", [], "", False),
    (3, "System prompt skeleton in both languages", [],
     "Citation rules, confidence labels, refusal policy, disclosure.", False),
    (3, "Pydantic output schema and LangChain tool-calling agent (agent.py, tools/)", [],
     "Docstrings on every tool.", False),
    (3, "Command-line harness printing answer, citations, confidence, tool calls", [], "", False),
    (3, "10 scripted conversations saved in docs/transcripts/", [],
     "Benchmark: correct tool selection; confidence label on 100% of answers.", False),
    (3, "LinkedIn post 3", ["linkedin"], "Suggested: how the agent decides which tool to call; a Not found answer done well.", False),
    # ---------- Week 4: Nov 16-20 ----------
    (4, "Streamlit pages: language toggle with RTL CSS, questionnaire, chat with citation cards, My Plan with PDF", [], "", False),
    (4, "Profile injection and rules.yaml applied to next steps", [], "", False),
    (4, "Bilingual parity test: 15 questions in both languages", ["evaluation"],
     "Benchmark: same top source cited in at least 12 of 15 pairs.", False),
    (4, "First deployment to Streamlit Community Cloud with secrets", [], "", False),
    (4, "Gate 2: It advises with citations, in both languages (Nov 20)", ["gate"],
     "Live dev URL shared with Benjamin.", False),
    (4, "LinkedIn post 4 (first demo clip)", ["linkedin"], "Same question in English and Arabic, with citations.", False),
    # ---------- Week 5: Nov 23-27 ----------
    (5, "Expand golden set: 40+ answerable, 10 out-of-scope, 8 sensitive-topic questions", ["evaluation"], "", False),
    (5, "Deterministic pytest checks: citation present and exists, refusal and hand-off when expected", ["evaluation"], "", False),
    (5, "LLM-as-judge groundedness score; record prompt and model", ["evaluation"],
     "Benchmark: groundedness at or above 85%; correct refusal on 9 of 10 out-of-scope.", False),
    (5, "evals/run_eval.py and eval_report.md with metrics table", ["evaluation"], "", False),
    (5, "Fix the top failure modes; iterate prompts and thresholds", [], "", False),
    (5, "Confirm no personal data is logged; add Clear my answers", [], "", False),
    (5, "LinkedIn post 5", ["linkedin"], "Suggested: the evaluation report, what you measure and why.", False),
    # ---------- Week 6: Nov 30-Dec 4 ----------
    (6, "Admin page: password from secrets, upload PDF/DOCX/MD/HTML/CSV, re-index, change summary", [], "", False),
    (6, "Knowledge Base Coverage Report", ["kb"],
     "Unanswerable golden questions, documents older than a configurable age, optional anonymized top questions.", False),
    (6, "institutions/<slug>/config.yaml and second institution from configuration only (timed)", [],
     "Benchmark: second-institution setup under 4 hours including upload, time recorded.", False),
    (6, "Measure tokens per conversation; cost_model.md at 500, 2,000, 10,000 conversations", [], "", False),
    (6, "Write the Dockerfile", [], "", False),
    (6, "Gate 3: Deployed, white-label ready, evaluated (Dec 4)", ["gate"],
     "Two institution instances live from the same code.", False),
    (6, "LinkedIn post 6", ["linkedin"], "", False),
    # ---------- Week 7: Dec 7-11 ----------
    (7, "README: architecture diagram, setup, configuration, eval results, limitations, roadmap", [], "", False),
    (7, "Record a 3 to 5 minute demo video", [],
     "Student flow, Arabic flow, admin upload, Coverage Report.", False),
    (7, "Pilot one-pager with ChiEAC", [],
     "Problem, product, evidence from the eval report, pilot offer, pricing placeholders.", False),
    (7, "Finalize resume and LinkedIn bullets with real numbers", [], "", False),
    (7, "Hand-off call with Benjamin; tag v1.0 release", [], "", False),
    (7, "Gate 4: Handed off and pitch-ready (Dec 11)", ["gate"],
     "v1.0 release; README complete; demo video; pilot one-pager; final LinkedIn post.", False),
    (7, "LinkedIn post 7 (final, with video)", ["linkedin"], "", False),
]


def gh(*args, check=True):
    return subprocess.run(["gh", *args, "--repo", REPO] if args[0] in ("issue", "label") else ["gh", *args],
                          capture_output=True, text=True, encoding="utf-8", check=check)


def main():
    create = "--create" in sys.argv
    if not create:
        for week, title, labels, body, done in ISSUES:
            print(f"[week-{week}] {'(closed) ' if done else ''}{title}")
        print(f"\n{len(ISSUES)} issues. Add --create to really create them.")
        return

    for name, color in LABELS.items():
        gh("label", "create", name, "--color", color, "--force")
    existing = json.loads(gh("issue", "list", "--state", "all", "--limit", "500", "--json", "title").stdout)
    have = {i["title"] for i in existing}

    made = skipped = 0
    for week, title, labels, body, done in ISSUES:
        if title in have:
            skipped += 1
            continue
        all_labels = ",".join([f"week-{week}", *labels])
        out = gh("issue", "create", "--title", title, "--body", body or "Deliverable from the project brief, section 8.",
                 "--label", all_labels).stdout.strip()
        if done:
            gh("issue", "close", out, "--comment", "Shipped.")
        print(("closed  " if done else "open    ") + title)
        made += 1
        time.sleep(1)
    print(f"\nCreated {made}, skipped {skipped} that already existed.")


if __name__ == "__main__":
    main()
