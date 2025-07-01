class PluginRegistry:
    """
    Registro de plugins de lectores de archivos con funcionalidad mejorada.
    """
    _registry = {}

    @classmethod
    def register(cls, extension):
        """
        Decorador para registrar una clase reader para una extensión específica.
        
        Args:
            extension: Extensión de archivo (sin punto)
            
        Returns:
            Función decoradora
        """
        def wrapper(reader_cls):
            cls._registry[extension.lower()] = reader_cls
            return reader_cls
        return wrapper

    @classmethod
    def get_reader(cls, extension):
        """
        Obtiene la clase reader para una extensión específica.
        
        Args:
            extension: Extensión de archivo (sin punto)
            
        Returns:
            Clase reader o None si no se encuentra
        """
        return cls._registry.get(extension.lower())

    @classmethod
    def get_supported_extensions(cls):
        """
        Obtiene lista de todas las extensiones soportadas.
        
        Returns:
            Lista de extensiones soportadas
        """
        return list(cls._registry.keys())

    @classmethod
    def is_supported(cls, extension):
        """
        Verifica si una extensión de archivo está soportada.
        
        Args:
            extension: Extensión de archivo (sin punto)
            
        Returns:
            True si la extensión está soportada, False en caso contrario
        """
        return extension.lower() in cls._registry

    @classmethod
    def get_registry_info(cls):
        """
        Obtiene información sobre todos los readers registrados.
        
        Returns:
            Diccionario con mapeo extensión -> nombre de clase reader
        """
        return {ext: reader_cls.__name__ for ext, reader_cls in cls._registry.items()}

    @classmethod
    def clear_registry(cls):
        """
        Limpia todos los readers registrados (principalmente para testing).
        """
        cls._registry.clear()