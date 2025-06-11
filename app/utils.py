import os

def load_prompt_template(filename: str) -> str:
    """Loads a prompt template from the app/prompts directory."""
    filepath = os.path.join(os.path.dirname(__file__), "prompts", filename)
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"Prompt file not found: {filepath}")
    except Exception as e:
        raise IOError(f"Error loading prompt file {filepath}: {e}") 