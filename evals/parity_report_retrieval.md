# Language parity (retrieval mode, 2026-11-19)

**12 of 15 pairs have the same top source** (target: at least 12). PASSED.

Softer reading: in **13 of 15** pairs each language's best document also appears in the other language's top 5 (the pass rule above is unchanged).

| Pair | Question (EN) | Top source EN | Top source AR | Result | Top-5 shared |
|---|---|---|---|---|---|
| p01 | What is the Illinois MAP grant and is there a deadline I should know about? | state-isac-map | state-isac-map | same | 2/5 |
| p02 | I cannot file the FAFSA. Is there any state aid I can apply for? | federal-fafsa-student-steps | state-isac-non-eligible-noncitizens | DIFFERENT | 3/5 |
| p03 | How do I apply to City Colleges of Chicago and what documents do I need? | institution-ccc-admissions | institution-ccc-undocumented-student-services | DIFFERENT | 3/5 |
| p04 | What is the Star Scholarship and who qualifies? | institution-ccc-star-scholarship | institution-ccc-star-scholarship | same | 1/5 |
| p05 | My aid status says verification. What does that mean and what do I do? | federal-fafsa-submission-summary | federal-fafsa-submission-summary | same | 3/5 |
| p06 | Where can I get help with food or emergency costs on campus? | institution-ccc-food-access-snap | institution-ccc-food-access-snap | same | 3/5 |
| p07 | My parents do not have Social Security numbers. Can I still fill out the FAFSA? | federal-dependency-status | federal-dependency-status | same | 4/5 |
| p08 | How much does tuition cost per credit hour if I live in Chicago? | institution-ccc-tuition | institution-ccc-tuition | same | 2/5 |
| p09 | How do I transfer from City Colleges to a four-year university? | institution-ccc-student-resources | institution-ccc-student-resources | same | 2/5 |
| p10 | What is a Federal Pell Grant and who can get one? | federal-pell-grants | federal-pell-grants | same | 2/5 |
| p11 | I work 35 hours a week. Can I be a full-time student and keep my aid? | federal-work-study | federal-fafsa-student-steps | DIFFERENT | 3/5 |
| p12 | When does the spring semester start and when is the last day to drop a class? | institution-ccc-academic-calendar | institution-ccc-academic-calendar | same | 1/5 |
| p13 | What are the three FAFSA deadlines I need to know? | federal-fafsa-deadlines | federal-fafsa-deadlines | same | 1/5 |
| p14 | What is Federal Work-Study and does it count against my future aid? | federal-work-study | federal-work-study | same | 2/5 |
| p15 | When does the 2027-28 Alternative Application open? | state-isac-alternative-application | state-isac-alternative-application | same | 5/5 |

## Pairs that differ

- **p02** I cannot file the FAFSA. Is there any state aid I can apply for?
  - EN cited: federal-fafsa-student-steps
  - AR cited: state-isac-non-eligible-noncitizens
  - cited in both: nothing
  - EN top 5: federal-fafsa-student-steps (0.883), institution-ccc-apply-financial-aid (0.882), federal-fafsa-checklist (0.875), institution-ccc-star-scholarship (0.873)
  - AR top 5: state-isac-non-eligible-noncitizens (0.844), institution-ccc-apply-financial-aid (0.843), federal-dependency-status (0.842), federal-fafsa-checklist (0.842), federal-fafsa-student-steps (0.84)
- **p03** How do I apply to City Colleges of Chicago and what documents do I need?
  - EN cited: institution-ccc-admissions
  - AR cited: institution-ccc-undocumented-student-services
  - cited in both: nothing
  - EN top 5: institution-ccc-admissions (0.893), institution-ccc-registration (0.889), institution-ccc-undocumented-student-services (0.886), institution-ccc-student-resources (0.883)
  - AR top 5: institution-ccc-undocumented-student-services (0.824), institution-ccc-transfer-services (0.819), institution-ccc-student-resources (0.817), institution-ccc-registration (0.81)
- **p11** I work 35 hours a week. Can I be a full-time student and keep my aid?
  - EN cited: federal-work-study
  - AR cited: federal-fafsa-student-steps
  - cited in both: nothing
  - EN top 5: federal-work-study (0.869), federal-financial-aid-glossary (0.861), federal-fafsa-student-steps (0.859)
  - AR top 5: federal-fafsa-student-steps (0.821), federal-fafsa-parent-steps (0.818), federal-financial-aid-glossary (0.817), federal-work-study (0.817), institution-ccc-apply-financial-aid (0.816)
