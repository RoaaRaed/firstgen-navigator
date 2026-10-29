"""Load and validate rules.yaml (the personalization rule set).

Run `python -m core.rules` to validate institutions/demo-ccc/rules.yaml.
"""
import json
import sys
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from core.tables import Category, Tag

Audience = Literal["applying", "enrolled", "transfer", "all"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Condition(_Strict):
    question: str
    any_of: list[str]


class NextStep(_Strict):
    en: str
    ar: str


class Handoff(_Strict):
    topic: str
    gentle: bool = True


class Rule(_Strict):
    id: str
    description: str
    match: Literal["any", "all"] = "all"
    conditions: list[Condition]
    priority: int = 3  # 1 = most important
    add_profile_tags: list[Tag] = []
    prefer_documents: list[str] = []
    prefer_program_categories: list[Category] = []
    prefer_deadline_audiences: list[Audience] = []
    search_hints: list[str] = []
    next_steps: list[NextStep] = []
    handoff: Optional[Handoff] = None
    must_not: list[str] = []
    notes: Optional[str] = None

    @model_validator(mode="after")
    def check_rule(self):
        if not self.conditions:
            raise ValueError("a rule needs at least one condition")
        if not 1 <= self.priority <= 5:
            raise ValueError("priority must be between 1 and 5")
        return self


class RuleSet(_Strict):
    version: int
    rules: list[Rule]

    @model_validator(mode="after")
    def unique_ids(self):
        ids = [r.id for r in self.rules]
        dups = sorted({i for i in ids if ids.count(i) > 1})
        if dups:
            raise ValueError(f"duplicate rule ids: {dups}")
        return self


def load_rules(path) -> RuleSet:
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    try:
        return RuleSet(**data)
    except ValidationError as err:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in err.errors()
        )
        raise ValueError(f"{path.name}: {problems}") from err


def questionnaire_ids(en_json_path) -> dict[str, set[str]]:
    """Map each question id to its set of option ids (free-text questions map to an empty set)."""
    data = json.loads(Path(en_json_path).read_text(encoding="utf-8"))
    return {
        q["id"]: {o["id"] for o in q.get("options", [])}
        for q in data["questionnaire"]["questions"]
    }


def check_references(ruleset: RuleSet, en_json_path, kb_dir) -> list[str]:
    """Return a list of problems: unknown question/option ids or missing KB documents."""
    known = questionnaire_ids(en_json_path)
    kb_dir = Path(kb_dir)
    problems = []
    for rule in ruleset.rules:
        for cond in rule.conditions:
            if cond.question not in known:
                problems.append(f"{rule.id}: unknown question id '{cond.question}'")
                continue
            for opt in cond.any_of:
                if opt not in known[cond.question]:
                    problems.append(f"{rule.id}: '{opt}' is not an option of '{cond.question}'")
        for doc in rule.prefer_documents:
            if not (kb_dir / f"{doc}.md").exists():
                problems.append(f"{rule.id}: document '{doc}' not found in {kb_dir}")
    return problems


if __name__ == "__main__":
    root = Path("institutions/demo-ccc")
    rules = load_rules(root / "rules.yaml")
    issues = check_references(rules, "app/i18n/en.json", root / "kb")
    if issues:
        print("\n".join(issues))
        sys.exit(1)
    print(f"OK: {len(rules.rules)} rules valid")
