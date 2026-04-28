"""Expected user-facing copy for slice-1 catalog tests (align with message_catalog._CATALOG_TEXT)."""

IDENTITY_READY_TEXT = (
    "Welcome! Your chat is connected.\n"
    "Use /menu to browse plans and purchase options.\n"
    "Use /my_subscription anytime to check current status."
)

NEEDS_ONBOARDING_TEXT = (
    "Send /start to register, then you can use /status or /help. "
    "The bot must know this chat before it can show access information."
)

INACTIVE_OR_NOT_ELIGIBLE_TEXT = (
    "No access is available for this account right now. If you are new here, send /start, then /status, or /help. "
    "This build does not grant new access and does not send files."
)

SLICE1_HELP_TEXT = (
    "Available commands:\n"
    "/start - connect this chat\n"
    "/menu - main menu\n"
    "/plans - available plans\n"
    "/buy - open checkout\n"
    "/checkout - alias of /buy\n"
    "/success - post-payment next steps\n"
    "/my_subscription - subscription status (same as /status)\n"
    "/status - subscription status\n"
    "/renew - renewal checkout link\n"
    "/support - help and FAQ\n"
    "/support_contact - contact options\n"
    "/resend_access - resend access instructions when eligible\n"
    "/get_access - alias of /resend_access\n"
    "/help - this help"
)

RESEND_ACCESS_ACCEPTED_TEXT = (
    "Access instructions request accepted. If safe delivery is available, instructions will be resent."
)

RESEND_ACCESS_NOT_ENABLED_TEXT = "This feature is not available yet."

RESEND_ACCESS_NOT_ELIGIBLE_TEXT = (
    "Access instructions cannot be resent for this account right now.\n"
    "If your subscription is inactive or expired, use /renew."
)

RESEND_ACCESS_COOLDOWN_TEXT = (
    "Please wait a moment before requesting access instructions again."
)

RESEND_ACCESS_NOT_READY_TEXT = (
    "Access instructions are not ready to resend yet. Please try again later."
)

RESEND_ACCESS_TEMPORARILY_UNAVAILABLE_TEXT = (
    "Access instructions resend is temporarily unavailable. Please try again later."
)

SUBSCRIPTION_ACTIVE_ACCESS_NOT_READY_TEXT = "Your subscription is active until {date}."

SUBSCRIPTION_ACTIVE_ACCESS_READY_TEXT = "Your subscription is active until {date}."

TELEGRAM_COMMAND_RATE_LIMITED_TEXT = "Too many requests. Please try again later."
