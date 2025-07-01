import pandas as pd
import openpyxl
import xlrd
import os
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

from file_reader.readers.base_reader import BaseReader
from file_reader.core.plugin_registry import PluginRegistry
from file_reader.core.enums import OutputFormat

logger = logging.getLogger(__name__)

@PluginRegistry.register("xlsx")
@PluginRegistry.register("xls")
@PluginRegistry.register("xlsm")
class ExcelReader(BaseReader):
    """
    Lector de archivos Excel optimizado para IA con soporte para múltiples formatos y hojas.
    """
    
    def read(self, file_path: str) -> str:
        """
        Lee y procesa un archivo Excel con estrategias adaptativas.
        """
        try:
            # Detectar tipo de archivo y estrategia óptima
            file_extension = Path(file_path).suffix.lower()
            strategy = self._select_reading_strategy(file_path, file_extension)
            
            logger.info(f"Procesando Excel con estrategia: {strategy}")
            
            # Extraer datos usando la estrategia seleccionada
            excel_data = self._extract_excel_data(file_path, strategy)
            
            # Formatear según configuración
            if self.config.output_format == OutputFormat.MARKDOWN_AI:
                content = self._format_ai_excel(excel_data, file_path)
            else:
                content = self._format_standard_excel(excel_data, file_path)
            
            # Aplicar formateo IA si está habilitado
            final_content = self._apply_ai_formatting(content, file_path, "excel_workbook")
            
            # Aplicar formateo JSON estructurado si es necesario
            return self._format_as_json(final_content, file_path, "excel_workbook")
            
        except Exception as e:
            logger.error(f"Error procesando archivo Excel: {e}")
            return self._handle_excel_error(file_path, str(e))
    
    def _select_reading_strategy(self, file_path: str, file_extension: str) -> str:
        """
        Selecciona la estrategia óptima de lectura basada en el archivo.
        """
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        
        # Archivos .xls legacy requieren xlrd
        if file_extension == '.xls':
            return 'xlrd'
        
        # Archivos grandes (>50MB) usan pandas por rendimiento
        elif file_size_mb > 50:
            return 'pandas_chunked'
        
        # Archivos medianos usan pandas estándar
        elif file_size_mb > 5:
            return 'pandas'
        
        # Archivos pequeños usan openpyxl para máximo detalle
        else:
            return 'openpyxl'
    
    def _extract_excel_data(self, file_path: str, strategy: str) -> Dict[str, Any]:
        """
        Extrae datos usando la estrategia seleccionada.
        """
        try:
            if strategy == 'openpyxl':
                return self._read_with_openpyxl(file_path)
            elif strategy == 'pandas':
                return self._read_with_pandas(file_path)
            elif strategy == 'pandas_chunked':
                return self._read_with_pandas_chunked(file_path)
            elif strategy == 'xlrd':
                return self._read_with_xlrd(file_path)
            else:
                raise ValueError(f"Estrategia desconocida: {strategy}")
                
        except Exception as e:
            logger.warning(f"Estrategia {strategy} falló: {e}, intentando fallback")
            return self._read_with_fallback(file_path)
    
    def _read_with_openpyxl(self, file_path: str) -> Dict[str, Any]:
        """
        Lee Excel con openpyxl para máximo detalle y metadatos.
        """
        workbook = openpyxl.load_workbook(file_path, data_only=True)
        
        excel_data = {
            'strategy': 'openpyxl',
            'metadata': self._extract_workbook_metadata(workbook, file_path),
            'sheets': {}
        }
        
        # Procesar cada hoja
        for sheet_name in workbook.sheetnames:
            sheet = workbook[sheet_name]
            
            # Extraer datos de la hoja
            sheet_data = []
            for row in sheet.iter_rows(values_only=True):
                # Filtrar filas completamente vacías
                if any(cell is not None for cell in row):
                    sheet_data.append([cell if cell is not None else "" for cell in row])
            
            if sheet_data:
                excel_data['sheets'][sheet_name] = {
                    'data': sheet_data,
                    'dimensions': f"{sheet.max_row} x {sheet.max_column}",
                    'has_merged_cells': len(sheet.merged_cells.ranges) > 0,
                    'formulas': self._extract_formulas(sheet)
                }
        
        workbook.close()
        return excel_data
    
    def _read_with_pandas(self, file_path: str) -> Dict[str, Any]:
        """
        Lee Excel con pandas para análisis eficiente de datos.
        """
        # Leer todas las hojas
        excel_file = pd.ExcelFile(file_path)
        
        excel_data = {
            'strategy': 'pandas',
            'metadata': {
                'file_name': Path(file_path).name,
                'file_size_mb': round(os.path.getsize(file_path) / (1024 * 1024), 2),
                'sheet_names': excel_file.sheet_names,
                'total_sheets': len(excel_file.sheet_names)
            },
            'sheets': {}
        }
        
        # Procesar cada hoja
        for sheet_name in excel_file.sheet_names:
            try:
                df = pd.read_excel(excel_file, sheet_name=sheet_name)
                
                if not df.empty:
                    excel_data['sheets'][sheet_name] = {
                        'data': self._dataframe_to_list(df),
                        'dimensions': f"{len(df)} x {len(df.columns)}",
                        'column_types': self._analyze_dataframe_types(df),
                        'data_quality': self._analyze_data_quality(df)
                    }
                    
            except Exception as e:
                logger.warning(f"Error procesando hoja '{sheet_name}': {e}")
                excel_data['sheets'][sheet_name] = {
                    'error': str(e),
                    'data': []
                }
        
        excel_file.close()
        return excel_data
    
    def _read_with_pandas_chunked(self, file_path: str) -> Dict[str, Any]:
        """
        Lee archivos Excel grandes usando chunking.
        """
        excel_file = pd.ExcelFile(file_path)
        
        excel_data = {
            'strategy': 'pandas_chunked',
            'metadata': {
                'file_name': Path(file_path).name,
                'file_size_mb': round(os.path.getsize(file_path) / (1024 * 1024), 2),
                'sheet_names': excel_file.sheet_names,
                'total_sheets': len(excel_file.sheet_names),
                'chunked_processing': True
            },
            'sheets': {}
        }
        
        # Para archivos grandes, procesar solo muestra de cada hoja
        for sheet_name in excel_file.sheet_names:
            try:
                # Leer solo primeras 1000 filas para análisis
                df = pd.read_excel(excel_file, sheet_name=sheet_name, nrows=1000)
                
                if not df.empty:
                    excel_data['sheets'][sheet_name] = {
                        'data': self._dataframe_to_list(df),
                        'dimensions': f"{len(df)} x {len(df.columns)} (muestra)",
                        'column_types': self._analyze_dataframe_types(df),
                        'note': 'Muestra de primeras 1000 filas para optimización'
                    }
                    
            except Exception as e:
                logger.warning(f"Error procesando hoja '{sheet_name}': {e}")
        
        excel_file.close()
        return excel_data
    
    def _read_with_xlrd(self, file_path: str) -> Dict[str, Any]:
        """
        Lee archivos .xls legacy con xlrd.
        """
        workbook = xlrd.open_workbook(file_path)
        
        excel_data = {
            'strategy': 'xlrd',
            'metadata': {
                'file_name': Path(file_path).name,
                'file_type': 'Legacy Excel (.xls)',
                'sheet_names': workbook.sheet_names(),
                'total_sheets': workbook.nsheets
            },
            'sheets': {}
        }
        
        # Procesar cada hoja
        for sheet_name in workbook.sheet_names():
            sheet = workbook.sheet_by_name(sheet_name)
            
            sheet_data = []
            for row_idx in range(sheet.nrows):
                row_data = []
                for col_idx in range(sheet.ncols):
                    cell = sheet.cell(row_idx, col_idx)
                    row_data.append(self._convert_xlrd_cell_value(cell))
                sheet_data.append(row_data)
            
            excel_data['sheets'][sheet_name] = {
                'data': sheet_data,
                'dimensions': f"{sheet.nrows} x {sheet.ncols}"
            }
        
        return excel_data
    
    def _read_with_fallback(self, file_path: str) -> Dict[str, Any]:
        """
        Estrategia de fallback cuando otras fallan.
        """
        fallback_strategies = ['pandas', 'openpyxl', 'xlrd']
        
        for strategy in fallback_strategies:
            try:
                logger.info(f"Intentando estrategia de fallback: {strategy}")
                
                if strategy == 'pandas':
                    return self._read_with_pandas(file_path)
                elif strategy == 'openpyxl':
                    return self._read_with_openpyxl(file_path)
                elif strategy == 'xlrd' and Path(file_path).suffix.lower() == '.xls':
                    return self._read_with_xlrd(file_path)
                    
            except Exception as e:
                logger.warning(f"Fallback {strategy} falló: {e}")
                continue
        
        # Si todo falla, retornar estructura mínima
        return {
            'strategy': 'fallback_failed',
            'metadata': {
                'file_name': Path(file_path).name,
                'error': 'Todas las estrategias de lectura fallaron'
            },
            'sheets': {}
        }
    
    def _extract_workbook_metadata(self, workbook: openpyxl.Workbook, file_path: str) -> Dict[str, Any]:
        """
        Extrae metadatos completos del workbook.
        """
        props = workbook.properties
        
        return {
            'file_name': Path(file_path).name,
            'file_size_mb': round(os.path.getsize(file_path) / (1024 * 1024), 2),
            'title': props.title or 'Sin título',
            'creator': props.creator or 'Desconocido',
            'created': props.created.isoformat() if props.created else None,
            'modified': props.modified.isoformat() if props.modified else None,
            'subject': props.subject or '',
            'description': props.description or '',
            'sheet_names': workbook.sheetnames,
            'total_sheets': len(workbook.sheetnames),
            'defined_names': [name.name for name in workbook.defined_names],
            'has_vba': workbook.vba_archive is not None
        }
    
    def _extract_formulas(self, sheet) -> List[Dict[str, str]]:
        """
        Extrae fórmulas de una hoja.
        """
        formulas = []
        
        for row in sheet.iter_rows():
            for cell in row:
                if cell.value and isinstance(cell.value, str) and cell.value.startswith('='):
                    formulas.append({
                        'cell': cell.coordinate,
                        'formula': cell.value
                    })
        
        return formulas[:10]  # Limitar a 10 fórmulas para el reporte
    
    def _dataframe_to_list(self, df: pd.DataFrame) -> List[List]:
        """
        Convierte DataFrame a lista de listas con headers.
        """
        # Incluir headers como primera fila
        result = [df.columns.tolist()]
        
        # Agregar datos, reemplazando NaN con cadenas vacías
        for _, row in df.iterrows():
            result.append([str(val) if pd.notna(val) else "" for val in row])
        
        return result
    
    def _analyze_dataframe_types(self, df: pd.DataFrame) -> Dict[str, str]:
        """
        Analiza tipos de datos en DataFrame.
        """
        type_mapping = {
            'object': 'Texto',
            'int64': 'Entero',
            'float64': 'Decimal',
            'datetime64[ns]': 'Fecha',
            'bool': 'Booleano'
        }
        
        return {
            col: type_mapping.get(str(df[col].dtype), str(df[col].dtype))
            for col in df.columns
        }
    
    def _analyze_data_quality(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analiza calidad de datos en DataFrame.
        """
        total_cells = df.size
        missing_cells = df.isnull().sum().sum()
        
        return {
            'total_rows': len(df),
            'total_columns': len(df.columns),
            'missing_values': int(missing_cells),
            'completeness_percentage': round((1 - missing_cells / total_cells) * 100, 2),
            'duplicate_rows': int(df.duplicated().sum())
        }
    
    def _convert_xlrd_cell_value(self, cell):
        """
        Convierte valores de celda xlrd a formato apropiado.
        """
        if cell.ctype == xlrd.XL_CELL_DATE:
            return xlrd.xldate_as_datetime(cell.value, 0).strftime('%Y-%m-%d')
        elif cell.ctype == xlrd.XL_CELL_NUMBER:
            return cell.value
        elif cell.ctype == xlrd.XL_CELL_BOOLEAN:
            return bool(cell.value)
        else:
            return str(cell.value) if cell.value else ""
    
    def _format_ai_excel(self, excel_data: Dict[str, Any], file_path: str) -> str:
        """
        Formatea datos de Excel optimizado para IA.
        """
        metadata = excel_data['metadata']
        
        # Header con análisis del archivo
        header = f"""## 📊 Excel Workbook Analysis
- **Archivo:** {metadata['file_name']}
- **Estrategia de lectura:** {excel_data['strategy']}
- **Tamaño:** {metadata.get('file_size_mb', 'Desconocido')} MB
- **Hojas:** {metadata.get('total_sheets', len(excel_data['sheets']))}
- **Creado por:** {metadata.get('creator', 'Desconocido')}
- **Fecha creación:** {metadata.get('created', 'Desconocida')}

"""
        
        # Mostrar información de hojas
        if excel_data['sheets']:
            header += "### 📋 Estructura de Hojas\n"
            for sheet_name, sheet_info in excel_data['sheets'].items():
                if 'error' in sheet_info:
                    header += f"- **{sheet_name}**: ❌ Error - {sheet_info['error']}\n"
                else:
                    dimensions = sheet_info.get('dimensions', 'Desconocido')
                    header += f"- **{sheet_name}**: {dimensions}"
                    
                    if 'column_types' in sheet_info:
                        types_summary = ", ".join(set(sheet_info['column_types'].values()))
                        header += f" (Tipos: {types_summary})"
                    
                    header += "\n"
            header += "\n"
        
        # Contenido de las hojas
        content_sections = []
        
        for sheet_name, sheet_info in excel_data['sheets'].items():
            if 'error' in sheet_info:
                continue
                
            sheet_data = sheet_info['data']
            if not sheet_data:
                continue
            
            section = f"### 📄 Hoja: {sheet_name}\n"
            
            # Información adicional de la hoja
            if 'data_quality' in sheet_info:
                quality = sheet_info['data_quality']
                section += f"**Calidad de datos:** {quality['completeness_percentage']}% completo, "
                section += f"{quality['duplicate_rows']} filas duplicadas\n\n"
            
            # Mostrar datos como tabla markdown
            if len(sheet_data) > 0:
                # Limitar a primeras 10 filas para formato IA
                preview_data = sheet_data[:11] if len(sheet_data) > 10 else sheet_data
                
                # Crear tabla markdown
                if len(preview_data) > 1:
                    headers = preview_data[0]
                    rows = preview_data[1:]
                    
                    # Header de tabla
                    section += "| " + " | ".join(str(h) for h in headers) + " |\n"
                    section += "| " + " | ".join("---" for _ in headers) + " |\n"
                    
                    # Filas de datos
                    for row in rows:
                        # Asegurar que la fila tenga el mismo número de columnas
                        padded_row = row + [""] * (len(headers) - len(row))
                        section += "| " + " | ".join(str(cell)[:50] for cell in padded_row[:len(headers)]) + " |\n"
                    
                    if len(sheet_data) > 11:
                        section += f"\n*Mostrando primeras 10 filas de {len(sheet_data)-1} total*\n"
                else:
                    section += "Datos no tabulares detectados\n"
            
            content_sections.append(section)
        
        return header + "\n".join(content_sections)
    
    def _format_standard_excel(self, excel_data: Dict[str, Any], file_path: str) -> str:
        """
        Formatea Excel en formato estándar.
        """
        if self.config.output_format == OutputFormat.PLAIN:
            # Formato texto plano
            result = []
            for sheet_name, sheet_info in excel_data['sheets'].items():
                if 'data' in sheet_info:
                    result.append(f"=== {sheet_name} ===")
                    for row in sheet_info['data']:
                        result.append("\t".join(str(cell) for cell in row))
                    result.append("")
            return "\n".join(result)
        else:
            # Formato markdown estándar
            result = []
            for sheet_name, sheet_info in excel_data['sheets'].items():
                if 'data' in sheet_info and sheet_info['data']:
                    result.append(f"## {sheet_name}")
                    
                    data = sheet_info['data']
                    if len(data) > 1:
                        headers = data[0]
                        rows = data[1:6]  # Primeras 5 filas
                        
                        result.append("| " + " | ".join(str(h) for h in headers) + " |")
                        result.append("| " + " | ".join("---" for _ in headers) + " |")
                        
                        for row in rows:
                            padded_row = row + [""] * (len(headers) - len(row))
                            result.append("| " + " | ".join(str(cell) for cell in padded_row[:len(headers)]) + " |")
                    
                    result.append("")
            
            return "\n".join(result)
    
    def _handle_excel_error(self, file_path: str, error_message: str) -> str:
        """
        Maneja errores de lectura de Excel con información útil.
        """
        file_name = Path(file_path).name
        
        error_content = f"""## ❌ Error procesando archivo Excel

**Archivo:** {file_name}
**Error:** {error_message}

### 💡 Posibles soluciones:
- Verificar que el archivo no esté corrupto
- Asegurar que el archivo no esté protegido con contraseña
- Verificar que sea un archivo Excel válido (.xlsx, .xls, .xlsm)
- Intentar abrir el archivo en Excel para verificar su integridad

### 📋 Información técnica:
- **Extensión detectada:** {Path(file_path).suffix}
- **Tamaño de archivo:** {round(os.path.getsize(file_path) / (1024 * 1024), 2)} MB
"""
        
        return error_content