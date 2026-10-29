"""Create password reset token table.

Revision ID: 20261029_01
Revises: 20261017_01
Create Date: 2026-10-29 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '20261029_01'
down_revision: str | None = '20261017_01'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
  op.create_table(
    'password_reset_tokens',
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
      name='fk_password_reset_tokens_user_id_users',
      ondelete='CASCADE',
    ),
    sa.PrimaryKeyConstraint('id', name='pk_password_reset_tokens'),
    sa.UniqueConstraint(
      'token_hash', name='uq_password_reset_tokens_token_hash'
    ),
  )
  op.create_index(
    'ix_password_reset_tokens_user_id_created_at',
    'password_reset_tokens',
    ['user_id', 'created_at'],
    unique=False,
  )


def downgrade() -> None:
  op.drop_index(
    'ix_password_reset_tokens_user_id_created_at',
    table_name='password_reset_tokens',
  )
  op.drop_table('password_reset_tokens')
