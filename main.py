import hashlib
import hmac
import os
import time
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from slack_sdk import WebClient
from claude_agent import run_agent

slack_client = WebClient(token=os.environ.get("SLACK_BOT_TOKEN", ""))

# In-memory conversation history per channel (resets on restart)
# For persistence upgrade to Supabase later
conversation_histories: dict[str, list] = {}
MAX_HISTORY = 20  # messages per channel


def verify_slack_signature(body: bytes, timestamp: str, signature: str) -> bool:
    signing_secret = os.environ.get("SLACK_SIGNING_SECRET", "").encode()
    base = f"v0:{timestamp}:{body.decode()}".encode()
    expected = "v0=" + hmac.new(signing_secret, base, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def handle_message(channel: str, user: str, text: str, thread_ts: str = None):
    """Process message and reply in Slack."""
    bot_user_id = os.environ.get("SLACK_BOT_USER_ID", "")

    # Strip bot mention from text
    clean_text = text.replace(f"<@{bot_user_id}>", "").strip()
    if not clean_text:
        return

    # Get or create conversation history for this channel
    history = conversation_histories.setdefault(channel, [])

    # Typing indicator
    slack_client.reactions_add(channel=channel, name="thinking_face", timestamp=thread_ts or "")

    try:
        response = run_agent(clean_text, history)
    except Exception as e:
        response = f"Ups, prišlo je do napake: {str(e)}"

    # Trim history to avoid token bloat
    if len(history) > MAX_HISTORY:
        conversation_histories[channel] = history[-MAX_HISTORY:]

    # Post reply (in thread if message was in thread)
    slack_client.chat_postMessage(
        channel=channel,
        text=response,
        thread_ts=thread_ts,
        mrkdwn=True,
    )

    slack_client.reactions_remove(channel=channel, name="thinking_face", timestamp=thread_ts or "")


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Eagle Events AI Bot started")
    yield


app = FastAPI(lifespan=lifespan)


@app.post("/slack/events")
async def slack_events(request: Request, background_tasks: BackgroundTasks):
    body = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    # Replay attack protection
    if abs(time.time() - int(timestamp)) > 60 * 5:
        raise HTTPException(status_code=400, detail="Request too old")

    if not verify_slack_signature(body, timestamp, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    payload = await request.json()

    # Slack URL verification challenge
    if payload.get("type") == "url_verification":
        return {"challenge": payload["challenge"]}

    event = payload.get("event", {})
    event_type = event.get("type")

    # Only handle direct messages and mentions
    bot_user_id = os.environ.get("SLACK_BOT_USER_ID", "")
    if event_type == "app_mention" or (
        event_type == "message"
        and event.get("channel_type") == "im"
        and event.get("user") != bot_user_id
        and not event.get("bot_id")
        and not event.get("subtype")
    ):
        channel = event["channel"]
        user = event.get("user", "")
        text = event.get("text", "")
        thread_ts = event.get("thread_ts") or event.get("ts")

        background_tasks.add_task(handle_message, channel, user, text, thread_ts)

    return {"ok": True}


@app.get("/health")
async def health():
    return {"status": "ok"}
