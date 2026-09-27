"""Core tables (docs/ARCHITECTURE.md §5): conversation, message, job, draft, outbound_message,
system_setting, audit_event. Other tables arrive with the tasks that use them (§14).

Status columns are ``text`` with CHECK constraints (not PostgreSQL enums) so later migrations can
add values without ``ALTER TYPE``. Every table with a status has a version column for CAS (§1.4);
``conversation`` calls it ``state_version`` as in §5.

The migration in ``migrations/versions`` is written by hand and must stay equal to these models;
``tests/db/test_migration.py`` compares them.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

CONVERSATION_STATES = (
    "new_request",
    "awaiting_info",
    "researching",
    "offer_presented",
    "awaiting_selection",
    "awaiting_confirmation",
    "reservation_pending",
    "completed",
    "closed",
)
CLOSE_REASONS = ("customer_withdrew", "inactive", "owner_closed")
AUTOMATION_STATES = ("active", "paused")
AUTHOR_ROLES = ("customer", "assistant", "owner_manual", "system", "unknown")
DIRECTIONS = ("in", "out")
ATTACHMENT_STATUSES = ("none", "stored", "attachment_unavailable")
JOB_STATUSES = ("queued", "running", "done", "dead", "superseded")
DRAFT_STATUSES = (
    "proposed",
    "approved",
    "rejected",
    "stale",
    "superseded",
    "sent",
    "sent_by_owner",
)
OUTBOUND_STATUSES = (
    "pending",
    "sending",
    "sent",
    "unknown",
    "needs_owner",
    "failed",
    "cancelled",
)
OUTBOUND_KINDS = ("text", "image")
# Pilot modes only (MA-2); ``auto_scoped`` is post-pilot (§15).
SYSTEM_AUTOMATION_MODES = ("draft_only", "approve_to_send")


def _in(column: str, values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({quoted})"


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Base(DeclarativeBase):
    pass


class Conversation(Base):
    __tablename__ = "conversation"
    __table_args__ = (
        CheckConstraint(_in("state", CONVERSATION_STATES), name="ck_conversation_state"),
        CheckConstraint(
            f"close_reason IS NULL OR {_in('close_reason', CLOSE_REASONS)}",
            name="ck_conversation_close_reason",
        ),
        CheckConstraint(_in("automation", AUTOMATION_STATES), name="ck_conversation_automation"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    avito_chat_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    counterpart_avito_id: Mapped[str | None] = mapped_column(Text)
    avito_item_id: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text, nullable=False, server_default="new_request")
    state_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    close_reason: Mapped[str | None] = mapped_column(Text)
    automation: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
    paused_reason: Mapped[str | None] = mapped_column(Text)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Seq of the newest customer message; drafts and send intents are fenced on it (§6.1, §6.5).
    last_inbound_seq: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    last_processed_seq: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    language: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()


class Message(Base):
    __tablename__ = "message"
    __table_args__ = (
        UniqueConstraint("conversation_id", "seq", name="uq_message_conversation_seq"),
        CheckConstraint(_in("author_role", AUTHOR_ROLES), name="ck_message_author_role"),
        CheckConstraint(_in("direction", DIRECTIONS), name="ck_message_direction"),
        CheckConstraint(
            _in("attachment_status", ATTACHMENT_STATUSES), name="ck_message_attachment_status"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    # Dedup key for webhook, poller and history import (§6.3).
    avito_message_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversation.id"), nullable=False)
    seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    author_role: Mapped[str] = mapped_column(Text, nullable=False)
    author_avito_id: Mapped[str | None] = mapped_column(Text)
    direction: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    created_at_avito: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content_masked: Mapped[str | None] = mapped_column(Text)
    raw_ref: Mapped[str | None] = mapped_column(Text)
    attachment_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="none")
    source: Mapped[str] = mapped_column(Text, nullable=False)
    outbound_id: Mapped[int | None] = mapped_column(ForeignKey("outbound_message.id"))
    created_at: Mapped[datetime] = _created_at()


class Job(Base):
    __tablename__ = "job"
    __table_args__ = (
        CheckConstraint(_in("status", JOB_STATUSES), name="ck_job_status"),
        # Uniqueness only while queued (§6.2): a running job never blocks a new queued one.
        Index(
            "uq_job_queued_kind_dedup_key",
            "kind",
            "dedup_key",
            unique=True,
            postgresql_where=text("status = 'queued'"),
        ),
        Index("ix_job_queued_run_after", "run_after", postgresql_where=text("status = 'queued'")),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    dedup_key: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="queued")
    run_after: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="8")
    claimed_by: Mapped[str | None] = mapped_column(Text)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = _created_at()


class Draft(Base):
    __tablename__ = "draft"
    __table_args__ = (CheckConstraint(_in("status", DRAFT_STATUSES), name="ck_draft_status"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversation.id"), nullable=False)
    based_on_seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    # Final rendered parts (<= 1000 chars each; enforced by the renderer/filter, §7.2).
    parts: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )
    photo_ids: Mapped[list[int]] = mapped_column(
        ARRAY(BigInteger), nullable=False, server_default=text("'{}'::bigint[]")
    )
    fact_sheet: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    used_fact_ids: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )
    kb_release: Mapped[int | None] = mapped_column(Integer)
    prompt_version: Mapped[str | None] = mapped_column(Text)
    model_id: Mapped[str | None] = mapped_column(Text)
    filter_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="proposed")
    owner_edit: Mapped[str | None] = mapped_column(Text)
    match_score: Mapped[float | None] = mapped_column(Float)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = _created_at()


class OutboundMessage(Base):
    __tablename__ = "outbound_message"
    __table_args__ = (
        CheckConstraint(_in("status", OUTBOUND_STATUSES), name="ck_outbound_message_status"),
        CheckConstraint(_in("kind", OUTBOUND_KINDS), name="ck_outbound_message_kind"),
        CheckConstraint(
            "(kind = 'text' AND body_text IS NOT NULL) "
            "OR (kind = 'image' AND photo_id IS NOT NULL)",
            name="ck_outbound_message_body",
        ),
        CheckConstraint("part_no BETWEEN 1 AND part_count", name="ck_outbound_message_part_no"),
        UniqueConstraint(
            "draft_id", "generation", "part_no", name="uq_outbound_message_draft_generation_part"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    # hash(draft_id, part_no, generation), computed by the outbox (T-025).
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("draft.id"), nullable=False)
    part_no: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    part_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    generation: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    body_text: Mapped[str | None] = mapped_column(Text)
    photo_id: Mapped[int | None] = mapped_column(BigInteger)
    text_norm_hash: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    intent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    avito_message_id: Mapped[str | None] = mapped_column(Text, unique=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = _created_at()


class SystemSetting(Base):
    """Single-row table (``id = 1``). Seeded by the initial migration."""

    __tablename__ = "system_setting"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_system_setting_single_row"),
        CheckConstraint(
            _in("automation_mode", SYSTEM_AUTOMATION_MODES), name="ck_system_setting_mode"
        ),
    )

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False)
    kill_switch: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    automation_mode: Mapped[str] = mapped_column(Text, nullable=False, server_default="draft_only")
    activation_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    images_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")


class AuditEvent(Base):
    """Append-only (AGENTS.md §7). Ids and codes only: no message text, contacts or reasoning."""

    __tablename__ = "audit_event"
    __table_args__ = (
        CheckConstraint("char_length(reason_short) <= 200", name="ck_audit_event_reason_short"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    op_id: Mapped[str] = mapped_column(Text, nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(Text)
    actor: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    entity_ids: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    reason_code: Mapped[str | None] = mapped_column(Text)
    reason_short: Mapped[str | None] = mapped_column(String(200))
    result: Mapped[str] = mapped_column(Text, nullable=False)
    kb_release: Mapped[int | None] = mapped_column(Integer)
    prompt_version: Mapped[str | None] = mapped_column(Text)
