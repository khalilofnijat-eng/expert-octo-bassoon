"""Core tables (docs/ARCHITECTURE.md §5): conversation, message, job, draft, outbound_message,
system_setting, audit_event. Other tables arrive with the tasks that use them (§14).

Status columns are ``text`` with CHECK constraints (not PostgreSQL enums) so later migrations can
add values without ``ALTER TYPE``. Every table with a status has a version column for CAS (§1.4);
``conversation`` calls it ``state_version`` as in §5.

The migration in ``migrations/versions`` is written by hand and must stay equal to these models;
``tests/db/test_db_migration.py`` compares them.
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
# Every paused(...) reason named in ARCHITECTURE rev.2 (§4.4, §6.3-§6.13, MA-4).
PAUSED_REASONS = (
    "owner_takeover",
    "owner_intervened",
    "owner_modified",
    "send_unknown",
    "group_incomplete",
    "unknown_author",
    "unsupported_content",
    "llm_outage",
    "budget",
    "restore_gap",
)
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
        CheckConstraint(
            f"paused_reason IS NULL OR {_in('paused_reason', PAUSED_REASONS)}",
            name="ck_conversation_paused_reason",
        ),
        CheckConstraint(
            "automation <> 'paused' OR paused_reason IS NOT NULL",
            name="ck_conversation_paused_has_reason",
        ),
        # A close reason exactly when closed (and never otherwise).
        CheckConstraint(
            "(state = 'closed') = (close_reason IS NOT NULL)",
            name="ck_conversation_closed_reason",
        ),
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
    # 12 claims: the backoff reaches its 1 h cap (app.queue.jobs.backoff_seconds).
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="12")
    claimed_by: Mapped[str | None] = mapped_column(Text)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = _created_at()


class Draft(Base):
    __tablename__ = "draft"
    __table_args__ = (
        CheckConstraint(_in("status", DRAFT_STATUSES), name="ck_draft_status"),
        # One open draft per (conversation, seq): a job re-run after a crash cannot add a second
        # one (app.db.writes.insert_draft_fenced is idempotent on this index).
        Index(
            "uq_draft_open_per_seq",
            "conversation_id",
            "based_on_seq",
            unique=True,
            postgresql_where=text("status IN ('proposed', 'approved')"),
        ),
        Index("ix_draft_conversation_id", "conversation_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversation.id"), nullable=False)
    based_on_seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    # Final rendered parts. No DB CHECK on part length on purpose: the limit is measured in
    # UTF-16 units by the output filter (app.safety.filter, FilterConfig.max_part_units,
    # reason PART_TOO_LONG) before a draft is written, and SQL char_length would count differently.
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
        Index("ix_outbound_message_status", "status"),
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
    """Single-row table (``id = 1``), the runtime source of truth for these settings. Seeded by
    the initial migration with ``kill_switch = true`` (nothing is sent until the owner turns it
    off) and ``automation_mode`` from the ``AUTOMATION_MODE`` environment value."""

    __tablename__ = "system_setting"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_system_setting_single_row"),
        CheckConstraint(
            _in("automation_mode", SYSTEM_AUTOMATION_MODES), name="ck_system_setting_mode"
        ),
    )

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False)
    kill_switch: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    automation_mode: Mapped[str] = mapped_column(Text, nullable=False, server_default="draft_only")
    activation_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    images_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")


class WorkerSingleton(Base):
    """Single-row table (``id = 1``): the epoch of the current worker singleton (§6.1, Y5).

    Each worker increments ``epoch`` right after taking advisory lock (1, 0). Fenced writes check
    the epoch as well as the backend pid, so a reused pid cannot pass for an old worker.
    """

    __tablename__ = "worker_singleton"
    __table_args__ = (CheckConstraint("id = 1", name="ck_worker_singleton_single_row"),)

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False)
    epoch: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    pid: Mapped[int | None] = mapped_column(Integer)
    acquired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditEvent(Base):
    """Append-only (AGENTS.md §7). Ids and codes only: no message text, contacts or reasoning.

    Enforced by privileges (the runtime role has SELECT/INSERT only) and by a trigger. The trigger
    alone is not enough: the table owner, not only a superuser, can disable it. The application
    therefore never connects as the owner (app.db.roles, app/README.md).
    """

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


# --- Catalog and stock (T-022, ARCHITECTURE §5 "Katalog ve stok") ---------------------------
# Field meanings that depend on the owner's warehouse system are pending B-002. Every row
# carries data_origin/source/fetched_at and a verification time. Synthetic rows are labelled:
# data_origin='synthetic' iff the SKU starts with 'SYN-' (product) or the photo key is a
# 'synthetic://' placeholder (photo). Migration: migrations/versions/0002_catalog_inventory.py.

DATA_ORIGINS = ("real", "synthetic")
PRODUCT_CONDITIONS = ("new", "used")
SET_KINDS = ("single", "virtual_set", "stocked_set")
FITMENT_STATUSES = ("verified", "needs_verification", "incompatible")
# Kinds that can make a fitment row 'verified' (app.catalog.types.QUALIFYING_EVIDENCE_KINDS).
QUALIFYING_EVIDENCE_TYPES = ("oem_catalog", "manufacturer_doc", "owner_confirmed")
EVIDENCE_TYPES = (
    *QUALIFYING_EVIDENCE_TYPES,
    "synthetic_fixture",
    "visual_similarity",
    "customer_statement",
    "llm_output",
    "listing_title",
    "body_code_only",
)


def _origin_check(table: str) -> CheckConstraint:
    return CheckConstraint(_in("data_origin", DATA_ORIGINS), name=f"ck_{table}_data_origin")


def _fetched_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False)


class Product(Base):
    __tablename__ = "product"
    __table_args__ = (
        UniqueConstraint("source", "sku", name="uq_product_source_sku"),
        CheckConstraint(_in("condition", PRODUCT_CONDITIONS), name="ck_product_condition"),
        CheckConstraint(_in("set_kind", SET_KINDS), name="ck_product_set_kind"),
        _origin_check("product"),
        CheckConstraint(
            "(data_origin = 'synthetic') = (sku LIKE 'SYN-%')", name="ck_product_synthetic_sku"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    sku: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    brand: Mapped[str | None] = mapped_column(Text)
    part_type: Mapped[str] = mapped_column(Text, nullable=False)
    condition: Mapped[str] = mapped_column(Text, nullable=False)
    color: Mapped[str | None] = mapped_column(Text)
    condition_notes: Mapped[str | None] = mapped_column(Text)
    set_kind: Mapped[str] = mapped_column(Text, nullable=False, server_default="single")
    data_origin: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime] = _fetched_at()
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = _created_at()


class ProductOemNumber(Base):
    """OEM/part numbers as written by the source plus a normalised form for search."""

    __tablename__ = "product_oem_number"
    __table_args__ = (
        UniqueConstraint("product_id", "oem_number_norm", name="uq_product_oem_number"),
        Index("ix_product_oem_number_norm", "oem_number_norm"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("product.id", ondelete="CASCADE"), nullable=False
    )
    oem_number: Mapped[str] = mapped_column(Text, nullable=False)
    oem_number_norm: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created_at()


class VehicleSpec(Base):
    """Vehicle applicability range. facelift: false = pre-facelift, true = facelift, NULL = the
    range does not distinguish."""

    __tablename__ = "vehicle_spec"
    __table_args__ = (
        CheckConstraint(
            "year_from IS NULL OR year_to IS NULL OR year_from <= year_to",
            name="ck_vehicle_spec_years",
        ),
        _origin_check("vehicle_spec"),
        Index("ix_vehicle_spec_chassis_code", "chassis_code"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    make: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    chassis_code: Mapped[str] = mapped_column(Text, nullable=False)
    year_from: Mapped[int | None] = mapped_column(SmallInteger)
    year_to: Mapped[int | None] = mapped_column(SmallInteger)
    facelift: Mapped[bool | None] = mapped_column(Boolean)
    data_origin: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()


_VERIFIED_EVIDENCE_SQL = (
    "status <> 'verified' OR ("
    "evidence_ref IS NOT NULL AND btrim(evidence_ref) <> '' AND verified_at IS NOT NULL AND ("
    f"{_in('evidence_type', QUALIFYING_EVIDENCE_TYPES)} "
    "OR (evidence_type = 'synthetic_fixture' AND data_origin = 'synthetic')))"
)


class Fitment(Base):
    """Stored fitment statement; the engine (app.catalog.fitment) turns rows into verdicts.
    conditions: equipment/variant requirements, e.g. {"trim_line": "amg_line",
    "parktronic_sensors": 6}. 'verified' needs a qualifying evidence type, a reference and a
    verification time; 'synthetic_fixture' evidence is allowed only on synthetic rows."""

    __tablename__ = "fitment"
    __table_args__ = (
        CheckConstraint(_in("status", FITMENT_STATUSES), name="ck_fitment_status"),
        CheckConstraint(
            f"evidence_type IS NULL OR {_in('evidence_type', EVIDENCE_TYPES)}",
            name="ck_fitment_evidence_type",
        ),
        CheckConstraint(_VERIFIED_EVIDENCE_SQL, name="ck_fitment_verified_evidence"),
        CheckConstraint(
            "evidence_type IS DISTINCT FROM 'synthetic_fixture' OR data_origin = 'synthetic'",
            name="ck_fitment_synthetic_evidence",
        ),
        CheckConstraint("jsonb_typeof(conditions) = 'object'", name="ck_fitment_conditions"),
        _origin_check("fitment"),
        UniqueConstraint("source", "source_ref", name="uq_fitment_source_ref"),
        Index("ix_fitment_product_id", "product_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), nullable=False)
    vehicle_spec_id: Mapped[int] = mapped_column(ForeignKey("vehicle_spec.id"), nullable=False)
    conditions: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_type: Mapped[str | None] = mapped_column(Text)
    evidence_ref: Mapped[str | None] = mapped_column(Text)
    verified_by: Mapped[str | None] = mapped_column(Text)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    data_origin: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime] = _fetched_at()
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = _created_at()


class SetComponent(Base):
    """Set → component lines. present=false: the stocked kit lacks this component (only
    meaningful for set_kind='stocked_set'; a virtual set derives missing items from stock)."""

    __tablename__ = "set_component"
    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_set_component_qty"),
        CheckConstraint("set_product_id <> component_product_id", name="ck_set_component_not_self"),
        _origin_check("set_component"),
    )

    set_product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), primary_key=True)
    component_product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), primary_key=True)
    qty: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    present: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    optional: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    data_origin: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created_at()


class InventoryItem(Base):
    """Stock line per location, as last read from the warehouse system. available_qty is the
    sellable quantity reported by the source (B-002); held_qty is our local hold (T-027,
    §6.7: hold only if available_qty - held_qty >= qty)."""

    __tablename__ = "inventory_item"
    __table_args__ = (
        CheckConstraint("physical_qty >= 0", name="ck_inventory_item_physical_qty"),
        CheckConstraint(
            "external_reserved_qty >= 0", name="ck_inventory_item_external_reserved_qty"
        ),
        CheckConstraint("available_qty >= 0", name="ck_inventory_item_available_qty"),
        CheckConstraint("held_qty >= 0", name="ck_inventory_item_held_qty"),
        _origin_check("inventory_item"),
        UniqueConstraint("source", "source_ref", name="uq_inventory_item_source_ref"),
        Index("ix_inventory_item_product_id", "product_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), nullable=False)
    location: Mapped[str | None] = mapped_column(Text)
    physical_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    external_reserved_qty: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    available_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    held_qty: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    data_origin: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime] = _fetched_at()
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = _created_at()


class Price(Base):
    """Price in integer minor units. discount_rule_key names the business_rule holding the
    allowed discount; the discount value itself is never stored here (§9.2)."""

    __tablename__ = "price"
    __table_args__ = (
        CheckConstraint("amount_minor >= 0", name="ck_price_amount_minor"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_price_currency"),
        _origin_check("price"),
        Index("ix_price_product_id_fetched_at", "product_id", "fetched_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), nullable=False)
    inventory_item_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_item.id"))
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False)
    discount_rule_key: Mapped[str | None] = mapped_column(Text)
    data_origin: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime] = _fetched_at()
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created_at()


class Photo(Base):
    """Photo reference of one stock record (§8): never a product-level or listing image.
    storage_uri is a key, not image bytes; synthetic rows use 'synthetic://' placeholders."""

    __tablename__ = "photo"
    __table_args__ = (
        _origin_check("photo"),
        CheckConstraint(
            "(data_origin = 'synthetic') = (storage_uri LIKE 'synthetic://%')",
            name="ck_photo_synthetic_uri",
        ),
        UniqueConstraint("inventory_item_id", "storage_uri", name="uq_photo_item_uri"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    inventory_item_id: Mapped[int] = mapped_column(ForeignKey("inventory_item.id"), nullable=False)
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    data_origin: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime] = _fetched_at()
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created_at()
