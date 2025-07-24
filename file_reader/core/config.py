import os
from file_reader.core.enums import OutputFormat

class FileReaderConfig:
    def __init__(self, 
                 output_format: OutputFormat = OutputFormat.MARKDOWN,
                 ai_optimized: bool = False,
                 include_metadata: bool = False,
                 max_chunk_size: int = 4000,
                 extract_key_sections: bool = False,
                 processing_images : bool = False):
        self.output_format = output_format
        self.ai_optimized = ai_optimized
        self.include_metadata = include_metadata
        self.max_chunk_size = max_chunk_size
        self.extract_key_sections = extract_key_sections
        self.processing_images = processing_images
        
        # Auto-enable AI features for markdown_ai format
        if output_format == OutputFormat.MARKDOWN_AI:
            self.ai_optimized = True
            self.include_metadata = True
            self.extract_key_sections = True

    @staticmethod
    def from_env() -> 'FileReaderConfig':
        format_str = os.getenv("OUTPUT_FORMAT").lower()
        try:
            output_format = OutputFormat(format_str)
        except ValueError:
            output_format = OutputFormat.MARKDOWN
        
        ai_optimized = os.getenv("AI_OPTIMIZED").lower() == "true"
        include_metadata = os.getenv("INCLUDE_METADATA").lower() == "true"
        max_chunk_size = int(os.getenv("MAX_CHUNK_SIZE"))
        extract_key_sections = os.getenv("EXTRACT_KEY_SECTIONS").lower() == "true"
        
        return FileReaderConfig(
            output_format=output_format,
            ai_optimized=ai_optimized,
            include_metadata=include_metadata,
            max_chunk_size=max_chunk_size,
            extract_key_sections=extract_key_sections
        )