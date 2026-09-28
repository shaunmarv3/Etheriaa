"""Document classification (spec 5.3 step 3, 5.5). Below 0.6 confidence the
type is `other`: better no structured extraction than the wrong extractor."""

from langchain_core.messages import HumanMessage, SystemMessage

from etheria.ingestion.schemas import Classification, PageText
from etheria.llm.prompts import load_prompt, wrap_document
from etheria.llm.registry import StructuredFactory

CONFIDENCE_FLOOR = 0.6
MAX_PAGES = 3
MAX_CHARS = 6000


async def classify_document(pages: list[PageText], make: StructuredFactory) -> Classification:
    text = "\n\n".join(f"[page {p.page}]\n{p.text}" for p in pages[:MAX_PAGES])[:MAX_CHARS]
    messages = [
        SystemMessage(load_prompt("classify_document")),
        HumanMessage(wrap_document(text)),
    ]
    result: Classification = await make("classify_document", Classification).ainvoke(messages)
    if result.confidence < CONFIDENCE_FLOOR:
        return result.model_copy(update={"doc_type": "other"})
    return result
