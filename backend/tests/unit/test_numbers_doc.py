from pathlib import Path

from etheria.seed.verify import BEGIN, END, Canary, render_section, write_numbers


def test_creates_the_file_with_the_section(tmp_path: Path) -> None:
    path = tmp_path / "NUMBERS.md"
    write_numbers(path, "hello")
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# Numbers")
    assert f"{BEGIN}\nhello\n{END}" in text


def test_replaces_only_the_marked_block(tmp_path: Path) -> None:
    path = tmp_path / "NUMBERS.md"
    path.write_text(
        f"# Numbers\n\nintro\n\n{BEGIN}\nold\n{END}\n\n## Docker\nkept\n", encoding="utf-8"
    )
    write_numbers(path, "new")
    text = path.read_text(encoding="utf-8")
    assert "old" not in text
    assert f"{BEGIN}\nnew\n{END}" in text
    assert "intro" in text and "## Docker\nkept" in text


def test_appends_the_block_when_markers_are_missing(tmp_path: Path) -> None:
    path = tmp_path / "NUMBERS.md"
    path.write_text("# Numbers\n\nhand-written\n", encoding="utf-8")
    write_numbers(path, "x")
    text = path.read_text(encoding="utf-8")
    assert "hand-written" in text and f"{BEGIN}\nx\n{END}" in text


def test_render_section_lists_counts_and_canaries() -> None:
    text = render_section(
        {"Neo4j": {"Drug (ddinter)": 1939}, "Postgres": {"medicine_brands": 253973}},
        [
            Canary("Dolo 650 -> acetaminophen", True, "Acetaminophen"),
            Canary("loose motions -> diarrhoea", False, "None"),
        ],
        measured_on="2026-09-28",
    )
    assert "| Drug (ddinter) | 1,939 |" in text
    assert "| medicine_brands | 253,973 |" in text
    assert "| PASS | Dolo 650 -> acetaminophen | Acetaminophen |" in text
    assert "| FAIL | loose motions -> diarrhoea | None |" in text
    assert "2026-09-28" in text
