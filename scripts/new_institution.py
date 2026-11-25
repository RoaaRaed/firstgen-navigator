"""Create a new institution folder and time the setup (brief: a second institution in under 4 hours).

    python scripts/new_institution.py start uic --name "University of Illinois Chicago"
    ... upload documents on the Admin page, edit programs.csv and deadlines.csv, set INSTITUTION=uic ...
    python scripts/new_institution.py finish uic

`start` makes institutions/<slug>/ with a valid, almost empty set of files and writes the start time.
`finish` writes how long it took to institutions/<slug>/SETUP_TIME.md.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

import yaml

ROOT = Path("institutions")
TEMPLATE = "demo-ccc"
STARTED = ".setup_started"
GOLDEN_HEADER = "id,language,question,expected_behavior,expected_layer,expected_source_ids,requires_handoff,sensitive,notes\n"
DEADLINES_HEADER = "id,layer,institution,term,item,date,applies_to,source_url,retrieved_date,notes,language\n"


def _now() -> dt.datetime:
    return dt.datetime.now().replace(microsecond=0)


def create(slug: str, name: str, root: Path = ROOT, now: dt.datetime | None = None, state: str = "",
           website: str = "") -> Path:
    """Make institutions/<slug>/ that loads without errors. Raises ValueError if it already has a config."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug):
        raise ValueError("The folder name may only have lowercase letters, digits and dashes.")
    base = Path(root) / slug
    if (base / "config.yaml").exists():
        raise ValueError(f"{base} already has a config.yaml. Choose another name or delete the folder.")
    now = now or _now()
    base.mkdir(parents=True, exist_ok=True)
    (base / "kb").mkdir(exist_ok=True)
    (base / "kb" / ".gitkeep").touch()

    config = {"name": name, "short_name": "", "default_language": "en"}
    if state:
        config["state"] = state
    if website:
        config["website"] = website
    (base / "config.yaml").write_text("# Settings for this institution. To serve it, set INSTITUTION=" + slug + "\n"
                                      + yaml.safe_dump(config, sort_keys=False, allow_unicode=True), encoding="utf-8")

    # One placeholder office. Replace it with real rows (programs.csv); every hand-off topic points at it
    # until handoffs.yaml is edited, so the advisor always names a real row.
    placeholder = f"{slug}-student-services"
    import csv
    import io

    buf = io.StringIO(newline="")
    writer = csv.writer(buf, lineterminator="\n")
    site = website or "https://example.edu"
    writer.writerow(["id", "institution", "name", "category", "eligibility_tags", "description", "contact_office",
                     "contact_url", "contact_phone", "hours", "language_support", "source_url", "retrieved_date"])
    writer.writerow([placeholder, name, "Student Services (replace this row)", "academic", "",
                     "Placeholder office. Replace this row with a real office from the institution's website.",
                     "Student Services", site, "", "", "en", site, str(now.date())])
    (base / "programs.csv").write_text(buf.getvalue(), encoding="utf-8")
    (base / "deadlines.csv").write_text(DEADLINES_HEADER, encoding="utf-8")
    (base / "golden_questions.csv").write_text(GOLDEN_HEADER, encoding="utf-8")
    (base / "rules.yaml").write_text("# Personalization rules for this institution (see institutions/demo-ccc/rules.yaml)\n"
                                     "version: 0\nrules: []\n", encoding="utf-8")

    template = yaml.safe_load((Path(root) / TEMPLATE / "handoffs.yaml").read_text(encoding="utf-8"))
    topics = {}
    for key, cfg in template["topics"].items():
        topics[key] = {"program": placeholder, "aliases": cfg.get("aliases", []), "sensitive": bool(cfg.get("sensitive"))}
    (base / "handoffs.yaml").write_text(
        "# Who a student is sent to. Each topic points at a row of programs.csv. Edit after programs.csv is filled in.\n"
        + yaml.safe_dump({"version": 0, "topics": topics, "default": template.get("default", "academic")},
                         sort_keys=False, allow_unicode=True), encoding="utf-8")
    (base / STARTED).write_text(now.isoformat(), encoding="utf-8")
    return base


def finish(slug: str, root: Path = ROOT, now: dt.datetime | None = None) -> str:
    """Write SETUP_TIME.md and return the sentence that says how long the setup took."""
    base = Path(root) / slug
    marker = base / STARTED
    if not marker.exists():
        raise ValueError(f"{marker} not found. Run 'start' first (it writes the start time).")
    started = dt.datetime.fromisoformat(marker.read_text(encoding="utf-8").strip())
    ended = now or _now()
    minutes = round((ended - started).total_seconds() / 60)
    h, m = divmod(minutes, 60)
    sentence = f"Setup of '{slug}' took {h} h {m} min (started {started:%Y-%m-%d %H:%M}, finished {ended:%Y-%m-%d %H:%M})."
    (base / "SETUP_TIME.md").write_text(
        f"# Setup time: {slug}\n\n{sentence}\n\nTarget: under 4 hours, including document upload.\n"
        f"Result: {'within' if minutes < 240 else 'OVER'} the target.\n", encoding="utf-8")
    return sentence


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    s = sub.add_parser("start", help="create the folder and start the clock")
    s.add_argument("slug")
    s.add_argument("--name", required=True)
    s.add_argument("--state", default="")
    s.add_argument("--website", default="")
    f = sub.add_parser("finish", help="stop the clock and write SETUP_TIME.md")
    f.add_argument("slug")
    args = ap.parse_args(argv)
    try:
        if args.command == "start":
            base = create(args.slug, args.name, state=args.state, website=args.website)
            print(f"Created {base}. The clock is running.\nNext: upload documents on the Admin page, fill in "
                  f"programs.csv and deadlines.csv, then set INSTITUTION={args.slug}.")
        else:
            print(finish(args.slug))
    except ValueError as e:
        print(e)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
