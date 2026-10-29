"""Pure search-first product invariants; no networking, AI calls or customer data."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

CandidateSource = Literal["PUBLIC_WEB", "PUBLIC_PROFILE", "OWNER_PROVIDED_UNVERIFIED"]
ClaimKind = Literal["OBSERVED", "INFERRED", "UNKNOWN"]

@dataclass(frozen=True)
class EvidenceClaim:
    text: str
    kind: ClaimKind
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("An evidence claim requires text")
        if self.kind == "OBSERVED" and not self.evidence_ids:
            raise ValueError("Observed facts must cite real source evidence")

@dataclass(frozen=True)
class OrganizationLeadPreview:
    name: str
    source_id: str
    url: str
    status: str = "DISCOVERED"

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.source_id.strip() or not self.url.startswith("https://"):
            raise ValueError("Lead preview requires a sourced public business and a secure URL")
        if self.status != "DISCOVERED":
            raise ValueError("Anonymous leads cannot be treated as contacted or sold")

@dataclass(frozen=True)
class PublicMiniReport:
    source_kind: CandidateSource
    claims: tuple[EvidenceClaim, ...]
    leads: tuple[OrganizationLeadPreview, ...] = ()
    has_actual_provider_evidence: bool = False
    website_ownership_verified: bool = False
    shopify_connected: bool = False
    possible_revenue: float | None = None

    def __post_init__(self) -> None:
        if len(self.leads) > 3:
            raise ValueError("Anonymous lead previews are capped at three")
        if self.leads and not self.has_actual_provider_evidence:
            raise ValueError("Never fabricate leads when no search provider returned evidence")
        if self.website_ownership_verified or self.shopify_connected or self.possible_revenue is not None:
            raise ValueError("Anonymous public research never proves ownership or merchant revenue")
        if self.source_kind == "OWNER_PROVIDED_UNVERIFIED" and any(c.kind == "OBSERVED" for c in self.claims):
            raise ValueError("Owner supplied statements cannot masquerade as independently observed web facts")

    @property
    def next_primary_action(self) -> str:
        return "Create your free Ayo account"
