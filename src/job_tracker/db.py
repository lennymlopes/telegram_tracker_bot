import sqlite3
from datetime import datetime

def init_database(db_path):
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS jobs (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               name TEXT NOT NULL,
               url TEXT NOT NULL UNIQUE,
               first_seen DATE NOT NULL,
               last_seen DATE NOT NULL,
               is_active BOOLEAN DEFAULT TRUE
                    )
            ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subscribers (
                user_id INTEGER PRIMARY KEY,     -- Telegram user ID
                first_name TEXT,                 -- User's first name
                subscribed_date DATE NOT NULL    -- When they subscribed
            )
        ''')

        conn.commit()

def save_jobs(db_path, jobs):
    current_date = datetime.now().date()
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # Mark current jobs as inactive
        cursor.execute("UPDATE jobs SET is_active = FALSE")

        new_jobs = 0
        updated_jobs = 0

        for job in jobs:
            # Check if job already exists
            cursor.execute("SELECT id, first_seen FROM jobs WHERE url = ?", (job['url'],))
            existing = cursor.fetchone()

            if existing:
                # Update existing job - mark as active and update last_seen
                cursor.execute('''
                               UPDATE jobs
                               SET name = ?, last_seen = ?, is_active = TRUE
                               WHERE url = ?
                               ''', (job['name'], current_date, job['url']))
                updated_jobs += 1
            else:
                # Insert new job
                cursor.execute('''
                               INSERT INTO jobs (name, url, first_seen, last_seen, is_active)
                               VALUES (?, ?, ?, ?, TRUE)
                               ''', (job['name'], job['url'], current_date, current_date))
                new_jobs += 1

        conn.commit()
        return new_jobs, updated_jobs

def get_all_jobs(db_path, active_only=True):
    """
    Retrieve all jobs from the database
    """
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        if active_only:
            cursor.execute('''
                           SELECT name, url, first_seen, last_seen
                           FROM jobs
                           WHERE is_active = TRUE
                           ORDER BY first_seen DESC
                           ''')
        else:
            cursor.execute('''
                           SELECT name, url, first_seen, last_seen, is_active
                           FROM jobs
                           ORDER BY first_seen DESC
                           ''')

        return cursor.fetchall()

def get_new_jobs_today(db_path):
    """
    Get jobs that were first seen today
    """
    today = datetime.now().date()

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('''
                       SELECT name, url, first_seen, last_seen
                       FROM jobs
                       WHERE first_seen = ? AND is_active = TRUE
                       ORDER BY first_seen DESC
                       ''', (today,))

        return cursor.fetchall()

def update_discovery_date_by_url(db_path, job_url, new_date):
    """
    Update the discovery date for a specific job by URL
    """
    if isinstance(new_date, str):
        new_date = datetime.strptime(new_date, '%Y-%m-%d').date()

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # Check if job exists
        cursor.execute("SELECT id, name FROM jobs WHERE url = ?", (job_url,))
        job = cursor.fetchone()

        if job:
            cursor.execute('''
                           UPDATE jobs
                           SET first_seen = ?
                           WHERE url = ?
                           ''', (new_date, job_url))

            conn.commit()
            print(f"Updated discovery date for '{job[1]}' to {new_date}")
            return True
        else:
            print(f"Job with URL '{job_url}' not found")
            return False

def subscribe_user(db_path, user_id, first_name):
    """
    Subscribe a user to notifications

    Args:
        db_path: Path to the database
        user_id: Telegram user ID
        first_name: User's first name

    Returns:
        bool: True if newly subscribed, False if already subscribed
    """
    current_date = datetime.now().date()

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # Check if already subscribed
        cursor.execute("SELECT user_id FROM subscribers WHERE user_id = ?", (user_id,))
        if cursor.fetchone():
            return False  # Already subscribed

        # Add new subscriber
        cursor.execute('''
                       INSERT INTO subscribers (user_id, first_name, subscribed_date)
                       VALUES (?, ?, ?)
                       ''', (user_id, first_name, current_date))

        conn.commit()
        return True

def unsubscribe_user(db_path, user_id):
    """
    Unsubscribe a user from notifications

    Args:
        db_path: Path to the database
        user_id: Telegram user ID

    Returns:
        bool: True if unsubscribed, False if wasn't subscribed
    """
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # Remove subscriber
        cursor.execute("DELETE FROM subscribers WHERE user_id = ?", (user_id,))

        conn.commit()
        return cursor.rowcount > 0  # True if a row was deleted

def get_subscribers(db_path):
    """
    Get list of all subscribed user IDs

    Returns:
        list: List of user IDs that are subscribed
    """
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM subscribers")
        return [row[0] for row in cursor.fetchall()]

def is_subscribed(db_path, user_id):
    """
    Check if a user is subscribed

    Args:
        db_path: Path to the database
        user_id: Telegram user ID

    Returns:
        bool: True if subscribed, False otherwise
    """
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM subscribers WHERE user_id = ?", (user_id,))
        return cursor.fetchone() is not None