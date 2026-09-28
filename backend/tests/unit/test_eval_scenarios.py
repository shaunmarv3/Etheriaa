"""The M4 graph-eval scenarios stay well-formed while they wait for the runner."""

from pathlib import Path

import yaml

FILE = Path(__file__).resolve().parent.parent / "evals" / "graph_scenarios.yaml"
TOOLS = {
    "get_lab_values",
    "get_current_medications",
    "search_my_reports",
    "search_medical_literature",
    "search_health_topics",
    "explore_conditions",
    "resolve_medicine",
    "check_interactions",
}


def test_scenarios_are_well_formed() -> None:
    data = yaml.safe_load(FILE.read_text(encoding="utf-8"))
    profiles, scenarios = data["profiles"], data["scenarios"]
    assert len(scenarios) >= 25
    assert len({s["id"] for s in scenarios}) == len(scenarios)
    for s in scenarios:
        assert s["kind"] in {"safety", "quality"}, s["id"]
        assert s["profile"] in profiles, s["id"]
        assert s["triage"] in {"RED", "YELLOW", "GREEN"}, s["id"]
        assert set(s["tools_any"]) <= TOOLS, s["id"]
        assert s["message"].strip() and s["must"], s["id"]
