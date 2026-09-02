"""Documented special trading sessions.

The weekday rule and the list of exceptions to it are different things, and conflating
them is how a genuine session gets deleted for looking wrong.

NEPSE traded Sunday-Thursday historically and moved to Monday-Friday in April 2026. A
session falling outside whichever rule is in force is not automatically an error: exchanges
run make-up sessions. Each such date must be listed here individually, with its evidence
and its verification status, rather than admitted by a blanket "Saturdays are allowed".

Status vocabulary
-----------------
``VERIFIED``               confirmed against an exchange notice or circular
``PROVISIONAL``            data signature is unambiguous; institutional citation pending
``SUSPECTED_DATA_ERROR``   looks like a carried-forward or malformed file
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

__all__ = ["SpecialSession", "SPECIAL_SESSIONS", "is_special_session", "status_of"]


@dataclass(frozen=True)
class SpecialSession:
    date: str
    status: str
    empirical_evidence: str
    institutional_citation: str
    note: str = ""
    recorded: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)


SPECIAL_SESSIONS: dict[pd.Timestamp, SpecialSession] = {
    pd.Timestamp("2026-07-25"): SpecialSession(
        date="2026-07-25",
        status="PROVISIONAL",
        empirical_evidence=(
            "Behaves as a genuine session on every available signature: only 5.9% of closes "
            "match the previous session (a carried-forward file runs ~100%); 70,158 trades "
            "across 353 securities; 94.3% of rows have high != low; no zero-volume rows; "
            "turnover NPR 6.27bn. The adjacent Friday 2026-07-24 and Sunday 2026-07-26 are "
            "both absent from the panel, so the week runs Wed, Thu, [no Fri], Sat, [no Sun], Mon "
            "-- the signature of a make-up session replacing a holiday Friday."
        ),
        institutional_citation="PENDING -- not yet checked against an exchange notice",
        note=(
            "Retain. Do not delete for falling outside the Mon-Fri rule in force from April 2026. "
            "Reclassify to VERIFIED once the circular is obtained, or to SUSPECTED_DATA_ERROR if "
            "the exchange confirms no session occurred."
        ),
        recorded="2026-08-28",
        tags=("make-up-session", "post-april-2026-regime"),
    ),
}


def is_special_session(date) -> bool:
    """True if `date` is a documented special session that the weekday rule would reject."""
    ts = pd.Timestamp(date).normalize()
    entry = SPECIAL_SESSIONS.get(ts)
    return entry is not None and entry.status in ("VERIFIED", "PROVISIONAL")


def status_of(date) -> str | None:
    """Verification status for a documented date, or None if it is not documented."""
    entry = SPECIAL_SESSIONS.get(pd.Timestamp(date).normalize())
    return None if entry is None else entry.status
