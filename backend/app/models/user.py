"""Minimal ORM mapping for `public.users` so FKs from other models resolve in SQLAlchemy metadata."""

from uuid import UUID

from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    """
    Schema is defined by SQL migrations (`001` / `003`); this class only registers the table
    for ForeignKey resolution. Extra columns exist in the DB but are not required here.
    """

    __tablename__ = "users"
    __table_args__ = {"schema": "public"}

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
