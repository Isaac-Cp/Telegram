from openai import OpenAI

from app.core.config import get_settings

SUPPORT_DRAFT_SYSTEM_PROMPT = """
You are a support drafting assistant for Streamexpert.
Only help with users who already initiated contact or granted explicit consent.
Draft concise, technically accurate IPTV support replies.
Do not use manipulative sales language, false urgency, or unverifiable claims.
Mark the draft as needing human review when the issue touches billing, refunds, service outages, or reseller terms.
""".strip()


def build_client() -> OpenAI | None:
    settings = get_settings()
    if not settings.openai_api_key:
        return None
    return OpenAI(api_key=settings.openai_api_key)


def draft_support_reply(user_message: str) -> str:
    client = build_client()
    if client is None:
        return "Thanks for reaching out. We have your request logged and a support agent can review the issue and reply shortly."

    completion = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {"role": "system", "content": SUPPORT_DRAFT_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    )
    return completion.output_text

