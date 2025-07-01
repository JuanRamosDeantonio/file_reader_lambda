import re
import json
from datetime import datetime
from typing import Dict, List, Optional

class DocumentIntelligence:
    """Extrae información estructurada de documentos para optimizar consumo por IA"""
    
    @staticmethod
    def generate_metadata(file_path: str, content: str, doc_type: str = "unknown") -> str:
        """Genera metadata YAML front-matter para IA"""
        word_count = len(content.split())
        char_count = len(content)
        
        # Detectar idioma básico (español vs inglés)
        spanish_indicators = ['el ', 'la ', 'de ', 'que ', 'y ', 'a ', 'en ', 'un ', 'es ', 'se ']
        spanish_count = sum(1 for indicator in spanish_indicators if indicator in content.lower())
        language = "es" if spanish_count > 5 else "en"
        
        metadata = f"""---
document_type: {doc_type}
source_file: {file_path.split('/')[-1]}
processed_at: {datetime.now().isoformat()}
word_count: {word_count}
char_count: {char_count}
language: {language}
ai_ready: true
---

"""
        return metadata
    
    @staticmethod
    def extract_key_sections(content: str) -> Dict[str, str]:
        """Extrae secciones clave del documento"""
        sections = {
            "summary": "",
            "key_points": "",
            "metrics": "",
            "recommendations": ""
        }
        
        # Buscar secciones por palabras clave
        lines = content.split('\n')
        current_section = None
        section_content = []
        
        for line in lines:
            line_lower = line.lower().strip()
            
            # Identificar tipos de sección
            if any(keyword in line_lower for keyword in ['resumen', 'summary', 'executive']):
                if section_content and current_section:
                    sections[current_section] = '\n'.join(section_content)
                current_section = "summary"
                section_content = [line]
            elif any(keyword in line_lower for keyword in ['conclusión', 'conclusion', 'recomendación', 'recommendation']):
                if section_content and current_section:
                    sections[current_section] = '\n'.join(section_content)
                current_section = "recommendations"
                section_content = [line]
            elif any(keyword in line_lower for keyword in ['métrica', 'metric', 'kpi', 'resultado', 'result']):
                if section_content and current_section:
                    sections[current_section] = '\n'.join(section_content)
                current_section = "metrics"
                section_content = [line]
            elif current_section and line.strip():
                section_content.append(line)
        
        # Guardar última sección
        if section_content and current_section:
            sections[current_section] = '\n'.join(section_content)
        
        return sections
    
    @staticmethod
    def extract_metrics_and_numbers(content: str) -> List[str]:
        """Extrae métricas y números importantes del documento"""
        # Patrones para números con contexto
        patterns = [
            r'(\d+(?:\.\d+)?%)',  # Porcentajes
            r'(\$\d+(?:,\d{3})*(?:\.\d{2})?)',  # Dinero
            r'(\d+(?:,\d{3})*\s*(?:millones?|millions?|mil|thousand))',  # Grandes números
            r'(\d+(?:\.\d+)?\s*(?:años?|years?|meses?|months?))',  # Tiempo
        ]
        
        metrics = []
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            metrics.extend(matches)
        
        return list(set(metrics))  # Eliminar duplicados
    
    @staticmethod
    def generate_ai_summary(content: str, max_length: int = 500) -> str:
        """Genera un resumen optimizado para IA"""
        # Extraer primeras líneas significativas
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        
        # Filtrar líneas muy cortas o que parecen metadatos
        meaningful_lines = [
            line for line in lines 
            if len(line) > 10 and not line.startswith(('---', '```', '#'))
        ]
        
        summary_lines = meaningful_lines[:5]  # Primeras 5 líneas significativas
        summary = ' '.join(summary_lines)
        
        if len(summary) > max_length:
            summary = summary[:max_length] + "..."
        
        return summary
    
    @staticmethod
    def format_for_ai_consumption(content: str, file_path: str, doc_type: str = "document") -> str:
        """Formatea contenido completo optimizado para consumo por IA"""
        
        # Generar metadata
        metadata = DocumentIntelligence.generate_metadata(file_path, content, doc_type)
        
        # Extraer información clave
        sections = DocumentIntelligence.extract_key_sections(content)
        metrics = DocumentIntelligence.extract_metrics_and_numbers(content)
        summary = DocumentIntelligence.generate_ai_summary(content)
        
        # Construir documento optimizado
        ai_document = metadata
        
        # Resumen ejecutivo
        ai_document += f"## 🎯 AI Summary\n{summary}\n\n"
        
        # Métricas importantes
        if metrics:
            ai_document += "## 📊 Key Metrics\n"
            for metric in metrics[:10]:  # Top 10 métricas
                ai_document += f"- {metric}\n"
            ai_document += "\n"
        
        # Secciones clave identificadas
        if sections["summary"]:
            ai_document += f"## 📋 Executive Summary\n{sections['summary']}\n\n"
        
        if sections["metrics"]:
            ai_document += f"## 📈 Performance Metrics\n{sections['metrics']}\n\n"
            
        if sections["recommendations"]:
            ai_document += f"## 💡 Recommendations\n{sections['recommendations']}\n\n"
        
        # Contenido completo
        ai_document += "## 📖 Full Document Content\n"
        ai_document += content
        
        # Footer para IA
        ai_document += "\n\n---\n*Document processed and optimized for AI analysis*"
        
        return ai_document