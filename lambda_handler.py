import json
import base64
import logging
import tempfile
import os
import traceback
from datetime import datetime
from typing import Dict, Any, Optional

from file_reader.core.config import FileReaderConfig
from file_reader.core.enums import OutputFormat
from file_reader.core.file_reader import FileReader
from file_reader.utils.s3_file_fetcher import S3FileFetcher, is_s3_path

# IMPORTAR READERS PARA REGISTRO AUTOMÁTICO (sin problemas)
import file_reader.readers.csv_reader
import file_reader.readers.docx_reader  
import file_reader.readers.excel_reader  # Excel Reader (xlsx, xls, xlsm)
import file_reader.readers.json_reader
import file_reader.readers.txt_reader
import file_reader.readers.xml_reader
import file_reader.readers.yaml_reader

# PDF Reader con import condicional
def _import_pdf_reader():
    """Importa el PDF reader de forma condicional para evitar errores de PyMuPDF"""
    try:
        logger.info("✅ PDF Reader cargado exitosamente")
        return True
    except ImportError as e:
        logger.warning(f"⚠️ PDF Reader no disponible: {str(e)}")
        logger.warning("📋 Los archivos PDF no podrán ser procesados")
        return False

# Configurar logging para Lambda en español
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Manejador AWS Lambda para File Reader con soporte S3 y base64.
    Procesa documentos de múltiples formatos con optimización para IA.
    
    Estructura del evento:
    {
        "file_name": "documento.pdf",
        "file_content": "contenido_base64_codificado",  # O
        "s3_path": "s3://bucket/ruta/al/archivo",
        "output_format": "markdown_ai",
        "ai_optimized": true,
        "include_metadata": true,
        "extract_key_sections": true,
        "max_chunk_size": 4000,
        "region": "us-east-1"  # opcional para S3
    }
    
    Formatos soportados:
    - PDF (.pdf) - Análisis por páginas con metadata
    - Word (.docx) - Estructura semántica y tablas  
    - Excel (.xlsx, .xls, .xlsm) - Multi-hoja con análisis de datos
    - CSV (.csv) - Análisis de dataset con tipos de datos
    - JSON (.json) - Análisis de estructura y complejidad
    - XML (.xml) - Schema y namespaces
    - YAML (.yaml, .yml) - Patrones de configuración
    - Texto (.txt) - Estructura y análisis semántico
    """
    tmp_file_path: Optional[str] = None
    file_bytes: Optional[bytes] = None
    start_time = datetime.now()

    try:
        logger.info("📥 Iniciando ejecución de Lambda")
        
        # Validación temprana del evento
        if not event:
            raise ValueError("Evento vacío recibido")
        
        logger.info(f"📥 Tipo de evento recibido: {type(event)}")
        
        # Intentar cargar PDF reader al inicio de la ejecución
        pdf_available = _import_pdf_reader()
        
        # Parsear cuerpo del evento - VERSIÓN CORREGIDA
        body = event.get("body")
        
        # Caso 1: Invocación desde API Gateway (body es string JSON)
        if isinstance(body, str):
            try:
                body = json.loads(body)
                logger.info("📥 Evento recibido desde API Gateway")
            except json.JSONDecodeError as e:
                raise ValueError(f"JSON inválido en el cuerpo de la solicitud: {e}")
        
        # Caso 2: Invocación directa o body es None (usar event directamente)
        elif body is None:
            body = event
            logger.info("📥 Evento recibido directamente (sin API Gateway)")
        
        # Caso 3: body ya es un diccionario (algunos casos de API Gateway)
        elif isinstance(body, dict):
            logger.info("📥 Evento recibido con body como diccionario")
            # body ya está listo para usar
        
        else:
            raise ValueError(f"Formato de evento no soportado. Tipo de body: {type(body)}")

        # Extraer y validar parámetros requeridos
        file_name = body.get("file_name")
        file_content_b64 = body.get("file_content")
        s3_path = body.get("s3_path")

        # Verificar si se está intentando procesar un PDF sin el reader disponible
        if file_name and file_name.lower().endswith('.pdf') and not pdf_available:
            raise ValueError("El procesamiento de archivos PDF no está disponible en este momento. "
                           "Formatos disponibles: DOCX, XLSX, CSV, JSON, XML, YAML, TXT")

        # Extraer parámetros opcionales con valores por defecto
        output_format = body.get("output_format", "markdown")
        ai_optimized = body.get("ai_optimized", False)
        include_metadata = body.get("include_metadata", False)
        extract_key_sections = body.get("extract_key_sections", False)
        max_chunk_size = body.get("max_chunk_size", 4000)
        region = body.get("region")  # Región AWS opcional
        processing_images = body.get("processing_images", False)

        # Validar entradas requeridas
        if not file_name:
            raise ValueError("Falta el parámetro requerido: 'file_name'")

        if not file_content_b64 and not s3_path:
            raise ValueError("Debe proporcionar 'file_content' (base64) o 's3_path'")

        if file_content_b64 and s3_path:
            raise ValueError("No puede proporcionar tanto 'file_content' como 's3_path'. Elija un método de entrada")

        # Validar formato de salida
        try:
            OutputFormat(output_format)
        except ValueError:
            valid_formats = [f.value for f in OutputFormat]
            raise ValueError(f"Formato de salida inválido: '{output_format}'. Opciones válidas: {valid_formats}")

        # 📦 Procesar entrada de archivo (base64 o S3)
        if file_content_b64:
            logger.info(f"📂 Procesando contenido base64 para archivo: {file_name}")
            tmp_file_path = _procesar_contenido_base64(file_content_b64, file_name)
            
        else:  # s3_path
            logger.info(f"📂 Procesando archivo S3: {s3_path}")
            tmp_file_path = _procesar_archivo_s3(s3_path, region)

        # Leer tamaño de archivo para metadata
        with open(tmp_file_path, "rb") as f:
            file_bytes = f.read()

        # 🛠️ Configurar y ejecutar lector de archivos
        config = FileReaderConfig(
            output_format=OutputFormat(output_format),
            ai_optimized=ai_optimized,
            include_metadata=include_metadata,
            extract_key_sections=extract_key_sections,
            max_chunk_size=max_chunk_size,
            processing_images=processing_images
        )

        logger.info(f"🔄 Procesando archivo con formato: {output_format}, IA: {ai_optimized}")
        reader = FileReader(config)
        result = reader.read(tmp_file_path)

        # Calcular tiempo de procesamiento
        processing_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"✅ Archivo procesado exitosamente en {processing_time:.2f}s")

        # Construir respuesta exitosa
        response_body = {
            "success": True,
            "mensaje": "Archivo procesado exitosamente",
            "archivo": {
                "nombre": file_name,
                "formato_salida": output_format,
                "optimizado_ia": ai_optimized,
                "metodo_entrada": "s3" if s3_path else "base64"
            },
            "resultado": result,
            "estadisticas": {
                "procesado_en": datetime.now().isoformat(),
                "tiempo_procesamiento_segundos": round(processing_time, 2),
                "id_solicitud_lambda": context.aws_request_id if context else "local",
                "tamano_archivo_bytes": len(file_bytes),
                "tamano_salida_caracteres": len(result),
                "version_procesador": "FileReader v2.0 - IA Optimizado",
                "pdf_disponible": pdf_available
            }
        }

        if s3_path:
            response_body["archivo"]["ruta_s3"] = s3_path

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json; charset=utf-8",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization",
                "X-Processed-By": "FileReader-Lambda-ES",
                "X-Processing-Time": str(round(processing_time, 2)),
                "X-PDF-Available": str(pdf_available)
            },
            "body": json.dumps(response_body, ensure_ascii=False, indent=2)
        }

    except ValueError as e:
        # Errores del cliente (400)
        logger.warning(f"⚠️ Error del cliente: {str(e)}")
        return _crear_respuesta_error(400, str(e), "ErrorValidacion")

    except Exception as e:
        # Errores del servidor (500)
        logger.exception(f"❌ Error interno del servidor: {str(e)}")
        return _crear_respuesta_error(
            500, 
            "Ocurrió un error interno al procesar el archivo", 
            type(e).__name__,
            str(e) if context and hasattr(context, 'get_remaining_time_in_millis') else None
        )

    finally:
        # 🗑️ Limpiar archivos temporales
        if tmp_file_path and os.path.exists(tmp_file_path):
            try:
                os.unlink(tmp_file_path)
                logger.info(f"🗑️ Archivo temporal limpiado: {tmp_file_path}")
            except Exception as cleanup_error:
                logger.warning(f"⚠️ Error al limpiar archivo temporal: {cleanup_error}")


def _procesar_contenido_base64(file_content_b64: str, file_name: str) -> str:
    """
    Procesa contenido de archivo codificado en base64 y lo guarda en archivo temporal.
    
    Args:
        file_content_b64: Contenido del archivo codificado en base64
        file_name: Nombre original del archivo para nomenclatura del temporal
        
    Returns:
        Ruta al archivo temporal
        
    Raises:
        ValueError: Si la decodificación base64 falla o el contenido está vacío
    """
    try:
        file_bytes = base64.b64decode(file_content_b64)
    except Exception as e:
        raise ValueError(f"Contenido base64 inválido: {e}")

    if len(file_bytes) == 0:
        raise ValueError("El contenido del archivo decodificado está vacío")

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file_name}", prefix="lambda_") as tmp_file:
            tmp_file.write(file_bytes)
            logger.info(f"📁 Contenido base64 guardado en archivo temporal: {tmp_file.name}")
            return tmp_file.name
    except Exception as e:
        raise ValueError(f"Error al crear archivo temporal: {e}")


def _procesar_archivo_s3(s3_path: str, region: Optional[str] = None) -> str:
    """
    Descarga archivo desde S3 y lo guarda en ubicación temporal.
    
    Args:
        s3_path: URI S3 (s3://bucket/clave)
        region: Región AWS opcional
        
    Returns:
        Ruta al archivo temporal
        
    Raises:
        ValueError: Para errores relacionados con S3
    """
    if not is_s3_path(s3_path):
        raise ValueError(f"Formato de ruta S3 inválido: {s3_path}")

    try:
        s3_fetcher = S3FileFetcher(region_name=region)
        
        # Verificar si el objeto existe primero
        if not s3_fetcher.check_object_exists(s3_path):
            raise ValueError(f"Objeto S3 no encontrado: {s3_path}")
        
        # Descargar archivo
        temp_path = s3_fetcher.download_to_temp(s3_path)
        logger.info(f"📁 Archivo S3 descargado a ubicación temporal: {temp_path}")
        return temp_path
        
    except Exception as e:
        if "no encontrado" in str(e).lower() or "not found" in str(e).lower():
            raise ValueError(f"Objeto S3 no encontrado: {s3_path}")
        elif "acceso denegado" in str(e).lower() or "access denied" in str(e).lower():
            raise ValueError(f"Acceso denegado al objeto S3: {s3_path}")
        else:
            raise ValueError(f"Error de descarga desde S3: {e}")


def _crear_respuesta_error(status_code: int, mensaje: str, tipo_error: str, detalles: Optional[str] = None) -> Dict[str, Any]:
    """
    Crea respuesta de error estandarizada en español.
    
    Args:
        status_code: Código de estado HTTP
        mensaje: Mensaje de error amigable para el usuario
        tipo_error: Tipo de error técnico
        detalles: Información detallada opcional del error
        
    Returns:
        Diccionario de respuesta Lambda
    """
    error_body = {
        "success": False,
        "error": {
            "mensaje": mensaje,
            "tipo": tipo_error,
            "codigo": status_code,
            "timestamp": datetime.now().isoformat()
        }
    }
    
    if detalles:
        error_body["error"]["detalles_tecnicos"] = detalles

    # Agregar mensajes de ayuda según el tipo de error
    if status_code == 400:
        error_body["ayuda"] = {
            "sugerencias": [
                "Verifique que todos los parámetros requeridos estén presentes",
                "Asegúrese de que el formato de salida sea válido",
                "Para S3: verifique que la ruta tenga formato s3://bucket/archivo",
                "Para base64: verifique que el contenido esté correctamente codificado"
            ],
            "formatos_soportados": [
                "PDF (.pdf) - Condicional", "Word (.docx)", "Excel (.xlsx, .xls, .xlsm)",
                "CSV (.csv)", "JSON (.json)", "XML (.xml)", 
                "YAML (.yaml, .yml)", "Texto (.txt)"
            ],
            "ejemplo_solicitud": {
                "file_name": "documento.pdf",
                "s3_path": "s3://mi-bucket/documentos/archivo.pdf",
                "output_format": "markdown_ai",
                "ai_optimized": True
            }
        }
    elif status_code == 500:
        error_body["ayuda"] = {
            "sugerencias": [
                "Verifique que el archivo no esté corrupto",
                "Asegúrese de que el archivo sea de un formato soportado",
                "Para archivos grandes, intente procesarlos por partes",
                "Contacte al soporte técnico si el problema persiste"
            ],
            "soporte": "Si el error continúa, proporcione el ID de solicitud para diagnóstico"
        }

    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json; charset=utf-8",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "X-Error-Type": tipo_error
        },
        "body": json.dumps(error_body, ensure_ascii=False, indent=2)
    }


def health_check_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Endpoint de verificación de salud para monitoreo del servicio.
    
    Returns:
        Respuesta con estado del servicio y estadísticas
    """
    from file_reader.core.plugin_registry import PluginRegistry
    
    # Importar readers para asegurar registro (excepto PDF)
    import file_reader.readers.csv_reader
    import file_reader.readers.docx_reader  
    import file_reader.readers.excel_reader
    import file_reader.readers.json_reader
    import file_reader.readers.txt_reader
    import file_reader.readers.xml_reader
    import file_reader.readers.yaml_reader
    
    # Verificar PDF reader de forma condicional
    pdf_available = _import_pdf_reader()
    
    health_info = {
        "estado": "saludable",
        "servicio": "FileReader Lambda - Procesador de Documentos con IA",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat(),
        "capacidades": {
            "formatos_soportados": sorted(PluginRegistry.get_supported_extensions()),
            "total_formatos": len(PluginRegistry.get_supported_extensions()),
            "optimizacion_ia": True,
            "soporte_s3": True,
            "procesamiento_multi_hoja": True,
            "pdf_disponible": pdf_available
        },
        "estadisticas": {
            "memoria_disponible": "Disponible",
            "readers_registrados": len(PluginRegistry.get_supported_extensions()),
            "tiempo_respuesta_ms": "<100"
        }
    }
    
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json; charset=utf-8",
            "Cache-Control": "no-cache"
        },
        "body": json.dumps(health_info, ensure_ascii=False, indent=2)
    }