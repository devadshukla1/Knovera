"""Create research intelligence tables (Phase 10 C10.1, C10.2, C10.3).

Revision ID: 20261109_013
Revises: 20261108_012
Create Date: 2026-11-09 09:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20261109_013"
down_revision: Union[str, None] = "20261108_012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. research_analysis_runs
    op.create_table(
        "research_analysis_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("document_version", sa.String(length=50), server_default="v1.0", nullable=False),
        sa.Column("status", sa.String(length=40), server_default="queued", nullable=False),
        sa.Column("components_requested", sa.JSON(), nullable=False),
        sa.Column("metadata_status", sa.String(length=30), server_default="not_requested", nullable=False),
        sa.Column("objectives_status", sa.String(length=30), server_default="not_requested", nullable=False),
        sa.Column("methodology_status", sa.String(length=30), server_default="not_requested", nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("provider_used", sa.String(length=60), nullable=True),
        sa.Column("model_used", sa.String(length=100), nullable=True),
        sa.Column("prompt_version", sa.String(length=50), server_default="v1.0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_res_runs_ws_doc", "research_analysis_runs", ["workspace_id", "document_id"])
    op.create_index("ix_res_runs_ws_status", "research_analysis_runs", ["workspace_id", "status"])

    # 2. research_metadata_profiles (C10.1)
    op.create_table(
        "research_metadata_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("document_version", sa.String(length=50), server_default="v1.0", nullable=False),
        sa.Column("document_type", sa.String(length=60), server_default="unknown", nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("subtitle", sa.Text(), nullable=True),
        sa.Column("alternative_title", sa.Text(), nullable=True),
        sa.Column("language", sa.String(length=20), server_default="en", nullable=False),
        sa.Column("abstract", sa.Text(), nullable=True),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("authors", sa.JSON(), nullable=False),
        sa.Column("publication_year", sa.Integer(), nullable=True),
        sa.Column("publication_date", sa.String(length=50), nullable=True),
        sa.Column("journal_name", sa.String(length=255), nullable=True),
        sa.Column("conference_name", sa.String(length=255), nullable=True),
        sa.Column("publisher", sa.String(length=255), nullable=True),
        sa.Column("volume", sa.String(length=50), nullable=True),
        sa.Column("issue", sa.String(length=50), nullable=True),
        sa.Column("page_range", sa.String(length=50), nullable=True),
        sa.Column("doi", sa.String(length=120), nullable=True),
        sa.Column("arxiv_id", sa.String(length=60), nullable=True),
        sa.Column("isbn_issn", sa.String(length=60), nullable=True),
        sa.Column("publication_status", sa.String(length=60), nullable=True),
        sa.Column("funding_organization", sa.Text(), nullable=True),
        sa.Column("acknowledgements", sa.Text(), nullable=True),
        sa.Column("grant_identifiers", sa.JSON(), nullable=False),
        sa.Column("research_domain", sa.String(length=100), nullable=True),
        sa.Column("subdomain", sa.String(length=100), nullable=True),
        sa.Column("metadata_fields", sa.JSON(), nullable=False),
        sa.Column("conflicts", sa.JSON(), nullable=False),
        sa.Column("validation_status", sa.String(length=30), server_default="validated", nullable=False),
        sa.Column("is_manually_edited", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["research_analysis_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_res_meta_ws_doc", "research_metadata_profiles", ["workspace_id", "document_id"])
    op.create_index("ix_res_meta_doc_type", "research_metadata_profiles", ["document_type"])
    op.create_index("ix_res_meta_doi", "research_metadata_profiles", ["doi"])
    op.create_index("ix_res_meta_year", "research_metadata_profiles", ["publication_year"])

    # 3. research_objective_profiles (C10.2)
    op.create_table(
        "research_objective_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("document_version", sa.String(length=50), server_default="v1.0", nullable=False),
        sa.Column("primary_objective", sa.Text(), nullable=True),
        sa.Column("problem_statement", sa.Text(), nullable=True),
        sa.Column("motivation", sa.Text(), nullable=True),
        sa.Column("research_scope", sa.JSON(), nullable=False),
        sa.Column("objectives", sa.JSON(), nullable=False),
        sa.Column("research_questions", sa.JSON(), nullable=False),
        sa.Column("hypotheses", sa.JSON(), nullable=False),
        sa.Column("claimed_contributions", sa.JSON(), nullable=False),
        sa.Column("validation_status", sa.String(length=30), server_default="validated", nullable=False),
        sa.Column("is_manually_edited", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["research_analysis_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_res_obj_ws_doc", "research_objective_profiles", ["workspace_id", "document_id"])

    # 4. research_methodology_profiles (C10.3)
    op.create_table(
        "research_methodology_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("document_version", sa.String(length=50), server_default="v1.0", nullable=False),
        sa.Column("research_approaches", sa.JSON(), nullable=False),
        sa.Column("research_designs", sa.JSON(), nullable=False),
        sa.Column("study_setting", sa.Text(), nullable=True),
        sa.Column("datasets", sa.JSON(), nullable=False),
        sa.Column("variables", sa.JSON(), nullable=False),
        sa.Column("methods_and_models", sa.JSON(), nullable=False),
        sa.Column("tools_and_instruments", sa.JSON(), nullable=False),
        sa.Column("experimental_setup", sa.JSON(), nullable=False),
        sa.Column("evaluation_metrics", sa.JSON(), nullable=False),
        sa.Column("limitations", sa.JSON(), nullable=False),
        sa.Column("validation_status", sa.String(length=30), server_default="validated", nullable=False),
        sa.Column("is_manually_edited", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["research_analysis_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_res_meth_ws_doc", "research_methodology_profiles", ["workspace_id", "document_id"])


def downgrade() -> None:
    op.drop_table("research_methodology_profiles")
    op.drop_table("research_objective_profiles")
    op.drop_table("research_metadata_profiles")
    op.drop_table("research_analysis_runs")
