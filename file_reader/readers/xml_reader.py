import xml.dom.minidom
import xml.etree.ElementTree as ET
from file_reader.readers.base_reader import BaseReader
from file_reader.core.plugin_registry import PluginRegistry
from file_reader.core.enums import OutputFormat

@PluginRegistry.register("xml")
class XmlReader(BaseReader):
    def read(self, file_path: str) -> str:
        # Parsear XML para análisis
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            xml_analysis = self._analyze_xml_structure(root)
            
            # También obtener versión pretty-printed
            dom = xml.dom.minidom.parse(file_path)
            pretty_xml = dom.toprettyxml(indent="  ")
            
        except Exception as e:
            # Fallback si hay problemas de parsing
            with open(file_path, 'r', encoding='utf-8') as f:
                raw_content = f.read()
            return self._format_standard_xml(raw_content, file_path)
        
        if self.config.output_format == OutputFormat.MARKDOWN_AI:
            content = self._format_ai_xml(pretty_xml, xml_analysis, file_path)
        else:
            content = self._format_standard_xml(pretty_xml, file_path)
        
        # Aplicar formateo IA si está habilitado
        final_content = self._apply_ai_formatting(content, file_path, "xml_document")
        
        # Aplicar formateo JSON estructurado si es necesario
        return self._format_as_json(final_content, file_path, "xml_document")
    
    def _analyze_xml_structure(self, root) -> dict:
        """Analiza la estructura del XML para información IA"""
        
        analysis = {
            'root_element': root.tag,
            'namespace': self._extract_namespace(root.tag),
            'total_elements': 0,
            'max_depth': 0,
            'unique_tags': set(),
            'attributes_count': 0,
            'text_content_length': 0,
            'structure_summary': {}
        }
        
        def analyze_recursive(element, depth=0):
            analysis['max_depth'] = max(analysis['max_depth'], depth)
            analysis['total_elements'] += 1
            
            # Limpiar tag de namespace para análisis
            clean_tag = self._clean_tag_name(element.tag)
            analysis['unique_tags'].add(clean_tag)
            
            # Contar atributos
            analysis['attributes_count'] += len(element.attrib)
            
            # Contar contenido de texto
            if element.text and element.text.strip():
                analysis['text_content_length'] += len(element.text.strip())
            
            # Estructura resumen
            if clean_tag not in analysis['structure_summary']:
                analysis['structure_summary'][clean_tag] = {
                    'count': 0,
                    'has_attributes': False,
                    'has_text_content': False,
                    'children': set()
                }
            
            analysis['structure_summary'][clean_tag]['count'] += 1
            
            if element.attrib:
                analysis['structure_summary'][clean_tag]['has_attributes'] = True
            
            if element.text and element.text.strip():
                analysis['structure_summary'][clean_tag]['has_text_content'] = True
            
            # Analizar hijos
            for child in element:
                child_clean_tag = self._clean_tag_name(child.tag)
                analysis['structure_summary'][clean_tag]['children'].add(child_clean_tag)
                analyze_recursive(child, depth + 1)
        
        analyze_recursive(root)
        
        # Convertir sets a listas para serialización
        analysis['unique_tags'] = list(analysis['unique_tags'])
        for tag_info in analysis['structure_summary'].values():
            tag_info['children'] = list(tag_info['children'])
        
        return analysis
    
    def _extract_namespace(self, tag: str) -> str:
        """Extrae namespace del tag XML"""
        if tag.startswith('{'):
            return tag[1:tag.find('}')]
        return ""
    
    def _clean_tag_name(self, tag: str) -> str:
        """Limpia el nombre del tag removiendo namespace"""
        if tag.startswith('{'):
            return tag[tag.find('}') + 1:]
        return tag
    
    def _format_ai_xml(self, pretty_xml: str, analysis: dict, file_path: str) -> str:
        """Formatea XML optimizado para IA con análisis estructural"""
        
        # Header con análisis del documento
        header = f"""## 🔧 XML Document Analysis
- **File:** {file_path.split('/')[-1]}
- **Root Element:** {analysis['root_element']}
- **Namespace:** {analysis['namespace'] or 'None'}
- **Total Elements:** {analysis['total_elements']}
- **Unique Tags:** {len(analysis['unique_tags'])}
- **Max Depth:** {analysis['max_depth']}
- **Attributes:** {analysis['attributes_count']}
- **Text Content:** {analysis['text_content_length']} characters

"""
        
        # Mostrar estructura de elementos
        header += "### 🗂️ XML Structure Overview\n"
        for tag, info in analysis['structure_summary'].items():
            children_info = f" → {', '.join(info['children'])}" if info['children'] else ""
            attributes_info = " (with attributes)" if info['has_attributes'] else ""
            text_info = " (contains text)" if info['has_text_content'] else ""
            
            header += f"- **{tag}** ({info['count']}x){attributes_info}{text_info}{children_info}\n"
        
        header += "\n### 📋 Raw XML Content\n"
        
        # XML content con syntax highlighting
        return f"{header}```xml\n{pretty_xml}\n```"
    
    def _format_standard_xml(self, pretty_xml: str, file_path: str) -> str:
        """Formatea XML en formato estándar"""
        
        if self.config.output_format == OutputFormat.MARKDOWN:
            return f"```xml\n{pretty_xml}\n```"
        else:
            return pretty_xml