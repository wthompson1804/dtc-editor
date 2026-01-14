from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from pathlib import Path
import logging
import json

logger = logging.getLogger(__name__)


@dataclass
class GoogleExportConfig:
    """Configuration for Google Drive export."""
    credentials_path: str  # Path to service account JSON or OAuth credentials
    folder_id: Optional[str] = None  # Target folder ID (None = root)


@dataclass
class GoogleExportResult:
    """Result of Google Drive upload."""
    status: str  # "ok" | "failed" | "skipped"
    file_id: Optional[str] = None
    web_view_link: Optional[str] = None
    message: str = ""


def _load_credentials(credentials_path: str):
    """Load credentials from service account JSON or OAuth JSON."""
    from google.oauth2 import service_account
    from google.oauth2.credentials import Credentials

    with open(credentials_path, 'r') as f:
        cred_data = json.load(f)

    # Detect credential type
    if 'type' in cred_data and cred_data['type'] == 'service_account':
        logger.debug("Loading service account credentials")
        return service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=['https://www.googleapis.com/auth/drive.file']
        )
    else:
        # OAuth credentials (from user consent flow)
        logger.debug("Loading OAuth user credentials")
        return Credentials.from_authorized_user_file(
            credentials_path,
            scopes=['https://www.googleapis.com/auth/drive.file']
        )


def upload_to_google_drive(
    docx_path: str,
    config: GoogleExportConfig,
    title: Optional[str] = None,
) -> GoogleExportResult:
    """
    Upload a DOCX file to Google Drive with auto-conversion to Google Docs.

    Args:
        docx_path: Path to the .docx file to upload
        config: Google Drive configuration
        title: Optional title for the Google Doc (defaults to filename)

    Returns:
        GoogleExportResult with file ID and web link
    """
    # Check for library availability
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        logger.warning("google-api-python-client not installed")
        return GoogleExportResult(
            status="skipped",
            message="google-api-python-client not installed. Run: pip install google-api-python-client google-auth"
        )

    # Validate inputs
    if not Path(docx_path).exists():
        return GoogleExportResult(
            status="failed",
            message=f"DOCX file not found: {docx_path}"
        )

    if not Path(config.credentials_path).exists():
        return GoogleExportResult(
            status="failed",
            message=f"Credentials file not found: {config.credentials_path}"
        )

    try:
        # Load credentials
        creds = _load_credentials(config.credentials_path)

        # Build Drive API client
        service = build('drive', 'v3', credentials=creds)

        # Prepare file metadata
        file_title = title or Path(docx_path).stem
        file_metadata = {
            'name': file_title,
            'mimeType': 'application/vnd.google-apps.document',  # Auto-convert to Google Docs
        }
        if config.folder_id:
            file_metadata['parents'] = [config.folder_id]

        logger.info(f"Uploading '{file_title}' to Google Drive...")

        # Upload with conversion
        media = MediaFileUpload(
            docx_path,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            resumable=True
        )

        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        ).execute()

        file_id = file.get('id')
        web_link = file.get('webViewLink')

        logger.info(f"Upload successful: {web_link}")

        return GoogleExportResult(
            status="ok",
            file_id=file_id,
            web_view_link=web_link,
            message="Successfully uploaded and converted to Google Docs"
        )

    except Exception as e:
        logger.error(f"Google Drive upload failed: {type(e).__name__}: {e}")
        return GoogleExportResult(
            status="failed",
            message=f"Google Drive upload failed: {type(e).__name__}: {e}"
        )
