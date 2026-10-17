"""Create user, email verification, and refresh token tables.

Revision ID: 20261017_01
Revises:
Create Date: 2026-10-17 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '20261017_01'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
  op.create_table(
    'users',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column(
      'is_email_verified',
      sa.Boolean(),
      server_default=sa.text('false'),
      nullable=False,
    ),
    sa.Column(
      'is_active',
      sa.Boolean(),
      server_default=sa.text('true'),
      nullable=False,
    ),
    sa.Column(
      'created_at',
      sa.DateTime(timezone=True),
      server_default=sa.text('now()'),
      nullable=False,
    ),
    sa.PrimaryKeyConstraint('id', name='pk_users'),
    sa.UniqueConstraint('email', name='uq_users_email'),
  )
  op.create_table(
    'email_verification_tokens',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('consumed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column(
      'created_at',
      sa.DateTime(timezone=True),
      server_default=sa.text('now()'),
      nullable=False,
    ),
    sa.ForeignKeyConstraint(
      ['user_id'],
      ['users.id'],
      name='fk_email_verification_tokens_user_id_users',
      ondelete='CASCADE',
    ),
    sa.PrimaryKeyConstraint('id', name='pk_email_verification_tokens'),
    sa.UniqueConstraint(
      'token_hash', name='uq_email_verification_tokens_token_hash'
    ),
  )
  op.create_index(
    'ix_email_verification_tokens_user_id_created_at',
    'email_verification_tokens',
    ['user_id', 'created_at'],
    unique=False,
  )
  op.create_table(
    'refresh_tokens',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('family_id', sa.Uuid(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('replaced_by_id', sa.Uuid(), nullable=True),
    sa.Column(
      'created_at',
      sa.DateTime(timezone=True),
      server_default=sa.text('now()'),
      nullable=False,
    ),
    sa.ForeignKeyConstraint(
      ['replaced_by_id'],
      ['refresh_tokens.id'],
      name='fk_refresh_tokens_replaced_by_id_refresh_tokens',
      ondelete='SET NULL',
    ),
    sa.ForeignKeyConstraint(
      ['user_id'],
      ['users.id'],
      name='fk_refresh_tokens_user_id_users',
      ondelete='CASCADE',
    ),
    sa.PrimaryKeyConstraint('id', name='pk_refresh_tokens'),
    sa.UniqueConstraint('token_hash', name='uq_refresh_tokens_token_hash'),
  )
  op.create_index(
    'ix_refresh_tokens_family_id', 'refresh_tokens', ['family_id'], unique=False
  )


def downgrade() -> None:
  op.drop_index('ix_refresh_tokens_family_id', table_name='refresh_tokens')
  op.drop_table('refresh_tokens')
  op.drop_index(
    'ix_email_verification_tokens_user_id_created_at',
    table_name='email_verification_tokens',
  )
  op.drop_table('email_verification_tokens')
  op.drop_table('users')
