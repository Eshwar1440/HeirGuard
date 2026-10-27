"""The AI-log summary: hand-checked RMD matches the simulator, and every on-purpose bad text is blocked."""

from hg import ai_log_summary


def test_summary_rmd_matches_and_all_examples_are_blocked():
    text = ai_log_summary.render()  # conftest points ai_log at an empty temp folder
    assert "Match: **yes**" in text and "$3,623.19 | $3,623.19" in text
    assert text.count("| **blocked** |") == len(ai_log_summary.SAFETY_EXAMPLES) == 3
    assert "Logged calls: **0**" in text and "Not run yet" in text
