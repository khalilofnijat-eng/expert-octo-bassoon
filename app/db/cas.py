"""Compare-and-set helpers (docs/ARCHITECTURE.md §1.4, §6.5 item 1).

Each helper is a single conditional UPDATE; it returns ``True`` only if exactly one row changed.
``False`` means the transition did not happen (someone else moved the row first, or a guard
condition failed) and the caller must re-read instead of assuming success. Helpers do not commit.
"""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy import Connection, Table, text, update

from app.db.models import Base
from app.queue.locks import singleton_fence_sql


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


_INTENT_SQL = f"""
UPDATE outbound_message AS o
SET status = 'sending', intent_at = now(), attempts = o.attempts + 1, version = o.version + 1
WHERE o.id = :id AND o.status = 'pending' AND o.version = :version
  -- kill switch; a missing settings row yields NULL, which also blocks the send
  AND NOT (SELECT s.kill_switch FROM system_setting AS s WHERE s.id = 1)
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
    conn: Connection, outbound_id: int, expected_version: int, singleton_pid: int
) -> bool:
    """Intent CAS for one outbox part: ``pending`` → ``sending`` (§6.5 item 1).

    Succeeds only if the kill switch is off, the conversation's automation is ``active``, the
    draft is not stale (part 1) or the previous part is ``sent`` (parts 2..n), and the worker
    singleton lock is still held by ``singleton_pid`` (fencing, see ``app.queue.locks``).
    ``attempts`` counts HTTP attempts, so it grows here. The send itself is T-025.
    """
    result = conn.execute(
        text(_INTENT_SQL),
        {"id": outbound_id, "version": expected_version, "singleton_pid": singleton_pid},
    )
    return result.rowcount == 1
