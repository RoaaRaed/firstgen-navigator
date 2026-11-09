"""Generate the 10 scripted conversations required for Week 3 and save each as a transcript
JSON under docs/transcripts/. Run with:

    python -m scripts.run_transcripts

If one question hits a transient error (for example the free Groq tier's per-minute token
limit), this script prints the error and moves on to the next question instead of losing the
transcripts that already succeeded. Rerun the whole script afterwards - already-saved
transcripts are simply overwritten with a fresh result, so rerunning is always safe.
"""
from __future__ import annotations

import time

from core.harness import ask, save_transcript

CONVERSATIONS = [
    ("g001", "01-map-deadline-en", "en",
     "What is the Illinois MAP grant and is there a deadline I should know about?"),
    ("g002", "02-fafsa-alternative-application-en", "en",
     "I cannot file the FAFSA. Is there any state aid I can apply for?"),
    ("g007", "03-food-emergency-help-en", "en",
     "Where can I get help with food or emergency costs on campus?"),
    ("g008", "04-spring-semester-dates-en", "en",
     "When does the spring semester start and when is the last day to drop a class?"),
    ("g017", "05-undocumented-enrollment-en", "en",
     "Does being undocumented affect whether I can enroll at City Colleges?"),
    ("g025", "06-best-college-refuse-en", "en",
     "What is the best college in Chicago?"),
    ("g027", "07-bookstore-hours-not-found-en", "en",
     "What time does the Wright College bookstore close on Saturdays?"),
    ("g031", "08-map-deadline-ar", "ar",
     "ما هي منحة MAP ومتى الموعد النهائي للتقديم؟"),
    ("g036", "09-food-emergency-help-ar", "ar",
     "أين أجد مساعدة في الطعام أو في التكاليف الطارئة داخل الجامعة؟"),
    ("g032", "10-fafsa-alternative-application-ar", "ar",
     "لا أستطيع تعبئة طلب FAFSA. هل هناك مساعدات من الولاية يمكنني التقديم عليها؟"),
]


def main() -> int:
    from dotenv import load_dotenv

    load_dotenv()
    rows = []
    for i, (golden_id, slug, language, question) in enumerate(CONVERSATIONS, 1):
        print(f"[{i}/10] {golden_id} ({language}): {question[:60]}")
        try:
            result, seconds = ask(question, language=language)
        except Exception as e:
            print(f"        FAILED: {type(e).__name__}: {e}")
            rows.append((golden_id, language, "FAILED", "(none)"))
            time.sleep(5)  # let the free tier's per-minute token budget recover before the next try
            continue

        path = save_transcript(f"docs/transcripts/{slug}.json", question, language, result, seconds)
        tools = ", ".join(c["name"] for c in result.tool_calls) or "(none)"
        print(f"        confidence={result.answer.confidence}  tools=[{tools}]  ({seconds:.1f}s)  -> {path}")
        rows.append((golden_id, language, result.answer.confidence, tools))
        time.sleep(3)  # small gap between questions so we stay under the free tier's TPM limit

    print(f"\n{'id':6} {'lang':5} {'confidence':11} tools")
    for golden_id, language, confidence, tools in rows:
        print(f"{golden_id:6} {language:5} {confidence:11} {tools}")

    have_confidence = sum(1 for r in rows if r[2] in ("High", "Medium", "Low"))
    failed = sum(1 for r in rows if r[2] == "FAILED")
    print(f"\n{len(rows)}/10 questions attempted. Confidence label present on "
          f"{have_confidence}/{len(rows)} answers.")
    if failed:
        print(f"{failed} question(s) failed and were skipped - rerun this script again; "
              "the ones that already succeeded are safe and will just be saved again.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
