# Cost model

What it costs to run FirstGen Navigator AI, per conversation and per month. **Status: preliminary.**
The token counts come from 23 real evaluation questions (2026-11-25). The numbers get replaced
by the full 62-question run (see "How to update this").

## What costs money, and what does not

| Part | Cost |
|---|---|
| LLM calls (Groq, `openai/gpt-oss-120b`) | **The only variable cost.** Priced per token. |
| Embeddings (`multilingual-e5-small`) | $0. Runs on the server's own CPU. |
| Vector index (Chroma) | $0. A local folder. |
| Hosting (Streamlit Community Cloud) | $0 on the free plan. |
| LLM-as-judge (evaluation only) | Small. Not part of student conversations. |

## Price used

Groq pay-as-you-go (Developer tier) for `openai/gpt-oss-120b`:
**$0.15 per 1M input tokens, $0.60 per 1M output tokens.**
Source: a third-party price page (morphllm.com/groq-pricing), checked 2026-11-24.
**Check the current price on Groq's own pricing page before quoting it to a customer.**

## Measured tokens per question

One student question = one tool-calling loop (1 to 6 model calls) plus one final call that writes
the structured answer.

| | Input tokens | Output tokens |
|---|---|---|
| Tool-calling loop, average of 23 questions (measured) | 6,736 | 946 |
| Tool-calling loop, simple question (median, input only) | 4,305 | - |
| Tool-calling loop, hardest question seen | 17,395 | 2,048 |
| Final structured-answer call (**estimated**, see below) | 3,433 | 406 |
| **Total per question (average)** | **about 10,200** | **about 1,350** |

The final call is not printed in our token log, so it is estimated: its input is about the last
loop call's input plus that call's output plus the instruction text; its output is about 70% of
the last draft. This is the weakest number in this file.

**Cost per question: about $0.0023.** A hard question costs about 1.5 times more; a simple one
(a deadline lookup) about half.

## Monthly estimate

A "conversation" is assumed to be **3 student questions** (a guess to be replaced with real usage;
follow-up questions re-send the chat history, so long conversations cost more per question).

Per conversation: about 35,000 tokens, **about $0.007**.

| Usage level | Conversations / month | Tokens / month | Cost / month | Cost / year |
|---|---|---|---|---|
| Pilot (one office) | 500 | about 17 million | **about $3.50** | about $42 |
| One college | 2,000 | about 69 million | **about $14** | about $168 |
| Several colleges | 10,000 | about 346 million | **about $70** | about $840 |

Round these up by 25% for a safety margin when quoting a price.

## The free tier

Groq's free tier allows 200,000 tokens per day for this model (a rolling 24 hours), which is about
**17 questions a day (about 500 a month)**. It is enough for development and a very small demo.
It is not enough for a real pilot, and it is why the full evaluation takes several days.

## Ways to lower the cost

- A smaller model for easy questions (for example deadline lookups). Not tested.
- Fewer or shorter passages per search. Already reduced once (`LEAN_SEARCH_K`, tool limit of 4).
- Prompt caching of the system prompt. Groq lists a discount for cached input tokens; we have not
  measured it, so it is not counted above.
- A daily question limit in the app and a monthly spending cap at Groq (the cap is monthly only).

## How to update this

1. Finish the full evaluation (`python -m evals.run_eval`).
2. On the Groq console usage page, note the total tokens used and divide by the number of
   questions run. That replaces the estimated final-call number with a measured one.
3. Recompute the table with the new average and today's price.
