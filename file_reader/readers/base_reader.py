from file_reader.core.document_intelligence import DocumentIntelligence
from file_reader.core.enums import OutputFormat
import json

class BaseReader:
    def __init__(self, config):
        self.config = config

    def read(self, file_path: str) -> str:
        raise NotImplementedError("Subclasses must implement this method.")
    
    def _apply_ai_formatting(self, content: str, file_path: str, doc_type: str = "document") -> str:
        """Aplica formateo optimizado para IA si está habilitado"""
        if self.config.output_format == OutputFormat.MARKDOWN_AI:
            return DocumentIntelligence.format_for_ai_consumption(content, file_path, doc_type)
        elif self.config.ai_optimized and self.config.include_metadata:
            # Agregar solo metadata si AI está optimizado pero no es formato completo
            metadata = DocumentIntelligence.generate_metadata(file_path, content, doc_type)
            return metadata + content
        else:
            return content
    
    def _format_as_json(self, content: str, file_path: str, doc_type: str = "document") -> str:
        """Formatea contenido como JSON estructurado"""
        if self.config.output_format == OutputFormat.STRUCTURED_JSON:
            sections = DocumentIntelligence.extract_key_sections(content)
            metrics = DocumentIntelligence.extract_metrics_and_numbers(content)
            summary = DocumentIntelligence.generate_ai_summary(content)
            
            structured_data = {
                "metadata": {
                    "source_file": file_path.split('/')[-1],
                    "document_type": doc_type,
                    "word_count": len(content.split()),
                    "char_count": len(content)
                },
                "summary": summary,
                "key_metrics": metrics,
                "sections": sections,
                "full_content": content
            }
            
            return json.dumps(structured_data, indent=2, ensure_ascii=False)
        
        return content