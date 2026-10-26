"""Recommendation language the writer may never use.

Matching is case-insensitive on whole words, after curly quotes are straightened
and whitespace is collapsed. The writer explains; it never recommends.
"""

from __future__ import annotations

#: Phrases that turn an explanation into advice.
ADVICE_PHRASES: tuple[str, ...] = (
    "you should",
    "you shouldn't",
    "you ought to",
    "we recommend",
    "i recommend",
    "we suggest",
    "i suggest",
    "my advice",
    "our advice",
    "the best option",
    "best choice",
    "the right choice",
    "the smart choice",
    "the better option",
    "you'd be better off",
    "you would be better off",
    "it's best to",
    "it is best to",
    "you need to choose",
    "you must choose",
    "do this",
)

#: Ways a scenario can be named in text, keyed by the M4 scenario name.
SCENARIO_PHRASES: dict[str, tuple[str, ...]] = {
    "lump_sum_now": ("lump sum", "lump-sum", "everything now", "all of it now", "whole balance now"),
    "minimums_then_balloon": ("minimums then balloon", "balloon", "minimums only", "only the minimums", "the minimums"),
    "even_spread": ("even spread", "spread it evenly", "equal withdrawals", "same amount each year"),
    "fill_bracket": ("fill bracket", "fill the bracket", "fill your bracket", "bracket fill", "bracket-filling"),
}

#: Verbs that, opening a clause, turn a scenario name into an instruction.
IMPERATIVE_VERBS: tuple[str, ...] = (
    "take",
    "choose",
    "pick",
    "select",
    "go with",
    "opt for",
    "stick with",
    "consider",
    "use",
    "try",
    "do",
    "withdraw",
)

#: Filler words that may precede an imperative verb at the start of a clause.
CLAUSE_LEADERS: tuple[str, ...] = ("so", "just", "simply", "please", "then", "instead", "definitely", "really")
