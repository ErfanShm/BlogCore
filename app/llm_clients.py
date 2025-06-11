import os
import logging
from dotenv import load_dotenv
from openai import OpenAI

# ── Load environment variables ───────────────────────────────────────────────
load_dotenv()
API_KEY     = os.getenv("API_KEY")              # your OpenAI API key
BASE_URL    = os.getenv("BASE_URL")             # e.g. "https://api.avalapis.ir/v1"
TIMEOUT_SEC = float(os.getenv("OPENAI_TIMEOUT", 90))

# ── Configure logging ────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ── Initialize OpenAI v1 client ─────────────────────────────────────────────
if not API_KEY or not BASE_URL:
    logger.warning("API_KEY or BASE_URL not set—OpenAI client will not initialize.")
    openai_client = None
else:
    openai_client = OpenAI(
        api_key=API_KEY,
        base_url=BASE_URL,      # <— correct param name
        timeout=TIMEOUT_SEC,
    )
    logger.info("OpenAI client initialized with base_url=%s", BASE_URL)

# ── Define your function‐calling schema ──────────────────────────────────────
FUNCTIONS = [
    {
        "name": "return_blog_content",
        "description": "Returns the generated article metadata and markdown",
        "parameters": {
            "type": "object",
            "properties": {
                "meta_descriptions": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "blog_post_markdown": {"type": "string"},
                "image_prompts": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            },
            "required": ["meta_descriptions", "blog_post_markdown"]
        }
    }
]

def get_openai_clients():
    """
    Returns (openai_client, FUNCTIONS) for use in services.py.
    """
    return openai_client, FUNCTIONS
