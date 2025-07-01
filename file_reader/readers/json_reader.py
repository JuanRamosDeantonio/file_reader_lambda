import json
from file_reader.readers.base_reader import BaseReader
from file_reader.core.plugin_registry import PluginRegistry
from file_reader.core.enums import OutputFormat

@PluginRegistry.register("json")
class JsonReader(BaseReader):
    def read(self, file_path: str) -> str:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        content = self._format_json_content(data, file_path)
        
        # Aplicar formateo IA si está habilitado
        final_content = self._apply_ai_formatting(content, file_path, "json_data")
        
        # Aplicar formateo JSON estructurado si es necesario
        return self._format_as_json(final_content, file_path, "json_data")
    
    def _format_json_content(self, data: dict, file_path: str) -> str:
        """Formatea el contenido JSON según el formato de salida"""
        
        if self.config.output_format in [OutputFormat.MARKDOWN, OutputFormat.MARKDOWN_AI]:
            return self._format_as_markdown(data, file_path)
        elif self.config.output_format == OutputFormat.PLAIN:
            return json.dumps(data, indent=2, ensure_ascii=False)
        else:
            return self._format_as_markdown(data, file_path)
    
    def _format_as_markdown(self, data: dict, file_path: str) -> str:
        """Formatea JSON como Markdown optimizado para IA"""
        
        # Para formato AI, agregar análisis estructural
        if self.config.output_format == OutputFormat.MARKDOWN_AI:
            analysis = self._analyze_json_structure(data)
            
            metadata = f"""## 📊 JSON Structure Analysis
- **File:** {file_path.split('/')[-1]}
- **Root Type:** {type(data).__name__}
- **Complexity:** {analysis['complexity']}
- **Depth Levels:** {analysis['max_depth']}
- **Total Keys:** {analysis['total_keys']}
- **Data Types:** {', '.join(analysis['data_types'])}

### 🗂️ Key Structure Overview
{self._generate_structure_overview(data)}

### 📋 JSON Content
"""
        else:
            metadata = ""
        
        # Formatear JSON con syntax highlighting
        json_formatted = json.dumps(data, indent=2, ensure_ascii=False)
        
        return f"{metadata}```json\n{json_formatted}\n```"
    
    def _analyze_json_structure(self, data) -> dict:
        """Analiza la estructura del JSON para información IA"""
        analysis = {
            'complexity': 'Simple',
            'max_depth': 0,
            'total_keys': 0,
            'data_types': set()
        }
        
        def analyze_recursive(obj, depth=0):
            analysis['max_depth'] = max(analysis['max_depth'], depth)
            
            if isinstance(obj, dict):
                analysis['data_types'].add('Object')
                analysis['total_keys'] += len(obj)
                
                for key, value in obj.items():
                    analyze_recursive(value, depth + 1)
                    
            elif isinstance(obj, list):
                analysis['data_types'].add('Array')
                for item in obj:
                    analyze_recursive(item, depth + 1)
                    
            elif isinstance(obj, str):
                analysis['data_types'].add('String')
            elif isinstance(obj, (int, float)):
                analysis['data_types'].add('Number')
            elif isinstance(obj, bool):
                analysis['data_types'].add('Boolean')
            elif obj is None:
                analysis['data_types'].add('Null')
        
        analyze_recursive(data)
        
        # Determinar complejidad
        if analysis['max_depth'] > 4 or analysis['total_keys'] > 50:
            analysis['complexity'] = 'Complex'
        elif analysis['max_depth'] > 2 or analysis['total_keys'] > 10:
            analysis['complexity'] = 'Moderate'
        
        analysis['data_types'] = list(analysis['data_types'])
        
        return analysis
    
    def _generate_structure_overview(self, data, max_items=5) -> str:
        """Genera un overview de la estructura para IA"""
        
        def describe_structure(obj, depth=0, max_depth=3):
            if depth > max_depth:
                return "..."
            
            indent = "  " * depth
            
            if isinstance(obj, dict):
                if not obj:
                    return f"{indent}(empty object)"
                
                items = []
                for i, (key, value) in enumerate(obj.items()):
                    if i >= max_items:
                        items.append(f"{indent}- ... ({len(obj) - max_items} more keys)")
                        break
                    
                    value_desc = describe_structure(value, depth + 1, max_depth)
                    if '\n' in value_desc:
                        items.append(f"{indent}- **{key}:**\n{value_desc}")
                    else:
                        items.append(f"{indent}- **{key}:** {value_desc}")
                
                return "\n".join(items)
                
            elif isinstance(obj, list):
                if not obj:
                    return f"{indent}(empty array)"
                
                length = len(obj)
                if length == 1:
                    sample_desc = describe_structure(obj[0], depth, max_depth)
                    return f"{indent}Array[{length}]: {sample_desc}"
                else:
                    sample_desc = describe_structure(obj[0], depth, max_depth)
                    return f"{indent}Array[{length}]: {sample_desc} (and {length-1} more)"
                    
            elif isinstance(obj, str):
                preview = obj[:30] + "..." if len(obj) > 30 else obj
                return f'"{preview}"'
            elif isinstance(obj, (int, float)):
                return str(obj)
            elif isinstance(obj, bool):
                return str(obj).lower()
            elif obj is None:
                return "null"
            else:
                return str(type(obj).__name__)
        
        return describe_structure(data)