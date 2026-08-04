"""End-to-end test of the task-success eval harness.

It must: run every offline task fixture through the REAL flows, be fully
deterministic on the mock LLM, report the success rate the README/scorecard
quote, actually fail when the answer key is wrong (so the checks are not
vacuous), and keep the committed scorecard files in sync with a fresh run.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "task_success", ROOT / "eval" / "task_success.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _norm(text: str) -> str:
    return text.replace("\r\n", "\n")


def test_runs_end_to_end_and_is_deterministic():
    ts = _load()
    r1 = ts.evaluate()
    r2 = ts.evaluate()
    assert r1 == r2, "task-success eval must be fully deterministic on the mock LLM"
    assert ts.render_markdown(r1) == ts.render_markdown(r2)
    assert ts.render_csv(r1) == ts.render_csv(r2)

    s = r1["summary"]
    assert s["n_tasks"] == 9
    assert s["passed"] == 9
    assert s["success_rate"] == 1.0
    # both flows are exercised
    assert r1["by_usecase"]["rfq_intake"]["tasks"] == 5
    assert r1["by_usecase"]["product_enrichment"]["tasks"] == 4
    # every task ran real assertions (not a vacuous pass)
    for row in r1["tasks"]:
        assert row["n_checks"] >= 5, row["id"]
        assert row["passed"], row["id"]


def test_checks_are_not_vacuous():
    """A deliberately wrong answer key must be reported as a failure — proves the
    harness measures the real business outcome, not just that a run completed."""
    ts = _load()
    wrong = {
        "id": "probe", "usecase": "rfq_intake", "title": "probe",
        "input": "From: x@y.de\nSubject: p\n\n25 x hex nut M8 zinc\n",
        "expect": {"total_eur": 999.99, "skus": ["WRONG"], "flagged_count": 3},
    }
    row = ts.run_task(wrong)
    assert not row["passed"]
    reasons = " ".join(row["failures"])
    assert "total_eur" in reasons and "skus" in reasons and "flagged_count" in reasons


def test_offcatalog_line_is_flagged_not_guessed():
    """The honest-behaviour case: an item with no catalog match is flagged for
    human review, never silently quoted against a wrong SKU."""
    ts = _load()
    rows = {r["id"]: r for r in ts.evaluate()["tasks"]}
    off = rows["rfq_02_offcatalog"]
    assert off["passed"]
    assert off["observed"]["flagged_count"] == 1
    assert None in off["observed"]["skus"]


def test_committed_scorecards_are_up_to_date():
    """The committed CSV/Markdown deliverables must match a fresh run, so the
    numbers the README references are never stale."""
    ts = _load()
    results = ts.evaluate()
    md = _norm((ROOT / "eval" / "task_scorecard.md").read_text(encoding="utf-8"))
    csv_text = _norm((ROOT / "eval" / "task_scorecard.csv").read_text(encoding="utf-8"))
    assert md == _norm(ts.render_markdown(results)), "run: python eval/task_success.py"
    assert csv_text == _norm(ts.render_csv(results)), "run: python eval/task_success.py"
