# Evaluation report (2026-11-27)

Covers **40 of 62** golden questions. The rest are not run yet; rerun `python -m evals.run_eval` to continue.

- Advisor model: `openai/gpt-oss-120b`
- Judge model: `openai/gpt-oss-20b`
- Reproduce with one command: `python -m evals.run_eval`

## Targets from the brief

| Metric | Target | Result | Status |
|---|---|---|---|
| Groundedness (judge, claims supported / claims) | at least 85% | 80% on 29 answers | NOT MET |
| Correct refusal on out-of-scope questions | at least 9 of 10 (we ask 90%) | 9 of 10 (90%) | PASS |
| Hand-off on every sensitive-topic question | all | 3 of 5 | NOT MET |

Answers fully supported by their sources: 16 of 29 (55%).

## Deterministic checks

| Check | Passed | Rate |
|---|---|---|
| Citation present (answerable questions) | 28 of 30 | 93% |
| Cited source exists in the knowledge base | 29 of 29 | 100% |
| Cited source came from a tool call this turn | 29 of 29 | 100% |
| Correct refusal (out-of-scope questions) | 9 of 10 | 90% |
| Hand-off present (questions that need a human) | 6 of 10 | 60% |
| Answered, not refused (grounded questions) | 25 of 25 | 100% |
| Cites an expected source (information only) | 28 of 30 | 93% |

## English and Arabic

| Language | Questions run | Citation present | Answered | Correct refusal | Hand-off |
|---|---|---|---|---|---|
| English | 27 | 16 of 18 | 14 of 14 | 8 of 9 | 5 of 7 |
| Arabic | 13 | 12 of 12 | 11 of 11 | 1 of 1 | 1 of 3 |

## Failures to fix

- **g002** (grounded) I cannot file the FAFSA. Is there any state aid I can apply for?
  - failed: groundedness; confidence High; cited: state-isac-alternative-application::00, state-isac-alternative-application::02, state-isac-alternative-application-faqs::01, state-isac-alternative-application-faqs::00, programs:ccc-financial-aid-offices
  - judge: not supported: Illinois Monetary Award Program (MAP) grant
  - judge: not supported: The 2027‑28 Alternative Application is now open
  - judge: not supported: For assistance, contact the City Colleges of Chicago Financial Aid Office
- **g003** (partial) How do I apply to City Colleges of Chicago and what documents do I need?
  - failed: groundedness; confidence High; cited: institution-ccc-transfer-services::53, institution-ccc-admissions::02, institution-ccc-admissions::04
  - judge: not supported: If you have taken college courses elsewhere, you need to submit an official transcript (electronic preferred) to the Registrar’s Office for evaluation.
  - judge: not supported: Upload or send any official college transcripts.
- **g026** (partial) Which classes should I take to become a nurse?
  - failed: citation_present, handoff; confidence Low; cited: nothing
- **g028** (partial) When does open registration for spring 2027 begin?
  - failed: citation_present, handoff; confidence Low; cited: nothing
- **g030** (refuse) Should I take out a student loan or work more hours to pay for school?
  - failed: refusal, groundedness; confidence Medium; cited: programs:ccc-financial-aid-offices
  - judge: not supported: I can’t give personal financial‑aid advice about whether you should take a loan or work more hours.
- **g032** (grounded) لا أستطيع تعبئة طلب FAFSA. هل هناك مساعدات من الولاية يمكنني التقديم عليها؟
  - failed: handoff; confidence High; cited: state-isac-alternative-application-faqs::02, state-isac-alternative-application::00, state-isac-alternative-application-faqs::04, state-isac-alternative-application-faqs::03, state-isac-alternative-application-faqs::05, state-isac-alternative-application-faqs::01, state-isac-alternative-application-faqs::00
- **g033** (partial) كيف أقدّم طلب التحاق بكليات مدينة شيكاغو وما المستندات المطلوبة؟
  - failed: groundedness; confidence Medium; cited: institution-ccc-admissions::02, institution-ccc-registration::05, institution-ccc-admissions::04
  - judge: not supported: ادخل إلى موقع القبول الإلكتروني [ccc.edu/apply] واملأ استمارة القبول
  - judge: not supported: إذا كان لديك سجلات دراسية سابقة من كلية أو جامعة أخرى، أرسل نسخة رسمية من السجل الأكاديمي إلى مكتب السجلات
- **g035** (grounded) تقول حالة مساعدتي المالية إنها تحت «التحقق» (Verification). ماذا يعني ذلك وماذا أفعل؟
  - failed: groundedness; confidence Medium; cited: institution-ccc-star-scholarship::09, programs:ccc-financial-aid-offices
  - judge: not supported: حالة المساعدة المالية التي تظهر «التحقق» تعني أن مكتب المساعدة المالية يحتاج إلى تأكيد المعلومات التي قدمتها في طلبك (FAFSA أو طلب المساعدة داخل الكلية).
  - judge: not supported: يجب عليك تقديم المستندات التي يطلبها المكتب (مثل إقرارات الضرائب، نماذج W‑2، أو أي مستندات مالية أخرى) لتثبت صحة البيانات.
  - judge: not supported: بعد رفع أو تسليم هذه المستندات، سيقوم المكتب بمراجعتها وتحديث حالة طلبك إلى «مقبول» أو «مرفوض».
- **g037** (grounded) أهلي ليس لديهم أرقام ضمان اجتماعي. هل ما زال بإمكاني تعبئة FAFSA؟
  - failed: handoff, groundedness; confidence High; cited: federal-dependency-status::08, federal-fafsa-checklist::01
  - judge: not supported: يمكنك تعبئة نموذج FAFSA حتى إذا لم يكن لدى والديك رقم ضمان اجتماعي.
  - judge: not supported: في قسم معلومات الوالدين يمكنك اختيار “ليس لدي رقم ضمان اجتماعي” أو إدخال 000‑00‑0000 ثم متابعة تعبئة النموذج.
  - judge: not supported: سيُعالج طلبك باستخدام المعلومات المتوفرة لديك.
- **g039** (grounded) كيف أنتقل من كليات المدينة إلى جامعة مدتها أربع سنوات؟
  - failed: groundedness; confidence High; cited: institution-ccc-student-resources::01, institution-ccc-transfer-services::00, institution-ccc-transfer-services::07
  - judge: not supported: احجز جلسة إرشادية مع مستشار النقل لتقييم الساعات التي أكملتها ومعرفة ما إذا كانت ستُعتمد في الجامعة ذات الأربع سنوات
  - judge: not supported: استخدم خدمات Transfer Services لمعرفة متطلبات القبول في الجامعات المستهدفة وتحديد مواعيد التقديم
  - judge: not supported: قدّم طلب القبول للجامعة التي اخترتها عبر نظامها الإلكتروني مع إرفاق سجل الدرجات ونصوص المقررات التي تم اعتمادها
- **g045** (grounded) I live outside Chicago but I work there full time. Can I still get in-district tuition?
  - failed: groundedness; confidence High; cited: institution-ccc-tuition::07
  - judge: not supported: Your residence outside Chicago makes you an out‑of‑district student, regardless of where you work.
- **g049** (grounded) Can I get college credit for what I learned at work?
  - failed: groundedness; confidence High; cited: institution-ccc-transfer-services::54
  - judge: not supported: You start by contacting the CPL office
  - judge: not supported: provide documentation of your job duties, training, certifications, or other evidence of what you learned
  - judge: not supported: the college will review it to see if it matches the learning outcomes of existing courses

## How the judge works

Model: `openai/gpt-oss-20b` (a different model from the advisor). Score per answer = supported claims / total claims, judged against the full text of the passages the answer cited. Answers with no citation are not judged (the citation check already fails them). The prompt:

```
You are a strict fact-checker for a college-advising chatbot.

You get a student's QUESTION, the chatbot's ANSWER, and the SOURCES the chatbot cited.
1. Split the ANSWER into its factual claims: dates, amounts, eligibility rules, steps, names of
   offices or programs. Ignore greetings, polite phrasing, "contact your advisor" style
   suggestions, and statements that something was not found.
2. For each claim decide whether the SOURCES state it or it follows directly from them. A claim
   that is true in the real world but not in the SOURCES is NOT supported.
3. The ANSWER may be in Arabic. Judge by meaning, not by wording.

Reply with ONLY one JSON object, no other text:
{"total_claims": <integer>, "supported_claims": <integer>, "unsupported": ["<short quote of each unsupported claim>"]}
```
