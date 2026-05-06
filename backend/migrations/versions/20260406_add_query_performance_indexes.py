"""add query performance indexes

Revision ID: 20260406_perf_idx
Revises:
Create Date: 2026-04-06
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260406_perf_idx"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("idx_candidates_agency_id", "candidates", ["agency_id"], unique=False)
    op.create_index("idx_candidates_job_id", "candidates", ["job_id"], unique=False)
    op.create_index("idx_candidates_stage", "candidates", ["stage"], unique=False)
    op.create_index("idx_candidates_assigned_to_user_id", "candidates", ["assigned_to_user_id"], unique=False)
    op.create_index("idx_candidates_created_at", "candidates", ["created_at"], unique=False)
    op.create_index("idx_candidates_agency_id_job_id", "candidates", ["agency_id", "job_id"], unique=False)
    op.create_index("idx_candidates_agency_id_stage", "candidates", ["agency_id", "stage"], unique=False)

    op.create_index("idx_interviews_agency_id", "interviews", ["agency_id"], unique=False)
    op.create_index("idx_interviews_candidate_id", "interviews", ["candidate_id"], unique=False)
    op.create_index("idx_interviews_scheduled_at", "interviews", ["scheduled_at"], unique=False)
    op.create_index("idx_interviews_status", "interviews", ["status"], unique=False)
    op.create_index("idx_interviews_agency_id_status", "interviews", ["agency_id", "status"], unique=False)
    op.create_index("idx_interviews_candidate_id_scheduled_at", "interviews", ["candidate_id", "scheduled_at"], unique=False)

    op.create_index("idx_job_descriptions_agency_id", "job_descriptions", ["agency_id"], unique=False)
    op.create_index("idx_job_descriptions_is_active", "job_descriptions", ["is_active"], unique=False)
    op.create_index("idx_job_descriptions_agency_id_is_active", "job_descriptions", ["agency_id", "is_active"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_job_descriptions_agency_id_is_active", table_name="job_descriptions")
    op.drop_index("idx_job_descriptions_is_active", table_name="job_descriptions")
    op.drop_index("idx_job_descriptions_agency_id", table_name="job_descriptions")

    op.drop_index("idx_interviews_candidate_id_scheduled_at", table_name="interviews")
    op.drop_index("idx_interviews_agency_id_status", table_name="interviews")
    op.drop_index("idx_interviews_status", table_name="interviews")
    op.drop_index("idx_interviews_scheduled_at", table_name="interviews")
    op.drop_index("idx_interviews_candidate_id", table_name="interviews")
    op.drop_index("idx_interviews_agency_id", table_name="interviews")

    op.drop_index("idx_candidates_agency_id_stage", table_name="candidates")
    op.drop_index("idx_candidates_agency_id_job_id", table_name="candidates")
    op.drop_index("idx_candidates_created_at", table_name="candidates")
    op.drop_index("idx_candidates_assigned_to_user_id", table_name="candidates")
    op.drop_index("idx_candidates_stage", table_name="candidates")
    op.drop_index("idx_candidates_job_id", table_name="candidates")
    op.drop_index("idx_candidates_agency_id", table_name="candidates")
