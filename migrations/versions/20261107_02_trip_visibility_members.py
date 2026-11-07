"""Add trip visibility and trip_members.

Revision ID: 20261107_02
Revises: 20261107_01
Create Date: 2026-11-07 16:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '20261107_02'
down_revision: str | None = '20261107_01'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
  op.add_column(
    'trips',
    sa.Column(
      'visibility',
      sa.String(length=16),
      server_default='private',
      nullable=False,
    ),
  )
  op.create_table(
    'trip_members',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('trip_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column(
      'role',
      sa.String(length=16),
      server_default='member',
      nullable=False,
    ),
    sa.Column(
      'created_at',
      sa.DateTime(timezone=True),
      server_default=sa.text('now()'),
      nullable=False,
    ),
    sa.Column(
      'updated_at',
      sa.DateTime(timezone=True),
      server_default=sa.text('now()'),
      nullable=False,
    ),
    sa.ForeignKeyConstraint(
      ['trip_id'],
      ['trips.id'],
      name='fk_trip_members_trip_id_trips',
      ondelete='CASCADE',
    ),
    sa.ForeignKeyConstraint(
      ['user_id'],
      ['users.id'],
      name='fk_trip_members_user_id_users',
      ondelete='CASCADE',
    ),
    sa.PrimaryKeyConstraint('id', name='pk_trip_members'),
    sa.UniqueConstraint('trip_id', 'user_id', name='uq_trip_members_trip_user'),
  )
  op.create_index(
    'ix_trip_members_user_id', 'trip_members', ['user_id'], unique=False
  )

  # Backfill owners for existing trips.
  op.execute(
    sa.text(
      """
      INSERT INTO trip_members (id, trip_id, user_id, role, created_at, updated_at)
      SELECT gen_random_uuid(), t.id, t.user_id, 'owner', now(), now()
      FROM trips t
      WHERE NOT EXISTS (
        SELECT 1 FROM trip_members m
        WHERE m.trip_id = t.id AND m.user_id = t.user_id
      )
      """
    )
  )


def downgrade() -> None:
  op.drop_index('ix_trip_members_user_id', table_name='trip_members')
  op.drop_table('trip_members')
  op.drop_column('trips', 'visibility')
