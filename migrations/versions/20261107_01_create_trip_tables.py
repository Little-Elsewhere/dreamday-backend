"""Create trips and trip_activities tables.

Revision ID: 20261107_01
Revises: 20261029_01
Create Date: 2026-11-07 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '20261107_01'
down_revision: str | None = '20261029_01'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
  op.create_table(
    'trips',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=40), server_default='', nullable=False),
    sa.Column(
      'destination',
      sa.String(length=40),
      server_default='',
      nullable=False,
    ),
    sa.Column(
      'description',
      sa.String(length=100),
      server_default='',
      nullable=False,
    ),
    sa.Column('start_date', sa.Date(), nullable=True),
    sa.Column('end_date', sa.Date(), nullable=True),
    sa.Column('pace', sa.String(length=16), nullable=True),
    sa.Column(
      'timezone',
      sa.String(length=64),
      server_default='Asia/Ho_Chi_Minh',
      nullable=False,
    ),
    sa.Column(
      'lifecycle',
      sa.String(length=16),
      server_default='draft',
      nullable=False,
    ),
    sa.Column('note', sa.Text(), server_default='', nullable=False),
    sa.Column('cover_path', sa.String(length=500), nullable=True),
    sa.Column('cover_url', sa.String(length=1000), nullable=True),
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
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(
      ['user_id'],
      ['users.id'],
      name='fk_trips_user_id_users',
      ondelete='CASCADE',
    ),
    sa.PrimaryKeyConstraint('id', name='pk_trips'),
  )
  op.create_index(
    'ix_trips_user_id_deleted_at',
    'trips',
    ['user_id', 'deleted_at'],
    unique=False,
  )
  op.create_index(
    'uq_trips_one_active_draft_per_user',
    'trips',
    ['user_id'],
    unique=True,
    postgresql_where=sa.text("lifecycle = 'draft' AND deleted_at IS NULL"),
  )

  op.create_table(
    'trip_activities',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('trip_id', sa.Uuid(), nullable=False),
    sa.Column('title', sa.String(length=80), nullable=False),
    sa.Column('activity_date', sa.Date(), nullable=False),
    sa.Column('activity_type', sa.String(length=16), nullable=False),
    sa.Column('start_minute', sa.Integer(), nullable=False),
    sa.Column('end_minute', sa.Integer(), nullable=False),
    sa.Column(
      'note',
      sa.String(length=500),
      server_default='',
      nullable=False,
    ),
    sa.Column(
      'deleted_with_trip',
      sa.Boolean(),
      server_default=sa.text('false'),
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
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(
      ['trip_id'],
      ['trips.id'],
      name='fk_trip_activities_trip_id_trips',
      ondelete='CASCADE',
    ),
    sa.PrimaryKeyConstraint('id', name='pk_trip_activities'),
  )
  op.create_index(
    'ix_trip_activities_trip_id_deleted_at',
    'trip_activities',
    ['trip_id', 'deleted_at'],
    unique=False,
  )


def downgrade() -> None:
  op.drop_index(
    'ix_trip_activities_trip_id_deleted_at',
    table_name='trip_activities',
  )
  op.drop_table('trip_activities')
  op.drop_index(
    'uq_trips_one_active_draft_per_user',
    table_name='trips',
  )
  op.drop_index('ix_trips_user_id_deleted_at', table_name='trips')
  op.drop_table('trips')
