"""Boundary surface for internal admin principal extraction contract (no I/O)."""

from app.admin_support import (
    AdminActorRef,
    InternalAdminPrincipalExtractionInput,
    InternalAdminPrincipalExtractionOutcome,
    InternalAdminPrincipalExtractionResult,
)


def test_internal_admin_principal_extraction_contract_construct() -> None:
    missing = InternalAdminPrincipalExtractionResult(
        outcome=InternalAdminPrincipalExtractionOutcome.MISSING_PRINCIPAL,
        principal=None,
    )
    success = InternalAdminPrincipalExtractionResult(
        outcome=InternalAdminPrincipalExtractionOutcome.SUCCESS,
        principal=AdminActorRef(internal_admin_principal_id="adm-1"),
    )
    inp = InternalAdminPrincipalExtractionInput(
        principal_id_candidate="adm-1",
        trusted_source=True,
    )

    assert missing.principal is None
    assert success.principal is not None
    assert success.principal.internal_admin_principal_id == "adm-1"
    assert inp.trusted_source is True
