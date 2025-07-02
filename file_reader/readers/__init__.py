# file_reader/readers/__init__.py
"""
Auto-importación de todos los readers para registro automático de plugins.
"""

# Importar todos los readers para que se registren automáticamente
from .base_reader import BaseReader
from .csv_reader import CsvReader
from .docx_reader import DocxReader
from .json_reader import JsonReader

from .txt_reader import TxtReader
from .xml_reader import XmlReader
from .yaml_reader import YamlReader

__all__ = [
    'BaseReader',
    'CsvReader', 
    'DocxReader',
    'JsonReader',
    'TxtReader',
    'XmlReader',
    'YamlReader'
]