"""Exact-host HTTPS control proofs, separate from research and write consent."""
from sqlalchemy import CheckConstraint, Column, Float, ForeignKey, Index, Integer, String, Text

from ayo.model_base import Base


class SiteControlClaim(Base):
    __tablename__ = 'site_control_claims'
    __table_args__ = (
        CheckConstraint("status IN ('pending','checking','failed','verified','expired','revoked')", name='ck_site_control_status'),
        CheckConstraint('attempts >= 0 AND attempts <= 5', name='ck_site_control_attempts'),
        CheckConstraint("method = 'https_file'", name='ck_site_control_method'),
        CheckConstraint('expires_at > created_at', name='ck_site_control_expiry'),
        CheckConstraint("status != 'verified' OR (verified_at IS NOT NULL AND verified_until > verified_at AND proof_body_sha256 IS NOT NULL AND token_cipher IS NULL)", name='ck_site_control_proof'),
        Index('ix_site_control_business_host', 'business_id', 'host', 'created_at'),
        Index('ix_site_control_actor_created', 'created_by', 'created_at'),
    )
    id = Column(String(64), primary_key=True)
    business_id = Column(String(64), ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False)
    created_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    host = Column(String(253), nullable=False)
    method = Column(String(20), nullable=False, default='https_file')
    status = Column(String(20), nullable=False, default='pending')
    token_hash = Column(String(64), nullable=False)
    token_cipher = Column(Text, nullable=True)
    created_at = Column(Float, nullable=False)
    expires_at = Column(Float, nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
    checked_at = Column(Float, nullable=True)
    lease_hash = Column(String(64), nullable=True)
    lease_until = Column(Float, nullable=True)
    verified_at = Column(Float, nullable=True)
    verified_until = Column(Float, nullable=True)
    proof_body_sha256 = Column(String(64), nullable=True)
    error_code = Column(String(60), nullable=True)
