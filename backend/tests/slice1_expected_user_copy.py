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
    "/help - show this list\n"
    "\n"
    "This preview is read-only for purchase flows and for sending connection material. "
    "It does not add new entitlement and does not send credentials or files."
)
