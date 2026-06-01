import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def _service():
    creds_json = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    creds_info = json.loads(creds_json)
    creds = service_account.Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)


def list_marketing_files(query: str = "", max_results: int = 20) -> dict:
    """List files in the Eagle Events marketing Drive folder."""
    folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "")
    service = _service()

    q_parts = [f"'{folder_id}' in parents", "trashed = false"] if folder_id else ["trashed = false"]
    if query:
        q_parts.append(f"name contains '{query}'")

    results = service.files().list(
        q=" and ".join(q_parts),
        pageSize=max_results,
        fields="files(id,name,mimeType,modifiedTime,size,description)",
    ).execute()
    return results


def read_file_content(file_id: str) -> str:
    """Read text content from a Drive file (Docs, txt, etc.)."""
    service = _service()
    file_meta = service.files().get(fileId=file_id, fields="mimeType,name").execute()
    mime = file_meta.get("mimeType", "")

    if "google-apps.document" in mime:
        content = service.files().export(fileId=file_id, mimeType="text/plain").execute()
        return content.decode("utf-8") if isinstance(content, bytes) else content
    else:
        request = service.files().get_media(fileId=file_id)
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buf.getvalue().decode("utf-8", errors="replace")


# Tool definitions for Claude
TOOLS = [
    {
        "name": "list_marketing_files",
        "description": "Prikaži datoteke iz Eagle Events Google Drive marketing mape. Poišči slike, videe, copy dokumente, briefe za oglase.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Iskalni niz za filtriranje po imenu datoteke (npr. 'festival', 'oglas', 'september')"},
                "max_results": {"type": "integer", "description": "Max število rezultatov", "default": 20},
            },
        },
    },
    {
        "name": "read_file_content",
        "description": "Preberi vsebino datoteke iz Google Drive (brief, copy dokument, navodila).",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_id": {"type": "string", "description": "Google Drive file ID"},
            },
            "required": ["file_id"],
        },
    },
]

HANDLERS = {
    "list_marketing_files": lambda inp: list_marketing_files(**inp),
    "read_file_content": lambda inp: read_file_content(**inp),
}
