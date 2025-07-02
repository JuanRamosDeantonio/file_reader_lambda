from file_reader.readers.base_reader import BaseReader
from file_reader.core.plugin_registry import PluginRegistry
from file_reader.core.enums import OutputFormat
import os
import logging
import re
from typing import Dict, List, Optional, Any, Tuple

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

@PluginRegistry.register("docx")
class DocxReader(BaseReader):
    """
    Reader de producción para AWS Lambda usando Mammoth con post-procesamiento premium.
    Genera markdown de alta calidad con:
    - Detección automática de tablas y conversión a formato markdown
    - Unificación inteligente de bloques de código fragmentados  
    - Detección y mejora de índices/TOC
    - Limpieza avanzada de caracteres especiales y escapes
    - Estructura jerárquica mejorada de headers
    - Formateo automático de JSON, XML, HTTP y YAML
    - Compatible 100% con API existente
    """
    
    def __init__(self, config):
        super().__init__(config)
        self.limits = ProcessingLimits()
        
        # Lazy loading
        self._mammoth_module = None
        self._start_time = None
        
        if ENABLE_DEBUG:
            logger.info(f"DocxReader inicializado con Mammoth Premium - Modo: {QUALITY_MODE}")
            logger.info("Características: Detección de tablas, unificación de código, TOC mejorado")
    
    def _load_dependencies(self):
        """Lazy loading usando mammoth (sin dependencias lxml)"""
        if self._mammoth_module is None:
            try:
                import mammoth
                self._mammoth_module = mammoth
                logger.info("✅ Mammoth cargado exitosamente (sin dependencias lxml)")
            except ImportError as e:
                logger.error(f"Error cargando mammoth: {e}")
                raise
    
    def read(self, file_path: str) -> str:
        """
        Procesa documento DOCX usando Mammoth con post-procesamiento mejorado.
        MISMA API que tu versión anterior - sin cambios en el uso.
        """
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
        """Validación rápida - IGUAL que tu versión anterior"""
        if not os.path.exists(file_path):
            raise FileNotFoundError("Archivo no encontrado")
        
        file_size = os.path.getsize(file_path)
        max_size = self.limits.MAX_FILE_SIZE_MB * 1024 * 1024
        
        if file_size > max_size:
            raise ValueError(f"Archivo muy grande: {file_size / (1024*1024):.1f}MB")
        
        if file_size == 0:
            raise ValueError("Archivo vacío")
        
        # Validación de integridad DOCX
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
                        
        except (zipfile.BadZipFile, zipfile.LargeZipFile):
            raise ValueError("Archivo DOCX corrupto o inválido")
        except Exception as e:
            logger.warning(f"No se pudo validar completamente: {e}")
    
    def _is_compatible_format(self, file_path: str) -> bool:
        """Verificación de formato - IGUAL que antes"""
        return file_path.lower().endswith(('.docx', '.docm'))
    
    def _process_document_optimized(self, file_path: str) -> str:
        """
        Procesamiento principal usando Mammoth con mejoras avanzadas.
        """
        try:
            # Configurar opciones de Mammoth para mejor output
            with open(file_path, "rb") as docx_file:
                result = self._mammoth_module.convert_to_markdown(docx_file)
                base_markdown = result.value
                
                # Verificar que se generó contenido
                if not base_markdown or not base_markdown.strip():
                    return self._create_simple_error_fallback(file_path, "Documento vacío o no pudo ser procesado")
                
                # POST-PROCESAMIENTO MEJORADO
                processed_content = self._post_process_markdown(base_markdown)
                
                # Procesar según configuración
                if QUALITY_MODE == 'fast':
                    final_content = self._process_fast_mode(processed_content, file_path)
                else:
                    final_content = self._process_full_mode(processed_content, file_path, result)
                
                # MANTIENE tu sistema de AI formatting (si existe en la clase base)
                if hasattr(self, '_apply_ai_formatting'):
                    final_content = self._apply_ai_formatting(final_content, file_path, "docx_document")
                
                # Formatear salida final (si el método existe en la clase base)
                if hasattr(self, '_format_as_json'):
                    return self._format_as_json(final_content, file_path, "docx_document")
                else:
                    return final_content
        
        except Exception as e:
            logger.error(f"Error procesando con mammoth: {str(e)}")
            return self._create_simple_error_fallback(file_path, str(e))
    
    # ================== NUEVAS MEJORAS DE POST-PROCESAMIENTO ==================
    
    def _post_process_markdown(self, markdown_content: str) -> str:
        """Post-procesamiento avanzado para mejorar calidad del markdown"""
        if ENABLE_DEBUG:
            logger.info("Aplicando post-procesamiento avanzado")
        
        # 1. Limpiar caracteres extraños y espacios
        content = self._clean_special_characters(markdown_content)
        
        # 2. Mejorar estructura de headers
        content = self._improve_header_structure(content)
        
        # 3. Detectar y mejorar índices (TOC)
        content = self._improve_toc_detection(content)
        
        # 4. Unificar bloques de código fragmentados
        content = self._merge_fragmented_code_blocks(content)
        
        # 5. Mejorar detección y formato de tablas
        content = self._improve_table_detection(content)
        
        # 6. Mejorar formato de tablas existentes
        content = self._improve_tables(content)
        
        # 7. Mejorar listas y numeración
        content = self._improve_lists(content)
        
        # 8. Mejorar enlaces y referencias
        content = self._improve_links(content)
        
        # 9. Detectar y formatear mejor el código
        content = self._improve_code_detection(content)
        
        # 10. Limpieza final de escapes y formato
        content = self._final_escape_cleanup(content)
        
        # 11. Limpiar líneas vacías excesivas al final
        content = self._clean_final_formatting(content)
        
        return content
    
    def _clean_special_characters(self, content: str) -> str:
        """Limpia caracteres problemáticos como \\xa0, escapes innecesarios"""
        # Reemplazar espacios no separables
        content = content.replace('\xa0', ' ')
        content = content.replace('\u00a0', ' ')
        
        # Limpiar escapes innecesarios de caracteres comunes
        content = re.sub(r'\\([().,;:{}[\]])', r'\1', content)
        
        # Limpiar guiones y puntos escapados innecesariamente
        content = re.sub(r'\\([-.])', r'\1', content)
        
        # Limpiar hashtags escapados en texto normal (no headers)
        content = re.sub(r'\\#(?![#\s])', '#', content)
        
        # Limpiar múltiples espacios
        content = re.sub(r'[ \t]+', ' ', content)
        
        # Limpiar espacios al final de líneas
        content = re.sub(r'[ \t]+$', '', content, flags=re.MULTILINE)
        
        return content
    
    def _improve_header_structure(self, content: str) -> str:
        """Mejora la jerarquía y formato de headers"""
        lines = content.split('\n')
        improved_lines = []
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Procesar headers existentes
            if stripped.startswith('#'):
                # Limpiar headers mal formateados
                header_match = re.match(r'^(#+)\s*(.+)', stripped)
                if header_match:
                    level, title = header_match.groups()
                    # Limpiar título
                    clean_title = re.sub(r'[\\]', '', title.strip())
                    improved_lines.append(f"{level} {clean_title}")
                else:
                    improved_lines.append(line)
            # Detectar posibles headers sin formato
            elif (stripped and 
                  len(stripped) < 100 and 
                  not stripped.endswith('.') and 
                  len(stripped) > 0 and
                  stripped[0].isupper() and
                  self._looks_like_header(stripped, i, lines)):
                
                level = self._determine_header_level(stripped, i, lines)
                improved_lines.append(f"{'#' * level} {stripped}")
            else:
                improved_lines.append(line)
        
        return '\n'.join(improved_lines)
    
    def _looks_like_header(self, line: str, index: int, lines: List[str]) -> bool:
        """Determina si una línea parece ser un header"""
        # No debe contener muchos caracteres especiales
        if len(re.findall(r'[{}()\[\]"|:]', line)) > 2:
            return False
        
        # Debe ser relativamente corta
        if len(line) > 80:
            return False
        
        # Siguiente línea debe estar vacía o ser contenido
        if index + 1 < len(lines):
            next_line = lines[index + 1].strip()
            if next_line and next_line.startswith('#'):
                return False
        
        return True
    
    def _determine_header_level(self, line: str, index: int, lines: List[str]) -> int:
        """Determina el nivel de header basado en contexto"""
        # Por defecto nivel 2
        line_upper = line.upper()
        if any(keyword in line_upper for keyword in ['INTRODUCCIÓN', 'DESCRIPCIÓN', 'ESPECIFICACIÓN']):
            return 1
        elif any(keyword in line_upper for keyword in ['EJEMPLO', 'MENSAJE', 'CÓDIGO']):
            return 2
        else:
            return 2
    
    def _improve_tables(self, content: str) -> str:
        """Mejora formato de tablas markdown"""
        lines = content.split('\n')
        improved_lines = []
        
        i = 0
        while i < len(lines):
            if self._is_table_start(lines[i]):
                table_block, lines_consumed = self._process_table_block(lines[i:])
                improved_lines.extend(table_block)
                i += lines_consumed
            else:
                improved_lines.append(lines[i])
                i += 1
        
        return '\n'.join(improved_lines)
    
    def _is_table_start(self, line: str) -> bool:
        """Detecta inicio de tabla"""
        stripped = line.strip()
        return ('|' in stripped and 
                stripped.count('|') >= 2 and
                len(stripped) > 5)
    
    def _process_table_block(self, lines: List[str]) -> Tuple[List[str], int]:
        """Procesa y mejora un bloque de tabla"""
        table_lines = []
        i = 0
        
        # Extraer líneas de tabla
        while i < len(lines):
            line = lines[i]
            if '|' in line or not line.strip():
                table_lines.append(line)
                i += 1
                # Si encontramos línea vacía después de tabla, parar
                if not line.strip() and table_lines:
                    break
            else:
                break
        
        # Procesar tabla si tiene contenido
        if len([l for l in table_lines if '|' in l]) > 1:
            processed_table = self._format_table(table_lines)
            return processed_table, i
        
        return table_lines, i
    
    def _format_table(self, table_lines: List[str]) -> List[str]:
        """Formatea tabla con separadores y alineación"""
        # Filtrar solo líneas con contenido de tabla
        data_lines = [line for line in table_lines if '|' in line.strip() and line.strip()]
        
        if len(data_lines) < 1:
            return table_lines
        
        # Asegurar separador de header
        has_separator = any('---' in line or ':-:' in line or ':--' in line for line in data_lines[:3])
        
        if not has_separator and len(data_lines) >= 1:
            header = data_lines[0]
            # Contar columnas más precisamente
            header_clean = header.strip()
            if header_clean.startswith('|') and header_clean.endswith('|'):
                col_count = header_clean.count('|') - 1
            else:
                col_count = header_clean.count('|') + 1
            
            # Crear separador
            if col_count > 0:
                separator = '|' + '|'.join(['---'] * col_count) + '|'
                data_lines.insert(1, separator)
        
        # Limpiar formato de cada línea
        cleaned_lines = []
        for line in data_lines:
            # Limpiar caracteres extraños en celdas
            clean_line = re.sub(r'\\([*_])', r'\1', line)
            clean_line = re.sub(r'\s+', ' ', clean_line)
            # Asegurar espacios alrededor de pipes
            clean_line = re.sub(r'\s*\|\s*', ' | ', clean_line)
            cleaned_lines.append(clean_line.strip())
        
        return cleaned_lines
    
    def _improve_lists(self, content: str) -> str:
        """Mejora formato de listas y numeración"""
        lines = content.split('\n')
        improved_lines = []
        
        for line in lines:
            stripped = line.strip()
            
            # Mejorar listas con números
            list_match = re.match(r'^(\d+)\\\.\s*(.+)', stripped)
            if list_match:
                num, text = list_match.groups()
                improved_lines.append(f"{num}. {text}")
            # Mejorar listas con guiones
            elif stripped.startswith('- '):
                improved_lines.append(line)
            # Detectar listas mal formateadas
            elif re.match(r'^[•·]\s*', stripped):
                text = re.sub(r'^[•·]\s*', '', stripped)
                indent = len(line) - len(line.lstrip())
                improved_lines.append(' ' * indent + f"- {text}")
            else:
                improved_lines.append(line)
        
        return '\n'.join(improved_lines)
    
    def _improve_links(self, content: str) -> str:
        """Mejora enlaces y referencias"""
        # Detectar URLs sueltas y convertirlas a enlaces markdown
        url_pattern = r'(?<![\[\(])(https?://[^\s<>\)]+)(?![\]\)])'
        content = re.sub(url_pattern, r'[\1](\1)', content)
        
        # Limpiar enlaces mal formateados
        content = re.sub(r'\[([^\]]+)\]\s*\(([^)]+)\)', r'[\1](\2)', content)
        
        return content
    
    def _improve_code_detection(self, content: str) -> str:
        """Detección mejorada de código, JSON, XML, etc."""
        lines = content.split('\n')
        improved_lines = []
        i = 0
        in_existing_code_block = False
        
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            # Rastrear bloques de código existentes
            if stripped.startswith('```'):
                in_existing_code_block = not in_existing_code_block
                improved_lines.append(line)
                i += 1
                continue
            
            # No procesar si estamos dentro de un bloque existente
            if in_existing_code_block:
                improved_lines.append(line)
                i += 1
                continue
            
            # Detectar bloques de código multilínea
            if self._starts_code_block(stripped):
                code_block, lines_consumed = self._extract_code_block(lines[i:])
                improved_lines.extend(code_block)
                i += lines_consumed
            else:
                improved_lines.append(line)
                i += 1
        
        return '\n'.join(improved_lines)
    
    def _starts_code_block(self, line: str) -> bool:
        """Detecta inicio de bloque de código"""
        if not line or len(line.strip()) < 2:
            return False
            
        stripped = line.strip()
        
        # Patrones más precisos
        patterns = [
            r'^\s*[\{\[]',  # JSON opening brace/bracket
            r'^\s*<[a-zA-Z][^>]*>',  # XML/HTML tags
            r'^(POST|GET|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+/',  # HTTP methods
            r'^HTTP/[0-9]\.[0-9]',  # HTTP response
            r'^[A-Za-z][-\w]*:\s+.+',  # Headers (key: value)
            r'^\s*"[^"]+"\s*:\s*',  # JSON properties
        ]
        
        # Verificar patrones
        for pattern in patterns:
            if re.match(pattern, stripped):
                return True
        
        # Verificar si parece JSON por contenido
        if (stripped.startswith(('{', '[')) or 
            ('"' in stripped and ':' in stripped and 
             stripped.count('"') >= 2)):
            return True
            
        return False
    
    def _extract_code_block(self, lines: List[str]) -> Tuple[List[str], int]:
        """Extrae y formatea un bloque de código"""
        if not lines:
            return [], 0
            
        code_lines = []
        i = 0
        first_line = lines[0].strip()
        
        # Determinar tipo de código
        lang = ''
        if first_line.startswith(('{', '[')):
            lang = 'json'
        elif first_line.startswith('<'):
            lang = 'xml'
        elif re.match(r'^(POST|GET|PUT|DELETE|PATCH)\s+', first_line):
            lang = 'http'
        elif ':' in first_line and '=' not in first_line and not first_line.startswith('http'):
            lang = 'yaml'
        
        # Extraer líneas del bloque
        brace_count = 0
        bracket_count = 0
        in_json = lang == 'json'
        
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            if in_json:
                brace_count += stripped.count('{') - stripped.count('}')
                bracket_count += stripped.count('[') - stripped.count(']')
            
            code_lines.append(line)
            i += 1
            
            # Condiciones de parada
            if not stripped and len(code_lines) > 1:
                break
            
            # Para JSON, parar cuando se balanceen las llaves/corchetes
            if in_json and len(code_lines) > 1 and brace_count <= 0 and bracket_count <= 0:
                break
                
            # Para HTTP, parar en línea vacía después del header
            if lang == 'http' and not stripped and i > 1:
                break
                
            # Límite de seguridad
            if i >= 50:  # Máximo 50 líneas por bloque
                break
        
        # Formatear como bloque de código solo si tiene múltiples líneas o es código claro
        if len(code_lines) > 1 or lang:
            result = [f'```{lang}'] + code_lines + ['```']
        else:
            result = code_lines
        
        return result, i
    
    def _clean_final_formatting(self, content: str) -> str:
        """Limpieza final del formato"""
        # Limpiar múltiples líneas vacías
        content = re.sub(r'\n\n\n+', '\n\n', content)
        
        # Limpiar espacios al final
        content = content.rstrip()
        
        return content
    
    # ================== MÉTODOS DE REFINAMIENTO FINAL ==================
    
    def _improve_toc_detection(self, content: str) -> str:
        """Detecta y mejora índices/TOC mal formateados"""
        lines = content.split('\n')
        improved_lines = []
        i = 0
        
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            # Detectar bloques JSON que parecen TOC
            if (stripped.startswith('```json') and 
                i + 2 < len(lines) and
                self._looks_like_toc_entry(lines[i + 1])):
                
                # Procesar bloque TOC
                toc_block, lines_consumed = self._process_toc_block(lines[i:])
                improved_lines.extend(toc_block)
                i += lines_consumed
            else:
                improved_lines.append(line)
                i += 1
        
        return '\n'.join(improved_lines)
    
    def _looks_like_toc_entry(self, line: str) -> bool:
        """Detecta si una línea parece entrada de TOC"""
        stripped = line.strip()
        if not stripped:
            return False
            
        # Patrón típico: [Texto](#anchor) o [Número. Texto](#anchor)
        toc_patterns = [
            r'^\[[\d\.]+\s+.*\]\(#.*\)$',  # [1.1. Título](#anchor)
            r'^\[.*\]\(#.*\)$',            # [Título](#anchor)
            r'^\[.*\d+\]\(#.*\)$'          # [Texto 123](#anchor)
        ]
        return any(re.match(pattern, stripped) for pattern in toc_patterns)
    
    def _process_toc_block(self, lines: List[str]) -> Tuple[List[str], int]:
        """Procesa bloque TOC y lo convierte a lista markdown"""
        toc_entries = []
        i = 1  # Saltar ```json
        
        # Extraer entradas TOC
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith('```'):
                i += 1  # Incluir línea de cierre
                break
            if line and self._looks_like_toc_entry(line):
                # Convertir a item de lista
                toc_entries.append(f"- {line}")
            elif line:  # Línea no vacía que no es TOC
                break
            i += 1
        
        # Si encontramos entradas TOC válidas, convertir
        if toc_entries:
            result = ['## Contenido', ''] + toc_entries + ['']
            return result, i
        else:
            # No es TOC, devolver original hasta donde llegamos
            return lines[:i], i
    
    def _merge_fragmented_code_blocks(self, content: str) -> str:
        """Unifica bloques de código fragmentados innecesariamente"""
        lines = content.split('\n')
        improved_lines = []
        i = 0
        
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            # Detectar inicio de bloque JSON/YAML fragmentado
            if stripped.startswith('```json') or stripped.startswith('```yaml'):
                merged_block, lines_consumed = self._try_merge_code_blocks(lines[i:])
                improved_lines.extend(merged_block)
                i += lines_consumed
            else:
                improved_lines.append(line)
                i += 1
        
        return '\n'.join(improved_lines)
    
    def _try_merge_code_blocks(self, lines: List[str]) -> Tuple[List[str], int]:
        """Intenta fusionar bloques de código consecutivos del mismo tipo"""
        if len(lines) < 3:
            return [lines[0]], 1
            
        first_block_type = lines[0].strip().replace('```', '')
        content_lines = []
        i = 1
        
        # Procesar primer bloque
        while i < len(lines):
            line = lines[i].strip()
            if line == '```':
                i += 1
                break
            else:
                content_lines.append(lines[i])
                i += 1
        
        # Buscar bloques adicionales del mismo tipo
        while i < len(lines):
            # Saltar líneas vacías
            while i < len(lines) and not lines[i].strip():
                i += 1
            
            # Verificar si hay otro bloque del mismo tipo
            if (i < len(lines) and 
                lines[i].strip() == f'```{first_block_type}'):
                
                # Verificar si debemos fusionar
                preview_lines = []
                j = i + 1
                while j < len(lines) and j < i + 4:  # Previsualizar máximo 3 líneas
                    if lines[j].strip() == '```':
                        break
                    preview_lines.append(lines[j])
                    j += 1
                
                if self._should_merge_blocks(content_lines, preview_lines):
                    i += 1  # Saltar ```type
                    # Agregar contenido del siguiente bloque
                    while i < len(lines):
                        line = lines[i].strip()
                        if line == '```':
                            i += 1
                            break
                        else:
                            content_lines.append(lines[i])
                            i += 1
                else:
                    break
            else:
                break
        
        # Si solo tenemos una línea muy simple, considerar convertir a texto normal
        if (len(content_lines) == 1 and 
            len(content_lines[0].strip()) < 50 and
            not self._is_complex_code(content_lines[0]) and
            not content_lines[0].strip().startswith('[')):
            return [content_lines[0]], i
        
        # Crear bloque fusionado
        if content_lines:
            result = [f'```{first_block_type}'] + content_lines + ['```']
            return result, i
        else:
            return [lines[0]], 1
    
    def _should_merge_blocks(self, existing_content: List[str], next_content: List[str]) -> bool:
        """Determina si dos bloques deben fusionarse"""
        if not existing_content or not next_content:
            return False
            
        # Si el contenido es muy simple (enlaces TOC), no fusionar
        if all(line.strip().startswith('[') and '](' in line for line in existing_content[:3] if line.strip()):
            return False
            
        # Si los bloques son muy diferentes en estructura, no fusionar
        if len(existing_content) > 0 and len(next_content) > 0:
            existing_has_brackets = any('{' in line or '[' in line for line in existing_content[:2])
            next_has_brackets = any('{' in line or '[' in line for line in next_content[:2])
            if existing_has_brackets != next_has_brackets:
                return False
        return True
    
    def _is_complex_code(self, line: str) -> bool:
        """Determina si una línea contiene código complejo"""
        complex_indicators = ['{', '}', '[', ']', ':', '=', '=>', '->', '&&', '||']
        return any(indicator in line for indicator in complex_indicators)
    
    def _improve_table_detection(self, content: str) -> str:
        """Detecta y convierte tablas de texto plano a formato markdown"""
        lines = content.split('\n')
        improved_lines = []
        i = 0
        
        while i < len(lines):
            if self._looks_like_table_header(lines[i:i+3]):
                table_block, lines_consumed = self._convert_text_table(lines[i:])
                improved_lines.extend(table_block)
                i += lines_consumed
            else:
                improved_lines.append(lines[i])
                i += 1
        
        return '\n'.join(improved_lines)
    
    def _looks_like_table_header(self, lines: List[str]) -> bool:
        """Detecta patrones de tabla de texto plano"""
        if len(lines) < 1:
            return False
            
        first_line = lines[0].strip()
        
        if not first_line:
            return False
        
        # Patrón: __Header1__ __Header2__ __Header3__
        header_pattern = r'__[^_]+__.*__[^_]+__'
        if re.search(header_pattern, first_line):
            return True
            
        # Patrón alternativo: *Header1* *Header2* *Header3*
        header_pattern_alt = r'\*[^*]+\*.*\*[^*]+\*'
        if re.search(header_pattern_alt, first_line):
            return True
            
        return False
    
    def _convert_text_table(self, lines: List[str]) -> Tuple[List[str], int]:
        """Convierte tabla de texto plano a markdown"""
        if not lines:
            return [], 0
            
        table_lines = []
        i = 0
        headers = []
        
        # Extraer headers de la primera línea
        first_line = lines[0].strip()
        if '__' in first_line:
            headers = re.findall(r'__([^_]+)__', first_line)
        elif '*' in first_line and first_line.count('*') >= 4:
            headers = re.findall(r'\*([^*]+)\*', first_line)
        
        # Limpiar headers
        headers = [h.strip() for h in headers if h.strip()]
        
        if not headers or len(headers) < 2:
            return [lines[0]], 1
        
        # Crear header de tabla markdown
        header_row = '| ' + ' | '.join(headers) + ' |'
        separator_row = '|' + '|'.join(['---'] * len(headers)) + '|'
        table_lines = [header_row, separator_row]
        
        i = 1
        # Procesar filas de datos
        while i < len(lines):
            if i >= len(lines):
                break
                
            line = lines[i].strip()
            if not line:
                i += 1
                break
                
            # Intentar extraer valores de la fila
            row_values = self._extract_table_row_values(line, len(headers))
            if row_values and len(row_values) >= 2:
                # Asegurar que tenemos el número correcto de columnas
                while len(row_values) < len(headers):
                    row_values.append('')
                row_values = row_values[:len(headers)]  # Truncar si hay demasiadas
                
                row = '| ' + ' | '.join(row_values) + ' |'
                table_lines.append(row)
            else:
                # Si no podemos extraer valores, parar
                break
            i += 1
        
        # Solo devolver tabla si tenemos al menos una fila de datos
        if len(table_lines) > 2:  # header + separator + al menos una fila
            return table_lines + [''], i
        else:
            return [lines[0]], 1
    
    def _extract_table_row_values(self, line: str, expected_cols: int) -> List[str]:
        """Extrae valores de una fila de tabla de texto plano"""
        # Limpiar línea
        clean_line = line.strip()
        
        if not clean_line:
            return []
        
        # Si la línea contiene principalmente asteriscos o guiones bajos, intentar extraer
        if '*' in clean_line and clean_line.count('*') >= 2:
            # Patrón: *valor1* *valor2* *valor3*
            values = re.findall(r'\*([^*]+)\*', clean_line)
            if len(values) >= 2:
                return [v.strip() for v in values]
        
        # Si no hay marcadores claros, dividir por espacios múltiples o tabulaciones
        parts = re.split(r'\s{3,}|\t+', clean_line)
        parts = [p.strip() for p in parts if p.strip()]
        if len(parts) >= 2:
            return parts
        
        # Último recurso: valores separados por pipes
        if '|' in clean_line:
            parts = [p.strip() for p in clean_line.split('|') if p.strip()]
            if len(parts) >= 2:
                return parts
        
        # Si solo tenemos espacios dobles, intentar esa separación
        if '  ' in clean_line:
            parts = re.split(r'\s{2,}', clean_line)
            parts = [p.strip() for p in parts if p.strip()]
            if len(parts) >= 2:
                return parts
        
        return []
    
    def _final_escape_cleanup(self, content: str) -> str:
        """Limpieza final de escapes innecesarios"""
        # Limpiar escapes de caracteres que no necesitan escape en markdown normal
        # Pero preservar escapes importantes
        
        # Limpiar escapes de hashtags solo si no están al inicio de línea (headers)
        lines = content.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # No tocar líneas que son headers
            if line.strip().startswith('#'):
                cleaned_lines.append(line)
                continue
            
            # Limpiar escapes en contenido normal
            cleaned_line = line
            
            # Limpiar escapes de caracteres comunes
            cleaned_line = re.sub(r'\\([#])', r'\1', cleaned_line)
            
            # Limpiar escapes en direcciones y emails
            cleaned_line = re.sub(r'\\([.@])', r'\1', cleaned_line)
            
            # Limpiar escapes en URLs (pero solo si parece URL)
            if 'http' in cleaned_line or 'www.' in cleaned_line:
                cleaned_line = re.sub(r'\\([:/])', r'\1', cleaned_line)
            
            cleaned_lines.append(cleaned_line)
        
        return '\n'.join(cleaned_lines)
    
    # ================== MÉTODOS EXISTENTES MEJORADOS ==================
    
    def _process_fast_mode(self, markdown_content: str, file_path: str) -> str:
        """Modo rápido - solo aplicar header AI si corresponde"""
        if self.config.output_format == OutputFormat.MARKDOWN_AI:
            return self._add_ai_header(markdown_content, file_path, basic=True)
        return markdown_content
    
    def _process_full_mode(self, markdown_content: str, file_path: str, mammoth_result) -> str:
        """Modo completo - incluye mejoras de contenido"""
        enhanced_content = markdown_content
        
        # Agregar warnings de mammoth si existen
        if mammoth_result.messages and not SAFE_MODE:
            warnings = []
            for msg in mammoth_result.messages[:3]:  # Solo primeros 3
                if hasattr(msg, 'message'):
                    warnings.append(f"- {msg.message}")
            
            if warnings:
                enhanced_content += "\n\n⚠️ **Notas de conversión:**\n" + "\n".join(warnings)
        
        # Aplicar header AI si corresponde
        if self.config.output_format == OutputFormat.MARKDOWN_AI:
            enhanced_content = self._add_ai_header(enhanced_content, file_path, basic=False)
        
        return enhanced_content
    
    def _add_ai_header(self, markdown_content: str, file_path: str, basic: bool = False) -> str:
        """Agregar header AI - MANTIENE tu formato existente"""
        file_name = os.path.basename(file_path)
        word_count = len(markdown_content.split())
        
        if basic:
            # Header básico para modo fast
            header = [
                "## 📝 Word Document Analysis",
                f"- **File:** {file_name}",
                f"- **Content:** ~{word_count:,} words processed with premium Mammoth",
                "",
                "### 📖 Document Content",
                ""
            ]
        else:
            # Header completo con análisis
            lines = markdown_content.split('\n')
            heading_count = len([l for l in lines if l.strip().startswith('#')])
            table_count = max(0, markdown_content.count('|') // 4)
            
            header = [
                "## 📝 Word Document Analysis",
                f"- **File:** {file_name}",
                f"- **Content:** ~{word_count:,} words, {heading_count} headings, ~{table_count} tables",
                f"- **Processing:** Premium Mammoth converter with advanced post-processing",
                f"- **Quality:** High-fidelity markdown with table detection and code formatting",
                "",
                "### 📖 Document Content",
                ""
            ]
        
        return "\n".join(header) + markdown_content
    
    def _create_format_error(self, file_path: str) -> str:
        """Error de formato - IGUAL que tu versión anterior"""
        file_name = os.path.basename(file_path)
        return f"""## ❌ Unsupported Format

**File:** {file_name}

Only .docx and .docm files are supported. Please convert your document and try again.
"""
    
    def _create_simple_error_fallback(self, file_path: str, error: str) -> str:
        """Fallback de error - IGUAL que tu versión anterior"""
        file_name = os.path.basename(file_path)
        return f"""## ❌ Processing Error

**File:** {file_name}
**Error:** {error}

Unable to process document. Please check file format and try again.
"""