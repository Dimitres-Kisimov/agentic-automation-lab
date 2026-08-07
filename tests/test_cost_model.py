"""End-to-end test of the token & cost model harness.

It must: run every offline task fixture through the REAL flows, be fully
deterministic on the mock LLM, do the token->cost arithmetic correctly, actually
depend on the price sheet (not vacuous), and keep the committed scorecard files
in sync with a fresh run.
"""
import copy
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "cost_model", ROOT / "eval" / "cost_model.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _norm(text: str) -> str:
    return text.replace("\r\n", "\n")


def test_runs_end_to_end_and_is_deterministic():
    cm = _load()
    r1 = cm.evaluate()
    r2 = cm.evaluate()
    assert r1 == r2, "cost model must be fully deterministic on the mock LLM"
    assert cm.render_markdown(r1) == cm.render_markdown(r2)
    assert cm.render_csv(r1) == cm.render_csv(r2)

    s = r1["summary"]
    assert s["n_tasks"] == 9
    assert s["provider"] == "mock (deterministic)"
    # both flows exercised, with the expected fixture counts
    assert r1["by_usecase"]["rfq_intake"]["runs"] == 5
    assert r1["by_usecase"]["product_enrichment"]["runs"] == 4
    # every run recorded real, positive token usage (not a vacuous zero)
    for row in r1["tasks"]:
        assert row["input_tokens"] > 0 and row["output_tokens"] > 0, row["id"]
        assert set(row["cost_per_run"]) == {m["id"] for m in r1["models"]}


def test_cost_arithmetic_matches_price_sheet():
    """Each per-run cost must equal tokens/1e6 * price for that model — proves the
    reported dollars are the real arithmetic, not a hard-coded constant."""
    cm = _load()
    results = cm.evaluate()
    models = {m["id"]: m for m in results["models"]}
    for row in results["tasks"]:
        for mid, cost in row["cost_per_run"].items():
            m = models[mid]
            exp_in = round(row["input_tokens"] / 1_000_000 * m["input"], 6)
            exp_out = round(row["output_tokens"] / 1_000_000 * m["output"], 6)
            assert cost["input"] == exp_in, (row["id"], mid)
            assert cost["output"] == exp_out, (row["id"], mid)
            assert cost["total"] == round(exp_in + exp_out, 6), (row["id"], mid)


def test_cost_depends_on_the_price_sheet_not_vacuous():
    """Doubling every price must roughly double every cost — proves the harness
    actually consumes eval/pricing.json rather than emitting fixed numbers."""
    cm = _load()
    base = cm.evaluate()
    doubled = cm.load_pricing()
    for m in doubled["models"]:
        m["input"] *= 2
        m["output"] *= 2
    bumped = cm.evaluate(pricing=doubled)

    assert base["tasks"][0]["input_tokens"] == bumped["tasks"][0]["input_tokens"]
    for b, d in zip(base["tasks"], bumped["tasks"], strict=True):
        for mid in b["cost_per_run"]:
            got = d["cost_per_run"][mid]["total"]
            want = b["cost_per_run"][mid]["total"] * 2
            assert abs(got - want) <= 2e-6, (b["id"], mid)  # tolerate rounding


def test_annual_projection_scales_from_mean_cost():
    """The annual figure must be the mean cost/run times the stated yearly volume."""
    cm = _load()
    results = cm.evaluate()
    proj = {p["usecase"]: p for p in results["projections"]}
    assert "rfq_intake" in proj, "the RFQ flow has a grounded volume and must project"
    p = proj["rfq_intake"]
    assert p["runs_per_year"] == p["runs_per_week"] * 52
    mean = results["by_usecase"]["rfq_intake"]["mean_cost_per_run"]
    for mid, annual in p["annual_cost"].items():
        assert abs(annual - round(mean[mid] * p["runs_per_year"], 2)) <= 0.01, mid


def test_price_sheet_is_a_dated_snapshot():
    """The prices must carry a dated provenance label — an honest cost model does
    not present list prices as timeless."""
    cm = _load()
    pricing = cm.load_pricing()
    assert pricing["as_of"] and pricing["currency"] == "USD"
    assert pricing["provider_default_model"] == "claude-haiku-4-5"
    # the sheet is not mutated in place by evaluate()
    snapshot = copy.deepcopy(pricing)
    cm.evaluate(pricing=pricing)
    assert pricing == snapshot


def test_committed_scorecards_are_up_to_date():
    """The committed JSON/MD/CSV deliverables must match a fresh run, so the numbers
    the README references are never stale."""
    cm = _load()
    results = cm.evaluate()
    import json
    committed_json = _norm((ROOT / "eval" / "cost_results.json").read_text(encoding="utf-8"))
    md = _norm((ROOT / "eval" / "cost_scorecard.md").read_text(encoding="utf-8"))
    csv_text = _norm((ROOT / "eval" / "cost_scorecard.csv").read_text(encoding="utf-8"))
    assert committed_json == _norm(json.dumps(results, indent=2)), "run: python eval/cost_model.py"
    assert md == _norm(cm.render_markdown(results)), "run: python eval/cost_model.py"
    assert csv_text == _norm(cm.render_csv(results)), "run: python eval/cost_model.py"
