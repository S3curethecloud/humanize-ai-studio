"""Humanize V3.4 authority-preservation public surface."""

from .claim_protection import ClaimProtectionAssessment, evaluate_claim_protection
from .contracts import (
    AuthorityContext,
    AuthorityDisposition,
    AuthorityIssue,
    AuthorityIssueCode,
    AuthorityResult,
    PresentationDerivation,
    ProtectedDeliveryFact,
    SourceAuthorityBinding,
)
from .provenance import bind_source_authority
from .service import (
    bind_protected_fact,
    derive_presentation,
    validate_protected_fact,
)

__all__ = [
    "AuthorityContext",
    "AuthorityDisposition",
    "AuthorityIssue",
    "AuthorityIssueCode",
    "AuthorityResult",
    "ClaimProtectionAssessment",
    "PresentationDerivation",
    "ProtectedDeliveryFact",
    "SourceAuthorityBinding",
    "bind_protected_fact",
    "bind_source_authority",
    "derive_presentation",
    "evaluate_claim_protection",
    "validate_protected_fact",
]
