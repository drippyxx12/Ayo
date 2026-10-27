"""Private prospect organization and draft records; these never authorize sends."""
import time

from sqlalchemy import (CheckConstraint, Column, Float, ForeignKey, ForeignKeyConstraint,
                        Integer, String, Text, UniqueConstraint)

from ayo.model_base import Base, opaque_id


class LeadList(Base):
    __tablename__ = 'lead_lists'
    __table_args__ = (UniqueConstraint('business_id', 'id', name='uq_lead_list_business_id'),)
    id = Column(String(64), primary_key=True, default=opaque_id)
    business_id = Column(String(64), ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=False, default='')
    actor_user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    provenance = Column(String(40), nullable=False, default='merchant_created')
    created_at = Column(Float, nullable=False, default=time.time)
    updated_at = Column(Float, nullable=False, default=time.time)


class LeadListItem(Base):
    __tablename__ = 'lead_list_items'
    __table_args__ = (
        ForeignKeyConstraint(['business_id', 'list_id'], ['lead_lists.business_id', 'lead_lists.id'],
                             ondelete='CASCADE', name='fk_lead_list_item_list'),
        ForeignKeyConstraint(['business_id', 'lead_id'], ['leads.business_id', 'leads.id'],
                             ondelete='CASCADE', name='fk_lead_list_item_lead'),
    )
    business_id = Column(String(64), ForeignKey('businesses.id', ondelete='CASCADE'), primary_key=True)
    list_id = Column(String(64), primary_key=True)
    lead_id = Column(String(64), primary_key=True)
    actor_user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    provenance = Column(String(40), nullable=False, default='merchant_selected')
    created_at = Column(Float, nullable=False, default=time.time)


class LeadNote(Base):
    __tablename__ = 'lead_notes'
    __table_args__ = (
        ForeignKeyConstraint(['business_id', 'lead_id'], ['leads.business_id', 'leads.id'],
                             ondelete='CASCADE', name='fk_lead_note_lead'),
    )
    id = Column(String(64), primary_key=True, default=opaque_id)
    business_id = Column(String(64), ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    lead_id = Column(String(64), nullable=False, index=True)
    actor_user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    body = Column(Text, nullable=False)
    provenance = Column(String(40), nullable=False, default='merchant_note')
    created_at = Column(Float, nullable=False, default=time.time)


class OutreachDraft(Base):
    __tablename__ = 'outreach_drafts'
    __table_args__ = (
        ForeignKeyConstraint(['business_id', 'lead_id'], ['leads.business_id', 'leads.id'],
                             ondelete='CASCADE', name='fk_outreach_draft_lead'),
        UniqueConstraint('business_id', 'lead_id', name='uq_outreach_draft_business_lead'),
        CheckConstraint('version >= 1', name='ck_outreach_draft_version'),
        CheckConstraint("status = 'draft'", name='ck_outreach_draft_status'),
    )
    id = Column(String(64), primary_key=True, default=opaque_id)
    business_id = Column(String(64), ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    lead_id = Column(String(64), nullable=False, index=True)
    actor_user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    offer = Column(Text, nullable=False)
    source_id = Column(String(160), nullable=False)
    source_url = Column(String(2048), nullable=False)
    source_excerpt = Column(Text, nullable=False)
    subject = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default='draft')
    provenance = Column(String(40), nullable=False, default='deterministic_template')
    template_version = Column(String(40), nullable=False, default='sourced-introduction-v1')
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(Float, nullable=False, default=time.time)
    updated_at = Column(Float, nullable=False, default=time.time)
