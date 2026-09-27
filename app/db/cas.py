"""Compare-and-set helpers (docs/ARCHITECTURE.md §1.4, §6.5 item 1).

Each helper is a single conditional UPDATE; it returns ``True`` only if exactly one row changed.
``False`` means the transition did not happen (someone else moved the row first, or a guard
condition failed) and the caller must re-read instead of assuming success. Helpers do not commit.
"""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy import Connection, Table, text, update

from app.db.models import Base
from app.db.settings import SENDING_MODES
from app.queue.locks import SingletonToken, singleton_fence_sql


def cas_update(
    conn: Connection,
    model: type[Base],
    row_id: int,
    *,
    expected_status: str,
    expected_version: int,
    values: dict[str, Any],
    status_column: str = "status",
    version_column: str = "version",
) -> bool:
    """``UPDATE … SET values, version = version + 1 WHERE id = :id AND status = :expected
    AND version = :v``. For ``conversation`` pass ``status_column="state"`` and
    ``version_column="state_version"``."""
    table = cast(Table, model.__table__)
    status_col = table.c[status_column]
    version_col = table.c[version_column]
    stmt = (
        update(table)
        .where(
            table.c.id == row_id,
            status_col == expected_status,
            version_col == expected_version,
        )
        .values({**values, version_column: version_col + 1})
    )
    return conn.execute(stmt).rowcount == 1


_SENDING_MODES_SQL = ", ".join(f"'{m}'" for m in SENDING_MODES)

_INTENT_SQL = f"""
UPDATE outbound_message AS o
SET status = 'sending', intent_at = now(), attempts = o.attempts + 1, version = o.version + 1
WHERE o.id = :id AND o.status = 'pending' AND o.version = :version
  -- positive allowlist: the settings row must exist, the kill switch be off and the mode be a
  -- sending mode; a missing row or NULL blocks the send (every part, not only part 1)
  AND EXISTS (
    SELECT 1 FROM system_setting AS s
    WHERE s.id = 1 AND s.kill_switch = false AND s.automation_mode IN ({_SENDING_MODES_SQL}))
  AND EXISTS (
    SELECT 1 FROM draft AS d JOIN conversation AS c ON c.id = d.conversation_id
    WHERE d.id = o.draft_id AND c.automation = 'active'
      -- part 1: the draft still answers the newest customer message
      AND (o.part_no > 1 OR c.last_inbound_seq = d.based_on_seq))
  -- later parts: the previous part of the same group is sent
  AND (o.part_no = 1 OR EXISTS (
    SELECT 1 FROM outbound_message AS p
    WHERE p.draft_id = o.draft_id AND p.generation = o.generation
      AND p.part_no = o.part_no - 1 AND p.status = 'sent'))
  AND {singleton_fence_sql()}
"""


def claim_send_intent(
    conn: Connection, outbound_id: int, expected_version: int, token: SingletonToken
) -> bool:
    """Intent CAS for one outbox part: ``pending`` → ``sending`` (§6.5 item 1).

    Succeeds only if the settings row allows sending (kill switch off, mode in
    ``SENDING_MODES``), the conversation's automation is ``active``, the draft is not stale
    (part 1) or the previous part is ``sent`` (parts 2..n), and ``token`` is still the live
    worker singleton (fencing, see ``app.queue.locks``). ``attempts`` counts HTTP attempts, so it
    grows here. The send itself is T-025. If sending stops mid-group, the group rule in
    ``app.db.settings.stop_open_outbox_groups`` applies.
    """
    result = conn.execute(
        text(_INTENT_SQL),
        {"id": outbound_id, "version": expected_version, **token.params()},
    )
    return result.rowcount == 1
