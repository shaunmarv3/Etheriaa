"""Page-aware chunking (spec 5.3 step 6): about 500 tokens with a 50-token
overlap, never crossing a page, each chunk carrying its page and source kind.
Tokens are counted with the embedding model's own tokenizer, so a chunk is
never silently truncated by BGE's 512-token window."""

from collections.abc import Callable

from etheria.ingestion.schemas import ChunkDraft, PageText


def _words(text: str) -> list[tuple[str, bool]]:
    """(word, ends_a_line) pairs, so chunks keep the page's line breaks."""
    out: list[tuple[str, bool]] = []
    for line in text.splitlines():
        ws = line.split()
        out += [(w, i == len(ws) - 1) for i, w in enumerate(ws)]
    return out


def _join(words: list[tuple[str, bool]]) -> str:
    parts = []
    for i, (w, eol) in enumerate(words):
        parts.append(w)
        if i < len(words) - 1:
            parts.append("\n" if eol else " ")
    return "".join(parts)


def chunk_pages(
    pages: list[PageText],
    count_tokens: Callable[[str], int],
    max_tokens: int = 500,
    overlap: int = 50,
) -> list[ChunkDraft]:
    specials = count_tokens("")  # e.g. BGE's [CLS] and [SEP]
    budget = max_tokens - specials
    chunks: list[ChunkDraft] = []
    for page in pages:
        words = _words(page.text)
        cost = [max(count_tokens(w) - specials, 1) for w, _ in words]
        start = 0
        while start < len(words):
            end, total = start, 0
            while end < len(words) and total + cost[end] <= budget:
                total += cost[end]
                end += 1
            end = max(end, start + 1)  # one over-long word still makes progress
            chunks.append(
                ChunkDraft(
                    index=len(chunks),
                    page=page.page,
                    source_kind=page.source_kind,
                    content=_join(words[start:end]),
                )
            )
            if end >= len(words):
                break
            # Step back so the next chunk repeats about `overlap` tokens.
            back, carried = end, 0
            while back - 1 > start and carried + cost[back - 1] <= overlap:
                back -= 1
                carried += cost[back]
            start = back
    return chunks
