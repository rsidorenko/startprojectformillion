"""Framework-neutral internal admin principal extractor for ADM-01."""

from __future__ import annotations

from app.admin_support.contracts import (
    AdminActorRef,
    InternalAdminPrincipalExtractionInput,
    InternalAdminPrincipalExtractionOutcome,
    InternalAdminPrincipalExtractionResult,
    InternalAdminPrincipalExtractor,
)


class DefaultInternalAdminPrincipalExtractor(InternalAdminPrincipalExtractor):
    """Fail-closed principal extraction from trusted internal ingress."""

    async def extract_trusted_internal_admin_principal(
        self,
        inp: InternalAdminPrincipalExtractionInput,
    ) -> InternalAdminPrincipalExtractionResult:
        if not inp.trusted_source:
            return InternalAdminPrincipalExtractionResult(
                outcome=InternalAdminPrincipalExtractionOutcome.UNTRUSTED_SOURCE,
                principal=None,
            )
        candidate = inp.principal_id_candidate
        if candidate is None:
            return InternalAdminPrincipalExtractionResult(
                outcome=InternalAdminPrincipalExtractionOutcome.MISSING_PRINCIPAL,
                principal=None,
            )
        if not isinstance(candidate, str):
            return InternalAdminPrincipalExtractionResult(
                outcome=InternalAdminPrincipalExtractionOutcome.MALFORMED_PRINCIPAL,
                principal=None,
            )
        normalized = candidate.strip()
        if not normalized:
            return InternalAdminPrincipalExtractionResult(
                outcome=InternalAdminPrincipalExtractionOutcome.MALFORMED_PRINCIPAL,
                principal=None,
            )
        return InternalAdminPrincipalExtractionResult(
            outcome=InternalAdminPrincipalExtractionOutcome.SUCCESS,
            principal=AdminActorRef(internal_admin_principal_id=normalized),
        )
