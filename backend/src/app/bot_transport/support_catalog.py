"""Customer-facing support copy: short FAQ and validated contact lines only."""

from __future__ import annotations

from app.bot_transport.storefront_config import StorefrontPublicConfig


def get_support_faq_items() -> list[dict[str, str]]:
    """Static FAQ entries; no env reads, no user input."""
    return [
        {
            "key": "pricing",
            "question": "Where do I see the price?",
            "answer": (
                "Plan details and the amount due appear at checkout before you pay. "
                "Use /plans for a short summary, then /buy when you are ready."
            ),
        },
        {
            "key": "access",
            "question": "How do I get access after paying?",
            "answer": (
                "Activation can take a short moment after checkout. "
                "Use /my_subscription to check status, then /get_access when it shows active."
            ),
        },
        {
            "key": "refund",
            "question": "What about refunds?",
            "answer": (
                "If you need a refund, reach out through the contact options when they are available. "
                "Each request is reviewed individually; outcomes depend on your situation."
            ),
        },
    ]


def build_support_menu_text() -> str:
    """Header, FAQ list, and hint toward safe contact command."""
    items = get_support_faq_items()
    lines: list[str] = ["Support & Help", ""]
    for i, item in enumerate(items, start=1):
        lines.append(f"{i}. {item['question']}")
        lines.append(f"   {item['answer']}")
        lines.append("")
    lines.append("Use /support_contact to reach us.")
    return "\n".join(lines).rstrip() + "\n"


def build_support_contact_text(cfg: StorefrontPublicConfig) -> str:
    """
    Show only storefront fields already validated in :func:`load_storefront_public_config`.
    Never emit raw, unvalidated URLs.
    """
    if not cfg.support_handle and not cfg.support_url:
        return "Support is currently unavailable. Please try again later."
    lines: list[str] = ["Contact support", ""]
    if cfg.support_handle:
        lines.append(cfg.support_handle)
    if cfg.support_url:
        lines.append(cfg.support_url)
    return "\n".join(lines)
