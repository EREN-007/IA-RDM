"""
Connexion à l'API Google Drive et extraction du contenu des fichiers.
"""
import io
import os
import pickle
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

try:
    from docx import Document as DocxDocument
except ImportError:
    DocxDocument = None

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
TOKEN_FILE = "token.pickle"
CREDENTIALS_FILE = "credentials.json"

SUPPORTED_MIME_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/plain": "txt",
    "application/vnd.google-apps.document": "gdoc",
    "application/vnd.google-apps.presentation": "gslides",
}


def get_drive_service():
    """Authentifie et retourne le service Google Drive."""
    creds = None

    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"Fichier '{CREDENTIALS_FILE}' introuvable. "
                    "Téléchargez-le depuis Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "wb") as token:
            pickle.dump(creds, token)

    return build("drive", "v3", credentials=creds)


def list_files_in_folder(service, folder_id: str) -> list[dict]:
    """Liste récursivement tous les fichiers supportés dans le dossier Drive."""
    files = []
    page_token = None

    while True:
        query = (
            f"'{folder_id}' in parents and trashed = false and ("
            + " or ".join(f"mimeType='{m}'" for m in SUPPORTED_MIME_TYPES)
            + ")"
        )
        response = (
            service.files()
            .list(
                q=query,
                spaces="drive",
                fields="nextPageToken, files(id, name, mimeType, size)",
                pageToken=page_token,
            )
            .execute()
        )
        files.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    # Chercher aussi dans les sous-dossiers
    subfolder_query = f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    subfolders = service.files().list(q=subfolder_query, fields="files(id, name)").execute()
    for subfolder in subfolders.get("files", []):
        files.extend(list_files_in_folder(service, subfolder["id"]))

    return files


def _extract_text_from_pdf(content: bytes) -> str:
    if PyPDF2 is None:
        return "[PyPDF2 non installé — impossible d'extraire le PDF]"
    reader = PyPDF2.PdfReader(io.BytesIO(content))
    return "\n".join(
        page.extract_text() or "" for page in reader.pages
    )


def _extract_text_from_docx(content: bytes) -> str:
    if DocxDocument is None:
        return "[python-docx non installé — impossible d'extraire le DOCX]"
    doc = DocxDocument(io.BytesIO(content))
    return "\n".join(p.text for p in doc.paragraphs)


def download_and_extract_text(service, file_info: dict) -> str:
    """Télécharge un fichier Drive et retourne son contenu texte."""
    file_id = file_info["id"]
    mime = file_info["mimeType"]
    name = file_info["name"]

    try:
        # Les Google Docs natifs s'exportent en texte brut
        if mime == "application/vnd.google-apps.document":
            request = service.files().export_media(fileId=file_id, mimeType="text/plain")
        elif mime == "application/vnd.google-apps.presentation":
            request = service.files().export_media(fileId=file_id, mimeType="text/plain")
        else:
            request = service.files().get_media(fileId=file_id)

        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

        content = buffer.getvalue()

        if mime == "application/pdf":
            return f"=== {name} ===\n{_extract_text_from_pdf(content)}\n"
        elif mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            return f"=== {name} ===\n{_extract_text_from_docx(content)}\n"
        else:
            return f"=== {name} ===\n{content.decode('utf-8', errors='replace')}\n"

    except Exception as e:
        return f"[Erreur lors du téléchargement de '{name}': {e}]\n"


def sync_drive_content(folder_id: str, progress_callback=None) -> tuple[str, list[str]]:
    """
    Synchronise tous les fichiers du dossier Drive et retourne le texte agrégé.
    Retourne (texte_complet, liste_noms_fichiers).
    """
    service = get_drive_service()
    files = list_files_in_folder(service, folder_id)

    if not files:
        return "", []

    all_text = []
    file_names = []

    for i, file_info in enumerate(files):
        if progress_callback:
            progress_callback(i, len(files), file_info["name"])
        text = download_and_extract_text(service, file_info)
        all_text.append(text)
        file_names.append(file_info["name"])

    return "\n\n".join(all_text), file_names
