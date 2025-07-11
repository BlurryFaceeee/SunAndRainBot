import sqlite3
from datetime import datetime, timedelta

def init_db():
    conn = sqlite3.connect('notifications.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            city TEXT NOT NULL, 
            notification_time TEXT NOT NULL,
            timezone_offset TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1
        )
    ''')
    conn.commit()
    conn.close()


def add_notification(user_id: int, city: str, notification_time: str, timezone_offset: str):
    conn = sqlite3.connect('notifications.db')
    cursor = conn.cursor()
    cursor.execute(
        '''
        INSERT INTO notifications (user_id, city, notification_time, timezone_offset, is_active)
        VALUES (?, ?, ?, ?, ?)
        ''',
        (user_id, city, notification_time, timezone_offset, 1)
    )
    conn.commit()
    conn.close()


def get_user_notifications(user_id):
    conn = sqlite3.connect('notifications.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT city, notification_time FROM notifications 
        WHERE user_id = ? AND is_active = 1
    ''', (user_id,))

    notifications = cursor.fetchall()
    conn.close()
    return notifications

def get_all_user_notifications(user_id):
    conn = sqlite3.connect('notifications.db')
    cursor = conn.cursor()

    cursor.execute('''
           SELECT id, city, notification_time, timezone_offset, is_active 
           FROM notifications 
           WHERE user_id = ?
       ''', (user_id,))

    notifications = []
    for row in cursor.fetchall():
        notif_id, city, bot_time, offset, is_active = row

        user_time = (datetime.strptime(bot_time, "%H:%M") + timedelta(hours=float(offset))).strftime("%H:%M")
        notifications.append((notif_id, city, user_time, is_active))
    conn.close()
    return notifications

def delete_notification(notification_id):
    conn = sqlite3.connect('notifications.db')
    cursor = conn.cursor()

    cursor.execute('DELETE FROM notifications WHERE id = ?', (notification_id,))

    conn.commit()
    conn.close()

def toggle_notification_status(notification_id):
    conn = sqlite3.connect('notifications.db')
    cursor = conn.cursor()

    cursor.execute('SELECT is_active FROM notifications WHERE id = ?', (notification_id,))
    current_status = cursor.fetchone()[0]
    new_status = not current_status

    cursor.execute('''
        UPDATE notifications 
        SET is_active = ? 
        WHERE id = ?
    ''', (new_status, notification_id))

    conn.commit()
    conn.close()
    return new_status

def get_notifications_to_send():
    """Возвращает все активные уведомления."""
    conn = sqlite3.connect('notifications.db')
    cursor = conn.cursor()
    cursor.execute(
        '''
        SELECT user_id, city, notification_time, timezone_offset
        FROM notifications
        WHERE is_active = 1
        '''
    )
    notifications = cursor.fetchall()
    conn.close()
    return notifications