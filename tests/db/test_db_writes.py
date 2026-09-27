# SYNTHETIC: chats, message ids and texts are made up.
"""Message dedup, fenced draft INSERT, CAS, intent CAS and append-only audit on real PostgreSQL."""

from __future__ import annotations

import threading
import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError, ProgrammingError

from app.db.cas import cas_update, claim_send_intent
from app.db.models import Conversation, Draft
from app.db.writes import append_audit, insert_draft_fenced, record_message
from app.queue.locks import WorkerSingleton, conversation_lock
from tests.db.factories import make_conversation, make_draft, make_outbound


def _customer_message(engine: Engine, cid: int, mid: str) -> int | None:
    with engine.begin() as conn:
        return record_message(
            conn,
            conversation_id=cid,
            avito_message_id=mid,
            author_role="customer",
            direction="in",
            type="text",
            source="webhook",
            content_masked="SYN hello",
        )


def test_message_dedup_on_avito_message_id(engine: Engine) -> None:
    with engine.begin() as conn:
        cid = make_conversation(conn)
    assert _customer_message(engine, cid, "SYN-m1") == 1
    assert _customer_message(engine, cid, "SYN-m1") is None  # webhook + poller: one row
    assert _customer_message(engine, cid, "SYN-m2") == 2
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM message")).scalar() == 2
        seq = conn.execute(text("SELECT last_inbound_seq FROM conversation")).scalar()
    assert seq == 2


def test_draft_insert_fenced_on_seq_and_lock(engine: Engine) -> None:
    with engine.begin() as conn:
        cid = make_conversation(conn)
    _customer_message(engine, cid, "SYN-m1")
    with conversation_lock(engine, cid) as lock:
        assert lock is not None
        with lock.connection.begin():
            ok = insert_draft_fenced(lock, based_on_seq=1, action="ask_info", parts=["SYN a"])
        assert ok is not None
        _customer_message(engine, cid, "SYN-m2")  # new message while the draft was being made
        with lock.connection.begin():
            stale = insert_draft_fenced(lock, based_on_seq=1, action="ask_info", parts=["SYN b"])
        assert stale is None
    # A handle whose session no longer holds the lock cannot write either.
    with conversation_lock(engine, cid) as lock:
        assert lock is not None
        lock.connection.execute(text("SELECT pg_advisory_unlock_all()"))
        lock.connection.commit()
        with lock.connection.begin():
            assert insert_draft_fenced(lock, based_on_seq=2, action="a", parts=["SYN c"]) is None
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM draft")).scalar() == 1


def test_cas_conflict_second_writer_loses(engine: Engine) -> None:
    with engine.begin() as conn:
        draft = make_draft(conn, make_conversation(conn), 0)
    with engine.begin() as conn:
        assert cas_update(
            conn,
            Draft,
            draft,
            expected_status="proposed",
            expected_version=0,
            values={"status": "approved"},
        )
    with engine.begin() as conn:
        # Same expectation, read before the first write committed: must fail.
        assert not cas_update(
            conn,
            Draft,
            draft,
            expected_status="proposed",
            expected_version=0,
            values={"status": "rejected"},
        )
        assert not cas_update(
            conn,
            Draft,
            draft,
            expected_status="approved",
            expected_version=0,
            values={"status": "stale"},
        )
        status, version = conn.execute(
            text("SELECT status, version FROM draft WHERE id = :i"), {"i": draft}
        ).one()
    assert (status, version) == ("approved", 1)


def test_cas_race_exactly_one_winner(engine: Engine) -> None:
    with engine.begin() as conn:
        cid = make_conversation(conn)
    wins: list[bool] = []
    barrier = threading.Barrier(8)

    def attempt(target: str) -> None:
        barrier.wait()
        with engine.begin() as conn:
            wins.append(
                cas_update(
                    conn,
                    Conversation,
                    cid,
                    expected_status="new_request",
                    expected_version=0,
                    values={"state": target},
                    status_column="state",
                    version_column="state_version",
                )
            )

    threads = [
        threading.Thread(target=attempt, args=(s,)) for s in ["awaiting_info", "researching"] * 4
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(wins) == [False] * 7 + [True]


@pytest.fixture
def singleton(engine: Engine) -> Iterator[WorkerSingleton]:
    s = WorkerSingleton(engine, on_lost=lambda code: None)
    s.acquire()
    yield s
    s.release()


def _intent_setup(engine: Engine) -> tuple[int, int, int]:
    with engine.begin() as conn:
        cid = make_conversation(conn)
    _customer_message(engine, cid, "SYN-m1")
    with engine.begin() as conn:
        draft = make_draft(conn, cid, 1)
        part1 = make_outbound(conn, draft, 1, 2)
        part2 = make_outbound(conn, draft, 2, 2)
    return cid, part1, part2


def _intent(engine: Engine, outbound: int, singleton: WorkerSingleton, version: int = 0) -> bool:
    assert singleton.pid is not None
    with engine.begin() as conn:
        return claim_send_intent(conn, outbound, version, singleton.pid)


def test_intent_cas_happy_path_and_part_order(engine: Engine, singleton: WorkerSingleton) -> None:
    cid, part1, part2 = _intent_setup(engine)
    assert not _intent(engine, part2, singleton)  # part 2 before part 1 is sent
    assert _intent(engine, part1, singleton)
    assert not _intent(engine, part1, singleton)  # version moved: second CAS fails
    with engine.begin() as conn:
        row = conn.execute(
            text(
                "SELECT status, attempts, intent_at IS NOT NULL AS has_intent "
                "FROM outbound_message WHERE id = :i"
            ),
            {"i": part1},
        ).one()
        assert tuple(row) == ("sending", 1, True)
        conn.execute(
            text("UPDATE outbound_message SET status = 'sent' WHERE id = :i"), {"i": part1}
        )
    _customer_message(engine, cid, "SYN-m2")  # a new message after part 1 does not stop part 2
    assert _intent(engine, part2, singleton)


def test_intent_cas_rejects_stale_seq(engine: Engine, singleton: WorkerSingleton) -> None:
    cid, part1, _ = _intent_setup(engine)
    _customer_message(engine, cid, "SYN-m2")
    assert not _intent(engine, part1, singleton)


def test_intent_cas_rejects_kill_switch(engine: Engine, singleton: WorkerSingleton) -> None:
    _, part1, _ = _intent_setup(engine)
    with engine.begin() as conn:
        conn.execute(text("UPDATE system_setting SET kill_switch = true"))
    assert not _intent(engine, part1, singleton)
    with engine.begin() as conn:
        conn.execute(text("UPDATE system_setting SET kill_switch = false"))
    assert _intent(engine, part1, singleton)


def test_intent_cas_rejects_paused_automation(engine: Engine, singleton: WorkerSingleton) -> None:
    cid, part1, _ = _intent_setup(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE conversation SET automation = 'paused', paused_reason = 'owner_takeover', "
                "paused_at = now() WHERE id = :c"
            ),
            {"c": cid},
        )
    assert not _intent(engine, part1, singleton)


def test_intent_cas_rejects_without_singleton(engine: Engine, singleton: WorkerSingleton) -> None:
    _, part1, _ = _intent_setup(engine)
    assert singleton.pid is not None
    with engine.begin() as conn:
        other_pid = conn.execute(text("SELECT pg_backend_pid()")).scalar_one()
        assert not claim_send_intent(conn, part1, 0, other_pid)  # pid is not the lock holder


def test_audit_append_only_for_owner_and_app_role(engine: Engine) -> None:
    op_id = f"SYN-op-{uuid.uuid4().hex[:8]}"
    with engine.begin() as conn:
        append_audit(
            conn,
            op_id=op_id,
            actor="worker",
            action="draft_created",
            result="ok",
            entity_ids={"draft_id": 1},
        )
    # Owner / superuser: the trigger refuses UPDATE, DELETE and TRUNCATE.
    for stmt in (
        "UPDATE audit_event SET result = 'x' WHERE op_id = :o",
        "DELETE FROM audit_event WHERE op_id = :o",
        "TRUNCATE audit_event",
    ):
        with engine.begin() as conn, pytest.raises(DBAPIError, match="append-only"):
            conn.execute(text(stmt), {"o": op_id})
    # Runtime role: INSERT allowed, UPDATE/DELETE refused by privileges before any trigger.
    with engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE assistant_app"))
        append_audit(conn, op_id=op_id, actor="worker", action="second", result="ok")
    for stmt in (
        "UPDATE audit_event SET result = 'x' WHERE op_id = :o",
        "DELETE FROM audit_event WHERE op_id = :o",
    ):
        with engine.begin() as conn, pytest.raises(ProgrammingError, match="permission denied"):
            conn.execute(text("SET LOCAL ROLE assistant_app"))
            conn.execute(text(stmt), {"o": op_id})
    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT count(*) FROM audit_event WHERE op_id = :o"), {"o": op_id}
        ).scalar()
    assert count == 2
