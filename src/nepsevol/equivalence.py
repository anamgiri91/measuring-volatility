"""Equivalence testing for proxy-parity claims, against a STATED (post hoc) margin.

PEER-REVIEW ITEM B / MANDATORY ITEM 2. The manuscript's conclusions rested on ratios such as

    sqrt( sum(v_range) / sum(r_OC^2) )

sitting "close" to one, with "close" and "economically modest" left undefined, and with a
confidence interval spanning one read as though it established parity. Both moves are wrong in
the same direction, and the reviewer named both:

* **Failure to reject equality is not evidence of equivalence.** A wide interval covering one
  is uninformative, not confirmatory. The wider the interval -- that is, the WEAKER the
  evidence -- the more comfortably it covers one, so reading coverage as support rewards
  imprecision. This package's own two-way intervals are roughly twice the width of the
  security-only intervals they replaced, which would have made the old claim look *stronger*.
* **"Close" needs a number chosen in advance.** Without a margin fixed before the estimate is
  seen, "economically modest" is decided by whatever the estimate turned out to be.

The fix is the standard one: state a margin, then run TWO one-sided tests against it.

THE MARGIN, AND WHEN IT WAS DECLARED
------------------------------------
:data:`MARGIN` is +/-5% on the SD ratio scale, i.e. the interval [0.95, 1.05]. It is a
measurement tolerance, not a statistical quantity, and it is chosen from the decision the paper
actually supports -- a practitioner sizing risk in a frontier cash market from daily OHLC bars.
Two considerations fix it at 5% rather than leaving it to taste:

1. **It is below the effect the paper needs to detect.** A margin wide enough to admit the
   pooled-universe composition effect the paper is about would be useless for the comparison it
   is used in.
2. **It is symmetric on the SD scale**, which is the scale every ratio in the paper is reported
   on, so the same number can be read directly off Tables 6 and 7 without rescaling.

**DECLARED POST HOC. This margin is NOT prespecified**, and earlier revisions of this package
were wrong to call it so. Putting a number in a module constant makes it *consistent* -- it
cannot be tuned per table without the change appearing in one place, in the diff -- but
consistency is not preregistration. No timestamped protocol predating the estimates exists, and
an earlier version of this docstring justified the 5% partly by effects already observed in this
project, which is precisely the circularity the term "prespecified" is supposed to exclude. It is
therefore described throughout as declared post hoc, and :data:`MARGINS` exists so that the
verdicts are reported across a grid rather than at one privileged value.

CONFIDENCE LEVEL: A CONSERVATIVE CRITERION, NOT TEXTBOOK TOST
------------------------------------------------------------
Standard TOST at one-sided alpha = .05 corresponds to checking a **90%** two-sided interval, not
a 95% one. This package's tables report 95% intervals, so applying :func:`equivalence_verdict` to
them is a **conservative** equivalence criterion (roughly one-sided alpha = .025), not the
standard 5% TOST procedure: it declares equivalence less often than TOST would. Both are
defensible; conflating them is not. Callers that want textbook TOST should pass a 90% interval
(``alpha=0.10`` to the bootstrap functions in :mod:`nepsevol.inference`), and the package reports
both so the reader can see which verdicts depend on that choice.

READING THE RESULT
------------------
:func:`equivalence_verdict` returns one of three verdicts, and the third is the one the old
wording collapsed into the first:

    ``equivalent``     the whole CI lies inside the margin -> parity WITHIN the stated tolerance
    ``different``      the whole CI lies outside [1,1]'s neighbourhood -> distinguishable
    ``inconclusive``   the CI straddles a margin boundary -> the data cannot tell, and no
                       parity claim may be made from it

There is no verdict that means "proved equal". Equivalence is always equivalence *to within the
margin*, against an IMPERFECT PROXY, and the module refuses to phrase it otherwise.
"""

from __future__ import annotations

import numpy as np

__all__ = ["MARGIN", "MARGINS", "LOWER", "UPPER", "equivalence_verdict", "verdict_sentence"]

#: Equivalence margin on the SD-ratio scale, DECLARED POST HOC. See the module docstring: this
#: is a stated measurement tolerance applied consistently, not a preregistered one.
MARGIN = 0.05

#: The margin grid every equivalence verdict is reported across, so that no conclusion rests on
#: the single value above. A verdict that flips between 0.025 and 0.10 is a verdict about the
#: margin, not about the estimator, and the tables must let a reader see that.
MARGINS = (0.025, 0.05, 0.10)

#: The equivalence region [LOWER, UPPER] implied by :data:`MARGIN`.
LOWER = 1.0 - MARGIN
UPPER = 1.0 + MARGIN


def equivalence_verdict(lo: float, hi: float, lower: float = LOWER,
                        upper: float = UPPER) -> str:
    """Verdict for a two-sided CI ``[lo, hi]`` against the equivalence region.

    This is the confidence-interval form of TOST: a (1-2a) interval falling entirely inside the
    margin is exactly the rejection of both one-sided nulls at level a, so no separate p-value
    is computed and none is reported. The package's intervals are two-way cluster percentile
    intervals, which have no closed-form p-value anyway; the interval IS the test.
    """
    if not (np.isfinite(lo) and np.isfinite(hi)):
        return "inconclusive"
    if lo >= lower and hi <= upper:
        return "equivalent"
    if hi < lower or lo > upper:
        return "different"
    return "inconclusive"


def verdict_sentence(name: str, ratio: float, lo: float, hi: float,
                     margin: float = MARGIN) -> str:
    """One sentence stating the verdict in language that cannot be misread as unbiasedness.

    Every phrasing here is relative to the MATCHED PROXY. None of them says "accurate",
    "unbiased", or "true bias", because the denominator is an imperfect proxy for latent
    variance rather than latent variance itself.
    """
    v = equivalence_verdict(lo, hi)
    pct = f"{100 * margin:g}%"
    if v == "equivalent":
        return (f"{name} attains proxy parity: the ratio is {ratio:.3f} with a 95% interval of "
                f"[{lo:.3f}, {hi:.3f}], contained in the stated (post hoc) +/-{pct} equivalence "
                f"margin.")
    if v == "different":
        return (f"{name} is distinguishable from the matched proxy beyond the stated (post hoc) "
                f"+/-{pct} margin: ratio {ratio:.3f}, 95% interval [{lo:.3f}, {hi:.3f}].")
    return (f"{name} is inconclusive at the stated (post hoc) +/-{pct} margin: ratio {ratio:.3f} "
            f"with a 95% interval of [{lo:.3f}, {hi:.3f}] that straddles a margin boundary, so "
            f"the data neither establish parity nor a difference.")
