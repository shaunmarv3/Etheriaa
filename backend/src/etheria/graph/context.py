"""The trusted runtime context of one chat run (spec 4.1).

LangGraph concept: *runtime context*. It is passed as `context=` to
`astream`/`ainvoke`; nodes read it through `Runtime`, tools through
`ToolRuntime`. It is never part of the state and never shown to a model, so
neither the model nor a prompt injection can point a tool at another user."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ChatContext:
    user_id: UUID
    conversation_id: UUID
    request_id: str
    regenerate: bool = False
