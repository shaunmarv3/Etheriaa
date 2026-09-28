"""canned_reply (spec 4.3): fixed replies for blocked input, off-topic messages
and upload help. No model call."""

from langchain_core.messages import AIMessage

from etheria.graph.nodes.common import Timer, token
from etheria.graph.state import ChatState

REPLIES = {
    "prompt_injection": (
        "I can't change how I work or take on a different role, but I'm happy to help "
        "with a health question. What would you like to know?"
    ),
    "too_long": (
        "That message is too long for me to read in one go. Could you shorten it to the "
        "main question?"
    ),
    "off_topic": (
        "I'm a health assistant, so I can only help with health questions: symptoms, "
        "medicines, your uploaded reports or general health. What would you like to ask?"
    ),
    "upload_help": (
        "You can upload a lab report, prescription or discharge summary (PDF, PNG or JPEG, "
        "up to 10 MB and 30 pages) with the upload button. Once it has been processed, ask "
        'me about it, for example "Is my haemoglobin normal?".'
    ),
}


def reason_for(state: ChatState) -> str:
    turn = state["turn"]
    if turn.guard is not None and turn.guard.blocked:
        return turn.guard.reason or "prompt_injection"
    return turn.understanding.intent if turn.understanding else "off_topic"


async def canned_reply(state: ChatState) -> dict:
    timer = Timer()
    reason = reason_for(state)
    reply = REPLIES.get(reason, REPLIES["off_topic"])
    token(reply)
    return {
        "messages": [AIMessage(reply)],
        "turn": {
            "reply": reply,
            "canned": reason,
            "trace": [timer.entry("canned_reply", "fixed reply", reason)],
        },
    }
