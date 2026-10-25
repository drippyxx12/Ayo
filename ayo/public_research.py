"""Anonymous acquisition input handling; no networking or persistence.

These previews describe the current unavailable research capability. They never
represent a completed public assessment, source evidence, or business ownership.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal

from ayo.website_research import SiteInputError, classify_website_input


COUNTRIES = {"NG": "Nigeria", "GH": "Ghana"}


@dataclass(frozen=True)
class ResearchPreview:
    status: Literal["search_not_configured", "secure_fetch_not_configured", "owner_provided_unverified"]
    input_kind: Literal["search", "url", "owner_provided"]
    query: str
    country: str
    city: str
    no_website: bool
    owner_facts: str
    source_kind: Literal["NONE", "OWNER_PROVIDED_UNVERIFIED"]
    message: str

    @property
    def country_name(self) -> str:
        return COUNTRIES.get(self.country, "Not selected")


def _bounded_text(value: str, label: str, limit: int, multiline: bool = False) -> str:
    if len(value) > limit:
        raise SiteInputError(f"{label} must be {limit} characters or fewer.")
    allowed_controls = "\n\r\t" if multiline else ""
    if any((ord(c) < 32 and c not in allowed_controls) or ord(c) == 127 for c in value):
        raise SiteInputError(f"Enter valid text for {label.lower()}.")
    return re.sub(r"\s+", " ", value).strip()


def prepare_public_research(
    query: str,
    country: str = "",
    city: str = "",
    no_website: bool = False,
    owner_facts: str = "",
) -> ResearchPreview:
    """Validate a public request and return an honest zero-evidence preview.

    Market selection is explicit, never inferred. Owner text remains unverified
    input and is returned only in this response, not saved in a signed cookie.
    URL parsing admits an intent, not permission to fetch a network destination.
    """
    query = _bounded_text(query, "Business name or link", 250)
    city = _bounded_text(city, "City", 100)
    owner_facts = _bounded_text(owner_facts, "Business description", 2000, multiline=True)
    if country not in ("", *COUNTRIES):
        raise SiteInputError("Choose Nigeria or Ghana, or leave the market unselected.")
    if not query:
        raise SiteInputError("Enter a business name or a public website link.")
    if owner_facts and not no_website:
        raise SiteInputError("Choose the no-website option to include your own business description.")
    if "://" in query and not query.lower().startswith(("http://", "https://")):
        raise SiteInputError("Only public http and https website links are supported.")

    intent = classify_website_input(query)
    if no_website:
        if intent.kind != "search":
            raise SiteInputError("Enter your business name for the no-website option.")
        if not owner_facts:
            raise SiteInputError("Describe what your business sells to start without a website.")
        return ResearchPreview(
            status="owner_provided_unverified",
            input_kind="owner_provided",
            query=intent.value,
            country=country,
            city=city,
            no_website=True,
            owner_facts=owner_facts,
            source_kind="OWNER_PROVIDED_UNVERIFIED",
            message="Your starting profile uses only the details you entered. Public sources have not been checked.",
        )

    if intent.kind == "url":
        status = "secure_fetch_not_configured"
        message = "Website research is not available yet. Ayo has not opened or inspected this link."
    else:
        status = "search_not_configured"
        message = "Business search is not available yet. No matching businesses or public sources have been retrieved."
    return ResearchPreview(
        status=status,
        input_kind=intent.kind,
        query=intent.value,
        country=country,
        city=city,
        no_website=False,
        owner_facts="",
        source_kind="NONE",
        message=message,
    )
