"""Create approval-first workflow persistence.

Revision ID: 20260718_0001
Revises:
Create Date: 2026-07-18 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260718_0001"
down_revision = None
branch_labels = None
depends_on = None


work_item_kind = sa.Enum("bug", "feature", "failed_ci", name="work_item_kind")
project_connection_status = sa.Enum(
    "pending", "active", "revoked", name="project_connection_status"
)
work_item_status = sa.Enum(
    "draft",
    "snapshot_pinned",
    "plan_awaiting_approval",
    "patch_ready",
    "checks_queued",
    "checks_running",
    "review_ready",
    "pr_awaiting_approval",
    "complete",
    "failed",
    "cancelled",
    name="work_item_status",
)
run_stage = sa.Enum("plan", "patch", "checks", "pull_request", name="run_stage")
run_status = sa.Enum("queued", "running", "succeeded", "failed", "cancelled", name="run_status")
approval_action = sa.Enum("plan", "pull_request", name="approval_action")
approval_decision = sa.Enum("approved", "rejected", name="approval_decision")


def upgrade() -> None:
    bind = op.get_bind()
    for enum in (
        project_connection_status,
        work_item_kind,
        work_item_status,
        run_stage,
        run_status,
        approval_action,
        approval_decision,
    ):
        enum.create(bind, checkfirst=True)

    op.create_table(
        "repositories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_subject", sa.String(length=255), nullable=False),
        sa.Column("github_full_name", sa.String(length=255), nullable=False),
        sa.Column("default_branch", sa.String(length=255), nullable=False),
        sa.Column("connection_status", project_connection_status, nullable=False),
        sa.Column("github_installation_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_repositories"),
        sa.UniqueConstraint(
            "owner_subject", "github_full_name", name="uq_repositories_owner_full_name"
        ),
    )
    op.create_index(
        "ix_repositories_owner_subject", "repositories", ["owner_subject"], unique=False
    )
    op.create_index(
        "ix_repositories_owner_created",
        "repositories",
        ["owner_subject", "created_at"],
        unique=False,
    )

    op.create_table(
        "work_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=280), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("kind", work_item_kind, nullable=False),
        sa.Column("status", work_item_status, nullable=False),
        sa.Column("failed_ci_url", sa.String(length=500), nullable=True),
        sa.Column("base_commit_sha", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repositories.id"],
            name="fk_work_items_repository_id_repositories",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_work_items"),
    )
    op.create_index("ix_work_items_repository_id", "work_items", ["repository_id"], unique=False)
    op.create_index("ix_work_items_status", "work_items", ["status"], unique=False)
    op.create_index(
        "ix_work_items_repository_status", "work_items", ["repository_id", "status"], unique=False
    )

    op.create_table(
        "work_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("work_item_id", sa.Uuid(), nullable=False),
        sa.Column("stage", run_stage, nullable=False),
        sa.Column("status", run_status, nullable=False),
        sa.Column("is_current", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=True),
        sa.Column("base_commit_sha", sa.String(length=64), nullable=True),
        sa.Column("approval_artifact_sha256", sa.String(length=64), nullable=True),
        sa.Column("provider_response_id", sa.String(length=255), nullable=True),
        sa.Column("provider_output_items", sa.JSON(), nullable=True),
        sa.Column("provider_tool_call_ids", sa.JSON(), nullable=True),
        sa.Column("safety_identifier_hash", sa.String(length=64), nullable=True),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["work_item_id"],
            ["work_items.id"],
            name="fk_work_runs_work_item_id_work_items",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_work_runs"),
    )
    op.create_index("ix_work_runs_work_item_id", "work_runs", ["work_item_id"], unique=False)
    op.create_index("ix_work_runs_status", "work_runs", ["status"], unique=False)
    op.create_index(
        "ix_work_runs_work_item_stage_created",
        "work_runs",
        ["work_item_id", "stage", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_work_runs_work_item_stage_current",
        "work_runs",
        ["work_item_id", "stage", "is_current"],
        unique=False,
    )
    op.create_index(
        "uq_work_runs_current_stage",
        "work_runs",
        ["work_item_id", "stage"],
        unique=True,
        postgresql_where=sa.text("is_current"),
        sqlite_where=sa.text("is_current"),
    )

    op.create_table(
        "approvals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("action", approval_action, nullable=False),
        sa.Column("decision", approval_decision, nullable=False),
        sa.Column("actor_subject", sa.String(length=255), nullable=False),
        sa.Column("pinned_commit_sha", sa.String(length=64), nullable=False),
        sa.Column("artifact_sha256", sa.String(length=64), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["work_runs.id"], name="fk_approvals_run_id_work_runs", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_approvals"),
        sa.UniqueConstraint("run_id", "action", name="uq_approvals_run_action"),
    )
    op.create_index("ix_approvals_run_id", "approvals", ["run_id"], unique=False)

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_subject", sa.String(length=255), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_events"),
    )
    op.create_index(
        "ix_audit_events_actor_subject", "audit_events", ["actor_subject"], unique=False
    )
    op.create_index("ix_audit_events_entity_id", "audit_events", ["entity_id"], unique=False)
    op.create_index(
        "ix_audit_events_subject_created",
        "audit_events",
        ["actor_subject", "created_at"],
        unique=False,
    )

    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_subject", sa.String(length=255), nullable=False),
        sa.Column("scope", sa.String(length=160), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("response_body", sa.JSON(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_idempotency_records"),
        sa.UniqueConstraint("actor_subject", "scope", "key", name="uq_idempotency_actor_scope_key"),
    )
    op.create_index(
        "ix_idempotency_expires_at", "idempotency_records", ["expires_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_idempotency_expires_at", table_name="idempotency_records")
    op.drop_table("idempotency_records")
    op.drop_index("ix_audit_events_subject_created", table_name="audit_events")
    op.drop_index("ix_audit_events_entity_id", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_subject", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_approvals_run_id", table_name="approvals")
    op.drop_table("approvals")
    op.drop_index("uq_work_runs_current_stage", table_name="work_runs")
    op.drop_index("ix_work_runs_work_item_stage_current", table_name="work_runs")
    op.drop_index("ix_work_runs_work_item_stage_created", table_name="work_runs")
    op.drop_index("ix_work_runs_status", table_name="work_runs")
    op.drop_index("ix_work_runs_work_item_id", table_name="work_runs")
    op.drop_table("work_runs")
    op.drop_index("ix_work_items_repository_status", table_name="work_items")
    op.drop_index("ix_work_items_status", table_name="work_items")
    op.drop_index("ix_work_items_repository_id", table_name="work_items")
    op.drop_table("work_items")
    op.drop_index("ix_repositories_owner_created", table_name="repositories")
    op.drop_index("ix_repositories_owner_subject", table_name="repositories")
    op.drop_table("repositories")
    bind = op.get_bind()
    for enum in (
        approval_decision,
        approval_action,
        run_status,
        run_stage,
        work_item_status,
        work_item_kind,
        project_connection_status,
    ):
        enum.drop(bind, checkfirst=True)
