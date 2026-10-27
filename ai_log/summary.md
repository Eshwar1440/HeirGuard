# AI log summary

> Concept prototype. Not affiliated with Charles Schwab. All data is hypothetical.

Generated 2026-10-27 03:54 UTC by `python -m hg.ai_log_summary`. AI does two jobs only: reading documents (`hg/reader`) and writing plain English (`hg/writer`). Numbers, rules, routing and approval are code or a person.

## 1. Model calls

Every call goes through `hg/llm.py` and is logged to `ai_log/*.jsonl` (prompt, input summary, output, model). Logged calls: **374**.

| Job | Calls |
|---|---|
| extract_json | 304 |
| write_text | 70 |

| Model that answered | Calls |
|---|---|
| `claude-sonnet-5-5` | 374 |

Refusals: 0. Failed calls: 0.

## 2. Extraction accuracy (AI-log check #1)

The reader (`hg/reader`) against the truth files of every synthetic packet. Full report: `ai_log/extraction_accuracy.md`.

| Measure | Result |
|---|---|
| Document type correct | 36/36 (100.0%) |
| Fields correct | 347/347 (100.0%) |
| Wrong values flagged for review (caught) | n/a |
| **Wrong values with high confidence (silent errors)** | **0** |
| Correct values flagged anyway (false alarms) | 0 |
| Documents that failed to read | 0 |

**Planted errors read as printed (not silently fixed):**

The reader must report a planted error exactly as printed (not silently fix it), so the checker can catch it.

| Packet | Rule | Field | Printed | Read | As printed |
|---|---|---|---|---|---|
| packet_03 | name_match | executor_name | Joseh Ferguson | Joseh Ferguson | yes |
| packet_04 | dod_consistent | decedent_date_of_death | 2025-05-01 | 2025-05-01 | yes |
| packet_06 | certified_copy | certified_copy | no | no | yes |
| packet_07 | name_match | affiant_name | Melisa Fitzgerald | Melisa Fitzgerald | yes |
| packet_07 | dod_consistent | date_of_death | 2025-04-02 | 2025-04-02 | yes |
| packet_08 | certified_copy | certified_copy | no | no | yes |
| packet_09 | dod_consistent | decedent_date_of_death | 2025-06-30 | 2025-06-30 | yes |

**Limits:**

- The packets are clean, machine-generated PDFs with a text layer. They do not test scans, phone photos, handwriting, skew, stamps over text or low resolution, so real-world accuracy will be lower. Treat these numbers as a best case.
- Each packet uses the same five specimen layouts; unfamiliar layouts are not tested.
- certified_copy records visible signs that a certificate is a copy (a VOID background pattern, an "uncertified" notice). It cannot confirm a certified copy: a raised seal does not show in a scan. In these PDFs the VOID pattern is also in the text layer; in a real scan it is only pixels.
- Confidence is the model's own estimate. A high-confidence wrong value is the dangerous case, which is why silent errors are reported separately and every field still passes through the rule checks.

## 3. Hand-checked RMD (IRS Pub. 590-B example)

Pub. 590-B (2025), "Owner Died on or After Required Beginning Date", Example: the father died in 2021 at 80; the heir was 55 in 2022, so "the life expectancy for a 55-year-old is 31.6; therefore, you calculate your required minimum distribution for 2026 by dividing the account balance by 27.6 (31.6 - 4)."

| Step | By hand | Simulator (`hg/simulator/rmd.py`) |
|---|---|---|
| Heir factor, age 55 (Table I) | 31.6 | |
| 2026 is year 5: 31.6 - 4 | 27.6 | |
| Father: 11.2 at 80, minus 5 for 2026 | 6.2 | |
| Divisor used (the longer) | 27.6 | 27.6 |
| 2026 RMD on a hypothetical $100,000 | $3,623.19 | $3,623.19 |

Match: **yes**. The same example is a test (`tests/test_simulator_rmd.py`).

## 4. Safety check: three blocks

Every text the writer (`hg/writer`) produces passes `hg/safety/check.py` before anyone sees it: no number the calculator did not produce, no advice, no telling the heir which option to take. A blocked text is regenerated once, then replaced by a fixed template.

These three texts were written on purpose to break the rules and run through the real check. Allowed numbers for the examples: 10, 115447.78, 2035, 2035-12-31, 259219.44.

| Case | Text | Result | Reasons |
|---|---|---|---|
| A number the calculator never produced | Lump sum now: about $120,000 in tax, you keep $259,219.44. | **blocked** | number "$120,000" is not in the input |
| Advice instead of an explanation | You should take the lump sum, since the account must be empty by December 31, 2035. | **blocked** | advice phrase "you should" |
| A recommendation hidden in a bullet point | - Take the lump sum now and keep $259,219.44. | **blocked** | recommends a scenario: "take the lump sum" |
