from enum import Enum

class OutputFormat(str, Enum):
    MARKDOWN = "markdown"
    MARKDOWN_AI = "markdown_ai"  # Optimizado para IA con metadata y estructura semántica
    PLAIN = "plain"
    STRUCTURED_JSON = "structured_json"  # Para procesamiento programático