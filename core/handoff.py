"""A safety net for the hand-off: when a question clearly needs a person, make sure the student
gets the office, even if the model forgot to call escalate_to_human.

The evaluation showed the model sometimes answers a sensitive question (immigration, verification,
a parent's documents) without handing off, most often in Arabic. Asking it harder did not fix it,
so the code checks too. Two layers, both plain code (no LLM call, no tokens):

  1. the final structured answer has a `handoff_topic` field the model fills in;
  2. this file: a short keyword list for the topics where a missing hand-off is the worst mistake
     (immigration and law enforcement, a crisis, verification, a parent's information).

The question text is only matched here, in memory. It is never stored or logged.
"""
from __future__ import annotations

import re

# (topic, pattern), checked in this order: the most serious topic wins.
_RULES = [
    ("immigration", r"undocumented|\bdaca\b|immigra|\bvisa\b|deport|law enforcement|(?-i:\bICE\b)|"
                    r"غير موثق|بدون أوراق|دوكا|هجرة|مهاجر|تأشيرة|فيزا|ترحيل|الشرطة|إنفاذ القانون"),
    ("wellness", r"overwhelm|hopeless|depress|suicid|self[- ]harm|being abused|unsafe at home|"
                 r"homeless|nowhere to (live|sleep)|stable place to live|"
                 r"انتحار|إيذاء نفسي|أؤذي نفسي|مكتئب|يائس|مشرد|ما عندي مكان"),
    ("financial_aid", r"verification|selected for verification|"
                      r"التحقق|توثيق"),
]
_PARENT_AID = (
    r"\b(my )?(parents?|mom|dad|family)\b.*\b(fafsa|tax|taxes|income|information|ssn|social security)\b|"
    r"\b(fafsa|tax|taxes)\b.*\b(my )?(parents?|mom|dad)\b",
    r"(أهلي|والدي|والديّ|أبي|أمي|أسرتي|أهلي).*(fafsa|فافسا|ضرائب|ضمان اجتماعي|دخل)|"
    r"(fafsa|فافسا|ضرائب).*(أهلي|والدي|والديّ|أبي|أمي|أسرتي)",
)


def topic_for_question(question: str) -> str:
    """The hand-off topic a question clearly needs, or '' when none of the safety-net rules match."""
    q = question or ""
    for topic, pattern in _RULES:
        if re.search(pattern, q, flags=re.IGNORECASE):
            return topic
    if any(re.search(p, q, flags=re.IGNORECASE | re.DOTALL) for p in _PARENT_AID):
        return "financial_aid"
    return ""
