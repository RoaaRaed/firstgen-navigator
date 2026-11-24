# Language parity (answer mode, 2026-11-24)

**11 of 15 pairs have the same top source** (target: at least 12). NOT PASSED.

Notes on how this result was produced (re-running only some runs favours the result, so read the number with that in mind):
- Pair(s) p03, p08, p11 were run again after the first full run (after the tool-limit change).
- All AR runs were repeated after the search prompt changed (the search query is now always written in English). The other language's runs are from the earlier run. The change was made after seeing the 2026-11-24 results.
- Pair(s) p06 were run again after the first full run.

| Pair | Question (EN) | Top source EN | Top source AR | Result |
|---|---|---|---|---|
| p01 | What is the Illinois MAP grant and is there a deadline I should know about? | state-isac-map | state-isac-map | same |
| p02 | I cannot file the FAFSA. Is there any state aid I can apply for? | state-isac-alternative-application | state-isac-alternative-application-faqs | DIFFERENT |
| p03 | How do I apply to City Colleges of Chicago and what documents do I need? | institution-ccc-admissions | institution-ccc-transfer-services | DIFFERENT |
| p04 | What is the Star Scholarship and who qualifies? | institution-ccc-star-scholarship | institution-ccc-star-scholarship | same |
| p05 | My aid status says verification. What does that mean and what do I do? | federal-fafsa-submission-summary | institution-ccc-star-scholarship | DIFFERENT |
| p06 | Where can I get help with food or emergency costs on campus? | programs:ccc-food-pantries | programs:ccc-food-pantries | same |
| p07 | My parents do not have Social Security numbers. Can I still fill out the FAFSA? | state-isac-non-eligible-noncitizens | state-isac-non-eligible-noncitizens | same |
| p08 | How much does tuition cost per credit hour if I live in Chicago? | institution-ccc-tuition | institution-ccc-tuition | same |
| p09 | How do I transfer from City Colleges to a four-year university? | institution-ccc-student-resources | institution-ccc-student-resources | same |
| p10 | What is a Federal Pell Grant and who can get one? | federal-pell-grants | federal-pell-grants | same |
| p11 | I work 35 hours a week. Can I be a full-time student and keep my aid? | federal-financial-aid-glossary | federal-work-study | DIFFERENT |
| p12 | When does the spring semester start and when is the last day to drop a class? | deadlines:ccc-spring27-first-day-16wk | deadlines:ccc-spring27-first-day-16wk | same |
| p13 | What are the three FAFSA deadlines I need to know? | deadlines:fed-fafsa-federal-deadline-2026-27 | deadlines:fed-fafsa-federal-deadline-2026-27 | same |
| p14 | What is Federal Work-Study and does it count against my future aid? | federal-financial-aid-glossary | federal-financial-aid-glossary | same |
| p15 | When does the 2027-28 Alternative Application open? | deadlines:state-alt-app-2027-28-opens | deadlines:state-alt-app-2027-28-opens | same |

## Pairs that differ

- **p02** I cannot file the FAFSA. Is there any state aid I can apply for?
  - EN cited: state-isac-alternative-application, state-isac-alternative-application-faqs, state-isac-non-eligible-noncitizens
  - AR cited: state-isac-alternative-application-faqs, state-isac-alternative-application, state-isac-map, state-isac-non-eligible-noncitizens
  - cited in both: state-isac-alternative-application, state-isac-alternative-application-faqs, state-isac-non-eligible-noncitizens
- **p03** How do I apply to City Colleges of Chicago and what documents do I need?
  - EN cited: institution-ccc-admissions, institution-ccc-registration
  - AR cited: institution-ccc-transfer-services, institution-ccc-admissions, institution-ccc-registration
  - cited in both: institution-ccc-admissions, institution-ccc-registration
- **p05** My aid status says verification. What does that mean and what do I do?
  - EN cited: federal-fafsa-submission-summary, institution-ccc-apply-financial-aid, institution-ccc-registration
  - AR cited: institution-ccc-star-scholarship, programs:ccc-financial-aid-offices
  - cited in both: nothing
- **p11** I work 35 hours a week. Can I be a full-time student and keep my aid?
  - EN cited: federal-financial-aid-glossary, federal-work-study, institution-ccc-tuition
  - AR cited: federal-work-study, federal-financial-aid-glossary
  - cited in both: federal-financial-aid-glossary, federal-work-study
