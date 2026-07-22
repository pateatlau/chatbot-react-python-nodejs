"""0004 upload quota counters

Revision ID: 0004_upload_quota_counters
Revises: 0003_pgvector_embeddings
Create Date: 2026-07-22

Adds durable daily upload counters for authenticated document uploads (V1.1.1).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0004_upload_quota_counters"
down_revision: Union[str, None] = "0003_pgvector_embeddings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UUID = postgresql.UUID(as_uuid=True)
_NOW = sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "upload_quota_counters",
        sa.Column("user_id", _UUID, nullable=False),
        sa.Column("window_start", sa.Date(), nullable=False),
        sa.Column(
            "upload_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=_NOW,
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "user_id", "window_start", name="pk_upload_quota_counters"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_upload_quota_counters_user_id_users",
            ondelete="CASCADE",
        ),
    )


def downgrade() -> None:
    op.drop_table("upload_quota_counters")
