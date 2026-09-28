"""docs/ARCHITECTURE.md embeds a diagram generated from the compiled graph."""

from etheria.graph.diagram import END, START, write_diagram


def test_diagram_is_written_between_markers_and_is_idempotent(tmp_path) -> None:
    path = tmp_path / "ARCHITECTURE.md"
    path.write_text("# Architecture\n\nHand-written text.\n", encoding="utf-8")
    write_diagram(path)
    first = path.read_text(encoding="utf-8")
    write_diagram(path)
    assert path.read_text(encoding="utf-8") == first
    assert "Hand-written text." in first
    body = first.split(START, 1)[1].split(END, 1)[0]
    for node in (
        "load_context",
        "input_guard",
        "retrieval_agent",
        "triage",
        "rerank_evidence",
        "generate",
        "clinical_structuring",
        "canned_reply",
        "finalize",
    ):
        assert node in body
    assert "understand -.-> triage" in body  # a conditional fan-out edge
