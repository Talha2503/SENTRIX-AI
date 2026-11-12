# SENTRIX AI - Evaluation results

Generated: 2026-11-13 03:18  
Language model: `openai/gpt-oss-120b` (Groq)

## Scope and caveats

- Four synthetic, fictional test cases (supported claims, unsupported claim, incomplete application, alternative explanation). Ground truth is computed independently of the agents.
- This is a very small test set. Results show behaviour on controlled inputs, not general accuracy, and should not be read as a performance guarantee.
- No model accuracy is claimed. Numbers are extracted and calculated by deterministic code; the language model only extracts claims and drafts commentary.
- Scores use illustrative weights and thresholds (see README).

## Summary metrics

| Metric | Result |
|---|---|
| End-to-end success (completed, report, all agent tasks completed) | 4/4 (100%) |
| Agent task completion rate | 36/36 (100%) |
| Extraction accuracy (numeric fields vs reference) | 66/66 (100%) |
| Calculation correctness (vs independently computed values) | 33/33 (100%) |
| Findings traceable to a source or calculation | 21/21 (100%) |
| Claim quotes found verbatim in their source passage | 24/24 (100%) |
| Behaviour checks passed | 31/33 (94%) |
| Processing time per case | 3-21 s (mean 11 s) |

## Per case

| Case | Time | Agent tasks | Extraction | Calculations | Traceable | Quotes | Behaviour checks |
|---|---|---|---|---|---|---|---|
| case_b_unsupported_claim | 9 s | 9/9 (100%) | 22/22 (100%) | 11/11 (100%) | 6/6 (100%) | 7/7 (100%) | 11/11 |
| case_f_alternative_explanation | 3 s | 9/9 (100%) | 22/22 (100%) | 11/11 (100%) | 4/4 (100%) | 2/2 (100%) | 5/7 |
| case_a_supported_claims | 9 s | 9/9 (100%) | 22/22 (100%) | 11/11 (100%) | 8/8 (100%) | 9/9 (100%) | 8/8 |
| case_e_incomplete_application | 21 s | 9/9 (100%) | n/a | n/a | 3/3 (100%) | 6/6 (100%) | 7/7 |

## Behaviour checks

### case_b_unsupported_claim

- [x] Investigation completed and a report was produced
- [x] No accusatory language in the summary or finding titles
- [x] 40% emissions claim extracted as -40
- [x] Emissions claim extracted with no baseline
- [x] Missing baseline/method flagged as high-severity 'insufficient information'
- [x] Energy-efficiency claim flagged as contradicting the records
- [x] Anomalies carry an adversarial verdict
- [x] Electricity per tonne change is +12.4% (+/-0.2)
- [x] Practice claims reported as unverified
- [x] Summary says the claim is insufficiently supported (not fraud)
- [x] Overall risk given with coverage of at least 40%

### case_f_alternative_explanation

- [x] Investigation completed and a report was produced
- [x] No accusatory language in the summary or finding titles
- [ ] Baseline FY2025 attached to the emissions claim
- [ ] Verification triggered a targeted reassessment (taxonomy ran twice)
- [x] Electricity anomaly is DISPUTED (documented on-site solar plant)
- [x] Electricity change is +6.0% (+/-0.2)
- [x] Missing methodology still reported

### case_a_supported_claims

- [x] Investigation completed and a report was produced
- [x] No accusatory language in the summary or finding titles
- [x] Emissions claim has baseline FY2025
- [x] No contradictory findings
- [x] No high-severity risk findings
- [x] Emissions change confirmed consistent with the records
- [x] Statement figures match the underlying records
- [x] Overall risk is given and below 40

### case_e_incomplete_application

- [x] Investigation completed and a report was produced
- [x] No accusatory language in the summary or finding titles
- [x] No overall risk score is given (coverage too low)
- [x] Overall coverage is below 40%
- [x] No contradictions or anomalies were invented
- [x] Financial stability reported as not assessed
- [x] Missing financial data reported as insufficient information
