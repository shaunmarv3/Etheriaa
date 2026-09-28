from etheria.ingestion.chunking import chunk_pages
from etheria.ingestion.schemas import PageText


def words(n: int, prefix: str = "w") -> str:
    return "\n".join(" ".join(f"{prefix}{i}-{j}" for j in range(10)) for i in range(n // 10))


def count(s: str) -> int:
    return len(s.split())


def test_chunks_never_span_pages() -> None:
    pages = [
        PageText(page=1, text=words(700, "a"), source_kind="text_layer"),
        PageText(page=2, text=words(300, "b"), source_kind="text_layer"),
    ]
    chunks = chunk_pages(pages, count)
    for c in chunks:
        prefixes = {w[0] for w in c.content.split()}
        assert prefixes == {"a"} if c.page == 1 else prefixes == {"b"}


def test_chunk_size_and_overlap() -> None:
    chunks = chunk_pages([PageText(page=1, text=words(1200), source_kind="text_layer")], count)
    assert len(chunks) >= 3
    assert all(count(c.content) <= 500 for c in chunks)
    for a, b in zip(chunks, chunks[1:], strict=False):
        tail = a.content.split()[-50:]
        assert b.content.split()[:50] == tail


def test_every_word_is_covered() -> None:
    text = words(1200)
    chunks = chunk_pages([PageText(page=1, text=text, source_kind="text_layer")], count)
    covered = {w for c in chunks for w in c.content.split()}
    assert covered == set(text.split())


def test_long_line_is_split_by_words() -> None:
    text = " ".join(f"x{i}" for i in range(1200))  # one line, no newlines
    chunks = chunk_pages([PageText(page=1, text=text, source_kind="text_layer")], count)
    assert all(count(c.content) <= 500 for c in chunks)
    assert {w for c in chunks for w in c.content.split()} == set(text.split())


def test_source_kind_carried() -> None:
    chunks = chunk_pages([PageText(page=1, text="scan text here", source_kind="ocr")], count)
    assert [c.source_kind for c in chunks] == ["ocr"]


def test_short_pages_one_chunk_each() -> None:
    pages = [PageText(page=i, text=f"page {i} text", source_kind="text_layer") for i in (1, 2, 3)]
    assert [c.page for c in chunk_pages(pages, count)] == [1, 2, 3]


def test_indices_are_contiguous_from_zero() -> None:
    pages = [
        PageText(page=1, text=words(1200), source_kind="text_layer"),
        PageText(page=2, text="short", source_kind="text_layer"),
    ]
    chunks = chunk_pages(pages, count)
    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_empty_page_produces_no_chunk() -> None:
    pages = [
        PageText(page=1, text="  \n ", source_kind="ocr"),
        PageText(page=2, text="text", source_kind="text_layer"),
    ]
    assert [c.page for c in chunk_pages(pages, count)] == [2]
