from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
  Boolean,
  DateTime,
  ForeignKey,
  Index,
  String,
  Uuid,
  func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base


class User(Base):
  __tablename__ = 'users'

  id: Mapped[UUID] = mapped_column(
    Uuid(as_uuid=True), primary_key=True, default=uuid4
  )
  email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
  password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
  is_email_verified: Mapped[bool] = mapped_column(
    Boolean, default=False, server_default='false', nullable=False
  )
  is_active: Mapped[bool] = mapped_column(
    Boolean, default=True, server_default='true', nullable=False
  )
  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), server_default=func.now(), nullable=False
  )


class EmailVerificationToken(Base):
  __tablename__ = 'email_verification_tokens'
  __table_args__ = (
    Index(
      'ix_email_verification_tokens_user_id_created_at',
      'user_id',
      'created_at',
    ),
  )

  id: Mapped[UUID] = mapped_column(
    Uuid(as_uuid=True), primary_key=True, default=uuid4
  )
  user_id: Mapped[UUID] = mapped_column(
    Uuid(as_uuid=True),
    ForeignKey('users.id', ondelete='CASCADE'),
    nullable=False,
  )
  token_hash: Mapped[str] = mapped_column(
    String(64), unique=True, nullable=False
  )
  expires_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), nullable=False
  )
  consumed_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True
  )
  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), server_default=func.now(), nullable=False
  )


class RefreshToken(Base):
  __tablename__ = 'refresh_tokens'
  __table_args__ = (Index('ix_refresh_tokens_family_id', 'family_id'),)

  id: Mapped[UUID] = mapped_column(
    Uuid(as_uuid=True), primary_key=True, default=uuid4
  )
  user_id: Mapped[UUID] = mapped_column(
    Uuid(as_uuid=True),
    ForeignKey('users.id', ondelete='CASCADE'),
    nullable=False,
  )
  family_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
  token_hash: Mapped[str] = mapped_column(
    String(64), unique=True, nullable=False
  )
  expires_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), nullable=False
  )
  revoked_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True
  )
  replaced_by_id: Mapped[UUID | None] = mapped_column(
    Uuid(as_uuid=True),
    ForeignKey('refresh_tokens.id', ondelete='SET NULL'),
    nullable=True,
  )
  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), server_default=func.now(), nullable=False
  )
