import csv
from file_reader.readers.base_reader import BaseReader
from file_reader.core.plugin_registry import PluginRegistry
from file_reader.core.enums import OutputFormat

@PluginRegistry.register("csv")
class CsvReader(BaseReader):
    def read(self, file_path: str) -> str:
        with open(file_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            rows = list(reader)
        
        if not rows:
            return "Empty CSV file"
        
        content = self._format_csv_content(rows, file_path)
        
        # Aplicar formateo IA si está habilitado
        final_content = self._apply_ai_formatting(content, file_path, "csv_dataset")
        
        # Aplicar formateo JSON si es necesario
        return self._format_as_json(final_content, file_path, "csv_dataset")
    
    def _format_csv_content(self, rows: list, file_path: str) -> str:
        """Formatea el contenido CSV según el formato de salida"""
        
        if self.config.output_format in [OutputFormat.MARKDOWN, OutputFormat.MARKDOWN_AI]:
            return self._format_as_markdown(rows, file_path)
        elif self.config.output_format == OutputFormat.PLAIN:
            return "\n".join([",".join(row) for row in rows])
        else:
            return self._format_as_markdown(rows, file_path)
    
    def _format_as_markdown(self, rows: list, file_path: str) -> str:
        """Formatea CSV como tabla Markdown optimizada para IA"""
        
        # Para formato AI, agregar metadata del dataset
        if self.config.output_format == OutputFormat.MARKDOWN_AI:
            metadata = f"""## 📊 Dataset Information
- **File:** {file_path.split('/')[-1]}
- **Total Rows:** {len(rows)-1:,} (excluding header)
- **Columns:** {len(rows[0])}
- **Headers:** {', '.join(rows[0])}

### 📋 Data Preview
"""
        else:
            metadata = ""
        
        # Construir tabla
        header = "| " + " | ".join(rows[0]) + " |"
        separator = "| " + " | ".join("---" for _ in rows[0]) + " |"
        
        # Para archivos grandes, mostrar solo muestra en formato AI
        if self.config.output_format == OutputFormat.MARKDOWN_AI and len(rows) > 11:
            # Mostrar primeras 10 filas de datos
            sample_rows = rows[1:11]
            body = "\n".join("| " + " | ".join(str(cell) for cell in row) + " |" for row in sample_rows)
            
            additional_info = f"\n\n### 📈 Dataset Statistics\n"
            additional_info += f"- **Sample showing:** First 10 rows of {len(rows)-1:,} total records\n"
            additional_info += f"- **Data types detected:** {self._analyze_data_types(rows)}\n"
            additional_info += f"- **Completeness:** {self._analyze_completeness(rows)}\n"
            
            additional_info += f"\n*Full dataset contains {len(rows)-1:,} rows - showing preview for AI analysis efficiency*"
            
        else:
            # Mostrar todas las filas para otros formatos
            body = "\n".join("| " + " | ".join(str(cell) for cell in row) + " |" for row in rows[1:])
            additional_info = ""
        
        return f"{metadata}{header}\n{separator}\n{body}{additional_info}"
    
    def _analyze_data_types(self, rows: list) -> str:
        """Analiza tipos de datos en las columnas"""
        if len(rows) < 2:
            return "Unknown"
        
        columns = len(rows[0])
        types = []
        
        for col in range(columns):
            sample_values = [rows[i][col] for i in range(1, min(6, len(rows))) if col < len(rows[i])]
            
            if all(self._is_number(val) for val in sample_values if val.strip()):
                types.append("Numeric")
            elif all(self._is_date(val) for val in sample_values if val.strip()):
                types.append("Date")
            else:
                types.append("Text")
        
        type_summary = {}
        for t in types:
            type_summary[t] = type_summary.get(t, 0) + 1
        
        return ", ".join(f"{count} {dtype}" for dtype, count in type_summary.items())
    
    def _analyze_completeness(self, rows: list) -> str:
        """Analiza completitud de los datos"""
        if len(rows) < 2:
            return "No data"
        
        total_cells = (len(rows) - 1) * len(rows[0])
        empty_cells = 0
        
        for row in rows[1:]:
            for cell in row:
                if not cell.strip():
                    empty_cells += 1
        
        completeness = ((total_cells - empty_cells) / total_cells) * 100
        return f"{completeness:.1f}% complete"
    
    def _is_number(self, value: str) -> bool:
        """Verifica si un valor es numérico"""
        try:
            float(value.replace(',', ''))
            return True
        except ValueError:
            return False
    
    def _is_date(self, value: str) -> bool:
        """Verifica si un valor parece una fecha"""
        import re
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
            r'\d{2}/\d{2}/\d{4}',  # MM/DD/YYYY
            r'\d{2}-\d{2}-\d{4}',  # DD-MM-YYYY
        ]
        return any(re.match(pattern, value.strip()) for pattern in date_patterns)