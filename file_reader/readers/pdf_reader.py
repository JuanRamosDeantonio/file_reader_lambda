import fitz  # PyMuPDF
from file_reader.readers.base_reader import BaseReader
from file_reader.core.plugin_registry import PluginRegistry
from file_reader.core.enums import OutputFormat

@PluginRegistry.register("pdf")
class PdfReader(BaseReader):
    def read(self, file_path: str) -> str:
        text_content = ""
        pdf_metadata = {}
        
        with fitz.open(file_path) as doc:
            # Extraer metadata del PDF
            pdf_metadata = {
                'pages': doc.page_count,
                'title': doc.metadata.get('title', 'Unknown'),
                'author': doc.metadata.get('author', 'Unknown'),
                'subject': doc.metadata.get('subject', ''),
                'creator': doc.metadata.get('creator', ''),
            }
            
            # Extraer texto página por página
            pages_content = []
            for page_num, page in enumerate(doc, 1):
                page_text = page.get_text()
                if page_text.strip():  # Solo agregar páginas con contenido
                    if self.config.output_format == OutputFormat.MARKDOWN_AI:
                        pages_content.append({
                            'number': page_num,
                            'text': page_text.strip(),
                            'word_count': len(page_text.split())
                        })
                    else:
                        text_content += page_text
        
        if self.config.output_format == OutputFormat.MARKDOWN_AI:
            content = self._format_ai_pdf(pages_content, pdf_metadata, file_path)
        else:
            content = self._format_standard_pdf(text_content, file_path)
        
        # Aplicar formateo IA si está habilitado
        final_content = self._apply_ai_formatting(content, file_path, "pdf_document")
        
        # Aplicar formateo JSON estructurado si es necesario
        return self._format_as_json(final_content, file_path, "pdf_document")
    
    def _format_ai_pdf(self, pages_content: list, pdf_metadata: dict, file_path: str) -> str:
        """Formatea PDF optimizado para IA con estructura por páginas"""
        
        total_pages = len(pages_content)
        total_words = sum(page['word_count'] for page in pages_content)
        
        # Header con información del documento
        header = f"""## 📄 PDF Document Analysis
- **File:** {file_path.split('/')[-1]}
- **Title:** {pdf_metadata.get('title', 'Unknown')}
- **Author:** {pdf_metadata.get('author', 'Unknown')}
- **Pages:** {total_pages}
- **Total Words:** {total_words:,}
- **Average Words/Page:** {total_words // total_pages if total_pages > 0 else 0}

"""
        
        # Si hay muchas páginas, crear resumen ejecutivo
        if total_pages > 5:
            # Extraer texto de primeras páginas para resumen
            first_pages_text = " ".join([page['text'][:200] for page in pages_content[:3]])
            
            header += f"""### 🎯 Executive Summary (First 3 Pages)
{first_pages_text}...

### 📊 Document Structure
"""
            
            # Mostrar estructura de páginas
            for page in pages_content:
                preview = page['text'][:100].replace('\n', ' ')
                header += f"- **Page {page['number']}** ({page['word_count']} words): {preview}...\n"
            
            header += f"\n### 📖 Full Content\n"
        
        # Contenido completo estructurado por páginas
        content_sections = []
        for page in pages_content:
            page_header = f"#### 📄 Page {page['number']} ({page['word_count']} words)\n"
            content_sections.append(page_header + page['text'])
        
        full_content = "\n\n".join(content_sections)
        
        return header + full_content
    
    def _format_standard_pdf(self, text_content: str, file_path: str) -> str:
        """Formatea PDF en formato estándar"""
        
        if self.config.output_format == OutputFormat.MARKDOWN:
            return f"```pdf\n{text_content.strip()}\n```"
        else:
            return text_content.strip()