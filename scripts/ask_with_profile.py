"""Ask one question WITH a student profile and print the raw result, including the real
error text if the advisor falls back.

    python scripts/ask_with_profile.py "What help can I get for paying for college?"
    python scripts/ask_with_profile.py "..." --no-profile      (same question, no profile)
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import advisor, strings  # noqa: E402
from app.profile_block import build_profile_block  # noqa: E402

ANSWERS = {"stage": "returning", "language": "en", "work_hours": "over_30", "family": "children",
           "financial_aid": "not_eligible_or_unsure", "needs": ["support"], "contact": "phone"}

p = argparse.ArgumentParser()
p.add_argument("question")
p.add_argument("--no-profile", action="store_true")
args = p.parse_args()

ctx = advisor.get_context()
profile = "" if args.no_profile else build_profile_block(
    advisor.get_ruleset(ctx), strings.load_strings("en"), ANSWERS, "en")
print(f"profile: {len(profile)} characters")
agent = advisor.get_agent(ctx, "en")
t0 = time.time()
result, _ = advisor.answer(agent, args.question, "en", profile=profile)
print(f"({time.time() - t0:.1f}s)  confidence: {result.answer.confidence}")
print("tools:", [c["name"] for c in result.tool_calls])
print(result.answer.answer)
