# SENTRIX AI - Demo script (about 5 minutes)

## Before you start (10 minutes earlier)

- [ ] PostgreSQL running; `uvicorn app.main:app --reload` running; `npm run dev` running
- [ ] http://localhost:3000 shows "API connected" in the sidebar
- [ ] Groq key works: `python scripts\test_llm.py`
- [ ] Run Zenith once beforehand so a finished report is ready as a backup
- [ ] Browser zoom 100%, full screen, notifications off

## Flow

1. **The problem (30 s).** Green-finance applicants submit claims scattered across PDFs and spreadsheets. Manual
   checks miss unsupported claims and contradictions, and a single score hides what is unknown.
2. **Start the case (20 s).** New investigation, then Load and investigate on *Unsupported claim (Zenith)*:
   a fictional manufacturer asking for PKR 50 million, claiming a 40% emissions cut.
3. **Agent monitor (45 s).** Point out the parallel agents, then the verification step. Every task is logged.
4. **Report (60 s).** Read the summary: the claim is *insufficiently supported*, not "fraud". Show the rings:
   risk, coverage and confidence are separate. Explain that missing information lowers coverage, not risk.
5. **Claims and findings (60 s).** Open the 40% claim: verbatim quote, page, no baseline. In Findings, open the
   efficiency finding: electricity per tonne +12.4% against the claim. Show the adversarial review that tested
   production growth, energy source, boundary and data completeness, and ended *unresolved*.
6. **Evidence explorer (30 s).** Click a source link: the original PDF opens at the cited page.
7. **Contrast (45 s).** Load *Alternative explanation (Lakeview)*: the verification step finds a baseline stated
   elsewhere, re-runs the affected checks, and marks the anomaly *disputed* because an operating solar plant is
   documented. Then show *Incomplete application*: no overall score is given, because the evidence is too thin.
8. **Close (15 s).** Evidence-first, uncertainty-aware, human-centred. Decision support, not a decision-maker.

## Likely questions

- *How is hallucination controlled?* Numbers come from code; claim quotes are verified against the source text;
  invented baselines are discarded; the model cannot change a verdict; the summary is rejected if it adds
  numbers or accusatory wording.
- *Is the taxonomy official?* No. It is an illustrative rule set with a recorded version. The design allows the
  official criteria to be dropped in.
- *Accuracy?* Not claimed. See `docs/evaluation_results.md`: small synthetic set, results reported as measured.
- *Why no machine learning?* No labelled dataset exists. Transparent rules are preferred to unsupported accuracy
  claims, as the proposal states.
- *What if the model is down?* Deterministic agents still run; the report falls back to a template summary and
  records a warning.

## If something breaks live

- Page hangs: check the backend window; restart uvicorn, refresh.
- Model error or rate limit: wait a minute and press Re-run, or open the pre-run Zenith report.
- Port 8000 stuck: `netstat -ano | findstr :8000`, then `taskkill /F /T /PID <pid>`.