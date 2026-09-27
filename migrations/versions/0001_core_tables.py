"""Core tables: conversation, message, job, draft, outbound_message, system_setting, audit_event.

Also creates the runtime role ``assistant_app`` (NOLOGIN) with DML on the core tables but only
SELECT/INSERT on ``audit_event``, and a trigger that refuses UPDATE/DELETE/TRUNCATE on
``audit_event`` for every role, including the owner. Creating the role needs CREATEROLE; roles are
cluster-wide, so downgrade leaves the role in place.

Revision ID: 0001
Revises:
Create Date: 2026-09-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "assistant_app"
DML_TABLES = ("conversation", "message", "job", "draft", "outbound_message", "system_setting")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _id() -> sa.Column[int]:
    return sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True)


def _ts(name: str, *, nullable: bool = True, now: bool = False) -> sa.Column[object]:
    default = sa.text("now()") if now else None
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable, server_default=default)


def upgrade() -> None:
    op.create_table(
        "conversation",
        _id(),
        sa.Column("avito_chat_id", sa.Text(), nullable=False, unique=True),
        sa.Column("counterpart_avito_id", sa.Text()),
        sa.Column("avito_item_id", sa.Text()),
        sa.Column("state", sa.Text(), nullable=False, server_default="new_request"),
        sa.Column("state_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("close_reason", sa.Text()),
        sa.Column("automation", sa.Text(), nullable=False, server_default="active"),
        sa.Column("paused_reason", sa.Text()),
        _ts("paused_at"),
        sa.Column("last_inbound_seq", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("last_processed_seq", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("language", sa.Text()),
        _ts("created_at", nullable=False, now=True),
        sa.CheckConstraint(
            _in(
                "state",
                (
                    "new_request",
                    "awaiting_info",
                    "researching",
                    "offer_presented",
                    "awaiting_selection",
                    "awaiting_confirmation",
                    "reservation_pending",
                    "completed",
                    "closed",
                ),
            ),
            name="ck_conversation_state",
        ),
        sa.CheckConstraint(
            "close_reason IS NULL OR "
            + _in("close_reason", ("customer_withdrew", "inactive", "owner_closed")),
            name="ck_conversation_close_reason",
        ),
        sa.CheckConstraint(
            _in("automation", ("active", "paused")), name="ck_conversation_automation"
        ),
    )

    op.create_table(
        "job",
        _id(),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("dedup_key", sa.Text(), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("status", sa.Text(), nullable=False, server_default="queued"),
        _ts("run_after", nullable=False, now=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("claimed_by", sa.Text()),
        _ts("claimed_at"),
        sa.Column("last_error_code", sa.Text()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        _ts("created_at", nullable=False, now=True),
        sa.CheckConstraint(
            _in("status", ("queued", "running", "done", "dead", "superseded")),
            name="ck_job_status",
        ),
    )
    # Uniqueness only while queued (§6.2): a running job never blocks a new queued one.
    op.create_index(
        "uq_job_queued_kind_dedup_key",
        "job",
        ["kind", "dedup_key"],
        unique=True,
        postgresql_where=sa.text("status = 'queued'"),
    )
    op.create_index(
        "ix_job_queued_run_after",
        "job",
        ["run_after"],
        postgresql_where=sa.text("status = 'queued'"),
    )

    op.create_table(
        "draft",
        _id(),
        sa.Column(
            "conversation_id", sa.BigInteger(), sa.ForeignKey("conversation.id"), nullable=False
        ),
        sa.Column("based_on_seq", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column(
            "parts",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "photo_ids",
            postgresql.ARRAY(sa.BigInteger()),
            nullable=False,
            server_default=sa.text("'{}'::bigint[]"),
        ),
        sa.Column("fact_sheet", postgresql.JSONB()),
        sa.Column(
            "used_fact_ids",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column("kb_release", sa.Integer()),
        sa.Column("prompt_version", sa.Text()),
        sa.Column("model_id", sa.Text()),
        sa.Column("filter_result", postgresql.JSONB()),
        sa.Column("status", sa.Text(), nullable=False, server_default="proposed"),
        sa.Column("owner_edit", sa.Text()),
        sa.Column("match_score", sa.Float()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        _ts("created_at", nullable=False, now=True),
        sa.CheckConstraint(
            _in(
                "status",
                (
                    "proposed",
                    "approved",
                    "rejected",
                    "stale",
                    "superseded",
                    "sent",
                    "sent_by_owner",
                ),
            ),
            name="ck_draft_status",
        ),
    )

    op.create_table(
        "outbound_message",
        _id(),
        sa.Column("idempotency_key", sa.Text(), nullable=False, unique=True),
        sa.Column("draft_id", sa.BigInteger(), sa.ForeignKey("draft.id"), nullable=False),
        sa.Column("part_no", sa.SmallInteger(), nullable=False),
        sa.Column("part_count", sa.SmallInteger(), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("body_text", sa.Text()),
        sa.Column("photo_id", sa.BigInteger()),
        sa.Column("text_norm_hash", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        _ts("intent_at"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avito_message_id", sa.Text(), unique=True),
        _ts("confirmed_at"),
        sa.Column("last_error_code", sa.Text()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        _ts("created_at", nullable=False, now=True),
        sa.CheckConstraint(
            _in(
                "status",
                ("pending", "sending", "sent", "unknown", "needs_owner", "failed", "cancelled"),
            ),
            name="ck_outbound_message_status",
        ),
        sa.CheckConstraint(_in("kind", ("text", "image")), name="ck_outbound_message_kind"),
        sa.CheckConstraint(
            "(kind = 'text' AND body_text IS NOT NULL) "
            "OR (kind = 'image' AND photo_id IS NOT NULL)",
            name="ck_outbound_message_body",
        ),
        sa.CheckConstraint("part_no BETWEEN 1 AND part_count", name="ck_outbound_message_part_no"),
        sa.UniqueConstraint(
            "draft_id", "generation", "part_no", name="uq_outbound_message_draft_generation_part"
        ),
    )

    op.create_table(
        "message",
        _id(),
        sa.Column("avito_message_id", sa.Text(), nullable=False, unique=True),
        sa.Column(
            "conversation_id", sa.BigInteger(), sa.ForeignKey("conversation.id"), nullable=False
        ),
        sa.Column("seq", sa.BigInteger(), nullable=False),
        sa.Column("author_role", sa.Text(), nullable=False),
        sa.Column("author_avito_id", sa.Text()),
        sa.Column("direction", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        _ts("created_at_avito"),
        sa.Column("content_masked", sa.Text()),
        sa.Column("raw_ref", sa.Text()),
        sa.Column("attachment_status", sa.Text(), nullable=False, server_default="none"),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("outbound_id", sa.BigInteger(), sa.ForeignKey("outbound_message.id")),
        _ts("created_at", nullable=False, now=True),
        sa.UniqueConstraint("conversation_id", "seq", name="uq_message_conversation_seq"),
        sa.CheckConstraint(
            _in("author_role", ("customer", "assistant", "owner_manual", "system", "unknown")),
            name="ck_message_author_role",
        ),
        sa.CheckConstraint(_in("direction", ("in", "out")), name="ck_message_direction"),
        sa.CheckConstraint(
            _in("attachment_status", ("none", "stored", "attachment_unavailable")),
            name="ck_message_attachment_status",
        ),
    )

    op.create_table(
        "system_setting",
        sa.Column("id", sa.SmallInteger(), primary_key=True, autoincrement=False),
        sa.Column("kill_switch", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("automation_mode", sa.Text(), nullable=False, server_default="draft_only"),
        _ts("activation_at"),
        sa.Column("images_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("id = 1", name="ck_system_setting_single_row"),
        sa.CheckConstraint(
            _in("automation_mode", ("draft_only", "approve_to_send")),
            name="ck_system_setting_mode",
        ),
    )
    op.execute("INSERT INTO system_setting (id) VALUES (1)")

    op.create_table(
        "audit_event",
        _id(),
        _ts("ts", nullable=False, now=True),
        sa.Column("op_id", sa.Text(), nullable=False),
        sa.Column("correlation_id", sa.Text()),
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column(
            "entity_ids",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("reason_code", sa.Text()),
        sa.Column("reason_short", sa.String(200)),
        sa.Column("result", sa.Text(), nullable=False),
        sa.Column("kb_release", sa.Integer()),
        sa.Column("prompt_version", sa.Text()),
        sa.CheckConstraint("char_length(reason_short) <= 200", name="ck_audit_event_reason_short"),
    )
    # Append-only for everyone, owner included (a superuser could still disable the trigger).
    op.execute(
        """
        CREATE FUNCTION audit_event_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'audit_event is append-only: % refused', TG_OP
                USING ERRCODE = 'insufficient_privilege';
        END
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER audit_event_no_update_delete BEFORE UPDATE OR DELETE ON audit_event "
        "FOR EACH ROW EXECUTE FUNCTION audit_event_append_only()"
    )
    op.execute(
        "CREATE TRIGGER audit_event_no_truncate BEFORE TRUNCATE ON audit_event "
        "FOR EACH STATEMENT EXECUTE FUNCTION audit_event_append_only()"
    )

    # Runtime role: the application's login role is granted membership in it (app/README.md).
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                CREATE ROLE {APP_ROLE} NOLOGIN;
            END IF;
        END
        $$
        """
    )
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {', '.join(DML_TABLES)} TO {APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT ON audit_event TO {APP_ROLE}")


def downgrade() -> None:
    for table in ("audit_event", "system_setting", "message", "outbound_message", "draft", "job"):
        op.drop_table(table)
    op.drop_table("conversation")
    op.execute("DROP FUNCTION audit_event_append_only()")
