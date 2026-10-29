"""Shared declarative registry for independently imported domain model modules."""
import secrets

from sqlalchemy.orm import declarative_base

Base = declarative_base()


def opaque_id():
    return secrets.token_urlsafe(24)
