import sqlite3
from datetime import datetime

DB_NAME = "history.db"

def init_db():
    """Create the database and tables if they don't exist"""
    conn = sqlite3.connect(DB_NAME)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            platform TEXT,
            prediction TEXT,
            risk_score INTEGER,
            risk_level TEXT,
            confidence REAL,
            followers INTEGER,
            following INTEGER,
            posts INTEGER,
            bio_length INTEGER,
            is_verified INTEGER,
            spam_score INTEGER,
            face_detected INTEGER,
            clone_detected INTEGER,
            analyzed_at TEXT,
            owner TEXT DEFAULT 'admin'
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    print("Database initialized!")

def create_user(username, password_hash):
    """Register a new user in the database"""
    conn = sqlite3.connect(DB_NAME)
    try:
        conn.execute("""
            INSERT INTO users (username, password_hash, created_at)
            VALUES (?, ?, ?)
        """, (username, password_hash, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_user(username):
    """Retrieve a user by username"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def save_analysis(result, owner):
    """Save an analysis result to the database with owner"""
    conn = sqlite3.connect(DB_NAME)
    conn.execute("""
        INSERT INTO history (
            username, platform, prediction, risk_score,
            risk_level, confidence, followers, following,
            posts, bio_length, is_verified, spam_score,
            face_detected, clone_detected, analyzed_at, owner
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        result["data"]["username"],
        result["platform"],
        result["prediction"],
        result.get("risk_score", 0),
        result.get("risk_level", ""),
        result.get("confidence", 0),
        result["data"]["followers"],
        result["data"]["following"],
        result["data"].get("posts", result["data"].get("tweets", 0)),
        result["data"]["bio_length"],
        1 if result["data"]["is_verified"] else 0,
        result.get("spam", {}).get("spam_score", 0),
        1 if result.get("face", {}).get("has_face") else 0,
        1 if result.get("clone", {}).get("is_clone") else 0,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        owner
    ))
    conn.commit()
    conn.close()

def get_history(owner, limit=50):
    """Get recent analysis history for a specific owner"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("""
        SELECT * FROM history
        WHERE owner = ?
        ORDER BY analyzed_at DESC
        LIMIT ?
    """, (owner, limit))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def get_stats(owner):
    """Get overall statistics for a specific owner"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN prediction = 'fake' THEN 1 ELSE 0 END) as fake_count,
            SUM(CASE WHEN prediction = 'real' THEN 1 ELSE 0 END) as real_count,
            AVG(risk_score) as avg_risk,
            SUM(CASE WHEN clone_detected = 1 THEN 1 ELSE 0 END) as clones_found
        FROM history
        WHERE owner = ?
    """, (owner,))
    row = cursor.fetchone()
    conn.close()
    return {
        "total": row[0] or 0,
        "fake_count": row[1] or 0,
        "real_count": row[2] or 0,
        "avg_risk": round(row[3] or 0, 1),
        "clones_found": row[4] or 0
    }

def delete_history(owner):
    """Clear history for a specific owner"""
    conn = sqlite3.connect(DB_NAME)
    conn.execute("DELETE FROM history WHERE owner = ?", (owner,))
    conn.commit()
    conn.close()

# Initialize database when imported
init_db()

def init_monitoring():
    """Create monitoring table"""
    conn = sqlite3.connect(DB_NAME)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS monitored_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            platform TEXT,
            last_risk_score INTEGER,
            last_checked TEXT,
            alert_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            owner TEXT DEFAULT 'admin',
            UNIQUE(username, owner)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            platform TEXT,
            alert_type TEXT,
            message TEXT,
            old_score INTEGER,
            new_score INTEGER,
            created_at TEXT,
            owner TEXT DEFAULT 'admin'
        )
    """)
    conn.commit()
    conn.close()

def add_monitored_account(username, platform, owner):
    conn = sqlite3.connect(DB_NAME)
    try:
        conn.execute("""
            INSERT OR IGNORE INTO monitored_accounts 
            (username, platform, last_checked, owner)
            VALUES (?, ?, ?, ?)
        """, (username, platform, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), owner))
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()

def remove_monitored_account(username, owner):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("DELETE FROM monitored_accounts WHERE username = ? AND owner = ?", (username, owner))
    conn.commit()
    conn.close()

def get_monitored_accounts(owner=None):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    if owner:
        cursor = conn.execute("SELECT * FROM monitored_accounts WHERE owner = ? ORDER BY username", (owner,))
    else:
        cursor = conn.execute("SELECT * FROM monitored_accounts ORDER BY username")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def save_alert(username, platform, alert_type, message, old_score, new_score, owner):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("""
        INSERT INTO alerts (username, platform, alert_type, message, old_score, new_score, created_at, owner)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (username, platform, alert_type, message, old_score, new_score,
          datetime.now().strftime("%Y-%m-%d %H:%M:%S"), owner))
    conn.execute("""
        UPDATE monitored_accounts 
        SET alert_count = alert_count + 1, last_checked = ?
        WHERE username = ? AND owner = ?
    """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), username, owner))
    conn.commit()
    conn.close()

def get_alerts(owner, limit=20):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("""
        SELECT * FROM alerts 
        WHERE owner = ? 
        ORDER BY created_at DESC 
        LIMIT ?
    """, (owner, limit))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def update_monitored_score(username, new_score, owner):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("""
        UPDATE monitored_accounts 
        SET last_risk_score = ?, last_checked = ?
        WHERE username = ? AND owner = ?
    """, (new_score, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), username, owner))
    conn.commit()
    conn.close()

def run_migrations():
    """Ensure database has all required schema updates for user isolation"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 1. Add owner column to history table if not exists
    cursor.execute("PRAGMA table_info(history);")
    history_columns = [row[1] for row in cursor.fetchall()]
    if "owner" not in history_columns:
        print("Migrating database: Adding 'owner' column to 'history' table...")
        conn.execute("ALTER TABLE history ADD COLUMN owner TEXT DEFAULT 'admin';")
        conn.commit()

    # 2. Add owner column to alerts table if not exists
    cursor.execute("PRAGMA table_info(alerts);")
    alerts_columns = [row[1] for row in cursor.fetchall()]
    if "owner" not in alerts_columns:
        print("Migrating database: Adding 'owner' column to 'alerts' table...")
        conn.execute("ALTER TABLE alerts ADD COLUMN owner TEXT DEFAULT 'admin';")
        conn.commit()

    # 3. Migrate monitored_accounts to remove UNIQUE(username) and add composite UNIQUE(username, owner)
    cursor.execute("PRAGMA table_info(monitored_accounts);")
    mon_columns = [row[1] for row in cursor.fetchall()]
    if "owner" not in mon_columns:
        print("Migrating database: Recreating 'monitored_accounts' to support composite unique constraint (username, owner)...")
        conn.execute("ALTER TABLE monitored_accounts RENAME TO monitored_accounts_old;")
        conn.execute("""
            CREATE TABLE monitored_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                platform TEXT,
                last_risk_score INTEGER,
                last_checked TEXT,
                alert_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active',
                owner TEXT DEFAULT 'admin',
                UNIQUE(username, owner)
            )
        """)
        conn.execute("""
            INSERT INTO monitored_accounts (username, platform, last_risk_score, last_checked, alert_count, status, owner)
            SELECT username, platform, last_risk_score, last_checked, alert_count, status, 'admin'
            FROM monitored_accounts_old;
        """)
        conn.execute("DROP TABLE monitored_accounts_old;")
        conn.commit()
    conn.close()

# Initialize monitoring tables
init_monitoring()

# Run database migrations
run_migrations()