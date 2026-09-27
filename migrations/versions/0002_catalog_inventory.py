"""Catalog and stock tables (T-022): product, product_oem_number, vehicle_spec, fitment,
set_component, inventory_item, price, photo.

Field meanings that depend on the owner's warehouse system are pending B-002. Key constraints:
a 'verified' fitment needs a qualifying evidence type (oem_catalog, manufacturer_doc,
owner_confirmed) with a reference and a verification time, or 'synthetic_fixture' evidence on a
synthetic row; synthetic rows are labelled (SYN- SKU, synthetic:// photo keys); photos belong to
a stock record. The runtime role ``assistant_app`` (0001) gets DML on the new tables.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "assistant_app"
TABLES = (
    "product",
    "product_oem_number",
    "vehicle_spec",
    "fitment",
    "set_component",
    "inventory_item",
    "price",
    "photo",
)
DATA_ORIGINS = ("real", "synthetic")
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


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _id() -> sa.Column[int]:
    return sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True)


def _ts(name: str, *, nullable: bool = True, now: bool = False) -> sa.Column[object]:
    default = sa.text("now()") if now else None
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable, server_default=default)


def _origin(table: str) -> tuple[sa.Column[str], sa.CheckConstraint]:
    return (
        sa.Column("data_origin", sa.Text(), nullable=False),
        sa.CheckConstraint(_in("data_origin", DATA_ORIGINS), name=f"ck_{table}_data_origin"),
    )


def upgrade() -> None:
    op.create_table(
        "product",
        _id(),
        sa.Column("sku", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("brand", sa.Text()),
        sa.Column("part_type", sa.Text(), nullable=False),
        sa.Column("condition", sa.Text(), nullable=False),
        sa.Column("color", sa.Text()),
        sa.Column("condition_notes", sa.Text()),
        sa.Column("set_kind", sa.Text(), nullable=False, server_default="single"),
        *_origin("product"),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_ref", sa.Text()),
        _ts("fetched_at", nullable=False),
        _ts("last_verified_at"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        _ts("created_at", nullable=False, now=True),
        sa.UniqueConstraint("source", "sku", name="uq_product_source_sku"),
        sa.CheckConstraint(_in("condition", ("new", "used")), name="ck_product_condition"),
        sa.CheckConstraint(
            _in("set_kind", ("single", "virtual_set", "stocked_set")), name="ck_product_set_kind"
        ),
        sa.CheckConstraint(
            "(data_origin = 'synthetic') = (sku LIKE 'SYN-%')", name="ck_product_synthetic_sku"
        ),
    )

    op.create_table(
        "product_oem_number",
        _id(),
        sa.Column(
            "product_id",
            sa.BigInteger(),
            sa.ForeignKey("product.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("oem_number", sa.Text(), nullable=False),
        sa.Column("oem_number_norm", sa.Text(), nullable=False),
        _ts("created_at", nullable=False, now=True),
        sa.UniqueConstraint("product_id", "oem_number_norm", name="uq_product_oem_number"),
    )
    op.create_index("ix_product_oem_number_norm", "product_oem_number", ["oem_number_norm"])

    op.create_table(
        "vehicle_spec",
        _id(),
        sa.Column("make", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("chassis_code", sa.Text(), nullable=False),
        sa.Column("year_from", sa.SmallInteger()),
        sa.Column("year_to", sa.SmallInteger()),
        sa.Column("facelift", sa.Boolean()),
        *_origin("vehicle_spec"),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_ref", sa.Text()),
        _ts("created_at", nullable=False, now=True),
        sa.CheckConstraint(
            "year_from IS NULL OR year_to IS NULL OR year_from <= year_to",
            name="ck_vehicle_spec_years",
        ),
    )
    op.create_index("ix_vehicle_spec_chassis_code", "vehicle_spec", ["chassis_code"])

    op.create_table(
        "fitment",
        _id(),
        sa.Column("product_id", sa.BigInteger(), sa.ForeignKey("product.id"), nullable=False),
        sa.Column(
            "vehicle_spec_id", sa.BigInteger(), sa.ForeignKey("vehicle_spec.id"), nullable=False
        ),
        sa.Column(
            "conditions",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("evidence_type", sa.Text()),
        sa.Column("evidence_ref", sa.Text()),
        sa.Column("verified_by", sa.Text()),
        _ts("verified_at"),
        *_origin("fitment"),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_ref", sa.Text()),
        _ts("fetched_at", nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        _ts("created_at", nullable=False, now=True),
        sa.CheckConstraint(
            _in("status", ("verified", "needs_verification", "incompatible")),
            name="ck_fitment_status",
        ),
        sa.CheckConstraint(
            f"evidence_type IS NULL OR {_in('evidence_type', EVIDENCE_TYPES)}",
            name="ck_fitment_evidence_type",
        ),
        sa.CheckConstraint(
            "status <> 'verified' OR ("
            "evidence_ref IS NOT NULL AND btrim(evidence_ref) <> '' AND verified_at IS NOT NULL "
            f"AND ({_in('evidence_type', QUALIFYING_EVIDENCE_TYPES)} "
            "OR (evidence_type = 'synthetic_fixture' AND data_origin = 'synthetic')))",
            name="ck_fitment_verified_evidence",
        ),
        sa.CheckConstraint(
            "evidence_type IS DISTINCT FROM 'synthetic_fixture' OR data_origin = 'synthetic'",
            name="ck_fitment_synthetic_evidence",
        ),
        sa.CheckConstraint("jsonb_typeof(conditions) = 'object'", name="ck_fitment_conditions"),
        sa.UniqueConstraint("source", "source_ref", name="uq_fitment_source_ref"),
    )
    op.create_index("ix_fitment_product_id", "fitment", ["product_id"])

    op.create_table(
        "set_component",
        sa.Column("set_product_id", sa.BigInteger(), sa.ForeignKey("product.id"), primary_key=True),
        sa.Column(
            "component_product_id",
            sa.BigInteger(),
            sa.ForeignKey("product.id"),
            primary_key=True,
        ),
        sa.Column("qty", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("present", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("optional", sa.Boolean(), nullable=False, server_default="false"),
        *_origin("set_component"),
        sa.Column("source", sa.Text(), nullable=False),
        _ts("created_at", nullable=False, now=True),
        sa.CheckConstraint("qty > 0", name="ck_set_component_qty"),
        sa.CheckConstraint(
            "set_product_id <> component_product_id", name="ck_set_component_not_self"
        ),
    )

    op.create_table(
        "inventory_item",
        _id(),
        sa.Column("product_id", sa.BigInteger(), sa.ForeignKey("product.id"), nullable=False),
        sa.Column("location", sa.Text()),
        sa.Column("physical_qty", sa.Integer(), nullable=False),
        sa.Column("external_reserved_qty", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_qty", sa.Integer(), nullable=False),
        sa.Column("held_qty", sa.Integer(), nullable=False, server_default="0"),
        *_origin("inventory_item"),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_ref", sa.Text()),
        _ts("fetched_at", nullable=False),
        _ts("verified_at"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        _ts("created_at", nullable=False, now=True),
        sa.CheckConstraint("physical_qty >= 0", name="ck_inventory_item_physical_qty"),
        sa.CheckConstraint(
            "external_reserved_qty >= 0", name="ck_inventory_item_external_reserved_qty"
        ),
        sa.CheckConstraint("available_qty >= 0", name="ck_inventory_item_available_qty"),
        sa.CheckConstraint("held_qty >= 0", name="ck_inventory_item_held_qty"),
        sa.UniqueConstraint("source", "source_ref", name="uq_inventory_item_source_ref"),
    )
    op.create_index("ix_inventory_item_product_id", "inventory_item", ["product_id"])

    op.create_table(
        "price",
        _id(),
        sa.Column("product_id", sa.BigInteger(), sa.ForeignKey("product.id"), nullable=False),
        sa.Column("inventory_item_id", sa.BigInteger(), sa.ForeignKey("inventory_item.id")),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column("discount_rule_key", sa.Text()),
        *_origin("price"),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_ref", sa.Text()),
        _ts("fetched_at", nullable=False),
        _ts("verified_at"),
        _ts("created_at", nullable=False, now=True),
        sa.CheckConstraint("amount_minor >= 0", name="ck_price_amount_minor"),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_price_currency"),
    )
    op.create_index("ix_price_product_id_fetched_at", "price", ["product_id", "fetched_at"])

    op.create_table(
        "photo",
        _id(),
        sa.Column(
            "inventory_item_id",
            sa.BigInteger(),
            sa.ForeignKey("inventory_item.id"),
            nullable=False,
        ),
        sa.Column("storage_uri", sa.Text(), nullable=False),
        sa.Column("sha256", sa.Text()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="1"),
        *_origin("photo"),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_ref", sa.Text()),
        _ts("fetched_at", nullable=False),
        _ts("verified_at"),
        _ts("created_at", nullable=False, now=True),
        sa.CheckConstraint(
            "(data_origin = 'synthetic') = (storage_uri LIKE 'synthetic://%')",
            name="ck_photo_synthetic_uri",
        ),
        sa.UniqueConstraint("inventory_item_id", "storage_uri", name="uq_photo_item_uri"),
    )

    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {', '.join(TABLES)} TO {APP_ROLE}")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
