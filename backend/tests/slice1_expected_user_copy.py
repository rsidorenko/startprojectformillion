"""Expected user-facing copy for slice-1 catalog tests (align with message_catalog._CATALOG_TEXT)."""

IDENTITY_READY_TEXT = (
    "You are set up. Send /status to check the access the bot can show, or /help for a command list. "
    "This build does not include purchase links, checkout, or delivery of connection files."
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
    "Command list in this build:\n"
    "/start - register and link this chat to your account\n"
    "/status - show the access or eligibility information the bot can read (unknown state stays fail-closed)\n"
    "/resend_access - request a safe resend of access instructions (active accounts only)\n"
    "/get_access - alias of /resend_access\n"
    "/help - show this list\n"
    "\n"
    "This preview is read-only for purchase flows and for sending connection material. "
    "It does not add new entitlement and does not send credentials or files."
)

RESEND_ACCESS_ACCEPTED_TEXT = (
    "Access instructions request accepted. If safe delivery is available, instructions will be resent."
)

RESEND_ACCESS_NOT_ELIGIBLE_TEXT = (
    "Access instructions cannot be resent for this account right now."
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
