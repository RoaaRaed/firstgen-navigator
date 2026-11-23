"""Tests for app/student_answers.py and app/wizard.py (questionnaire logic, no Streamlit)."""
import pytest

from app import student_answers as profile, strings, wizard


@pytest.fixture
def en():
    return strings.load_strings("en")


@pytest.fixture
def qs(en):
    return en["questionnaire"]["questions"]


def by_id(qs, qid):
    return next(q for q in qs if q["id"] == qid)


def fresh():
    s = {}
    wizard.init_state(s)
    return s


# ---- profile.clean_value / set_answer -------------------------------------------------

def test_single_accepts_a_valid_option_and_rejects_unknown(qs):
    q = by_id(qs, "stage")
    assert profile.clean_value(q, "applying") == "applying"
    assert profile.clean_value(q, "made_up") is None
    assert profile.clean_value(q, None) is None


def test_multi_keeps_valid_unique_options_and_caps_at_max(qs):
    q = by_id(qs, "needs")
    assert q["max_choices"] == 3
    got = profile.clean_value(q, ["paying", "paying", "bogus", "deadlines", "support", "classes"])
    assert got == ["paying", "deadlines", "support"]
    assert profile.clean_value(q, []) is None
    assert profile.clean_value(q, "paying") is None  # a string is not a list


def test_free_text_is_trimmed_and_capped(qs):
    q = by_id(qs, "notes")
    assert profile.clean_value(q, "  hello  ") == "hello"
    assert profile.clean_value(q, "   ") is None
    assert len(profile.clean_value(q, "x" * 5000)) == profile.NOTES_MAX_CHARS


def test_set_answer_does_not_mutate_and_removes_when_empty(qs):
    q = by_id(qs, "stage")
    a = {}
    b = profile.set_answer(a, q, "applying")
    assert a == {} and b == {"stage": "applying"}
    assert profile.set_answer(b, q, None) == {}


def test_describe_answers_shows_labels_and_marks_skipped(en):
    answers = {"stage": "applying", "needs": ["paying", "deadlines"], "notes": "hi"}
    rows = dict(profile.describe_answers(en, answers))
    assert rows["Where are you right now?"] == "Applying now"
    assert rows["What do you need most right now?"] == "Paying for college, Not missing deadlines"
    assert rows["Anything else you want the advisor to know?"] == "hi"
    assert rows["Which language do you prefer?"] == en["questionnaire"]["skipped"]
    assert len(rows) == len(en["questionnaire"]["questions"])


def test_describe_answers_works_in_arabic():
    ar = strings.load_strings("ar")
    rows = profile.describe_answers(ar, {"stage": "applying"})
    assert len(rows) == 8 and rows[1][1] == ar["questionnaire"]["skipped"]


# ---- wizard navigation ------------------------------------------------------------------

def test_init_state_has_defaults_and_does_not_overwrite():
    s = fresh()
    assert s == {"page": "home", "q_index": 0, "answers": {}}
    s["page"] = "chat"
    wizard.init_state(s)
    assert s["page"] == "chat"


def test_start_goes_to_first_question():
    s = fresh(); s["q_index"] = 4
    wizard.start(s)
    assert (s["page"], s["q_index"]) == ("questionnaire", 0)


def test_next_saves_the_pick_and_moves_on(qs):
    s = fresh(); wizard.start(s)
    s[wizard.widget_key("stage")] = "first_year"
    wizard.save_and_next(s, qs)
    assert s["answers"] == {"stage": "first_year"} and s["q_index"] == 1


def test_next_with_nothing_picked_counts_as_skipped(qs):
    s = fresh(); wizard.start(s)
    wizard.save_and_next(s, qs)
    assert s["answers"] == {} and s["q_index"] == 1


def test_skip_forgets_the_old_answer(qs):
    s = fresh(); wizard.start(s)
    s["answers"] = {"stage": "applying"}
    s[wizard.widget_key("stage")] = "applying"
    wizard.skip(s, qs)
    assert s["answers"] == {} and s["q_index"] == 1
    assert wizard.widget_key("stage") not in s


def test_finishing_the_last_question_goes_to_chat(qs):
    s = fresh(); wizard.start(s)
    s["q_index"] = len(qs) - 1
    s[wizard.widget_key("notes")] = "need evening classes"
    wizard.save_and_next(s, qs)
    assert s["page"] == "chat" and s["answers"]["notes"] == "need evening classes"


def test_back_keeps_the_current_pick_and_goes_earlier(qs):
    s = fresh(); wizard.start(s)
    s["q_index"] = 2
    s[wizard.widget_key("work_hours")] = "h11_20"
    wizard.back(s, qs)
    assert s["q_index"] == 1 and s["answers"] == {"work_hours": "h11_20"}


def test_back_from_the_done_page_returns_to_the_last_question(qs):
    s = fresh(); s["page"] = "chat"; s["q_index"] = len(qs) - 1
    wizard.back(s, qs)
    assert s["page"] == "questionnaire" and s["q_index"] == len(qs) - 2


def test_back_on_the_first_question_stays_put(qs):
    s = fresh(); wizard.start(s)
    wizard.back(s, qs)
    assert s["q_index"] == 0


def test_clear_answers_resets_everything(qs):
    s = fresh(); wizard.start(s)
    s["answers"] = {"stage": "applying", "needs": ["paying"]}
    s["q_index"] = 5
    s[wizard.widget_key("needs")] = ["paying"]
    s["messages"] = [{"role": "user", "content": "I live at ..."}]
    s["pending_question"] = "a question"
    wizard.clear_answers(s, qs)
    assert s["answers"] == {} and s["q_index"] == 0 and s["page"] == "questionnaire"
    assert wizard.widget_key("needs") not in s
    assert s["messages"] == [] and "pending_question" not in s      # the chat is forgotten too


def test_a_full_walkthrough_ends_with_the_right_profile(qs):
    s = fresh(); wizard.start(s)
    picks = {"stage": "applying", "language": "ar", "work_hours": "over_30", "family": "children",
             "financial_aid": "not_eligible_or_unsure", "needs": ["paying", "support"],
             "contact": "email", "notes": "I work nights"}
    for q in qs:
        s[wizard.widget_key(q["id"])] = picks[q["id"]]
        wizard.save_and_next(s, qs)
    assert s["page"] == "chat" and s["answers"] == picks


def test_widget_key_is_different_per_language():
    assert wizard.widget_key("stage", "en") != wizard.widget_key("stage", "ar")


def test_remember_stores_the_pick_right_away_in_the_current_language(qs):
    s = fresh(); wizard.start(s)
    s["lang"] = "ar"
    q = by_id(qs, "needs")
    s[wizard.widget_key("needs", "ar")] = ["paying", "support"]
    wizard.remember(s, q)
    assert s["answers"] == {"needs": ["paying", "support"]}


def test_a_pick_survives_switching_language(qs):
    s = fresh(); wizard.start(s)
    q = by_id(qs, "needs")
    s["lang"] = "en"
    s[wizard.widget_key("needs", "en")] = ["deadlines"]
    wizard.remember(s, q)
    s["lang"] = "ar"  # the student switches language; the Arabic widget starts empty
    assert s["answers"]["needs"] == ["deadlines"]


def test_clear_and_skip_forget_the_widget_in_every_language(qs):
    s = fresh(); wizard.start(s)
    s[wizard.widget_key("stage", "en")] = "applying"
    s[wizard.widget_key("stage", "ar")] = "applying"
    wizard.skip(s, qs)
    assert wizard.widget_key("stage", "en") not in s and wizard.widget_key("stage", "ar") not in s
    s[wizard.widget_key("work_hours", "ar")] = "none"
    wizard.clear_answers(s, qs)
    assert wizard.widget_key("work_hours", "ar") not in s
