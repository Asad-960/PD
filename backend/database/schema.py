"""
SQLite database schema, pragmas, and initialization logic.
Strictly adheres to:
- 2026-10-03-physiological-twin-design.md (Section 12)
- implementation-plan.md (Phase 4)
"""

import sqlite3
from typing import Any

CREATE_TABLES_SQL = """
-- 1. Patient Profiles
CREATE TABLE IF NOT EXISTS patient_profiles (
    patient_id TEXT PRIMARY KEY,
    data JSON NOT NULL,
    created_at REAL NOT NULL
);

-- 2. Simulation Runs
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patient_profiles(patient_id) ON DELETE RESTRICT,
    config JSON NOT NULL,
    initial_schedule JSON NOT NULL,
    status TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

-- 3. Scheduled / Applied Interventions
CREATE TABLE IF NOT EXISTS interventions (
    event_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    simulation_time REAL NOT NULL,
    payload JSON NOT NULL
);

-- 4. Physiology Snapshots
CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    sequence INTEGER NOT NULL,
    simulation_time REAL NOT NULL,
    data JSON NOT NULL,
    is_valid INTEGER NOT NULL DEFAULT 1,
    is_stale INTEGER NOT NULL DEFAULT 0
);

-- 5. Append-only Event Stream
CREATE TABLE IF NOT EXISTS events (
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    sequence INTEGER NOT NULL,
    simulation_time REAL NOT NULL,
    wall_clock_time REAL NOT NULL,
    schema_version TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload JSON NOT NULL,
    parent_causal_ids JSON NOT NULL,
    PRIMARY KEY (run_id, sequence)
);

-- 6. Checkpoints for Branching and Time Travel
CREATE TABLE IF NOT EXISTS checkpoints (
    checkpoint_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    sequence INTEGER NOT NULL,
    simulation_time REAL NOT NULL,
    serialized_state TEXT NOT NULL,
    event_cursor INTEGER NOT NULL,
    content_hash TEXT NOT NULL
);

-- 7. Organ Council Findings
CREATE TABLE IF NOT EXISTS findings (
    finding_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    sequence INTEGER NOT NULL,
    simulation_time REAL NOT NULL,
    organ TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT NOT NULL,
    coverage TEXT NOT NULL,
    data JSON NOT NULL
);

-- 8. Evidence Sources
CREATE TABLE IF NOT EXISTS evidence_sources (
    source_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    publication_date TEXT,
    license TEXT,
    raw_extract TEXT
);

-- 9. Evidence Rule Versions
CREATE TABLE IF NOT EXISTS rule_versions (
    rule_id TEXT PRIMARY KEY,
    version TEXT NOT NULL,
    ingredient_id TEXT NOT NULL,
    precondition JSON NOT NULL,
    mechanism TEXT NOT NULL,
    status TEXT NOT NULL,
    limitations TEXT
);

-- 10. Clinical / Synthetic Reviews
CREATE TABLE IF NOT EXISTS reviews (
    review_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    reviewer TEXT NOT NULL,
    timestamp REAL NOT NULL,
    status TEXT NOT NULL,
    acknowledged_limitations JSON NOT NULL,
    notes TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assessment_reports (
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    event_cursor INTEGER NOT NULL,
    report_id TEXT NOT NULL,
    data JSON NOT NULL,
    PRIMARY KEY (run_id, event_cursor)
);

CREATE TABLE IF NOT EXISTS assessment_bases (
    run_id TEXT PRIMARY KEY REFERENCES runs(run_id) ON DELETE CASCADE,
    data JSON NOT NULL
);

-- Composite Indexes for High-Performance Scrubbing, Replay, and Aligned Charts
CREATE INDEX IF NOT EXISTS idx_snapshots_run_seq ON snapshots(run_id, sequence);
CREATE INDEX IF NOT EXISTS idx_snapshots_run_time ON snapshots(run_id, simulation_time);
CREATE INDEX IF NOT EXISTS idx_events_run_seq ON events(run_id, sequence);
CREATE INDEX IF NOT EXISTS idx_events_run_time ON events(run_id, simulation_time);
CREATE INDEX IF NOT EXISTS idx_findings_run_seq ON findings(run_id, sequence);
CREATE INDEX IF NOT EXISTS idx_checkpoints_run_seq ON checkpoints(run_id, sequence);
"""


def apply_pragmas(conn: sqlite3.Connection) -> None:
    """
    Apply high-performance, crash-safe SQLite pragmas:
    - journal_mode = WAL (Write-Ahead Logging for concurrency)
    - synchronous = NORMAL (Safe, optimal performance with WAL)
    - foreign_keys = ON (Enforce referential integrity)
    - busy_timeout = 5000 (Avoid lock contentions)
    """
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 5000;")


def init_db(conn: sqlite3.Connection) -> None:
    """
    Initialize database schema and apply pragmas.
    """
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    existing_tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    if version != 0 and version != 2:
        raise RuntimeError(f"Unsupported SQLite schema version {version}; preserve and migrate explicitly")
    if version == 0 and existing_tables:
        raise RuntimeError("Legacy unversioned SQLite database preserved; use a new demo database or explicit migration")
    apply_pragmas(conn)
    conn.executescript(CREATE_TABLES_SQL)
    conn.execute("PRAGMA user_version = 2")
    conn.commit()
