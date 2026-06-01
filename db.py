import json
import os
import psycopg2
from psycopg2.extras import Json

MAX_HISTORY = 20


def _conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def load_history(channel_id: str) -> list:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT messages FROM conversation_history WHERE channel_id = %s", (channel_id,))
            row = cur.fetchone()
            return row[0] if row else []


def save_history(channel_id: str, messages: list):
    trimmed = messages[-MAX_HISTORY:]
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO conversation_history (channel_id, messages, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (channel_id) DO UPDATE
                SET messages = EXCLUDED.messages, updated_at = NOW()
            """, (channel_id, Json(trimmed)))
