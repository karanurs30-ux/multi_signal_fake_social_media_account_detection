import sqlite3
import unittest
from app import app
from database import DB_NAME

class TestUserDataIsolation(unittest.TestCase):
    def setUp(self):
        # We can use the test client of Flask
        self.app = app.test_client()
        self.app.testing = True
        
        # Clean up database records for clean testing
        conn = sqlite3.connect(DB_NAME)
        conn.execute("DELETE FROM users WHERE username IN ('user_alpha', 'user_beta')")
        conn.execute("DELETE FROM history WHERE owner IN ('user_alpha', 'user_beta')")
        conn.execute("DELETE FROM monitored_accounts WHERE owner IN ('user_alpha', 'user_beta')")
        conn.execute("DELETE FROM alerts WHERE owner IN ('user_alpha', 'user_beta')")
        conn.commit()
        conn.close()

    def test_database_schema(self):
        """Verify that the database columns and constraints are correctly set up"""
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Check history schema
        cursor.execute("PRAGMA table_info(history);")
        columns = [row[1] for row in cursor.fetchall()]
        self.assertIn("owner", columns)
        
        # Check alerts schema
        cursor.execute("PRAGMA table_info(alerts);")
        columns = [row[1] for row in cursor.fetchall()]
        self.assertIn("owner", columns)
        
        # Check monitored_accounts schema
        cursor.execute("PRAGMA table_info(monitored_accounts);")
        columns = [row[1] for row in cursor.fetchall()]
        self.assertIn("owner", columns)
        
        # Check unique constraint on monitored_accounts
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='monitored_accounts';")
        create_sql = cursor.fetchone()[0]
        # Normalize sql string for robust check
        normalized_sql = "".join(create_sql.split()).upper()
        self.assertTrue(
            "UNIQUE(USERNAME,OWNER)" in normalized_sql or "UNIQUE(USERNAME,OWNER)" in normalized_sql,
            f"Expected composite UNIQUE(username, owner) constraint, but got: {create_sql}"
        )
        
        conn.close()

    def test_user_flow_and_isolation(self):
        """Register user_alpha and user_beta and check isolation"""
        # Register user_alpha
        resp = self.app.post('/register', json={
            "username": "user_alpha",
            "password": "password123"
        })
        self.assertEqual(resp.status_code, 200)
        
        # Register user_beta
        resp = self.app.post('/register', json={
            "username": "user_beta",
            "password": "password123"
        })
        self.assertEqual(resp.status_code, 200)
        
        # Log in as user_alpha
        resp = self.app.post('/login', json={
            "username": "user_alpha",
            "password": "password123"
        })
        self.assertEqual(resp.status_code, 200)
        
        # Add @nasa to monitoring under user_alpha
        resp = self.app.post('/monitoring/add', json={
            "username": "nasa",
            "platform": "instagram"
        })
        self.assertEqual(resp.status_code, 200)
        
        # Log out user_alpha
        resp = self.app.get('/logout')
        self.assertEqual(resp.status_code, 302) # Redirects to login
        
        # Log in as user_beta
        resp = self.app.post('/login', json={
            "username": "user_beta",
            "password": "password123"
        })
        self.assertEqual(resp.status_code, 200)
        
        # Verify user_beta watchlist is empty
        resp = self.app.get('/monitoring/status')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(len(data["accounts"]), 0)
        
        # Try to add @nasa to watchlist under user_beta (should succeed without UNIQUE violation)
        resp = self.app.post('/monitoring/add', json={
            "username": "nasa",
            "platform": "instagram"
        })
        self.assertEqual(resp.status_code, 200)
        
        # Verify user_beta now has @nasa on their watchlist
        resp = self.app.get('/monitoring/status')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(len(data["accounts"]), 1)
        self.assertEqual(data["accounts"][0]["username"], "nasa")

        # Verify that clear-history clears only the logged-in user's history
        # Let's manually insert mock history entries for both users
        conn = sqlite3.connect(DB_NAME)
        # Add history entry for user_alpha
        conn.execute("""
            INSERT INTO history (username, platform, prediction, risk_score, owner, analyzed_at)
            VALUES ('nasa', 'instagram', 'real', 10, 'user_alpha', '2026-07-03 12:00:00')
        """)
        # Add history entry for user_beta
        conn.execute("""
            INSERT INTO history (username, platform, prediction, risk_score, owner, analyzed_at)
            VALUES ('spacex', 'instagram', 'fake', 80, 'user_beta', '2026-07-03 12:05:00')
        """)
        conn.commit()
        conn.close()
        
        # Check history for user_beta (currently logged in)
        resp = self.app.get('/history')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(len(data["history"]), 1)
        self.assertEqual(data["history"][0]["username"], "spacex")
        
        # Clear history for user_beta
        resp = self.app.post('/clear-history')
        self.assertEqual(resp.status_code, 200)
        
        # Verify user_beta history is empty
        resp = self.app.get('/history')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(len(data["history"]), 0)
        
        # Log out user_beta and log in as user_alpha
        self.app.get('/logout')
        self.app.post('/login', json={
            "username": "user_alpha",
            "password": "password123"
        })
        
        # Verify user_alpha's history is still intact (isolated from user_beta's deletion)
        resp = self.app.get('/history')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(len(data["history"]), 1)
        self.assertEqual(data["history"][0]["username"], "nasa")

if __name__ == "__main__":
    unittest.main()
