import yaml
from file_reader.readers.base_reader import BaseReader
from file_reader.core.plugin_registry import PluginRegistry
from file_reader.core.enums import OutputFormat

@PluginRegistry.register("yaml")
@PluginRegistry.register("yml")
class YamlReader(BaseReader):
    def read(self, file_path: str) -> str:
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                data = yaml.safe_load(f)
                yaml_analysis = self._analyze_yaml_structure(data)
            except yaml.YAMLError as e:
                # Fallback para YAML malformado
                f.seek(0)
                raw_content = f.read()
                return self._format_standard_yaml(raw_content, file_path, error=str(e))
        
        # Formatear YAML limpio
        formatted_yaml = yaml.dump(data, allow_unicode=True, default_flow_style=False, indent=2)
        
        if self.config.output_format == OutputFormat.MARKDOWN_AI:
            content = self._format_ai_yaml(formatted_yaml, data, yaml_analysis, file_path)
        else:
            content = self._format_standard_yaml(formatted_yaml, file_path)
        
        # Aplicar formateo IA si está habilitado
        final_content = self._apply_ai_formatting(content, file_path, "yaml_config")
        
        # Aplicar formateo JSON estructurado si es necesario
        return self._format_as_json(final_content, file_path, "yaml_config")
    
    def _analyze_yaml_structure(self, data) -> dict:
        """Analiza la estructura del YAML para información IA"""
        
        analysis = {
            'data_type': type(data).__name__,
            'complexity': 'Simple',
            'max_depth': 0,
            'total_keys': 0,
            'data_types': set(),
            'top_level_keys': [],
            'config_patterns': []
        }
        
        def analyze_recursive(obj, depth=0, key_path=""):
            analysis['max_depth'] = max(analysis['max_depth'], depth)
            
            if isinstance(obj, dict):
                analysis['data_types'].add('Object')
                analysis['total_keys'] += len(obj)
                
                if depth == 0:
                    analysis['top_level_keys'] = list(obj.keys())
                
                for key, value in obj.items():
                    current_path = f"{key_path}.{key}" if key_path else key
                    
                    # Detectar patrones de configuración comunes
                    if depth <= 2:  # Solo niveles superiores
                        self._detect_config_patterns(key, value, analysis)
                    
                    analyze_recursive(value, depth + 1, current_path)
                    
            elif isinstance(obj, list):
                analysis['data_types'].add('Array')
                for i, item in enumerate(obj):
                    analyze_recursive(item, depth + 1, f"{key_path}[{i}]")
                    
            elif isinstance(obj, str):
                analysis['data_types'].add('String')
            elif isinstance(obj, (int, float)):
                analysis['data_types'].add('Number')
            elif isinstance(obj, bool):
                analysis['data_types'].add('Boolean')
            elif obj is None:
                analysis['data_types'].add('Null')
        
        if data is not None:
            analyze_recursive(data)
        
        # Determinar complejidad
        if analysis['max_depth'] > 4 or analysis['total_keys'] > 50:
            analysis['complexity'] = 'Complex'
        elif analysis['max_depth'] > 2 or analysis['total_keys'] > 10:
            analysis['complexity'] = 'Moderate'
        
        analysis['data_types'] = list(analysis['data_types'])
        
        return analysis
    
    def _detect_config_patterns(self, key: str, value, analysis: dict):
        """Detecta patrones comunes de configuración"""
        
        key_lower = key.lower()
        
        # Patrones de configuración comunes
        config_indicators = [
            ('database', ['host', 'port', 'user', 'password', 'name']),
            ('server', ['host', 'port', 'ssl', 'timeout']),
            ('api', ['url', 'key', 'token', 'endpoint']),
            ('logging', ['level', 'format', 'file', 'handlers']),
            ('cache', ['ttl', 'size', 'type', 'redis']),
            ('security', ['secret', 'key', 'token', 'auth']),
            ('docker', ['image', 'ports', 'volumes', 'env']),
            ('kubernetes', ['replicas', 'image', 'service', 'ingress']),
        ]
        
        for pattern_name, indicators in config_indicators:
            if pattern_name in key_lower:
                analysis['config_patterns'].append(f"{pattern_name.title()} Configuration")
                break
            elif isinstance(value, dict) and any(ind in str(value).lower() for ind in indicators):
                analysis['config_patterns'].append(f"Possible {pattern_name.title()} Config")
                break
    
    def _format_ai_yaml(self, formatted_yaml: str, data, analysis: dict, file_path: str) -> str:
        """Formatea YAML optimizado para IA con análisis estructural"""
        
        # Header con análisis del documento
        header = f"""## ⚙️ YAML Configuration Analysis
- **File:** {file_path.split('/')[-1]}
- **Data Type:** {analysis['data_type']}
- **Complexity:** {analysis['complexity']}
- **Structure Depth:** {analysis['max_depth']} levels
- **Total Keys:** {analysis['total_keys']}
- **Data Types:** {', '.join(analysis['data_types'])}

"""
        
        # Mostrar configuraciones detectadas
        if analysis['config_patterns']:
            header += "### 🔧 Detected Configuration Types\n"
            unique_patterns = list(set(analysis['config_patterns']))
            for pattern in unique_patterns:
                header += f"- {pattern}\n"
            header += "\n"
        
        # Mostrar estructura de alto nivel
        if analysis['top_level_keys']:
            header += "### 🗂️ Top-Level Structure\n"
            for key in analysis['top_level_keys']:
                value_type = type(data[key]).__name__ if isinstance(data, dict) else "Unknown"
                
                # Descripción más detallada para objetos complejos
                if isinstance(data[key], dict):
                    sub_keys = len(data[key])
                    header += f"- **{key}:** Object with {sub_keys} properties\n"
                elif isinstance(data[key], list):
                    items_count = len(data[key])
                    header += f"- **{key}:** Array with {items_count} items\n"
                else:
                    header += f"- **{key}:** {value_type}\n"
            header += "\n"
        
        # Contenido YAML
        header += "### 📋 YAML Content\n"
        
        return f"{header}```yaml\n{formatted_yaml}\n```"
    
    def _format_standard_yaml(self, formatted_yaml: str, file_path: str, error: str = None) -> str:
        """Formatea YAML en formato estándar"""
        
        if error:
            error_note = f"\n<!-- YAML Parse Error: {error} -->\n"
            formatted_yaml = error_note + formatted_yaml
        
        if self.config.output_format == OutputFormat.MARKDOWN:
            return f"```yaml\n{formatted_yaml}\n```"
        else:
            return formatted_yaml