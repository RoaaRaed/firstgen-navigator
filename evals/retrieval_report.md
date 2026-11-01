# Retrieval report (Gate 1)

Generated: 2026-11-02 | Embedding model: `intfloat/multilingual-e5-small` | Top-5 chunks, no threshold, no filters | chunks 200-1800 chars

**Gate 1 PASS**: English 23/25 = 92% (need 80%), Arabic 8/10 = 80% (need 70%).

A question counts as a hit when at least one of the top-5 chunks comes from a document listed in `expected_source_ids` of `golden_questions.csv`. Only knowledge-base documents are scored. Table rows (`deadlines:`, `programs:`) are answered by tools, not retrieval.

## Per question

| id | lang | behavior | rank | top score | expected | top 3 documents |
|---|---|---|---|---|---|---|
| g001 | en | grounded | 1 | 0.892 | state-isac-map, state-isac-priority-access-map | state-isac-map |
| g002 | en | grounded | miss | 0.883 | state-isac-alternative-application, state-isac-alternative-application-faqs, state-isac-student-family-faqs-2026-27 | federal-fafsa-student-steps, institution-ccc-apply-financial-aid, federal-fafsa-checklist |
| g003 | en | partial | 1 | 0.893 | institution-ccc-admissions, institution-ccc-registration | institution-ccc-admissions, institution-ccc-registration, institution-ccc-undocumented-student-services |
| g004 | en | grounded | 1 | 0.864 | institution-ccc-star-scholarship | institution-ccc-star-scholarship |
| g005 | en | grounded | 1 | 0.873 | federal-fafsa-submission-summary | federal-fafsa-submission-summary, federal-financial-aid-glossary, state-isac-non-eligible-noncitizens |
| g006 | en | partial | 1 | 0.869 | federal-financial-aid-glossary, federal-pell-grants, federal-work-study | federal-work-study, federal-financial-aid-glossary, federal-fafsa-student-steps |
| g007 | en | grounded | 1 | 0.866 | institution-ccc-food-access-snap, institution-ccc-student-resources | institution-ccc-food-access-snap, institution-ccc-student-resources, institution-ccc-undocumented-student-services |
| g008 | en | grounded | - | 0.888 | (none) | institution-ccc-academic-calendar |
| g009 | en | grounded | 2 | 0.895 | federal-fafsa-checklist, federal-fafsa-parent-steps, institution-ccc-apply-financial-aid | federal-dependency-status, federal-fafsa-parent-steps, federal-fafsa-checklist |
| g010 | en | grounded | 1 | 0.911 | institution-ccc-tuition | institution-ccc-tuition |
| g011 | en | grounded | 1 | 0.915 | federal-financial-aid-glossary, federal-pell-grants | federal-pell-grants, federal-financial-aid-glossary |
| g012 | en | grounded | 1 | 0.920 | federal-fafsa-deadlines | federal-fafsa-deadlines |
| g013 | en | grounded | 1 | 0.895 | federal-dependency-status, federal-financial-aid-glossary | federal-dependency-status, federal-financial-aid-glossary |
| g014 | en | grounded | 1 | 0.902 | federal-work-study | federal-work-study, federal-financial-aid-glossary |
| g015 | en | grounded | 2 | 0.915 | institution-ccc-transfer-services | institution-ccc-student-resources, institution-ccc-transfer-services |
| g016 | en | grounded | 1 | 0.872 | institution-ccc-registration | institution-ccc-registration, institution-ccc-undocumented-student-services |
| g017 | en | grounded | 1 | 0.892 | institution-ccc-undocumented-student-services | institution-ccc-undocumented-student-services |
| g018 | en | grounded | miss (rank 8) | 0.884 | state-isac-alternative-application, state-isac-student-family-faqs-2026-27 | state-isac-non-eligible-noncitizens, state-isac-priority-access-map, state-isac-alternative-application-faqs |
| g019 | en | partial | 1 | 0.893 | state-isac-alternative-application, state-isac-non-eligible-noncitizens, state-isac-student-family-faqs-2026-27 | state-isac-alternative-application, state-isac-alternative-application-faqs, state-isac-priority-access-map |
| g020 | en | grounded | 1 | 0.877 | state-isac-alternative-application, state-isac-student-family-faqs-2026-27 | state-isac-alternative-application, state-isac-map, state-isac-student-family-faqs-2026-27 |
| g021 | en | grounded | 1 | 0.904 | federal-dependency-status | federal-dependency-status, federal-fafsa-checklist, federal-fafsa-student-steps |
| g022 | en | grounded | 1 | 0.906 | federal-dependency-status | federal-dependency-status |
| g023 | en | grounded | 1 | 0.834 | institution-ccc-undocumented-student-services | institution-ccc-undocumented-student-services, state-isac-non-eligible-noncitizens |
| g024 | en | refuse | - | 0.853 | institution-ccc-undocumented-student-services, state-isac-non-eligible-noncitizens | state-isac-non-eligible-noncitizens, institution-ccc-undocumented-student-services, federal-dependency-status |
| g025 | en | refuse | - | 0.842 | (none) | institution-ccc-transfer-services, institution-ccc-admissions |
| g026 | en | partial | 1 | 0.824 | institution-ccc-tuition | institution-ccc-tuition, institution-ccc-registration, institution-ccc-transfer-services |
| g027 | en | not_found | - | 0.788 | (none) | institution-ccc-academic-calendar, institution-ccc-apply-financial-aid |
| g028 | en | partial | 1 | 0.870 | institution-ccc-academic-calendar | institution-ccc-academic-calendar, institution-ccc-tuition |
| g029 | en | partial | 1 | 0.872 | institution-ccc-food-access-snap | institution-ccc-food-access-snap, state-isac-non-eligible-noncitizens |
| g030 | en | refuse | - | 0.878 | federal-financial-aid-glossary, federal-work-study | federal-work-study |
| g031 | ar | grounded | 1 | 0.850 | state-isac-map, state-isac-priority-access-map | state-isac-map |
| g032 | ar | grounded | miss (rank 10) | 0.844 | state-isac-alternative-application, state-isac-alternative-application-faqs, state-isac-student-family-faqs-2026-27 | state-isac-non-eligible-noncitizens, institution-ccc-apply-financial-aid, federal-dependency-status |
| g033 | ar | partial | miss (rank 7) | 0.824 | institution-ccc-admissions, institution-ccc-registration | institution-ccc-undocumented-student-services, institution-ccc-transfer-services, institution-ccc-student-resources |
| g034 | ar | grounded | 1 | 0.843 | institution-ccc-star-scholarship | institution-ccc-star-scholarship |
| g035 | ar | grounded | 1 | 0.839 | federal-fafsa-submission-summary | federal-fafsa-submission-summary, federal-fafsa-parent-steps, institution-ccc-registration |
| g036 | ar | grounded | 1 | 0.807 | institution-ccc-food-access-snap, institution-ccc-student-resources | institution-ccc-food-access-snap, institution-ccc-student-resources, institution-ccc-undocumented-student-services |
| g037 | ar | grounded | 2 | 0.837 | federal-fafsa-checklist, federal-fafsa-parent-steps, institution-ccc-apply-financial-aid | federal-dependency-status, federal-fafsa-parent-steps, state-isac-non-eligible-noncitizens |
| g038 | ar | grounded | 1 | 0.793 | institution-ccc-tuition | institution-ccc-tuition, institution-ccc-undocumented-student-services |
| g039 | ar | grounded | 2 | 0.799 | institution-ccc-transfer-services | institution-ccc-student-resources, institution-ccc-transfer-services |
| g040 | ar | grounded | 1 | 0.855 | federal-financial-aid-glossary, federal-pell-grants | federal-pell-grants, federal-financial-aid-glossary |

## Misses

- **g002** (en): I cannot file the FAFSA. Is there any state aid I can apply for?
  - expected: state-isac-alternative-application, state-isac-alternative-application-faqs, state-isac-student-family-faqs-2026-27
  - got: federal-fafsa-student-steps, institution-ccc-apply-financial-aid, federal-fafsa-checklist
- **g018** (en): I heard undocumented students lost state financial aid. Is that true and what should I do?
  - expected: state-isac-alternative-application, state-isac-student-family-faqs-2026-27
  - got: state-isac-non-eligible-noncitizens, state-isac-priority-access-map, state-isac-alternative-application-faqs, state-isac-map, institution-ccc-undocumented-student-services
- **g032** (ar): لا أستطيع تعبئة طلب FAFSA. هل هناك مساعدات من الولاية يمكنني التقديم عليها؟
  - expected: state-isac-alternative-application, state-isac-alternative-application-faqs, state-isac-student-family-faqs-2026-27
  - got: state-isac-non-eligible-noncitizens, institution-ccc-apply-financial-aid, federal-dependency-status, federal-fafsa-checklist
- **g033** (ar): كيف أقدّم طلب التحاق بكليات مدينة شيكاغو وما المستندات المطلوبة؟
  - expected: institution-ccc-admissions, institution-ccc-registration
  - got: institution-ccc-undocumented-student-services, institution-ccc-transfer-services, institution-ccc-student-resources

## Threshold study

Each cell: questions that still have the right document in the top 5 after dropping chunks below the threshold. 'Left empty' = refuse / not_found questions that return nothing (that is what we want for them).

| threshold | English kept | Arabic kept | refuse / not_found left empty |
|---|---|---|---|
| 0.00 | 23/25 = 92% | 8/10 = 80% | 0/4 = 0% |
| 0.80 | 23/25 = 92% | 6/10 = 60% | 1/4 = 25% |
| 0.82 | 23/25 = 92% | 5/10 = 50% | 1/4 = 25% |
| 0.84 | 21/25 = 84% | 3/10 = 30% | 1/4 = 25% |
| 0.85 | 21/25 = 84% | 1/10 = 10% | 2/4 = 50% |
| 0.86 | 21/25 = 84% | 0/10 = 0% | 3/4 = 75% |
| 0.87 | 18/25 = 72% | 0/10 = 0% | 3/4 = 75% |
| 0.88 | 13/25 = 52% | 0/10 = 0% | 4/4 = 100% |
| 0.90 | 7/25 = 28% | 0/10 = 0% | 4/4 = 100% |

## Notes

- Not scored (answered from tables only): g008.
- Arabic has few questions (10), so one question moves the rate by 10 points.
