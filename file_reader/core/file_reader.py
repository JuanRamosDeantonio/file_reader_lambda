import os
import logging
from file_reader.core.plugin_registry import PluginRegistry

# IMPORTAR TODOS LOS READERS PARA REGISTRO AUTOMÁTICO
from file_reader.readers import *  # Importa todos los readers

logger = logging.getLogger(__name__)

class FileReader:
    """
    Clase principal de lectura de archivos con validación y manejo de errores integral.
    """
    
    def __init__(self, config):
        """
        Inicializa FileReader con configuración.
        
        Args:
            config: Instancia de FileReaderConfig
        """
        self.config = config
        logger.debug(f"FileReader inicializado con formato: {config.output_format}")
        
        # Debug: Mostrar extensiones registradas
        registered = PluginRegistry.get_supported_extensions()
        logger.debug(f"Extensiones registradas: {registered}")

    def read(self, file_path: str) -> str:
        """
        Lee y procesa un archivo usando el reader apropiado.
        
        Args:
            file_path: Ruta al archivo a leer
            
        Returns:
            Contenido del archivo procesado como string
            
        Raises:
            FileNotFoundError: Si el archivo no existe
            ValueError: Si la extensión no está soportada o el archivo está vacío
            PermissionError: Si el archivo no se puede leer por permisos
        """
        # Validar que el archivo existe
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Archivo no encontrado: {file_path}")
        
        # Validar que el archivo es legible
        if not os.access(file_path, os.R_OK):
            raise PermissionError(f"El archivo no es legible: {file_path}")
        
        # Validar que el archivo no está vacío
        if os.path.getsize(file_path) == 0:
            raise ValueError(f"El archivo está vacío: {file_path}")
        
        # Extraer y validar extensión del archivo
        _, ext = os.path.splitext(file_path)
        ext = ext[1:] if ext.startswith(".") else ext
        
        if not ext:
            raise ValueError(f"El archivo no tiene extensión: {file_path}")
        
        # Verificar si la extensión está soportada
        if not PluginRegistry.is_supported(ext):
            supported = ", ".join(sorted(PluginRegistry.get_supported_extensions()))
            raise ValueError(
                f"Extensión de archivo no soportada '{ext}'. "
                f"Extensiones soportadas: {supported}"
            )
        
        # Obtener e instanciar el reader apropiado
        reader_cls = PluginRegistry.get_reader(ext)
        logger.info(f"Procesando archivo {ext.upper()}: {os.path.basename(file_path)}")
        
        try:
            reader = reader_cls(self.config)
            result = reader.read(file_path)
            
            logger.info(f"Archivo procesado exitosamente: {len(result)} caracteres generados")
            return result
            
        except Exception as e:
            logger.error(f"Error procesando archivo con {reader_cls.__name__}: {e}")
            raise ValueError(f"Falló al procesar archivo {ext.upper()}: {e}")

    def get_supported_extensions(self) -> list:
        """
        Obtiene lista de extensiones de archivo soportadas.
        
        Returns:
            Lista de extensiones de archivo soportadas
        """
        return PluginRegistry.get_supported_extensions()

    def is_supported_file(self, file_path: str) -> bool:
        """
        Verifica si un archivo está soportado basado en su extensión.
        
        Args:
            file_path: Ruta al archivo
            
        Returns:
            True si la extensión está soportada, False en caso contrario
        """
        _, ext = os.path.splitext(file_path)
        ext = ext[1:] if ext.startswith(".") else ext
        return PluginRegistry.is_supported(ext) if ext else False