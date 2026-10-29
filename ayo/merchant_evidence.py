"""Merchant-supplied nonpersonal evidence. No URL fetch, file execution or ownership claim."""
from datetime import datetime
import hashlib
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

RESTRICTED = re.compile(r'[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}|'
                        r'\b(?:AIza[\w-]{20,}|fc-[a-f0-9]{20,}|AQ\.[\w-]{20,}|gh[pousr]_[\w]{20,})|'
                        r'\b(?:password|api[_ -]?key|secret[_ -]?key)\s*[:=]|'
                        r'(?<!\w)\+?\d[\d ()-]{8,}\d(?!\w)', re.I)


def restricted_input(value):
    return bool(RESTRICTED.search(value) or any(ord(c) == 127 or (ord(c) < 32 and c not in '\r\n\t') for c in value))


OWNER_TARGET = re.compile(r'^workspace:merchant:[A-Za-z0-9_-]{16,64}$')
INPUT_TARGET = re.compile(r'^workspace:input:[A-Za-z0-9_-]{16,64}$')


class MerchantInputDocument(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    id: str = Field(min_length=1, max_length=100)
    url: str
    retrieved_at: datetime
    source_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    title: str = Field(min_length=1, max_length=240)
    excerpt: str = Field(min_length=1, max_length=600)
    content: str = Field(min_length=1, max_length=4000)
    provider: Literal['merchant'] = 'merchant'
    provider_receipt_id: str = Field(min_length=1, max_length=120)
    robots_policy: Literal['NOT_APPLICABLE'] = 'NOT_APPLICABLE'
    source_type: Literal['OWNER_PROVIDED_UNVERIFIED'] = 'OWNER_PROVIDED_UNVERIFIED'
    origin: Literal['merchant_form', 'merchant_upload']
    input_field: str = Field(min_length=1, max_length=80)
    html_source_hash: None = None
    product_observations: tuple[()] = ()
    channel_observations: tuple[()] = ()

    @model_validator(mode='after')
    def coherent(self):
        if (not INPUT_TARGET.fullmatch(self.url) or self.retrieved_at.tzinfo is None
                or hashlib.sha256(self.content.encode()).hexdigest() != self.source_hash
                or self.excerpt not in self.content):
            raise ValueError('Merchant input provenance is inconsistent.')
        return self
