# Language parity (retrieval mode, 2026-11-17)

**12 of 15 pairs have the same top source** (target: at least 12). PASSED.

| Pair | Question (EN) | Top source EN | Top source AR | Result |
|---|---|---|---|---|
| p01 | What is the Illinois MAP grant and is there a deadline I should know about? | state-isac-map | state-isac-map | same |
| p02 | I cannot file the FAFSA. Is there any state aid I can apply for? | federal-fafsa-student-steps | state-isac-non-eligible-noncitizens | DIFFERENT |
| p03 | How do I apply to City Colleges of Chicago and what documents do I need? | institution-ccc-admissions | institution-ccc-undocumented-student-services | DIFFERENT |
| p04 | What is the Star Scholarship and who qualifies? | institution-ccc-star-scholarship | institution-ccc-star-scholarship | same |
| p05 | My aid status says verification. What does that mean and what do I do? | federal-fafsa-submission-summary | federal-fafsa-submission-summary | same |
| p06 | Where can I get help with food or emergency costs on campus? | institution-ccc-food-access-snap | institution-ccc-food-access-snap | same |
| p07 | My parents do not have Social Security numbers. Can I still fill out the FAFSA? | federal-dependency-status | federal-dependency-status | same |
| p08 | How much does tuition cost per credit hour if I live in Chicago? | institution-ccc-tuition | institution-ccc-tuition | same |
| p09 | How do I transfer from City Colleges to a four-year university? | institution-ccc-student-resources | institution-ccc-student-resources | same |
| p10 | What is a Federal Pell Grant and who can get one? | federal-pell-grants | federal-pell-grants | same |
| p11 | I work 35 hours a week. Can I be a full-time student and keep my aid? | federal-work-study | federal-fafsa-student-steps | DIFFERENT |
| p12 | When does the spring semester start and when is the last day to drop a class? | institution-ccc-academic-calendar | institution-ccc-academic-calendar | same |
| p13 | What are the three FAFSA deadlines I need to know? | federal-fafsa-deadlines | federal-fafsa-deadlines | same |
| p14 | What is Federal Work-Study and does it count against my future aid? | federal-work-study | federal-work-study | same |
| p15 | When does the 2027-28 Alternative Application open? | state-isac-alternative-application | state-isac-alternative-application | same |

## Pairs that differ

- **p02** I cannot file the FAFSA. Is there any state aid I can apply for?
  - EN cited: federal-fafsa-student-steps
  - AR cited: state-isac-non-eligible-noncitizens
  - cited in both: nothing
- **p03** How do I apply to City Colleges of Chicago and what documents do I need?
  - EN cited: institution-ccc-admissions
  - AR cited: institution-ccc-undocumented-student-services
  - cited in both: nothing
- **p11** I work 35 hours a week. Can I be a full-time student and keep my aid?
  - EN cited: federal-work-study
  - AR cited: federal-fafsa-student-steps
  - cited in both: nothing
