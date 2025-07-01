# File Reader - Motor de Procesamiento de Documentos con IA

🚀 **Procesador universal de documentos con salida optimizada para IA para aplicaciones modernas.**

## ✨ Características

- **📄 Soporte multi-formato**: PDF, DOCX, CSV, JSON, XML, YAML, TXT
- **🧠 Salida optimizada para IA**: Markdown estructurado con metadata y análisis
- **☁️ Integración S3**: Procesamiento directo desde AWS S3
- **⚡ Despliegue dual**: Herramienta CLI + AWS Lambda
- **🔧 Arquitectura de plugins**: Fácilmente extensible para nuevos formatos

## 🚀 Inicio Rápido

### Instalación
```bash
pip install -r requirements.txt
```

### Uso Básico
```bash
# Procesamiento de archivo local
python main.py documento.pdf --format markdown_ai

# Archivo Excel con análisis completo
python main.py reporte.xlsx --format markdown_ai

# Procesamiento de archivo S3
python main.py s3://mi-bucket/reporte.docx --format markdown_ai

# Salida a archivo
python main.py datos.csv -o analisis.md --format markdown_ai
```

## 📋 Formatos Soportados

| Formato | Extensión | Características IA |
|---------|-----------|-------------------|
| PDF | `.pdf` | ✅ Análisis por páginas, extracción de metadata |
| Word | `.docx` | ✅ Detección de estructura, extracción de tablas |
| Excel | `.xlsx`, `.xls`, `.xlsm` | ✅ Análisis multi-hoja, tipos de datos, calidad |
| CSV | `.csv` | ✅ Análisis de dataset, detección de tipos |
| JSON | `.json` | ✅ Análisis de estructura, evaluación de complejidad |
| XML | `.xml` | ✅ Análisis de schema, detección de namespaces |
| YAML | `.yaml`, `.yml` | ✅ Detección de patrones de configuración |
| Texto | `.txt` | ✅ Análisis de estructura, detección de encabezados |

## 🎯 Formatos de Salida

- **`markdown`** - Salida markdown estándar
- **`markdown_ai`** - 🧠 Optimizado para IA con metadata y análisis
- **`plain`** - Salida texto plano
- **`structured_json`** - JSON con metadata extraída

## 🔧 Configuración

### Variables de Entorno
Copia `.env.example` a `.env` y configura:

```bash
# Configuración AWS
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=tu_clave
AWS_SECRET_ACCESS_KEY=tu_secreto

# Configuración de Procesamiento
OUTPUT_FORMAT=markdown_ai
AI_OPTIMIZED=true
```

### Opciones CLI
```bash
python main.py [archivo] [opciones]

Opciones:
  --format {markdown,markdown_ai,plain,structured_json}
  --ai-optimized          Habilitar optimizaciones IA
  --include-metadata      Incluir metadata del archivo
  --extract-sections      Extraer secciones clave del documento
  --output, -o            Ruta del archivo de salida
  --verbose, -v           Logging detallado
  --region                Región AWS para S3
```

## ☁️ Despliegue en AWS Lambda

### Formato de Request
```json
{
  "file_name": "documento.pdf",
  "s3_path": "s3://bucket/ruta/archivo.pdf",
  "output_format": "markdown_ai",
  "ai_optimized": true,
  "region": "us-east-1"
}
```

### Formato de Response
```json
{
  "success": true,
  "output": "# Contenido del documento...",
  "metadata": {
    "processing_time_seconds": 2.45,
    "file_size_bytes": 1024000,
    "output_size_chars": 5420
  }
}
```

## 🏗️ Arquitectura

```
file_reader/
├── core/                   # Motor principal
│   ├── file_reader.py     # Orquestador principal
│   ├── plugin_registry.py # Sistema de plugins
│   ├── config.py          # Configuración
│   └── document_intelligence.py # Procesamiento IA
├── readers/               # Lectores específicos por formato
│   ├── base_reader.py    # Clase base
│   ├── pdf_reader.py     # Procesamiento PDF
│   ├── csv_reader.py     # Análisis CSV
│   └── ...               # Otros formatos
└── utils/                 # Utilidades
    └── s3_file_fetcher.py # Integración S3
```

## 🔌 Extensión

Agregar soporte para nuevo formato:

```python
from file_reader.readers.base_reader import BaseReader
from file_reader.core.plugin_registry import PluginRegistry

@PluginRegistry.register("nuevo_formato")
class NuevoFormatoReader(BaseReader):
    def read(self, file_path: str) -> str:
        # Tu implementación
        return contenido_procesado
```

## 📊 Casos de Uso

- **📈 Pipelines de Análisis de Documentos** - ETL para documentos corporativos
- **🤖 Preprocesamiento de Datos IA/ML** - Convertir documentos para entrenamiento de modelos
- **📚 Gestión de Contenido** - Normalizar documentos para búsqueda/indexación
- **🔄 Migración de Formatos** - Convertir entre formatos de documentos
- **📋 Procesamiento de Cumplimiento** - Extraer datos para requerimientos regulatorios

## 🏆 Listo para Producción

✅ **Manejo de errores** - Validación integral y recuperación de errores  
✅ **Logging** - Logging estructurado con métricas de rendimiento  
✅ **Limpieza de recursos** - Gestión automática de archivos temporales  
✅ **Escalabilidad** - Arquitectura de plugins para fácil extensión  
✅ **Cloud native** - Integración S3 y despliegue Lambda  

## 📞 Soporte

Para problemas y preguntas, por favor revisa la documentación o crea un issue en el repositorio.