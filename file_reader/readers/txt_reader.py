from file_reader.readers.base_reader import BaseReader
from file_reader.core.plugin_registry import PluginRegistry
from file_reader.core.enums import OutputFormat
import re

@PluginRegistry.register("default")
@PluginRegistry.register("txt")
class TxtReader(BaseReader):
    def read(self, file_path: str) -> str:
        with open(file_path, "r", encoding="utf-8") as f:
            raw_content = f.read()
        
        # Analizar estructura del texto
        text_analysis = self._analyze_text_structure(raw_content)
        
        if self.config.output_format == OutputFormat.MARKDOWN_AI:
            content = self._format_ai_text(raw_content, text_analysis, file_path)
        else:
            content = self._format_standard_text(raw_content, file_path)
        
        # Aplicar formateo IA si está habilitado
        final_content = self._apply_ai_formatting(content, file_path, "text_document")
        
        # Aplicar formateo JSON estructurado si es necesario
        return self._format_as_json(final_content, file_path, "text_document")
    
    def _analyze_text_structure(self, content: str) -> dict:
        """Analiza la estructura del texto para optimización IA"""
        
        lines = content.split('\n')
        analysis = {
            'total_lines': len(lines),
            'non_empty_lines': len([line for line in lines if line.strip()]),
            'total_words': len(content.split()),
            'total_chars': len(content),
            'paragraphs': [],
            'potential_headings': [],
            'lists': [],
            'structure_type': 'unstructured'
        }
        
        # Detectar párrafos (líneas separadas por líneas vacías)
        current_paragraph = []
        for line in lines:
            line = line.strip()
            if line:
                current_paragraph.append(line)
            else:
                if current_paragraph:
                    analysis['paragraphs'].append(' '.join(current_paragraph))
                    current_paragraph = []
        
        # Agregar último párrafo si existe
        if current_paragraph:
            analysis['paragraphs'].append(' '.join(current_paragraph))
        
        # Detectar posibles headings (líneas cortas, mayúsculas, etc.)
        for line in lines:
            line = line.strip()
            if line and len(line) < 100:
                # Criterios para heading
                if (line.isupper() or 
                    line.endswith(':') or 
                    re.match(r'^\d+\.?\s+', line) or  # Numeración
                    re.match(r'^[A-Z][^.!?]*$', line)):  # Solo mayúscula inicial, sin puntuación final
                    analysis['potential_headings'].append(line)
        
        # Detectar listas
        list_patterns = [r'^\s*[-*•]\s+', r'^\s*\d+\.?\s+', r'^\s*[a-zA-Z]\.?\s+']
        current_list = []
        
        for line in lines:
            if any(re.match(pattern, line) for pattern in list_patterns):
                current_list.append(line.strip())
            else:
                if current_list and len(current_list) >= 2:
                    analysis['lists'].append(current_list)
                current_list = []
        
        # Agregar última lista si existe
        if current_list and len(current_list) >= 2:
            analysis['lists'].append(current_list)
        
        # Determinar tipo de estructura
        if analysis['potential_headings']:
            analysis['structure_type'] = 'structured'
        elif analysis['lists']:
            analysis['structure_type'] = 'semi_structured'
        
        return analysis
    
    def _format_ai_text(self, content: str, analysis: dict, file_path: str) -> str:
        """Formatea texto optimizado para IA con análisis estructural"""
        
        # Header con análisis del documento
        header = f"""## 📄 Text Document Analysis
- **File:** {file_path.split('/')[-1]}
- **Structure Type:** {analysis['structure_type'].replace('_', ' ').title()}
- **Lines:** {analysis['total_lines']} total, {analysis['non_empty_lines']} with content
- **Words:** {analysis['total_words']:,}
- **Characters:** {analysis['total_chars']:,}
- **Paragraphs:** {len(analysis['paragraphs'])}

"""
        
        # Mostrar estructura detectada
        if analysis['potential_headings']:
            header += "### 🗂️ Detected Structure\n"
            for heading in analysis['potential_headings'][:10]:  # Máximo 10
                header += f"- {heading}\n"
            
            if len(analysis['potential_headings']) > 10:
                header += f"- ... and {len(analysis['potential_headings']) - 10} more sections\n"
            header += "\n"
        
        # Mostrar listas detectadas
        if analysis['lists']:
            header += f"### 📋 Detected Lists\n"
            header += f"Found {len(analysis['lists'])} structured lists in the document.\n\n"
        
        # Contenido principal
        if analysis['structure_type'] == 'structured':
            content_formatted = self._format_structured_content(content, analysis)
        else:
            content_formatted = self._format_unstructured_content(content, analysis)
        
        return header + "### 📖 Document Content\n\n" + content_formatted
    
    def _format_structured_content(self, content: str, analysis: dict) -> str:
        """Formatea contenido estructurado identificando secciones"""
        
        lines = content.split('\n')
        formatted_lines = []
        
        for line in lines:
            line_stripped = line.strip()
            
            # Convertir headings detectados a markdown
            if line_stripped in analysis['potential_headings']:
                # Determinar nivel basado en características
                if line_stripped.isupper():
                    formatted_lines.append(f"## {line_stripped}")
                elif line_stripped.endswith(':'):
                    formatted_lines.append(f"### {line_stripped}")
                elif re.match(r'^\d+\.?\s+', line_stripped):
                    formatted_lines.append(f"#### {line_stripped}")
                else:
                    formatted_lines.append(f"### {line_stripped}")
            else:
                formatted_lines.append(line)
        
        return '\n'.join(formatted_lines)
    
    def _format_unstructured_content(self, content: str, analysis: dict) -> str:
        """Formatea contenido no estructurado por párrafos"""
        
        if len(analysis['paragraphs']) > 1:
            # Formato por párrafos para mejor legibilidad IA
            formatted_paragraphs = []
            for i, paragraph in enumerate(analysis['paragraphs'], 1):
                if len(paragraph) > 50:  # Solo párrafos significativos
                    formatted_paragraphs.append(f"**Paragraph {i}:**\n{paragraph}")
            
            return '\n\n'.join(formatted_paragraphs)
        else:
            # Contenido simple
            return content
    
    def _format_standard_text(self, content: str, file_path: str) -> str:
        """Formatea texto en formato estándar"""
        
        if self.config.output_format == OutputFormat.MARKDOWN:
            return f"```text\n{content}\n```"
        else:
            return content