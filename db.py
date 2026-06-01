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
            if not row:
                return []
            # Keep only simple text messages — strip tool_use/tool_result to avoid API errors
            clean = []
            for msg in row[0]:
                content = msg.get("content", "")
                if isinstance(content, str) and content:
                    clean.append(msg)
                elif isinstance(content, list):
                    texts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
                    if texts:
                        clean.append({"role": msg["role"], "content": texts[0]})
            return clean


def _serialize(obj):
    """Convert Anthropic SDK objects to plain dicts for JSON storage."""
    if isinstance(obj, list):
        return [_serialize(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if hasattr(obj, "model_dump"):
        return _serialize(obj.model_dump())
    if hasattr(obj, "__dict__"):
        return _serialize(obj.__dict__)
    return obj


def save_history(channel_id: str, messages: list):
    trimmed = _serialize(messages[-MAX_HISTORY:])
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO conversation_history (channel_id, messages, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (channel_id) DO UPDATE
                SET messages = EXCLUDED.messages, updated_at = NOW()
            """, (channel_id, Json(trimmed)))
