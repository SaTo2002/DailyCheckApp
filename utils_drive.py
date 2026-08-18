import os

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def get_drive_service():
    """Authenticate and return the Google Drive service."""
    service_account_file = os.getenv("SERVICE_ACCOUNT_FILE", "service_account.json")

    if not os.path.exists(service_account_file):
        print(f"[Drive] Service account file not found: {service_account_file}")
        return None

    try:
        creds = service_account.Credentials.from_service_account_file(
            service_account_file, scopes=SCOPES
        )
        service = build("drive", "v3", credentials=creds)
        return service
    except Exception as e:
        print(f"[Drive] Authentication failed: {e}")
        return None


def get_or_create_folder(service, folder_name, parent_id):
    """Finds a folder by name inside a parent. If not found, creates it."""
    try:
        # Search for the folder
        query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and '{parent_id}' in parents and trashed=false"
        results = (
            service.files()
            .list(q=query, spaces="drive", fields="files(id, name)")
            .execute()
        )
        items = results.get("files", [])

        if items:
            return items[0]["id"]

        # If not found, create it
        file_metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id],
        }
        folder = service.files().create(body=file_metadata, fields="id").execute()
        return folder.get("id")
    except Exception as e:
        print(f"[Drive] Failed to get/create folder '{folder_name}': {e}")
        return None


def upload_pdf_to_drive(pdf_path, year_str, month_str, area_name):
    """
    Uploads the PDF to Drive maintaining the YYYY/MM/Area_Name hierarchy.
    """
    use_drive = os.getenv("USE_GOOGLE_DRIVE", "False").lower() in ["true", "1", "yes"]
    if not use_drive:
        print("[Drive] Google Drive upload is disabled in .env")
        return False

    root_folder_id = os.getenv("DRIVE_ROOT_FOLDER_ID")
    if not root_folder_id:
        print("[Drive] DRIVE_ROOT_FOLDER_ID is missing from .env")
        return False

    if not os.path.exists(pdf_path):
        print(f"[Drive] File not found: {pdf_path}")
        return False

    service = get_drive_service()
    if not service:
        return False

    # 1. Year Folder
    year_folder_id = get_or_create_folder(service, year_str, root_folder_id)
    if not year_folder_id:
        return False

    # 2. Month Folder
    month_folder_id = get_or_create_folder(service, month_str, year_folder_id)
    if not month_folder_id:
        return False

    # 3. Area Folder
    area_folder_id = get_or_create_folder(service, area_name, month_folder_id)
    if not area_folder_id:
        return False

    # 4. Upload File
    try:
        file_name = os.path.basename(pdf_path)
        file_metadata = {"name": file_name, "parents": [area_folder_id]}
        media = MediaFileUpload(pdf_path, mimetype="application/pdf", resumable=True)

        uploaded_file = (
            service.files()
            .create(body=file_metadata, media_body=media, fields="id")
            .execute()
        )

        print(
            f"[Drive] Successfully uploaded: {file_name} (ID: {uploaded_file.get('id')})"
        )
        return True
    except Exception as e:
        print(f"[Drive] Upload failed: {e}")
        return False
