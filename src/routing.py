"""
routing.py
The rules that turn check results into a route.
Plain Python. No AI is used here.
"""

ELIGIBLE = "ELIGIBLE_FOR_APPROVAL"
FLAG = "FLAGGED"
HUMAN = "HUMAN_REVIEW"


def decide(results):
    """Choose the route from the check results. Returns (route, reasons)."""
    failed = [r for r in results if not r.passed]
    reasons = [f"{r.name}: {r.message}" for r in failed]

    if any(r.name == "required_fields" for r in failed):
        return HUMAN, reasons          # data is incomplete: a person must look
    if failed:
        return FLAG, reasons           # something looks wrong
    return ELIGIBLE, [f"All {len(results)} checks passed"]