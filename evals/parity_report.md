# Language parity (answer mode, 2026-11-23)

**8 of 15 pairs have the same top source** (target: at least 12). NOT PASSED. 1 pair(s) had an error and count as not passing.

| Pair | Question (EN) | Top source EN | Top source AR | Result |
|---|---|---|---|---|
| p01 | What is the Illinois MAP grant and is there a deadline I should know about? | state-isac-map | state-isac-map | same |
| p02 | I cannot file the FAFSA. Is there any state aid I can apply for? | state-isac-alternative-application | state-isac-alternative-application-faqs | DIFFERENT |
| p03 | How do I apply to City Colleges of Chicago and what documents do I need? | institution-ccc-registration | - | ERROR (retry) |
| p04 | What is the Star Scholarship and who qualifies? | institution-ccc-star-scholarship | institution-ccc-star-scholarship | same |
| p05 | My aid status says verification. What does that mean and what do I do? | federal-fafsa-submission-summary | institution-ccc-apply-financial-aid | DIFFERENT |
| p06 | Where can I get help with food or emergency costs on campus? | programs:ccc-food-pantries | programs:ccc-food-pantries | same |
| p07 | My parents do not have Social Security numbers. Can I still fill out the FAFSA? | state-isac-non-eligible-noncitizens | federal-fafsa-parent-steps | DIFFERENT |
| p08 | How much does tuition cost per credit hour if I live in Chicago? | institution-ccc-tuition | - | DIFFERENT |
| p09 | How do I transfer from City Colleges to a four-year university? | institution-ccc-student-resources | institution-ccc-student-resources | same |
| p10 | What is a Federal Pell Grant and who can get one? | federal-pell-grants | federal-pell-grants | same |
| p11 | I work 35 hours a week. Can I be a full-time student and keep my aid? | - | institution-ccc-apply-financial-aid | DIFFERENT |
| p12 | When does the spring semester start and when is the last day to drop a class? | deadlines:ccc-spring27-first-day-16wk | deadlines:ccc-spring27-first-day-16wk | same |
| p13 | What are the three FAFSA deadlines I need to know? | deadlines:fed-fafsa-federal-deadline-2026-27 | deadlines:fed-fafsa-federal-deadline-2026-27 | same |
| p14 | What is Federal Work-Study and does it count against my future aid? | federal-financial-aid-glossary | federal-work-study | DIFFERENT |
| p15 | When does the 2027-28 Alternative Application open? | deadlines:state-alt-app-2027-28-opens | deadlines:state-alt-app-2027-28-opens | same |

## Pairs that differ

- **p02** I cannot file the FAFSA. Is there any state aid I can apply for?
  - EN cited: state-isac-alternative-application, state-isac-alternative-application-faqs, state-isac-non-eligible-noncitizens
  - AR cited: state-isac-alternative-application-faqs, state-isac-alternative-application, state-isac-non-eligible-noncitizens
  - cited in both: state-isac-alternative-application, state-isac-alternative-application-faqs, state-isac-non-eligible-noncitizens
- **p05** My aid status says verification. What does that mean and what do I do?
  - EN cited: federal-fafsa-submission-summary, institution-ccc-apply-financial-aid, institution-ccc-registration
  - AR cited: institution-ccc-apply-financial-aid, institution-ccc-registration, programs:ccc-financial-aid-offices
  - cited in both: institution-ccc-apply-financial-aid, institution-ccc-registration
- **p07** My parents do not have Social Security numbers. Can I still fill out the FAFSA?
  - EN cited: state-isac-non-eligible-noncitizens, federal-fafsa-checklist, federal-fafsa-parent-steps, institution-ccc-apply-financial-aid
  - AR cited: federal-fafsa-parent-steps, federal-fafsa-checklist, federal-fafsa-student-steps, federal-dependency-status
  - cited in both: federal-fafsa-checklist, federal-fafsa-parent-steps
- **p08** How much does tuition cost per credit hour if I live in Chicago?
  - EN cited: institution-ccc-tuition
  - AR cited: -
  - cited in both: nothing
- **p11** I work 35 hours a week. Can I be a full-time student and keep my aid?
  - EN cited: -
  - AR cited: institution-ccc-apply-financial-aid, federal-work-study, federal-fafsa-student-steps
  - cited in both: nothing
- **p14** What is Federal Work-Study and does it count against my future aid?
  - EN cited: federal-financial-aid-glossary, federal-work-study
  - AR cited: federal-work-study
  - cited in both: federal-work-study
