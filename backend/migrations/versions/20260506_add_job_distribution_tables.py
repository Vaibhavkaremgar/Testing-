"""add job distribution tables

Revision ID: 20260506_job_dist
Revises: 20260406_perf_idx
Create Date: 2026-05-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260506_job_dist"
down_revision = "20260406_perf_idx"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_portals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("portal_name", sa.String(length=100), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("feed_url", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("portal_name", name="uq_job_portals_portal_name"),
    )
    op.create_index("idx_job_portals_enabled", "job_portals", ["is_enabled"], unique=False)

    op.create_table(
        "job_distribution_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("portal_name", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_job_distribution_logs_job_id",
        "job_distribution_logs",
        ["job_id"],
        unique=False,
    )
    op.create_index(
        "idx_job_distribution_logs_portal_status",
        "job_distribution_logs",
        ["portal_name", "status"],
        unique=False,
    )
    op.create_index(
        "idx_job_distribution_logs_posted_at",
        "job_distribution_logs",
        ["posted_at"],
        unique=False,
    )

    op.create_table(
        "job_portal_mapping",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("portal_name", sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["job_descriptions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "portal_name", name="uq_job_portal_mapping_job_portal"),
    )
    op.create_index(
        "idx_job_portal_mapping_portal_name",
        "job_portal_mapping",
        ["portal_name"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_job_portal_mapping_portal_name", table_name="job_portal_mapping")
    op.drop_table("job_portal_mapping")

    op.drop_index("idx_job_distribution_logs_posted_at", table_name="job_distribution_logs")
    op.drop_index("idx_job_distribution_logs_portal_status", table_name="job_distribution_logs")
    op.drop_index("idx_job_distribution_logs_job_id", table_name="job_distribution_logs")
    op.drop_table("job_distribution_logs")

    op.drop_index("idx_job_portals_enabled", table_name="job_portals")
    op.drop_table("job_portals")
