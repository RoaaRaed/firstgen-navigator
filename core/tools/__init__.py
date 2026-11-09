"""The four advisor tools. Each returns plain data with a "source_id" on every item, so the
answer's citations come from tool output, never from the model's memory.

    search_knowledge_base(query, language, layer)  -> passages from the official documents
    lookup_deadlines(term, topic)                  -> exact dates from deadlines.csv
    match_programs(tags, categories, keywords)     -> support programs from programs.csv
    escalate_to_human(topic)                       -> the named office to contact

Try them:  python -m core.tools deadlines --term "Spring 2027" --topic drop
"""
from core.tools.context import ToolContext, load_context
from core.tools.deadlines import lookup_deadlines
from core.tools.escalate import escalate_to_human
from core.tools.programs import match_programs
from core.tools.search import search_knowledge_base

__all__ = ["ToolContext", "load_context", "search_knowledge_base", "lookup_deadlines",
           "match_programs", "escalate_to_human"]
