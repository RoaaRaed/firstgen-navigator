"""The hand-off safety net: the model's handoff_topic and the keyword list in core/handoff.py."""
import pytest

from tests.fake_langchain import install

install()
import core.agent as agent  # noqa: E402

from core.handoff import topic_for_question  # noqa: E402
from core.schema import AdvisorAnswer, Citation  # noqa: E402
from tests.fake_langchain import FakeMsg  # noqa: E402
from tests.test_agent import ctx  # noqa: E402


@pytest.mark.parametrize("question,topic", [
    ("Does being undocumented affect whether I can enroll?", "immigration"),
    ("I am a DACA student. Can I apply for MAP?", "immigration"),
    ("What happens if ICE comes to campus?", "immigration"),
    ("What happens if law enforcement officers come to campus?", "immigration"),
    ("أنا طالب غير موثق، هل أقدر أسجل؟", "immigration"),
    ("I feel overwhelmed and want to drop out", "wellness"),
    ("I do not have a stable place to live", "wellness"),
    ("My aid status says verification. What now?", "financial_aid"),
    ("تقول حالة مساعدتي إنها تحت «التحقق»", "financial_aid"),
    ("My parents refuse to give me their tax information for the FAFSA", "financial_aid"),
    ("My parents do not have Social Security numbers. Can I fill out the FAFSA?", "financial_aid"),
    ("أهلي ليس لديهم أرقام ضمان اجتماعي. هل أقدر أعبي FAFSA؟", "financial_aid"),
])
def test_clear_cases_get_a_topic(question, topic):
    assert topic_for_question(question) == topic


@pytest.mark.parametrize("question", [
    "What is the maximum Federal Pell Grant for 2026-27?",
    "When is the MAP grant deadline?",
    "Can I get an ice cream scholarship?",     # 'ice' inside another word is not ICE
    "ما هو موعد التسجيل؟",
    "",
])
def test_ordinary_questions_get_no_topic(question):
    assert topic_for_question(question) == ""


def _answer(**kw):
    base = dict(answer="ok", citations=[], confidence="Low", next_steps=[])
    base.update(kw)
    return AdvisorAnswer(**base)


def _run(question, answer, trace=None):
    record = install(agent_trace=trace or [FakeMsg("ai", "draft")], structured_answer=answer)
    a = agent.build_agent(ctx(), llm=record["llm"])
    return agent.run_agent(a, question)


def test_the_topic_the_model_names_gets_its_office():
    r = _run("I cannot file the FAFSA. Is there state aid?", _answer(handoff_topic="state_aid"))
    assert r.answer.human_contact is not None and r.answer.human_contact.office
    call = [c for c in r.tool_calls if c["name"] == "escalate_to_human"][0]
    assert call["args"]["added_by"] == "code"
    assert call["result"]["contacts"][0]["source_id"].startswith("programs:")


def test_the_keyword_net_works_when_the_model_names_nothing():
    r = _run("Does being undocumented affect enrollment?", _answer())
    assert r.answer.human_contact is not None
    assert r.tool_calls[-1]["result"]["topic"] == "immigration"


def test_an_ordinary_question_gets_no_contact():
    r = _run("What is the maximum Pell Grant?", _answer())
    assert r.answer.human_contact is None and r.tool_calls == []


def test_a_contact_the_model_already_has_is_not_replaced():
    mine = _answer(human_contact={"office": "My own office"}, handoff_topic="immigration")
    r = _run("undocumented question", mine)
    assert r.answer.human_contact.office == "My own office"
    assert r.tool_calls == []


def test_an_unknown_topic_name_still_gives_the_default_office():
    r = _run("q", _answer(handoff_topic="something odd"))
    assert r.answer.human_contact is not None


def test_the_office_from_the_tool_call_is_used_before_the_code_adds_one():
    out = {"topic": "financial_aid", "contacts": [{"source_id": "programs:ccc-financial-aid-offices",
           "contact_office": "Financial Aid Office", "contact_url": "", "contact_phone": ""}]}
    trace = [FakeMsg("ai", "", tool_calls=[{"id": "1", "name": "escalate_to_human", "args": {"topic": "aid"}}]),
             FakeMsg("tool", "t", tool_call_id="1", name="escalate_to_human", artifact=out),
             FakeMsg("ai", "draft")]
    r = _run("verification?", _answer(handoff_topic="immigration"), trace)
    assert r.answer.human_contact.office == "Financial Aid Office"
    assert len(r.tool_calls) == 1


def test_a_failed_run_still_names_the_office_for_a_sensitive_question():
    record = install(agent_trace=[FakeMsg("ai", "x")], structured_error=ValueError("bad"))
    a = agent.build_agent(ctx(), llm=record["llm"])
    r = agent.run_agent(a, "I am undocumented, can I enroll?")
    assert r.answer.confidence == "Low" and r.answer.human_contact is not None


def test_the_schema_accepts_and_defaults_handoff_topic():
    assert AdvisorAnswer(answer="a", confidence="Low").handoff_topic == ""
    assert AdvisorAnswer(answer="a", confidence="Low", handoff_topic="wellness").handoff_topic == "wellness"
    AdvisorAnswer(answer="a", confidence="High", citations=[Citation(source_id="x::01", label="x")])
