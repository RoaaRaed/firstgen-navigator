"""AdvisorAnswer is what the agent must produce every turn. These tests pin down the rules
the system prompt promises: a confident answer needs a citation, and citations must look like
real tool output, not an invented string."""
import pytest
from pydantic import ValidationError

from core.schema import AdvisorAnswer, Citation, Contact


def make(confidence="High", citations=None, **kw):
    kw.setdefault("answer", "The MAP grant priority date is February 1, 2027.")
    kw.setdefault("next_steps", [])
    citations = [Citation(source_id="deadlines:state-map-priority-2027-28", label="MAP priority date")] \
        if citations is None else citations
    return AdvisorAnswer(confidence=confidence, citations=citations, **kw)


def test_valid_answer_with_citation():
    a = make()
    assert a.confidence == "High" and a.citations[0].source_id.startswith("deadlines:")


def test_high_confidence_without_citation_is_rejected():
    with pytest.raises(ValidationError):
        make(confidence="High", citations=[])


def test_medium_confidence_without_citation_is_rejected():
    with pytest.raises(ValidationError):
        make(confidence="Medium", citations=[])


def test_low_confidence_without_citation_is_allowed_for_not_found():
    a = make(confidence="Low", citations=[], answer="I could not find this in the documents.")
    assert a.citations == []


def test_more_than_three_next_steps_is_rejected():
    with pytest.raises(ValidationError):
        make(next_steps=["a", "b", "c", "d"])


def test_three_next_steps_is_fine():
    a = make(next_steps=["a", "b", "c"])
    assert len(a.next_steps) == 3


@pytest.mark.parametrize("sid", ["state-isac-map::03", "deadlines:ccc-spring27-first-day-16wk",
                                 "programs:ccc-food-pantries"])
def test_real_source_id_shapes_are_accepted(sid):
    a = make(citations=[Citation(source_id=sid, label="x")])
    assert a.citations[0].source_id == sid


def test_invented_source_id_is_rejected():
    with pytest.raises(ValidationError):
        make(citations=[Citation(source_id="this page looks right", label="x")])


def test_human_contact_is_optional_and_typed():
    a = make(human_contact=Contact(office="Financial Aid Office", url="https://ccc.edu/financialaid"))
    assert a.human_contact.office == "Financial Aid Office"
    assert make().human_contact is None


def test_confidence_only_allows_the_three_labels():
    with pytest.raises(ValidationError):
        make(confidence="VeryHigh")
