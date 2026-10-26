# Extraction accuracy (AI-log check #1)

> All documents are synthetic specimens with hypothetical data. Ground truth is each packet's `truth.json` from the M1 generator.

- Run: 2026-10-26 05:20 UTC
- Model: `claude-sonnet-5-5` via `hg.llm.extract_json` (every call is in `ai_log/*.jsonl`)
- Packets: 11; documents: 36; fields scored: 347
- Review threshold: confidence below 0.85 (CONFIDENCE_THRESHOLD, hypothetical) or a null value
- The file name is not sent to the model. Text values are compared ignoring case and extra spaces; all other values must match exactly after normalization.

## Summary

| Measure | Result |
|---|---|
| Document type correct | 36/36 (100.0%) |
| Fields correct | 347/347 (100.0%) |
| Wrong values flagged for review (caught) | n/a |
| **Wrong values with high confidence (silent errors)** | **0** |
| Correct values flagged anyway (false alarms) | 0 |
| Documents that failed to read | 0 |

## By document type

| Document type | Documents | Type correct | Fields correct | Flagged for review |
|---|---|---|---|---|
| affidavit_of_domicile | 2 | 2/2 (100.0%) | 12/12 (100.0%) | 0 |
| death_certificate | 11 | 11/11 (100.0%) | 99/99 (100.0%) | 0 |
| inherited_ira_application | 19 | 19/19 (100.0%) | 209/209 (100.0%) | 0 |
| letters_testamentary | 3 | 3/3 (100.0%) | 21/21 (100.0%) | 0 |
| trust_certification | 1 | 1/1 (100.0%) | 6/6 (100.0%) | 0 |

## By field

| Field | Correct | Mean confidence |
|---|---|---|
| affidavit_of_domicile.affiant_capacity | 2/2 (100.0%) | 0.97 |
| affidavit_of_domicile.affiant_name | 2/2 (100.0%) | 0.98 |
| affidavit_of_domicile.date_of_death | 2/2 (100.0%) | 0.98 |
| affidavit_of_domicile.decedent_name | 2/2 (100.0%) | 0.98 |
| affidavit_of_domicile.domicile_address | 2/2 (100.0%) | 0.96 |
| affidavit_of_domicile.notary_date | 2/2 (100.0%) | 0.90 |
| death_certificate.certificate_number | 11/11 (100.0%) | 0.97 |
| death_certificate.certified_copy | 11/11 (100.0%) | 0.87 |
| death_certificate.date_issued | 11/11 (100.0%) | 0.97 |
| death_certificate.date_of_birth | 11/11 (100.0%) | 0.97 |
| death_certificate.date_of_death | 11/11 (100.0%) | 0.97 |
| death_certificate.decedent_name | 11/11 (100.0%) | 0.98 |
| death_certificate.issuing_county | 11/11 (100.0%) | 0.96 |
| death_certificate.issuing_state | 11/11 (100.0%) | 0.98 |
| death_certificate.place_of_death | 11/11 (100.0%) | 0.96 |
| inherited_ira_application.account_title | 19/19 (100.0%) | 0.97 |
| inherited_ira_application.account_type | 19/19 (100.0%) | 0.97 |
| inherited_ira_application.beneficiary_date_of_birth | 19/19 (100.0%) | 0.97 |
| inherited_ira_application.beneficiary_name | 19/19 (100.0%) | 0.98 |
| inherited_ira_application.decedent_date_of_death | 19/19 (100.0%) | 0.98 |
| inherited_ira_application.decedent_name | 19/19 (100.0%) | 0.98 |
| inherited_ira_application.designation | 19/19 (100.0%) | 0.97 |
| inherited_ira_application.relationship | 19/19 (100.0%) | 0.97 |
| inherited_ira_application.share_percent | 19/19 (100.0%) | 0.97 |
| inherited_ira_application.signature_date | 19/19 (100.0%) | 0.98 |
| inherited_ira_application.signature_name | 19/19 (100.0%) | 0.98 |
| letters_testamentary.case_number | 3/3 (100.0%) | 0.97 |
| letters_testamentary.court_county | 3/3 (100.0%) | 0.97 |
| letters_testamentary.court_name | 3/3 (100.0%) | 0.98 |
| letters_testamentary.date_issued | 3/3 (100.0%) | 0.98 |
| letters_testamentary.date_of_death | 3/3 (100.0%) | 0.98 |
| letters_testamentary.decedent_name | 3/3 (100.0%) | 0.98 |
| letters_testamentary.executor_name | 3/3 (100.0%) | 0.97 |
| trust_certification.certification_date | 1/1 (100.0%) | 0.97 |
| trust_certification.grantor_date_of_death | 1/1 (100.0%) | 0.97 |
| trust_certification.grantor_name | 1/1 (100.0%) | 0.98 |
| trust_certification.successor_trustee_name | 1/1 (100.0%) | 0.98 |
| trust_certification.trust_date | 1/1 (100.0%) | 0.97 |
| trust_certification.trust_name | 1/1 (100.0%) | 0.98 |

## Planted errors: read as printed?

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

## Every miss

No misses.

## Limits of this test

- The packets are clean, machine-generated PDFs with a text layer. They do not test scans, phone photos, handwriting, skew, stamps over text or low resolution, so real-world accuracy will be lower. Treat these numbers as a best case.
- Each packet uses the same five specimen layouts; unfamiliar layouts are not tested.
- certified_copy records visible signs that a certificate is a copy (a VOID background pattern, an "uncertified" notice). It cannot confirm a certified copy: a raised seal does not show in a scan. In these PDFs the VOID pattern is also in the text layer; in a real scan it is only pixels.
- Confidence is the model's own estimate. A high-confidence wrong value is the dangerous case, which is why silent errors are reported separately and every field still passes through the rule checks.
