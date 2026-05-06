"""add google for jobs fields

Revision ID: 20260506_google_jobs
Revises: 20260506_job_dist
Create Date: 2026-05-06
"""

from alembic import op
import sqlalchemy as sa


revision = "20260506_google_jobs"
down_revision = "20260506_job_dist"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("job_descriptions", sa.Column("company_website_url", sa.String(length=500), nullable=True))
    op.add_column("job_descriptions", sa.Column("company_logo_url", sa.String(length=1000), nullable=True))
    op.add_column("job_descriptions", sa.Column("industry", sa.String(length=255), nullable=True))
    op.add_column("job_descriptions", sa.Column("valid_through", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("job_descriptions", "valid_through")
    op.drop_column("job_descriptions", "industry")
    op.drop_column("job_descriptions", "company_logo_url")
    op.drop_column("job_descriptions", "company_website_url")
