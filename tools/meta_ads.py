import httpx
import os
from typing import Optional

BASE_URL = "https://graph.facebook.com/v20.0"


def _get(endpoint: str, params: dict) -> dict:
    params["access_token"] = os.environ["META_ACCESS_TOKEN"]
    r = httpx.get(f"{BASE_URL}{endpoint}", params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def get_ad_performance(days: int = 7, level: str = "ad") -> dict:
    """Fetch performance metrics for the last N days."""
    account_id = os.environ["META_AD_ACCOUNT_ID"]
    return _get(f"/{account_id}/insights", {
        "level": level,
        "date_preset": f"last_{days}d",
        "fields": "campaign_name,adset_name,ad_name,impressions,clicks,spend,ctr,cpm,cpp,actions,cost_per_action_type",
        "limit": 50,
    })


def get_active_campaigns() -> dict:
    """List all active campaigns."""
    account_id = os.environ["META_AD_ACCOUNT_ID"]
    return _get(f"/{account_id}/campaigns", {
        "effective_status": '["ACTIVE"]',
        "fields": "id,name,objective,status,budget_remaining,daily_budget,lifetime_budget",
        "limit": 25,
    })


def get_active_ads() -> dict:
    """List active ads with creative info."""
    account_id = os.environ["META_AD_ACCOUNT_ID"]
    return _get(f"/{account_id}/ads", {
        "effective_status": '["ACTIVE"]',
        "fields": "id,name,adset_id,creative{title,body,image_url},status",
        "limit": 25,
    })


def create_ad_creative(page_id: str, title: str, body: str, image_url: str = None, link_url: str = None) -> dict:
    """Create a new ad creative."""
    account_id = os.environ["META_AD_ACCOUNT_ID"]
    data = {
        "name": f"Creative - {title[:30]}",
        "object_story_spec": {
            "page_id": page_id,
            "link_data": {
                "message": body,
                "name": title,
                "link": link_url or "https://www.facebook.com",
            }
        },
        "access_token": os.environ["META_ACCESS_TOKEN"],
    }
    if image_url:
        data["object_story_spec"]["link_data"]["picture"] = image_url

    r = httpx.post(f"{BASE_URL}/{account_id}/adcreatives", json=data, timeout=15)
    r.raise_for_status()
    return r.json()


def create_ad(name: str, adset_id: str, creative_id: str, status: str = "PAUSED") -> dict:
    """Create a new ad in an existing ad set. Default status PAUSED for review before activation."""
    account_id = os.environ["META_AD_ACCOUNT_ID"]
    data = {
        "name": name,
        "adset_id": adset_id,
        "creative": {"creative_id": creative_id},
        "status": status,
        "access_token": os.environ["META_ACCESS_TOKEN"],
    }
    r = httpx.post(f"{BASE_URL}/{account_id}/ads", json=data, timeout=15)
    r.raise_for_status()
    return r.json()


def update_ad_status(ad_id: str, status: str) -> dict:
    """Activate, pause or archive an ad. Status: ACTIVE, PAUSED, ARCHIVED."""
    data = {"status": status, "access_token": os.environ["META_ACCESS_TOKEN"]}
    r = httpx.post(f"{BASE_URL}/{ad_id}", json=data, timeout=15)
    r.raise_for_status()
    return r.json()


def get_audience_insights(adset_id: str) -> dict:
    """Get targeting details for an ad set."""
    return _get(f"/{adset_id}", {
        "fields": "name,targeting,daily_budget,optimization_goal,billing_event",
    })


# Tool definitions for Claude
TOOLS = [
    {
        "name": "get_ad_performance",
        "description": "Pridobi performance metrike (CTR, CPC, spend, konverzije) za Facebook oglase Eagle Events za zadnjih N dni. Uporabi za analizo rezultatov in primerjavo oglasom.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Število dni nazaj (privzeto 7)", "default": 7},
                "level": {"type": "string", "enum": ["campaign", "adset", "ad"], "description": "Nivo agregacije", "default": "ad"},
            },
        },
    },
    {
        "name": "get_active_campaigns",
        "description": "Seznam vseh aktivnih kampanj Eagle Events na Facebooku z budget informacijami.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_active_ads",
        "description": "Seznam aktivnih oglasov z copy (naslov, tekst) in creative informacijami.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "create_ad_creative",
        "description": "Ustvari nov ad creative v Meta Ads (naslov, tekst, slika, link). Uporabi ko imaš pripravljen copy in želiš direktno objaviti oglas.",
        "input_schema": {
            "type": "object",
            "properties": {
                "page_id": {"type": "string", "description": "Facebook Page ID Eagle Events"},
                "title": {"type": "string", "description": "Naslov oglasa (headline)"},
                "body": {"type": "string", "description": "Glavni tekst oglasa"},
                "image_url": {"type": "string", "description": "URL slike za oglas (opcijsko)"},
                "link_url": {"type": "string", "description": "Destination URL za oglas"},
            },
            "required": ["page_id", "title", "body"],
        },
    },
    {
        "name": "create_ad",
        "description": "Ustvari nov oglas v obstoječem ad setu. Oglas je privzeto PAUSED za pregled pred aktivacijo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Ime oglasa"},
                "adset_id": {"type": "string", "description": "ID ad seta v katerega gre oglas"},
                "creative_id": {"type": "string", "description": "ID kreative (iz create_ad_creative)"},
                "status": {"type": "string", "enum": ["PAUSED", "ACTIVE"], "description": "PAUSED za pregled, ACTIVE za takojšnjo objavo", "default": "PAUSED"},
            },
            "required": ["name", "adset_id", "creative_id"],
        },
    },
    {
        "name": "update_ad_status",
        "description": "Aktiviraj, pavziraj ali arhiviraj obstoječ oglas.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ad_id": {"type": "string", "description": "ID oglasa"},
                "status": {"type": "string", "enum": ["ACTIVE", "PAUSED", "ARCHIVED"]},
            },
            "required": ["ad_id", "status"],
        },
    },
    {
        "name": "get_audience_insights",
        "description": "Targeting nastavitve (starost, interesi, lokacija) za določen ad set.",
        "input_schema": {
            "type": "object",
            "properties": {
                "adset_id": {"type": "string", "description": "ID ad seta"},
            },
            "required": ["adset_id"],
        },
    },
]

HANDLERS = {
    "get_ad_performance": lambda inp: get_ad_performance(**inp),
    "get_active_campaigns": lambda inp: get_active_campaigns(),
    "get_active_ads": lambda inp: get_active_ads(),
    "get_audience_insights": lambda inp: get_audience_insights(**inp),
    "create_ad_creative": lambda inp: create_ad_creative(**inp),
    "create_ad": lambda inp: create_ad(**inp),
    "update_ad_status": lambda inp: update_ad_status(**inp),
}
