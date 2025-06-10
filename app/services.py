import os
import re
import json
import requests
import markdown as md
import docx
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import logging

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configure a logger for this module
logger = logging.getLogger(__name__)

# ========== CONFIGS ==========
API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")
ENDPOINT = os.getenv("ENDPOINT")

GOOGLE_CREDENTIALS_FILE = os.getenv('GOOGLE_CREDENTIALS_FILE', 'credentials.json')
GOOGLE_DRIVE_FOLDER_ID = os.getenv('GOOGLE_DRIVE_FOLDER_ID')
API_KEY_GOOGLE = os.getenv("API_KEY_GOOGLE")
ENGINE_ID_GOOGLE = os.getenv("ENGINE_ID_GOOGLE")

# --------- Helpers ---------

def count_words_fa(text):
    """Count Persian/English words in a text."""
    if not text:
        return 0
    return len(re.findall(r'\\w+', text))


def upload_as_google_doc(local_filepath, article_title, folder_id):
    """
    Upload a docx file to Google Drive as a Google-Doc,
    then delete the local file and return the new file's ID.
    """
    try:
        SCOPES = ['https://www.googleapis.com/auth/drive']
        creds = service_account.Credentials.from_service_account_file(
            GOOGLE_CREDENTIALS_FILE, scopes=SCOPES
        )
        service = build('drive', 'v3', credentials=creds)
        metadata = {
            'name': article_title,
            'parents': [folder_id],
            'mimeType': 'application/vnd.google-apps.document'
        }
        media = MediaFileUpload(
            local_filepath,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            resumable=True
        )
        file = service.files().create(body=metadata, media_body=media, fields='id').execute()
        os.remove(local_filepath)
        return file.get('id')
    except Exception as e:
        logger.error(f"❌ Error uploading to Google Drive: {e}")
        return None


def create_word_document(markdown_text, file_title):
    """
    Convert the markdown_text into a .docx file,
    using right-to-left Vazirmatn font, and return the filename.
    """
    safe_filename = re.sub(r'[\\/*?:"<>|]', "", file_title)
    filename = f"مقاله - {safe_filename}.docx"
    # Save to a temporary location or data/generated_docs
    temp_dir = "data/generated_docs"
    os.makedirs(temp_dir, exist_ok=True)
    full_filepath = os.path.join(temp_dir, filename)

    doc = docx.Document()
    style = doc.styles['Normal']
    style.font.name = 'Vazirmatn'
    style.font.size = Pt(12)
    para_fmt = style.paragraph_format
    para_fmt.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    # make section RTL
    section = doc.sections[0]
    section.right_to_left = True

    lines = markdown_text.split('\\n')
    in_table, table = False, None

    for line in lines:
        line = line.rstrip()
        if not line:
            continue

        # Table rows
        if line.startswith('|') and line.endswith('|'):
            if not in_table:
                in_table = True
                # header row
                cells = [c.strip() for c in line.split('|')[1:-1]]
                table = doc.add_table(rows=1, cols=len(cells))
                table.style = 'Table Grid'
                for idx, txt in enumerate(cells):
                    table.rows[0].cells[idx].text = txt
            else:
                cells = [c.strip() for c in line.split('|')[1:-1]]
                row = table.add_row().cells
                for idx, txt in enumerate(cells):
                    row[idx].text = txt
            continue
        else:
            in_table = False

        # Headings
        if line.startswith('### '):
            p = doc.add_heading(line[4:], level=3)
        elif line.startswith('## '):
            p = doc.add_heading(line[3:], level=2)
        elif line.startswith('# '):
            p = doc.add_heading(line[2:], level=1)
        # Lists
        elif line.startswith('* '):
            p = doc.add_paragraph(line[2:], style='List Bullet')
        elif re.match(r'^\\d+\\.\\s', line):
            p = doc.add_paragraph(re.sub(r'^\\d+\\.\\s', '', line), style='List Number')
        # Blockquote
        elif line.startswith('> '):
            p = doc.add_paragraph(line[2:])
            p.style.font.italic = True
        else:
            # bold markup in-line
            p = doc.add_paragraph()
            parts = re.split(r'(\\*\\*.*?\\*\\*)', line)
            for part in parts:
                if part.startswith('**') and part.endswith('**'):
                    run = p.add_run(part[2:-2])
                    run.bold = True
                else:
                    p.add_run(part)

        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    doc.save(full_filepath)
    return full_filepath


def generate_content_bundle_with_avalai(prompt_text, temperature, expect_json=False):
    """
    Call AvvalAI ChatCompletion endpoint.
    If expect_json=True, request a pure JSON object in response.
    """
    url = f"{BASE_URL}{ENDPOINT}"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gemini-2.5-flash-preview-05-20",
        "messages": [{"role": "user", "content": prompt_text}],
        "temperature": temperature,
        "stream": False
    }
    if expect_json:
        payload["response_format"] = {"type": "json_object"}

    try:
        resp = requests.post(url, headers=headers, data=json.dumps(payload))
        resp.raise_for_status()
        data = resp.json()
        return data['choices'][0]['message']['content']
    except requests.exceptions.RequestException as e:
        logger.error(f"API Request Error to AvvalAI: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Raw AvvalAI response content on error: {e.response.text}")
            return {"error": f"AvvalAI API request failed: {e.response.text}"}
        return {"error": f"AvvalAI API request failed: {e}"}
    except json.JSONDecodeError as e:
        logger.error(f"JSON Decode Error from AvvalAI response: {e}. Raw response: {resp.text if 'resp' in locals() else 'N/A'}")
        return {"error": f"Invalid JSON response from AvvalAI API: {e}"}
    except Exception as e:
        logger.error(f"An unexpected error occurred during AvvalAI call: {e}")
        return {"error": f"An unexpected error occurred: {e}"}


def perform_Google_Search(query):
    """Return up to 5 top search results from Google Custom Search JSON API."""
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            'key': API_KEY_GOOGLE,
            'cx' : ENGINE_ID_GOOGLE,
            'q'  : query,
            'num': 5
        }
        r = requests.get(url, params=params)
        r.raise_for_status()
        return r.json().get('items', [])
    except requests.exceptions.RequestException as e:
        logger.error(f"Google Search API Request Error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Raw Google Search response content on error: {e.response.text}")
        return []
    except Exception as e:
        logger.error(f"An unexpected error occurred during Google Search: {e}")
        return [] 