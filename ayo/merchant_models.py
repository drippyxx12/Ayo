"""Merchant-supplied context and internal work records; neither grants authority."""
import time

from sqlalchemy import CheckConstraint, Column, Date, Float, ForeignKey, Integer, String, Text

from ayo.model_base import Base, opaque_id


class BusinessProfile(Base):
    __tablename__ = 'business_profiles'
    __table_args__ = (
        CheckConstraint("source_classification = 'OWNER_PROVIDED_UNVERIFIED'", name='ck_profile_source'),
        CheckConstraint('version >= 1', name='ck_profile_version'),
    )
    business_id = Column(String(64), ForeignKey('businesses.id', ondelete='CASCADE'), primary_key=True)
    offer = Column(Text, nullable=False, default='')
    products = Column(Text, nullable=False, default='')
    audience = Column(Text, nullable=False, default='')
    location = Column(String(250), nullable=False, default='')
    goals = Column(Text, nullable=False, default='')
    source_classification = Column(String(40), nullable=False, default='OWNER_PROVIDED_UNVERIFIED')
    updated_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at = Column(Float, nullable=False, default=time.time)
    updated_at = Column(Float, nullable=False, default=time.time)
    version = Column(Integer, nullable=False, default=1)


class Task(Base):
    __tablename__ = 'tasks'
    __table_args__ = (
        CheckConstraint("status IN ('open','in_progress','done','cancelled')", name='ck_task_status'),
        CheckConstraint('version >= 1', name='ck_task_version'),
        CheckConstraint('length(title) >= 1 AND length(title) <= 200', name='ck_task_title'),
    )
    id = Column(String(64), primary_key=True, default=opaque_id)
    business_id = Column(String(64), ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False, default='')
    status = Column(String(20), nullable=False, default='open')
    due_date = Column(Date, nullable=True)
    created_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    source_report_id = Column(String(64), ForeignKey('research_reports.id', ondelete='SET NULL'), nullable=True, index=True)
    source_lead_id = Column(String(64), ForeignKey('leads.id', ondelete='SET NULL'), nullable=True, index=True)
    created_at = Column(Float, nullable=False, default=time.time)
    updated_at = Column(Float, nullable=False, default=time.time)
    version = Column(Integer, nullable=False, default=1)
