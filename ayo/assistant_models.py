"""Private, tenant-scoped Ayo conversations and immutable read-tool snapshots."""
import time

from sqlalchemy import (CheckConstraint, Column, Float, ForeignKey, ForeignKeyConstraint,
                        Integer, String, Text, UniqueConstraint)

from ayo.model_base import Base, opaque_id


class AssistantConversation(Base):
    __tablename__ = 'assistant_conversations'
    __table_args__ = (
        UniqueConstraint('id', 'business_id', 'user_id', name='uq_assistant_conversation_scope'),
        UniqueConstraint('business_id', 'user_id', 'creation_key', name='uq_assistant_conversation_creation'),
        CheckConstraint('length(title) >= 1 AND length(title) <= 160', name='ck_assistant_title'),
    )
    id = Column(String(64), primary_key=True, default=opaque_id)
    business_id = Column(String(64), ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    creation_key = Column(String(64), nullable=False)
    title = Column(String(160), nullable=False)
    active_request = Column(String(64), nullable=True)
    created_at = Column(Float, nullable=False, default=time.time)
    updated_at = Column(Float, nullable=False, default=time.time)


class AssistantMessage(Base):
    __tablename__ = 'assistant_messages'
    __table_args__ = (
        ForeignKeyConstraint(['conversation_id', 'business_id', 'user_id'],
            ['assistant_conversations.id', 'assistant_conversations.business_id', 'assistant_conversations.user_id'],
            ondelete='CASCADE', name='fk_assistant_message_scope'),
        UniqueConstraint('id', 'business_id', 'user_id', name='uq_assistant_message_scope'),
        UniqueConstraint('conversation_id', 'request_key', 'role', name='uq_assistant_message_request'),
        CheckConstraint("role IN ('user','assistant')", name='ck_assistant_message_role'),
        CheckConstraint("status IN ('pending','completed','blocked','failed','uncertain')", name='ck_assistant_message_status'),
        CheckConstraint('length(content) <= 1000', name='ck_assistant_message_content'),
    )
    id = Column(String(64), primary_key=True, default=opaque_id)
    conversation_id = Column(String(64), nullable=False, index=True)
    business_id = Column(String(64), nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    request_key = Column(String(64), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False, default='')
    status = Column(String(20), nullable=False)
    plan_json = Column(Text, nullable=False, default='{}')
    result_json = Column(Text, nullable=False, default='{}')
    error_code = Column(String(80), nullable=True)
    created_at = Column(Float, nullable=False, default=time.time)
    finished_at = Column(Float, nullable=True)


class AssistantToolRun(Base):
    __tablename__ = 'assistant_tool_runs'
    __table_args__ = (
        ForeignKeyConstraint(['message_id', 'business_id', 'user_id'],
            ['assistant_messages.id', 'assistant_messages.business_id', 'assistant_messages.user_id'],
            ondelete='CASCADE', name='fk_assistant_tool_scope'),
        UniqueConstraint('message_id', 'tool_name', name='uq_assistant_tool_message'),
        CheckConstraint("tool_name IN ('business.profile','research.saved','opportunities.list','leads.saved','work.tasks')", name='ck_assistant_tool_name'),
        CheckConstraint('version = 1', name='ck_assistant_tool_version'),
        CheckConstraint("status IN ('completed','partial','empty')", name='ck_assistant_tool_status'),
    )
    id = Column(String(64), primary_key=True, default=opaque_id)
    message_id = Column(String(64), nullable=False, index=True)
    business_id = Column(String(64), nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    tool_name = Column(String(40), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    status = Column(String(20), nullable=False)
    result_json = Column(Text, nullable=False)
    created_at = Column(Float, nullable=False, default=time.time)
