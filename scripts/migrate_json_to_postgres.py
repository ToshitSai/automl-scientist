"""JSON → PostgreSQL migration for the AI Scientist store.

Usage (from the project root):

    # Preview counts without writing anything
    py -m scripts.migrate_json_to_postgres --dry-run

    # Run the migration (creates a timestamped backup of the JSON store first)
    py -m scripts.migrate_json_to_postgres

    # Compare JSON vs database after migration (exit code 0 = no loss)
    py -m scripts.migrate_json_to_postgres --verify

Idempotent: every write is an upsert or conflict-guarded insert, so re-running
converges instead of duplicating. The JSON file is never modified.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env so DATABASE_URL works in dev exactly like in the app.
try:
    import backend.config  # noqa: F401
except Exception:
    pass

from database.repository import Repository  # noqa: E402

DEFAULT_STORE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "database", "research_store.json")

SESSION_CONTEXT_KEYS = ("last_user_message", "last_assistant_message",
                        "last_topic", "last_reasoning_subjects",
                        "recent_topics", "pending_action",
                        "active_project_id")


def load_store(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def json_counts(data: dict) -> dict:
    sessions = data.get("sessions", {})
    return {
        "projects": len(data.get("projects", {})),
        "dataset_reports": len(data.get("datasets", {})),
        "baselines": len(data.get("baselines", {})),
        "tree_nodes": len(data.get("tree_nodes", {})),
        "error_analyses": len(data.get("error_analyses", {})),
        "literature": len(data.get("literature", {})),
        "reports": sum(1 for v in data.get("reports", {}).values() if v),
        "sessions": len(sessions),
        "messages": sum(len(s.get("messages", [])) for s in sessions.values()),
        "settings_keys": len(data.get("settings", {})),
    }


def backup_store(path: str) -> str:
    backup_dir = os.path.join(os.path.dirname(path), "..", "backups")
    os.makedirs(backup_dir, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dest = os.path.abspath(os.path.join(backup_dir, f"research_store.backup-{stamp}.json"))
    shutil.copy2(path, dest)
    return dest


def migrate(repo: Repository, data: dict, dry_run: bool = False) -> dict:
    """Migrate the legacy JSON store into PostgreSQL. Returns a stats dict."""
    stats = {"projects": 0, "messages": 0, "conversations": 0,
             "payloads": 0, "reports": 0, "papers": 0, "settings_keys": 0,
             "skipped_empty_messages": 0}
    orphans: list = []
    if dry_run:
        return stats

    # 1. Projects (typed columns + JSONB stage states + extra preservation).
    for pid, project in data.get("projects", {}).items():
        repo.save_project(pid, project)
        stats["projects"] += 1

    def not_orphan(pid: str, kind: str) -> bool:
        """The legacy JSON had no FK enforcement, so QA artifacts can reference
        project ids that never existed. Such orphans are skipped here (they stay
        in the timestamped backup) instead of violating the schema."""
        if repo.project_exists(pid):
            return True
        orphans.append(f"{kind}:{pid}")
        return False

    # 2. Per-project payload collections.
    for pid, payload in data.get("baselines", {}).items():
        if payload and not_orphan(pid, "baselines"):
            repo.save_baselines(pid, payload)
            stats["payloads"] += 1
    for pid, payload in data.get("tree_nodes", {}).items():
        if payload and not_orphan(pid, "tree_nodes"):
            repo.save_tree_nodes(pid, payload)
            stats["payloads"] += 1
    for pid, payload in data.get("datasets", {}).items():
        if payload and not_orphan(pid, "dataset_reports"):
            repo.save_dataset_report(pid, payload)
            stats["payloads"] += 1
    for pid, payload in data.get("error_analyses", {}).items():
        if payload and not_orphan(pid, "error_analyses"):
            repo.save_error_analysis(pid, payload)
            stats["payloads"] += 1
    for pid, payload in data.get("literature", {}).items():
        if payload and not_orphan(pid, "literature"):
            repo.save_literature(pid, payload)
            stats["payloads"] += 1
            stats["papers"] += len([p for p in payload if isinstance(p, dict) and p.get("title")])

    # 3. Reports (markdown strings) — skip when one already exists (idempotent).
    for pid, report_md in data.get("reports", {}).items():
        if report_md and not_orphan(pid, "reports") and repo.get_report(pid) is None:
            repo.save_report(pid, report_md)
            stats["reports"] += 1

    # 4. Sessions → conversations + messages + conversation_context.
    for sid, sess in data.get("sessions", {}).items():
        repo.ensure_conversation(sid)
        stats["conversations"] += 1
        messages = sess.get("messages", [])
        for m in messages:
            repo.record_message(
                sid, m.get("role", "user"), m.get("content", ""),
                intent=m.get("intent"), topic=m.get("topic"),
                research_id=m.get("research_id"),
                pending_action=m.get("pending_action"),
                message_id=m.get("id"),
                created_at=m.get("timestamp"))
        stats["messages"] += len(messages)
        context = {k: sess.get(k) for k in SESSION_CONTEXT_KEYS}
        context["session_id"] = sid
        repo.update_session(sid, context)
        if not messages:
            stats["skipped_empty_messages"] += 1

    # 5. Settings.
    settings = data.get("settings", {})
    if settings:
        repo.set_settings(settings)
        stats["settings_keys"] = len(settings)

    stats["orphan_payload_ids"] = len(orphans)
    stats["_orphans"] = orphans
    return stats


def verify(repo: Repository, data: dict) -> bool:
    """Compare JSON source-of-record counts against the database.

    Expected counts exclude what the migrator intentionally skips: orphan
    payload collections (project id never existed — QA artifacts) and empty
    values. Message contents are compared byte-for-byte per session.
    """
    def migrated_count(namespace: str, getter) -> int:
        return sum(
            1 for pid, payload in data.get(namespace, {}).items()
            if payload and repo.project_exists(pid)
        )

    expected = json_counts(data)
    expected["dataset_reports"] = migrated_count("datasets", repo.get_dataset_report)
    expected["baselines"] = migrated_count("baselines", repo.get_baselines)
    expected["tree_nodes"] = migrated_count("tree_nodes", repo.get_tree_nodes)
    expected["error_analyses"] = migrated_count("error_analyses", repo.get_error_analysis)
    expected["literature"] = migrated_count("literature", repo.get_literature)
    expected["reports"] = sum(
        1 for pid, md in data.get("reports", {}).items()
        if md and repo.project_exists(pid))
    sessions = data.get("sessions", {})

    actual = {
        "projects": int(repo._query_one("SELECT count(*) FROM research_projects")[0]),
        "sessions": int(repo._query_one("SELECT count(*) FROM conversations")[0]),
        "messages": int(repo._query_one("SELECT count(*) FROM messages")[0]),
        "contexts": int(repo._query_one("SELECT count(*) FROM conversation_context")[0]),
        "papers": int(repo._query_one("SELECT count(*) FROM papers")[0]),
        "reports": int(repo._query_one("SELECT count(*) FROM reports")[0]),
        "baselines": len([1 for pid in data.get("baselines", {})
                          if repo.get_baselines(pid)]),
        "tree_nodes": len([1 for pid in data.get("tree_nodes", {})
                           if repo.get_tree_nodes(pid)]),
        "dataset_reports": len([1 for pid in data.get("datasets", {})
                                if repo.get_dataset_report(pid)]),
        "error_analyses": len([1 for pid in data.get("error_analyses", {})
                               if repo.get_error_analysis(pid)]),
        "literature": len([1 for pid in data.get("literature", {})
                           if repo.get_literature(pid)]),
        "settings_keys": len(repo.get_all_settings()),
    }

    # Spot checks: every message content byte-identical, per session.
    mismatches = []
    for sid, sess in sessions.items():
        db_msgs = repo.get_messages(sid)
        json_msgs = sess.get("messages", [])
        if len(db_msgs) != len(json_msgs):
            mismatches.append(f"session {sid}: {len(json_msgs)} json vs {len(db_msgs)} db")
            continue
        for jm, dm in zip(json_msgs, db_msgs):
            if jm.get("content") != dm.get("content") or jm.get("role") != dm.get("role"):
                mismatches.append(f"session {sid} message {jm.get('id')}: content/role mismatch")

    ok = True
    print("\n=== MIGRATION VERIFY ===")
    for key in ("projects", "sessions", "messages", "settings_keys",
                "dataset_reports", "baselines", "tree_nodes",
                "error_analyses", "literature", "reports"):
        exp, act = expected.get(key), actual.get(key)
        status = "OK " if exp == act else "MISMATCH"
        if exp != act:
            ok = False
        print(f"  {key:<16} json={exp:<6} db={act:<6} {status}")
    extra_papers = actual["papers"]
    print(f"  {'papers (normalized)':<16} json=-{'':<7} db={extra_papers:<6} INFO")
    if mismatches:
        ok = False
        print(f"  Message-level mismatches: {len(mismatches)}")
        for m in mismatches[:10]:
            print(f"    - {m}")
    else:
        print("  Message spot-check: every stored message byte-identical OK")
    print(f"RESULT: {'PASS — no data loss detected' if ok else 'FAIL'}")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", default=DEFAULT_STORE, help="Path to research_store.json")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", ""),
                        help="Postgres URL (defaults to DATABASE_URL env)")
    parser.add_argument("--dry-run", action="store_true", help="Show counts, write nothing")
    parser.add_argument("--verify", action="store_true", help="Compare JSON vs DB and exit")
    args = parser.parse_args()

    if not args.database_url:
        print("ERROR: DATABASE_URL is not set (env or --database-url).")
        return 2

    data = load_store(args.store)
    repo = Repository(args.database_url)
    repo.ensure_schema()
    repo.ensure_system_user()

    if args.verify:
        return 0 if verify(repo, data) else 1

    print("JSON store contents:")
    for key, count in json_counts(data).items():
        print(f"  {key:<16} {count}")
    if args.dry_run:
        print("\nDRY RUN — nothing written.")
        return 0

    backup = backup_store(args.store)
    print(f"\nBackup written: {backup}")

    started = time.time()
    stats = migrate(repo, data)
    elapsed = time.time() - started
    orphans = stats.pop("_orphans", [])
    print(f"\nMigrated in {elapsed:.1f}s: "
          + ", ".join(f"{k}={v}" for k, v in stats.items()))
    if orphans:
        print("Orphan payload collections skipped (no matching project row; "
              "preserved in the backup):")
        for item in orphans:
            print(f"  - {item}")
    print("Verifying...")
    return 0 if verify(repo, data) else 1


if __name__ == "__main__":
    raise SystemExit(main())
