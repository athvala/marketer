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
from db import load_history, save_history

slack_client = WebClient(token=os.environ.get("SLACK_BOT_TOKEN", ""))

# Deduplication: track processed event IDs to ignore Slack retries
processed_events: set[str] = set()
MAX_PROCESSED = 1000


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

    history = load_history(channel)

    # Post "thinking" placeholder
    placeholder = slack_client.chat_postMessage(
        channel=channel,
        text="_Razmišljam..._",
        mrkdwn=True,
    )
    placeholder_ts = placeholder["ts"]

    try:
        response, updated_history = run_agent(clean_text, history)
    except Exception as e:
        import traceback
        print(f"ERROR in channel={channel}: {traceback.format_exc()}")
        response = f"Ups, prišlo je do napake: {str(e)}"
        updated_history = history

    save_history(channel, updated_history)

    # Update placeholder with real response
    slack_client.chat_update(
        channel=channel,
        ts=placeholder_ts,
        text=response,
        mrkdwn=True,
    )


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

    # Deduplicate retries
    event_id = payload.get("event_id", "")
    if event_id and event_id in processed_events:
        return {"ok": True}
    if event_id:
        processed_events.add(event_id)
        if len(processed_events) > MAX_PROCESSED:
            processed_events.clear()

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
