from file_reader.readers.base_reader import BaseReader
from file_reader.core.plugin_registry import PluginRegistry
from file_reader.core.enums import OutputFormat
import os
import logging
from typing import Dict, List, Tuple, Optional, Any

# Configuración minimalista para Lambda
logger = logging.getLogger(__name__)

# Variables de entorno para control de logging y optimización
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'ERROR')
ENABLE_DEBUG = os.environ.get('ENABLE_DEBUG', 'false').lower() == 'true'
ENABLE_METRICS = os.environ.get('ENABLE_METRICS', 'false').lower() == 'true'
QUALITY_MODE = os.environ.get('DOCX_QUALITY_MODE', 'balanced').lower()
SAFE_MODE = os.environ.get('DOCX_SAFE_MODE', 'false').lower() == 'true'

# Configurar logging mínimo con validación
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
    logger.addHandler(handler)
    
    # Validar LOG_LEVEL
    try:
        log_level = getattr(logging, LOG_LEVEL.upper())
        logger.setLevel(log_level)
    except AttributeError:
        logger.setLevel(logging.ERROR)
        logger.warning(f"LOG_LEVEL inválido '{LOG_LEVEL}', usando ERROR")

class ProcessingLimits:
    """Límites optimizados para Lambda"""
    MAX_FILE_SIZE_MB = 50
    MAX_PARAGRAPHS = 5000
    MAX_TABLES = 50
    MAX_TABLE_ROWS = 100
    MAX_TABLE_COLS = 10
    MAX_CELL_LENGTH = 50

class ContentType:
    """Tipos de contenido - constantes ligeras"""
    TEXT = 'text'
    JSON = 'json'
    HTTP = 'http'
    URL = 'url'
    LIST_ITEM = 'list_item'
    CODE = 'code'

@PluginRegistry.register("docx")
class DocxReader(BaseReader):
    """
    Reader optimizado para AWS Lambda con corrección de bugs críticos.
    """
    
    def __init__(self, config):
        super().__init__(config)
        self.limits = ProcessingLimits()
        
        # Lazy loading
        self._docx_module = None
        self._regex_patterns = None
        self._heading_keywords = None
        self._start_time = None
        
        if ENABLE_DEBUG:
            logger.info(f"DocxReader inicializado - Modo: {QUALITY_MODE}, Safe: {SAFE_MODE}")
    
    def _load_dependencies(self):
        """Lazy loading de dependencias pesadas"""
        if self._docx_module is None:
            try:
                from docx import Document
                import re
                
                self._docx_module = Document
                
                self._regex_patterns = {
                    'heading': re.compile(r'heading\s*(\d+)', re.IGNORECASE),
                    'level': re.compile(r'\d+')
                }
                
                self._heading_keywords = {
                    'CONTROL DE CAMBIOS', 'INTRODUCCIÓN', 'DESCRIPCIÓN DEL SERVICIO',
                    'DIAGRAMA GENERAL', 'ESPECIFICACIÓN DETALLADA', 'FIGURA',
                    'EJEMPLO MENSAJE', 'CÓDIGOS IFX', 'MECANISMOS'
                }
                    
            except ImportError as e:
                logger.error(f"Error cargando dependencias: {e}")
                raise
    
    def read(self, file_path: str) -> str:
        """Procesa documento DOCX de forma optimizada para Lambda."""
        if ENABLE_METRICS:
            import time
            self._start_time = time.time()
        
        file_name = os.path.basename(file_path)
        
        try:
            self._load_dependencies()
            self._validate_file_fast(file_path)
            
            if not self._is_compatible_format(file_path):
                return self._create_format_error(file_path)
            
            content = self._process_document_optimized(file_path)
            
            if ENABLE_METRICS:
                processing_time = (time.time() - self._start_time) * 1000
                logger.info(f"Documento procesado en {processing_time:.1f}ms")
            
            return content
            
        except FileNotFoundError:
            logger.error(f"Archivo no encontrado: {file_name}")
            raise
        except ValueError as e:
            logger.error(f"Error de validación en {file_name}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error procesando {file_name}: {str(e)}")
            return self._create_simple_error_fallback(file_path, str(e))
    
    def _validate_file_fast(self, file_path: str) -> None:
        """Validación rápida con detección mejorada"""
        if not os.path.exists(file_path):
            raise FileNotFoundError("Archivo no encontrado")
        
        file_size = os.path.getsize(file_path)
        max_size = self.limits.MAX_FILE_SIZE_MB * 1024 * 1024
        
        if file_size > max_size:
            raise ValueError(f"Archivo muy grande: {file_size / (1024*1024):.1f}MB")
        
        if file_size == 0:
            raise ValueError("Archivo vacío")
        
        # Validación de integridad
        try:
            import zipfile
            with zipfile.ZipFile(file_path, 'r') as test_zip:
                bad_file = test_zip.testzip()
                if bad_file:
                    raise ValueError(f"Archivo DOCX corrupto: {bad_file}")
                
                required_files = ['word/document.xml', '[Content_Types].xml']
                zip_files = test_zip.namelist()
                
                for required in required_files:
                    if required not in zip_files:
                        raise ValueError(f"Estructura DOCX inválida: falta {required}")
                
                if len(zip_files) > 1000:
                    logger.warning("Documento DOCX muy complejo detectado")
                    logger.warning("Recomendado usar DOCX_SAFE_MODE=true")
                        
        except (zipfile.BadZipFile, zipfile.LargeZipFile):
            raise ValueError("Archivo DOCX corrupto o inválido")
        except Exception as e:
            logger.warning(f"No se pudo validar completamente: {e}")
    
    def _is_compatible_format(self, file_path: str) -> bool:
        """Verificación rápida de formato"""
        return file_path.lower().endswith(('.docx', '.docm'))
    
    def _process_document_optimized(self, file_path: str) -> str:
        """Procesamiento principal optimizado"""
        try:
            doc = self._docx_module(file_path)
            doc_structure = self._extract_structure_fast(doc)
            content = self._format_content_efficient(doc_structure, file_path)
            
            final_content = self._apply_ai_formatting(content, file_path, "docx_document")
            return self._format_as_json(final_content, file_path, "docx_document")
            
        except (ValueError, OSError, TypeError) as e:
            raise ValueError(f"Archivo DOCX corrupto o inválido: {str(e)}")
        except Exception as e:
            logger.error(f"Error durante procesamiento: {str(e)}")
            return self._create_simple_error_fallback(file_path, str(e))
    
    def _extract_structure_fast(self, doc) -> Dict[str, Any]:
        """Extracción eficiente con consolidación segura"""
        paragraphs = []
        headings = []
        tables = []
        total_words = 0
        processing_truncated = False
        
        # Consolidación solo si no es modo fast o safe
        current_block = None
        current_block_type = None
        should_consolidate = QUALITY_MODE != 'fast' and not SAFE_MODE
        
        # Procesar párrafos
        for i, para in enumerate(doc.paragraphs):
            if i >= self.limits.MAX_PARAGRAPHS:
                processing_truncated = True
                break
            
            text = para.text.strip()
            if not text:
                continue
            
            try:
                para_info = self._analyze_paragraph_fast(para, text)
                
                # Consolidación inteligente
                if (should_consolidate and 
                    para_info['content_type'] in [ContentType.JSON, ContentType.HTTP, ContentType.CODE]):
                    
                    if (current_block_type == para_info['content_type'] and 
                        current_block and 
                        len(current_block['text']) + len(text) < 10000):
                        # Consolidar
                        current_block['text'] += '\n' + text
                        total_words += len(text.split())
                        continue
                    else:
                        # Finalizar bloque anterior
                        if current_block:
                            paragraphs.append(current_block)
                        
                        # Nuevo bloque
                        current_block = para_info.copy()
                        current_block_type = para_info['content_type']
                        total_words += len(text.split())
                        continue
                
                # Procesamiento normal
                if current_block:
                    paragraphs.append(current_block)
                    current_block = None
                    current_block_type = None
                
                if para_info['is_heading']:
                    headings.append(para_info)
                
                paragraphs.append(para_info)
                total_words += len(text.split())
                
            except Exception:
                continue
        
        # Finalizar último bloque
        if current_block:
            paragraphs.append(current_block)
        
        # Procesar tablas con anti-duplicación
        processed_table_ids = set()
        
        for i, table in enumerate(doc.tables):
            if i >= self.limits.MAX_TABLES:
                break
            
            try:
                table_id = self._generate_table_id(table, i)
                
                if table_id in processed_table_ids:
                    if ENABLE_DEBUG:
                        logger.debug(f"Tabla duplicada omitida: {i}")
                    continue
                
                table_data = self._extract_table_fast(table)
                if table_data:
                    tables.append(table_data)
                    processed_table_ids.add(table_id)
                    
            except Exception as e:
                if ENABLE_DEBUG:
                    logger.debug(f"Error procesando tabla {i}: {e}")
                continue
        
        return {
            'paragraphs': paragraphs,
            'headings': headings,
            'tables': tables,
            'metadata': {
                'total_paragraphs': len(paragraphs),
                'total_words': total_words,
                'total_tables': len(tables),
                'processing_truncated': processing_truncated
            }
        }
    
    def _analyze_paragraph_fast(self, para, text: str) -> Dict[str, Any]:
        """Análisis mejorado de párrafo"""
        is_heading = False
        level = 0
        
        # Detección de heading
        if para.style and 'heading' in para.style.name.lower():
            is_heading = True
            level_match = self._regex_patterns['level'].search(para.style.name)
            level = int(level_match.group()) if level_match else 1
        elif (len(text) > 0 and len(text) < 100 and len(text.split()) <= 8 and
              (':' not in text[:-1] if len(text) > 1 else True) and
              not text.startswith(('"', '{', '}', '[', ']')) and
              not text.startswith(('X-', 'Content-', 'Accept-', 'User-Agent')) and
              (text.isupper() or text.istitle() or text.endswith(':'))):
            is_heading = True
            level = 1 if text.isupper() and len(text.split()) <= 3 else 2
        
        # Detección de tipo de contenido
        if QUALITY_MODE == 'fast':
            content_type = self._detect_content_type_fast(text)
        else:
            content_type = self._detect_content_type_improved(text)
        
        return {
            'text': text,
            'style': para.style.name if para.style else 'Normal',
            'is_heading': is_heading,
            'level': min(level, 6),
            'content_type': content_type
        }
    
    def _detect_content_type_fast(self, text: str) -> str:
        """Detección ultra rápida"""
        if not text:
            return ContentType.TEXT
        
        first_char = text[0]
        
        if first_char in '{[':
            return ContentType.JSON
        elif first_char in '-*•':
            return ContentType.LIST_ITEM
        elif text.startswith(('POST', 'GET', 'PUT', 'DELETE', 'HTTP/', 'X-')):
            return ContentType.HTTP
        elif text.startswith(('http://', 'https://')):
            return ContentType.URL
        
        return ContentType.TEXT
    
    def _detect_content_type_improved(self, text: str) -> str:
        """Detección mejorada balanceada"""
        if not text:
            return ContentType.TEXT
        
        text_stripped = text.strip()
        first_char = text_stripped[0] if text_stripped else ''
        
        # Detección rápida por primer carácter
        if first_char in '{[':
            return ContentType.JSON
        elif first_char in '-*•':
            return ContentType.LIST_ITEM
        elif text_stripped.startswith(('POST ', 'GET ', 'PUT ', 'DELETE ', 'HTTP/')):
            return ContentType.HTTP
        elif text_stripped.startswith(('http://', 'https://')):
            return ContentType.URL
        
        # Detección específica para casos ambiguos
        if text_stripped.startswith('"') and (':' in text_stripped or text_stripped.endswith('",')):
            return ContentType.JSON
        
        if text_stripped.endswith(('},', '],')):
            return ContentType.JSON
        
        if text_stripped.startswith(('Accept-', 'Content-', 'X-', 'User-Agent:', 'Host:', 'Server:')):
            return ContentType.HTTP
        
        if text_stripped.count(':') > 3 or ('{' in text_stripped and '}' in text_stripped):
            return ContentType.CODE
        
        return ContentType.TEXT
    
    def _generate_table_id(self, table, index: int) -> str:
        """Genera ID único para tabla"""
        try:
            if not table.rows or not table.rows[0].cells:
                return f"empty_table_{index}"
            
            sample_content = []
            for i, row in enumerate(table.rows[:2]):
                for j, cell in enumerate(row.cells[:2]):
                    try:
                        cell_text = cell.text.strip()[:20]
                        if cell_text:
                            sample_content.append(cell_text)
                    except:
                        continue
                if len(sample_content) >= 3:
                    break
            
            content_hash = hash('|'.join(sample_content)) if sample_content else 0
            return f"table_{index}_{abs(content_hash)}"
            
        except Exception:
            return f"table_{index}_error"
    
    def _extract_table_fast(self, table) -> Optional[List[List[str]]]:
        """Extracción robusta de tabla"""
        try:
            if not table.rows:
                return None
            
            table_data = []
            
            for i, row in enumerate(table.rows):
                if i >= self.limits.MAX_TABLE_ROWS:
                    break
                
                row_data = []
                
                if not hasattr(row, 'cells') or not row.cells:
                    continue
                
                for j, cell in enumerate(row.cells[:self.limits.MAX_TABLE_COLS]):
                    try:
                        if hasattr(cell, 'text'):
                            cell_text = str(cell.text).strip()
                            cell_text = cell_text.replace('\x00', '').replace('\r', ' ').replace('\n', ' ')
                            cell_text = cell_text[:self.limits.MAX_CELL_LENGTH]
                            row_data.append(cell_text)
                        else:
                            row_data.append("")
                    except Exception as e:
                        if ENABLE_DEBUG:
                            logger.debug(f"Error en celda [{i},{j}]: {e}")
                        row_data.append("")
                
                # Solo agregar fila si tiene contenido válido
                if any(cell.strip() for cell in row_data if cell):
                    if len(row_data) < self.limits.MAX_TABLE_COLS and table_data:
                        target_length = len(table_data[0]) if table_data else len(row_data)
                        row_data.extend([''] * (target_length - len(row_data)))
                    
                    table_data.append(row_data)
            
            if not table_data or not table_data[0]:
                return None
            
            # Normalizar tabla
            max_cols = max(len(row) for row in table_data)
            max_cols = min(max_cols, self.limits.MAX_TABLE_COLS)
            
            normalized_table = []
            for row in table_data:
                normalized_row = (row + [''] * max_cols)[:max_cols]
                normalized_table.append(normalized_row)
            
            return normalized_table
            
        except Exception as e:
            if ENABLE_DEBUG:
                logger.warning(f"Error crítico extrayendo tabla: {e}")
            return None
    
    def _format_content_efficient(self, doc_structure: Dict[str, Any], file_path: str) -> str:
        """Formateo eficiente según configuración"""
        output_format = self.config.output_format
        
        if output_format == OutputFormat.MARKDOWN_AI:
            return self._format_ai_markdown_light(doc_structure, file_path)
        elif output_format == OutputFormat.MARKDOWN:
            return self._format_standard_markdown_fast(doc_structure)
        else:
            return self._format_plain_text_fast(doc_structure)
    
    def _format_standard_markdown_fast(self, doc_structure: Dict[str, Any]) -> str:
        """Conversión optimizada a Markdown"""
        content_parts = []
        in_code_block = False
        current_code_type = None
        
        for para in doc_structure['paragraphs']:
            text = para['text']
            content_type = para['content_type']
            
            if para['is_heading']:
                if in_code_block:
                    content_parts.append('```\n')
                    in_code_block = False
                    current_code_type = None
                
                level = para['level']
                content_parts.append(f"{'#' * level} {text}\n")
                
            elif content_type in [ContentType.JSON, ContentType.HTTP, ContentType.CODE]:
                if not in_code_block or current_code_type != content_type:
                    if in_code_block:
                        content_parts.append('```\n')
                    
                    lang = 'json' if content_type == ContentType.JSON else ('http' if content_type == ContentType.HTTP else '')
                    content_parts.append(f'```{lang}')
                    in_code_block = True
                    current_code_type = content_type
                
                content_parts.append(text)
                
            else:
                if in_code_block:
                    content_parts.append('```\n')
                    in_code_block = False
                    current_code_type = None
                
                if content_type == ContentType.URL:
                    content_parts.append(f"[{text}]({text})\n")
                elif content_type == ContentType.LIST_ITEM:
                    clean_text = text.lstrip('- *•').strip()
                    content_parts.append(f"- {clean_text}")
                else:
                    content_parts.append(f"{text}\n")
        
        if in_code_block:
            content_parts.append('```')
        
        # Agregar tablas con validación
        if doc_structure['tables'] and len(doc_structure['tables']) <= 10:
            content_parts.append("\n## Tablas\n")
            for i, table in enumerate(doc_structure['tables'], 1):
                if table and len(table) > 0:
                    content_parts.append(f"### Tabla {i}\n")
                    formatted_table = self._format_table_markdown_fast(table)
                    if formatted_table.strip():
                        content_parts.append(formatted_table)
                    else:
                        content_parts.append("*Tabla no pudo ser procesada correctamente*\n")
        
        result = "\n".join(content_parts)
        
        # Validación anti-duplicación
        if result.count('### Tabla') > len(doc_structure['tables']) * 2:
            logger.warning("Posible duplicación de tablas detectada")
            if SAFE_MODE:
                # Filtrar las partes que no son tablas
                filtered_parts = [part for part in content_parts if not part.startswith('## Tablas')]
                return "\n".join(filtered_parts)
        
        return result
    
    def _format_ai_markdown_light(self, doc_structure: Dict[str, Any], file_path: str) -> str:
        """Formato AI ligero"""
        metadata = doc_structure['metadata']
        file_name = os.path.basename(file_path)
        
        header_lines = [
            "## 📝 Word Document Analysis",
            f"- **File:** {file_name}",
            f"- **Content:** {metadata['total_paragraphs']} paragraphs, {metadata['total_words']:,} words, {metadata['total_tables']} tables"
        ]
        
        if metadata.get('processing_truncated'):
            header_lines.append("- **Note:** Document truncated due to size limits")
        
        header_lines.append("\n### 📖 Document Content\n")
        
        content = self._format_standard_markdown_fast(doc_structure)
        return "\n".join(header_lines) + content
    
    def _format_plain_text_fast(self, doc_structure: Dict[str, Any]) -> str:
        """Formato texto plano rápido"""
        return "\n".join(para['text'] for para in doc_structure['paragraphs'])
    
    def _format_table_markdown_fast(self, table_data: List[List[str]]) -> str:
        """Formato tabla Markdown robusto"""
        if not table_data or not table_data[0]:
            return ""
        
        try:
            max_cols = min(len(table_data[0]), self.limits.MAX_TABLE_COLS)
            if max_cols == 0:
                return ""
            
            # Limpiar datos
            clean_table = []
            for table_row in table_data[:20]:  # Cambié 'row' por 'table_row' para evitar conflictos
                clean_row = []
                for cell in table_row[:max_cols]:
                    clean_cell = str(cell).replace('|', '\\|').replace('\n', ' ').replace('\r', ' ').strip()
                    if len(clean_cell) > 100:
                        clean_cell = clean_cell[:97] + "..."
                    clean_row.append(clean_cell)
                
                while len(clean_row) < max_cols:
                    clean_row.append("")
                
                clean_table.append(clean_row)
            
            if not clean_table:
                return ""
            
            # Header
            header_row = clean_table[0]
            header = "| " + " | ".join(header_row) + " |"
            separator = "| " + " | ".join("---" for _ in header_row) + " |"
            
            # Rows
            markdown_rows = []  # Cambié 'rows' por 'markdown_rows' para evitar conflictos
            for table_row in clean_table[1:]:
                if len(table_row) == max_cols:
                    row_str = "| " + " | ".join(table_row) + " |"
                    markdown_rows.append(row_str)
            
            result = header + "\n" + separator + "\n" + "\n".join(markdown_rows) + "\n"
            
            if result.count('|') < 6:
                return ""
            
            return result
            
        except Exception as e:
            if ENABLE_DEBUG:
                logger.warning(f"Error formateando tabla: {e}")
            return ""
    
    def _create_format_error(self, file_path: str) -> str:
        """Error de formato simplificado"""
        file_name = os.path.basename(file_path)
        return f"""## ❌ Unsupported Format

**File:** {file_name}

Only .docx and .docm files are supported. Please convert your document and try again.
"""
    
    def _create_simple_error_fallback(self, file_path: str, error: str) -> str:
        """Fallback simple sin overhead"""
        file_name = os.path.basename(file_path)
        return f"""## ❌ Processing Error

**File:** {file_name}
**Error:** {error}

Unable to process document. Please check file format and try again.
"""