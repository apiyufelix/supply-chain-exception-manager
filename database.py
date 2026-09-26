import sqlite3
from datetime import datetime
TIME_FORMAT = "%Y-%m-%d %I:%M %p"
DB_NAME = "exception_manager.db"


def get_connection():
    return sqlite3.connect(
        DB_NAME,
        check_same_thread=False
    )


def initialize_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS exception_workflow (
            order_id TEXT PRIMARY KEY,
            resolution_status TEXT DEFAULT 'Open',
            assigned_owner TEXT DEFAULT 'Unassigned',
            manager_notes TEXT DEFAULT '',
            last_updated TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS exception_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT NOT NULL,
            old_status TEXT,
            new_status TEXT,
            old_owner TEXT,
            new_owner TEXT,
            manager_notes TEXT,
            changed_at TEXT,
            resolved_on TEXT
        )
    """)

    conn.commit()
    conn.close()

def ensure_resolved_on_column():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(exception_workflow)")
    columns = [row[1] for row in cursor.fetchall()]

    if "resolved_on" not in columns:
        cursor.execute("""
            ALTER TABLE exception_workflow
            ADD COLUMN resolved_on TEXT
        """)

    conn.commit()
    conn.close()

def calculate_resolution_hours(start_time, resolved_time):
    if not start_time or not resolved_time:
        return None

    fmt = TIME_FORMAT

    start = datetime.strptime(start_time, fmt)
    end = datetime.strptime(resolved_time, fmt)

    return round(
        (end - start).total_seconds() / 3600,
        1
    )

def get_first_history_timestamp(order_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT changed_at
        FROM exception_history
        WHERE order_id = ?
        ORDER BY id ASC
        LIMIT 1
    """, (order_id,))

    row = cursor.fetchone()
    conn.close()

    return row[0] if row else None

def get_workflow(order_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            resolution_status,
            assigned_owner,
            manager_notes,
            last_updated,
            resolved_on
        FROM exception_workflow
        WHERE order_id = ?
    """, (order_id,))

    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "resolution_status": row[0],
            "assigned_owner": row[1],
            "manager_notes": row[2],
            "last_updated": row[3],
            "resolved_on": row[4],
        }

    return {
        "resolution_status": "Open",
        "assigned_owner": "Unassigned",
        "manager_notes": "",
        "last_updated": None,
        "resolved_on": None,
    }


def save_workflow(
    order_id,
    resolution_status,
    assigned_owner,
    manager_notes=""
):
    updated_at = datetime.now().strftime(
        "%Y-%m-%d %I:%M %p"
    )

    conn = get_connection()
    cursor = conn.cursor()

    # Get existing workflow
    cursor.execute("""
        SELECT
            resolution_status,
            assigned_owner,
            manager_notes,
            resolved_on
        FROM exception_workflow
        WHERE order_id = ?
    """, (order_id,))

    existing = cursor.fetchone()

    if existing:
        old_status = existing[0]
        old_owner = existing[1]
        old_notes = existing[2]
        existing_resolved_on = existing[3]
    else:
        old_status = None
        old_owner = None
        old_notes = ""
        existing_resolved_on = None

    # ---------------------------------
    # RESOLVED ON LOGIC
    # ---------------------------------

    if resolution_status == "Resolved":

        # Keep original resolution time if already resolved
        if existing_resolved_on:
            resolved_on = existing_resolved_on

        else:
            resolved_on = updated_at

    else:
        resolved_on = None

    # ---------------------------------
    # SAVE CURRENT WORKFLOW
    # ---------------------------------

    cursor.execute("""
        INSERT INTO exception_workflow (
            order_id,
            resolution_status,
            assigned_owner,
            manager_notes,
            last_updated,
            resolved_on
        )
        VALUES (?, ?, ?, ?, ?, ?)

        ON CONFLICT(order_id)
        DO UPDATE SET
            resolution_status = excluded.resolution_status,
            assigned_owner = excluded.assigned_owner,
            manager_notes = excluded.manager_notes,
            last_updated = excluded.last_updated,
            resolved_on = excluded.resolved_on
    """, (
        order_id,
        resolution_status,
        assigned_owner,
        manager_notes,
        updated_at,
        resolved_on
    ))

    # ---------------------------------
    # HISTORY
    # ---------------------------------

    changed = (
        old_status != resolution_status
        or old_owner != assigned_owner
        or old_notes != manager_notes
    )

    if changed:
        cursor.execute("""
            INSERT INTO exception_history (
                order_id,
                old_status,
                new_status,
                old_owner,
                new_owner,
                manager_notes,
                changed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            order_id,
            old_status,
            resolution_status,
            old_owner,
            assigned_owner,
            manager_notes,
            updated_at
        ))

    conn.commit()
    conn.close()

    return updated_at

def get_exception_history(order_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            old_status,
            new_status,
            old_owner,
            new_owner,
            manager_notes,
            changed_at
        FROM exception_history
        WHERE order_id = ?
    """, (order_id,))

    rows = cursor.fetchall()
    conn.close()

    rows = sorted(
        rows,
        key=lambda row: datetime.strptime(
            row[5],
            TIME_FORMAT
        ),
        reverse=True
    )

    return rows

def get_resolved_today_count():
    conn = get_connection()
    cursor = conn.cursor()

    today = datetime.now().strftime("%Y-%m-%d")

    cursor.execute("""
        SELECT COUNT(*)
        FROM exception_workflow
        WHERE resolution_status = 'Resolved'
          AND resolved_on IS NOT NULL
          AND substr(resolved_on, 1, 10) = ?
    """, (today,))

    count = cursor.fetchone()[0]

    conn.close()

    return count

def get_all_workflows():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            order_id,
            resolution_status,
            assigned_owner,
            last_updated,
            resolved_on
        FROM exception_workflow
    """)

    rows = cursor.fetchall()

    conn.close()

    return rows

def get_oldest_open_hours():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT order_id
        FROM exception_workflow
        WHERE resolution_status IN ('Open', 'In Progress')
    """)

    order_ids = [
        row[0]
        for row in cursor.fetchall()
    ]

    conn.close()

    now = datetime.now()

    oldest_hours = None

    for order_id in order_ids:

        first_time = get_first_history_timestamp(
            order_id
        )

        if not first_time:
            continue

        start = datetime.strptime(
            first_time,
            TIME_FORMAT
        )

        hours = (
            now - start
        ).total_seconds() / 3600

        if (
            oldest_hours is None
            or hours > oldest_hours
        ):
            oldest_hours = hours

    return oldest_hours

def reset_exception_history(order_id=None):
    conn = get_connection()
    cursor = conn.cursor()

    if order_id:
        cursor.execute(
            "DELETE FROM exception_history WHERE order_id = ?",
            (order_id,)
        )
    else:
        cursor.execute(
            "DELETE FROM exception_history"
        )

    conn.commit()
    conn.close()
    