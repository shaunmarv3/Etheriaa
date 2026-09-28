"""The graph-eval scenarios stay well-formed (spec 1.2 criterion 5: at least 30)."""

from etheria.graph.eval import SCENARIOS_FILE, load_suite

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
    suite = load_suite(SCENARIOS_FILE)
    assert len(suite.scenarios) >= 30
    assert len({s.id for s in suite.scenarios}) == len(suite.scenarios)
    kinds = [s.kind for s in suite.scenarios]
    assert kinds.count("safety") >= 14
    for s in suite.scenarios:
        assert s.profile in suite.profiles, s.id
        assert set(s.tools_any) <= TOOLS and set(s.tools_not) <= TOOLS, s.id
        assert s.message.strip() and s.must, s.id
