import json
import base64
import logging
import tempfile
import os
from datetime import datetime
from typing import Dict, Any, Optional

from file_reader.core.config import FileReaderConfig
from file_reader.core.enums import OutputFormat
from file_reader.core.file_reader import FileReader
from file_reader.utils.s3_file_fetcher import S3FileFetcher, is_s3_path

# Forzar el registro de readers (sin problemas)
import file_reader.readers.csv_reader
import file_reader.readers.docx_reader
import file_reader.readers.excel_reader
import file_reader.readers.json_reader
import file_reader.readers.txt_reader
import file_reader.readers.xml_reader
import file_reader.readers.yaml_reader

# PDF Reader con import condicional
def _import_pdf_reader():
    """Importa el PDF reader de forma condicional para evitar errores de PyMuPDF"""
    try:
        logger.info("✅ PDF Reader, por el momento no aplica")
        return True
    except ImportError as e:
        logger.warning(f"⚠️ PDF Reader no disponible: {str(e)}")
        logger.warning("📋 Los archivos PDF no podrán ser procesados")
        return False

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

def main(input_json_path: str = "local_input_event.json"):
    try:
        logger.info("🚀 Iniciando simulación con archivo: %s", input_json_path)
        
        # Intentar cargar PDF reader
        pdf_available = _import_pdf_reader()
        
        event_body = cargar_entrada(input_json_path)
        response = procesar_evento_local(event_body, pdf_available)
        logger.info("✅ Proceso completado con éxito.")
        print(json.dumps(response, indent=2, ensure_ascii=False))
    except Exception as e:
        logger.exception("❌ Error crítico en ejecución local: %s", str(e))


def cargar_entrada(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("El JSON de entrada debe ser un objeto (diccionario)")
    return data


def procesar_evento_local(body: Dict[str, Any], pdf_available: bool = True) -> Dict[str, Any]:
    archivo_temporal: Optional[str] = None
    file_bytes: Optional[bytes] = None
    start_time = datetime.now()

    try:
        params = _extraer_parametros(body, pdf_available)
        archivo_temporal = _preparar_archivo(params)
        file_bytes = _leer_bytes(archivo_temporal)

        result = _procesar_con_file_reader(archivo_temporal, params)

        return _construir_respuesta(params, result, file_bytes, start_time, pdf_available)

    finally:
        _limpiar_temporal(archivo_temporal)


# ---------------------- Funciones Auxiliares ----------------------

def _extraer_parametros(body: Dict[str, Any], pdf_available: bool) -> Dict[str, Any]:
    file_name = body.get("file_name")
    file_content_b64 = body.get("file_content")
    s3_path = body.get("s3_path")

    if not file_name:
        raise ValueError("Falta el parámetro requerido: 'file_name'")
    if not file_content_b64 and not s3_path:
        raise ValueError("Debe proporcionar 'file_content' o 's3_path'")
    if file_content_b64 and s3_path:
        raise ValueError("Solo uno de 'file_content' o 's3_path' debe ser usado")

    # Verificar si se está intentando procesar un PDF sin el reader disponible
    if file_name and file_name.lower().endswith('.pdf') and not pdf_available:
        raise ValueError("El procesamiento de archivos PDF no está disponible. "
                       "Formatos disponibles: DOCX, XLSX, CSV, JSON, XML, YAML, TXT")

    output_format = body.get("output_format", "markdown")
    ai_optimized = body.get("ai_optimized", False)
    include_metadata = body.get("include_metadata", False)
    extract_key_sections = body.get("extract_key_sections", False)
    max_chunk_size = body.get("max_chunk_size", 4000)
    region = body.get("region")

    try:
        output_format_enum = OutputFormat(output_format)
    except ValueError:
        opciones = [f.value for f in OutputFormat]
        raise ValueError(f"Formato de salida inválido: '{output_format}'. Válidos: {opciones}")

    return {
        "file_name": file_name,
        "file_content": file_content_b64,
        "s3_path": s3_path,
        "region": region,
        "output_format": output_format_enum,
        "ai_optimized": ai_optimized,
        "include_metadata": include_metadata,
        "extract_key_sections": extract_key_sections,
        "max_chunk_size": max_chunk_size
    }


def _preparar_archivo(params: Dict[str, Any]) -> str:
    if params["file_content"]:
        logger.info("📄 Procesando archivo local base64: %s", params["file_name"])
        return _procesar_contenido_base64(params["file_content"], params["file_name"])
    else:
        logger.info("☁️ Descargando desde S3: %s", params["s3_path"])
        return _procesar_archivo_s3(params["s3_path"], params["region"])


def _leer_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def _procesar_con_file_reader(path: str, params: Dict[str, Any]) -> str:
    config = FileReaderConfig(
        output_format=params["output_format"],
        ai_optimized=params["ai_optimized"],
        include_metadata=params["include_metadata"],
        extract_key_sections=params["extract_key_sections"],
        max_chunk_size=params["max_chunk_size"]
    )
    logger.info("⚙️ Ejecutando FileReader con config: %s", config.__dict__)
    reader = FileReader(config)
    return reader.read(path)


def _construir_respuesta(params: Dict[str, Any], result: str, file_bytes: bytes, start_time: datetime, pdf_available: bool) -> Dict[str, Any]:
    elapsed = (datetime.now() - start_time).total_seconds()
    return {
        "success": True,
        "mensaje": "Archivo procesado exitosamente",
        "archivo": {
            "nombre": params["file_name"],
            "formato_salida": params["output_format"].value,
            "optimizado_ia": params["ai_optimized"],
            "metodo_entrada": "s3" if params["s3_path"] else "base64",
            "ruta_s3": params["s3_path"]
        },
        "resultado": result,
        "estadisticas": {
            "procesado_en": datetime.now().isoformat(),
            "tiempo_procesamiento_segundos": round(elapsed, 2),
            "id_solicitud_lambda": "simulado-local",
            "tamano_archivo_bytes": len(file_bytes),
            "tamano_salida_caracteres": len(result),
            "version_procesador": "FileReader v2.0 - IA Optimizado",
            "pdf_disponible": pdf_available
        }
    }


def _procesar_contenido_base64(file_b64: str, filename: str) -> str:
    try:
        file_bytes = base64.b64decode(file_b64)
    except Exception as e:
        raise ValueError(f"Error decodificando base64: {e}")
    if not file_bytes:
        raise ValueError("Contenido base64 vacío")

    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{filename}", prefix="local_")
    tmp_file.write(file_bytes)
    tmp_file.close()
    return tmp_file.name


def _procesar_archivo_s3(s3_path: str, region: Optional[str]) -> str:
    if not is_s3_path(s3_path):
        raise ValueError(f"Ruta S3 inválida: {s3_path}")
    fetcher = S3FileFetcher(region_name=region)
    if not fetcher.check_object_exists(s3_path):
        raise ValueError(f"Objeto no encontrado en S3: {s3_path}")
    return fetcher.download_to_temp(s3_path)


def _limpiar_temporal(path: Optional[str]):
    if path and os.path.exists(path):
        try:
            os.unlink(path)
            logger.info("🧹 Eliminado archivo temporal: %s", path)
        except Exception as e:
            logger.warning("⚠️ No se pudo eliminar el archivo temporal: %s", e)

# ------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    # Ruta por defecto a ./tests/test.json si no se pasa argumento
    default_path = os.path.join("tests", "test.json")
    input_path = sys.argv[1] if len(sys.argv) > 1 else default_path
    main(input_json_path=input_path)