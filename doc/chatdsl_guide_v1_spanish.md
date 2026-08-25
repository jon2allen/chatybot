# Guía Completa de ChatDSL

## Resumen

ChatDSL (Lenguaje de Dominio Específico para Chat) es un potente lenguaje de scripting diseñado para automatizar las interacciones con Modelos de Lenguaje Grande (LLMs). Esta guía proporciona una referencia completa para trabajar con ChatDSL, incluyendo características, tutoriales, guías prácticas y una referencia exhaustiva de palabras clave.

> *Última actualización: 19 de agosto de 2026*
>
> *Versión: 1.0*
>
> *Compatible con Chatybot v0.7.6+*

---

# Características

## Capacidades Principales

### 1. Soporte Multilingüe
ChatDSL soporta 6 idiomas con alias de comandos completos:
- **Inglés (EN)** - Idioma principal
- **Español (ES)** - Traducciones al español de todos los comandos
- **Francés (FR)** - Traducciones al francés de todos los comandos
- **Chino (ZH)** - Traducciones al chino de todos los comandos
- **Italiano (IT)** - Traducciones al italiano de todos los comandos
- **Árabe (AR)** - Traducciones al árabe de todos los comandos

### 2. Características de Scripting
- **Sistema de Variables**: Variables de ámbito de script con sintaxis `${nombre}`
- **Lógica Condicional**: Declaraciones `if` con operadores `==`, `!=` y `not` (usando `then` para ejecutar el comando)
- **Gestión de Búfer**: Búfer principal y 5 bancos de archivos para contexto persistente
- **Entrada Multilínea**: Prompts complejos que abarcan varias líneas
- **Operaciones de Archivo**: Cargar, ver, limpiar y guardar archivos
- **Parámetros de Script**: Parámetros `x`, `y`, `z` para scripts personalizados
- **Macros**: Plantillas de prompts reutilizables con análisis gramatical Parsley PEG
- **Operador de Salto Directo**: El operador `!` para buscar en el historial de comandos

### 3. Integración de LLM
- **Gestión de Modelos**: Cambiar entre más de 20 modelos configurados a través de 8 proveedores
- **Prompts de Sistema**: Establecer reglas de comportamiento principales
- **Control de Temperatura**: `0.0-2.0` para aleatoriedad de respuestas
- **Límites de Tokens**: Controlar la longitud de la generación
- **Control de Muestreo**: `top_p`, `top_k`, `freq_penalty`, `pres_penalty`
- **Controles de Razonamiento**: Modos `reasoning` (razonamiento), `effort` (esfuerzo) y `thinking` (pensamiento)
- **Optimizaciones Específicas del Proveedor**: Adaptaciones para NVIDIA, Mistral, Google, OpenAI

### 4. Características Avanzadas
- **Bucles de Herramientas**: Ejecución autónoma con llamada a herramientas (local + MCP)
- **Generación de Imágenes**: Soporte para OpenAI, Mistral, OpenRouter, Ollama
- **Integración de Base de Datos**: Almacenamiento vectorial TinyDB con reordenación (reranking)
- **Sistema de Perfiles**: Archivos `.chatdsl` como perfiles de sesión persistentes
- **Integración MCP**: Soporte para servidores del Protocolo de Contexto del Modelo (Model Context Protocol)

### 5. Diagnósticos y Monitoreo
- **Salidas de Rastreo**: TPS (tokens por segundo), payload crudo, depuración de imágenes, rerank, rastreo de bucles agénticos
- **Comandos de Depuración**: Ver respuestas crudas y uso de memoria virtual
- **Registro (Logging)**: Registro de archivos y seguimiento de errores
- **Inspección del Búfer**: Comprobar el estado de la memoria y las variables

---

# Estructura del Proyecto

## Diseño del Código Fuente

```
src/chatybot/                    # Paquete principal
├── __init__.py                  # Versión: "0.6.4"
├── main.py                      # Punto de entrada → chatybot_app.run()
├── chatybot_app.py              # Aplicación principal (5,887 líneas)
├── buffer_manager.py            # Bancos de archivos, bancos de imágenes, variables de script
├── chatydb.py                   # Integración de base de datos TinyDB
├── chaty_help.py                # Sistema de ayuda estructurado
├── chatdsl_parse.py             # Analizador sintáctico de gramática ChatDSL
├── config_manager.py            # Carga de configuración TOML
├── config_model.py              # Validación de configuración con Pydantic
├── config_sync.py               # Sincronización de archivos de configuración
├── config_tui.py                # Interfaz de usuario de terminal (TUI) para configuración
├── dispatcher.py                # Pasarela de ejecución de herramientas
├── extract_code.py              # Extracción de bloques de código
├── image_generator.py           # Generación de imágenes multiproveedor
├── image_manager.py             # Utilidades de carga de imágenes
├── localization.py              # Soporte de internacionalización (i18n) / multilingüe
├── logging_manager.py           # Registro de chat
├── macro.chatdsl                # Definiciones de macros predeterminadas
├── mcp_client.py                # Integración del protocolo MCP
├── menu.chatdsl                 # Script DSL del menú
├── pattern.py                   # Emparejador de patrones de comandos
├── profile_editor.py            # Editor de perfiles Curses
├── profile_manager.py           # Operaciones CRUD de perfiles
├── vendors.py                   # Definiciones de preajustes de proveedores
├── chat_config.toml             # Configuraciones de modelos predeterminadas
├── tools_config.toml            # Definiciones de herramientas para modo agéntico
├── translations.json            # Traducciones multilingües
├── profiles/                    # Scripts de perfiles preestablecidos
├── tinydb1/corpus_manager.py    # Envoltorio de TinyDB
└── tools/
    ├── __init__.py
    ├── file_utils.py            # Herramientas de archivos: list, read, write, grep, run, replace
    └── tool_config_tui.py       # TUI de configuración de herramientas
```

## Puntos de Entrada

```bash
chatybot                  # Punto de entrada CLI principal
chatdsl_parse             # Utilidad del analizador sintáctico DSL
chatybot-config           # Editor TUI de configuración
```

---

# Tutoriales

## Tutorial 1: Flujo de Trabajo Básico de Traducción

Este tutorial demuestra cómo traducir un archivo entre idiomas usando ChatDSL.

### Prerrequisitos
- Un archivo de texto de origen (`english.txt`)
- Claves de API configuradas en `~/.config/chatybot/chat_config.toml`

### Guía Paso a Paso

1. **Configurar Parámetros**
   ```dsl
   # Uso: /script translate.chatdsl x=english.txt y=spanish z=output.txt
   if ${x} != "" then establecer source_file = ${x}
   if ${source_file} == "" then establecer source_file = "english.txt"
   
   if ${y} != "" then establecer target_lang = ${y}
   if ${target_lang} == "" then establecer target_lang = "spanish"
   
   if ${z} != "" then establecer output_file = ${z}
   if ${output_file} == "" then establecer output_file = "output.txt"
   ```

2. **Cargar Archivo de Origen**
   ```dsl
   /archivo ${source_file}
   ```

3. **Realizar la Traducción**
   ```dsl
   /repetir "Translating to ${target_lang}..."
   
   /modelo gemini_flash
   Translate ${target_lang}:
   
   /guardar ${output_file}
   ```

4. **Resultados**
   - Archivo creado en `${output_file}`
   - Traducción guardada en el idioma de destino

### Script Completo

```dsl
# translate.chatdsl
# Uso: /script translate.chatdsl x=english.txt y=spanish z=output.txt

# Manejo de parámetros
if ${x} != "" then establecer source_file = ${x}
if ${source_file} == "" then establecer source_file = "english.txt"

if ${y} != "" then establecer target_lang = ${y}
if ${target_lang} == "" then establecer target_lang = "spanish"

if ${z} != "" then establecer output_file = ${z}
if ${output_file} == "" then establecer output_file = "output.txt"

# Cargar origen
/archivo ${source_file}

# Traducir
/repetir "Translating to ${target_lang}..."

/modelo gemini_flash
Translate ${target_lang}:

/guardar ${output_file}

/repetir "Translation saved to ${output_file}"
```

---

## Tutorial 2: Comparación de Archivos Usando ChatDSL

Aprenda cómo comparar dos archivos e identificar diferencias clave.

### Uso
```bash
chatybot
chat --> /script compare_articles.chatdsl x=articulo1.txt y=articulo2.txt z=comparacion.txt
```

### Script Completo

```dsl
# compare_articles.chatdsl
# Uso: /script compare_articles.chatdsl x=articulo1.txt y=articulo2.txt z=comparacion.txt

# Manejo de parámetros
if ${x} != "" then establecer file1 = ${x}
if ${file1} == "" then establecer file1 = "default1.txt"

if ${y} != "" then establecer file2 = ${y}
if ${file2} == "" then establecer file2 = "default2.txt"

if ${z} != "" then establecer output = ${z}
if ${output} == "" then establecer output = "comparison.txt"

# Cargar archivos en los bancos
/banco_arch1 ${file1}
/banco_arch2 ${file2}

/repetir "Comparing ${file1} and ${file2}"

# Generar comparación
/sistema "You are a precise text comparison expert."

/multilinea
Compare these two articles and identify:
1. Structural differences
2. Content differences
3. Style differences

Article A:
{filebank1}

Article B:
{filebank2}

Provide a detailed comparison.
;;
/multilinea

# Guardar resultado
/guardar ${output}

/repetir "Comparison saved to ${output}"
```

### Rendimiento Esperado
El script generará una comparación detallada que cubre:
- **Diferencias estructurales**: Orden de secciones, encabezados, formato
- **Diferencias de contenido**: Hechos, datos, argumentos principales
- **Diferencias de estilo**: Vocabulario, estructura de oraciones, tono

---

## Tutorial 3: Evaluación Multimodelo

Evalúe cómo responden diferentes modelos al mismo prompt.

### Uso
```bash
chatybot
chat --> /script evaluate.chatdsl x=prompt.txt y=output_dir
```

### Script Completo

```dsl
# evaluate.chatdsl
# Uso: /script evaluate.chatdsl x=prompt_file y=output_dir

establecer prompt_file = ${x}
establecer output_dir = ${y}

# Modelo 1 - GPT-4
/repetir "Processing with GPT-4..."
/modelo openai_gpt4
/prompt ${prompt_file}
/guardar ${output_dir}/gpt4_response.txt

# Modelo 2 - Claude
/repetir "Processing with Claude..."
/modelo claude
/prompt ${prompt_file}
/guardar ${output_dir}/claude_response.txt

# Comparar respuestas
/repetir "Comparing models..."

/banco_arch1 ${output_dir}/gpt4_response.txt
/banco_arch2 ${output_dir}/claude_response.txt

/multilinea
Compare these two responses to the same prompt:

Model A (GPT-4):
{filebank1}

Model B (Claude):
{filebank2}

Which is better and why?
;;
/multilinea
/guardar ${output_dir}/comparison.txt

/repetir "Evaluation complete! Results in ${output_dir}"
```

### Archivos de Salida
- `${output_dir}/gpt4_response.txt` - Respuesta de GPT-4
- `${output_dir}/claude_response.txt` - Respuesta de Claude
- `${output_dir}/comparison.txt` - Comparación lado a lado

---

# Guías de Procedimiento (HowTos)

## Cómo: Configurar Chatybot

### Ubicación del Archivo de Configuración
```bash
~/.config/chatybot/chat_config.toml    # Configuración de usuario (sobrescribe la predeterminada)
src/chatybot/chat_config.toml          # Configuración predeterminada (empaquetada)
```

### Formato del Archivo de Configuración (TOML)

```toml
# ============================================================================
# CONFIGURACIÓN DE GENERACIÓN DE IMÁGENES
# ============================================================================

[image_generation]
default_dir = "~/chatybot_images"
default_size = "1024x1024"
default_quality = "standard"

# ============================================================================
# MODELOS DE CHAT
# ============================================================================

[models.mistral_1]
name = "mistral-large-2512"
temperature = 0.7
top_k = 1
base_url = "https://api.mistral.ai/v1"
api_key = "MISTRAL_API_KEY"
image_generation = true
image_endpoint = "/images/generations"
vendor = "mistral"

[models.gemini_flash]
name = "gemini-2.5-flash"
temperature = 0.0
top_k = 1
base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
api_key = "GEMINI_API_KEY"
image_generation = true
vendor = "google"

[models.openai_gpt4]
name = "gpt-4o"
temperature = 0.1
top_k = 1
base_url = "https://api.openai.com/v1"
api_key = "OPENAI_API_KEY"
image_generation = true
vendor = "openai"

[models.ollama_llama3]
name = "llama3.2"
temperature = 0.7
top_k = 1
base_url = "http://localhost:11434/v1"
api_key = "OLLAMA"
```

### Propiedades de Configuración de Modelos

| Propiedad | Tipo | Descripción |
|-----------|------|-------------|
| `name` | string | Identificador del modelo (específico de la API) |
| `temperature` | float | Aleatoriedad de respuesta (0.0-2.0) |
| `top_k` | entero | Recuento de muestreo Top-K |
| `base_url` | string | URL del endpoint de la API |
| `api_key` | string | Nombre de variable de entorno para clave API |
| `image_generation` | booleano | Habilitar capacidad de generación de imágenes |
| `image_endpoint` | string | Ruta del endpoint de generación de imágenes |
| `vendor` | string | Identificador del proveedor |

### Proveedores Soportados

| Proveedor | Descripción |
|-----------|-------------|
| `mistral` | API de Mistral AI |
| `google` | Google Generative AI |
| `openai` | API de OpenAI |
| `openrouter` | API agregada de OpenRouter |
| `nvidia` | API de NVIDIA NIM |
| `publicai` | API de PublicAI |
| `bytez` | API de Bytez |
| `ollama` | Servidor Ollama local |

### Configuración de Herramientas

Ubicación: `src/chatybot/tools_config.toml`

```toml
[config]
tool_timeout = 60
rate_limit_delay = 2.0
max_turns = 25
strip_thinking_from_filebanks = true
shell = true
default_profile = ""
profile_dir = "~/.config/chatybot/profiles"
enable_profile_edit = true

agentic_instructions = """
IMPORTANT: You are executing in an autonomous, multi-turn tool-calling loop.
Use tools ONLY when necessary to perform actions on the system or fetch external information.
1. You can output one or more tool calls in a single turn if they can be executed in parallel or sequence. Use the JSON format enclosed in ```json ... ```.
2. Do NOT output any conversational text, descriptions, planning thoughts, or explanations before or after the tool calls.
3. Only output natural language when you have finished all tool executions and are ready to present the final result.
"""

[tools.list_directory]
enabled = true
description = "List contents of a directory"
module = "chatybot.tools.file_utils"
function = "list_directory"

[tools.read_file]
enabled = true
description = "Read the contents of a file"
module = "chatybot.tools.file_utils"
function = "read_file"
```

---

## Cómo: Procesar Archivos en Lote

Dado que ChatDSL no tiene bucles, procese los archivos repitiendo la lógica manualmente:

### Plantilla de Script

```dsl
# batch.chatdsl
# Uso: /script batch.chatdsl x=input_dir y=output_dir

establecer input_dir = ${x}
establecer output_dir = ${y}

# Archivo a
establecer file = "a.txt"
/archivo ${input_dir}/${file}
Analyze ${file}
/guardar ${output_dir}/${file}_processed.txt

# Archivo b
establecer file = "b.txt"
/archivo ${input_dir}/${file}
Analyze ${file}
/guardar ${output_dir}/${file}_processed.txt

# Archivo c
establecer file = "c.txt"
/archivo ${input_dir}/${file}
Analyze ${file}
/guardar ${output_dir}/${file}_processed.txt
```

---

## Cómo: Configurar el Bucle de Llamada a Herramientas

### Habilitar Modo Herramienta
```dsl
# Habilitar esquemas de herramientas en prompt de sistema
/herramienta on

# Hacer disponibles todas las herramientas
/herramienta habilitar all

# Configurar para ejecución autónoma
/herramienta auto

# Establecer límite de turnos
/herramienta max_turnos 10
```

### Ejecutar Bucle de Herramienta
```dsl
/herramienta bucle 50 force
```

### Comprobar Estado de Herramientas
```dsl
/herramienta listar
/herramienta prompt
```

### Herramientas Disponibles

| Herramienta | Descripción |
|-------------|-------------|
| `list_directory` | Listar contenido de directorio |
| `read_file` | Leer contenido de archivo |
| `find_files` | Buscar archivos por patrón |
| `run_command` | Ejecutar comando shell |
| `write_file` | Escribir o añadir a archivo |
| `change_dir` | Cambiar directorio de trabajo |
| `grep_search` | Buscar en contenido de archivos |
| `replace_file_content` | Buscar y reemplazar en archivo |

### Integración de Herramientas MCP

Las herramientas MCP están integradas bajo el espacio de nombres `mcp__<servidor>__<herramienta>`:
```dsl
# Herramientas MCP autodescubiertas de servidores conectados
/herramienta listar

# Ejecutar herramienta MCP
# (Automático mediante bucle de herramienta - el LLM genera llamadas JSON)
```

---

## Cómo: Flujo de Trabajo de Generación de Imágenes

### Generación Básica de Imagen
```dsl
# Establecer parámetros de imagen
/dir_imagen output/
/tamano_imagen 1024x1024
/calidad_imagen hd

# Generar imagen
/imaginar a beautiful sunset over mountains

# Listar imágenes generadas
/listar_imagenes

# Mostrar detalles de la imagen
/mostrar_imagen
```

### Guardar Imagen Generada
```dsl
# Generar y guardar
/imaginar a cat playing with yarn
/saveimage images/cat_toy.jpg
```

### Cargar Imagen en un Banco
```dsl
# Cargar imagen para usar en prompts
/cargar_imagen images/cat_toy.jpg imagebank1

# Referenciar en prompt
Describe this image: {imagebank1}
```

### Gestión de Banco de Imágenes
```dsl
# Cargar en banco específico
/banco_imag1 path/to/image.jpg

# Mostrar contenido del banco
/banco_imag1 show

# Limpiar banco
/banco_imag1 clear
```

### Proveedores de Imágenes Soportados

| Proveedor | Modelo | Notas |
|-----------|--------|-------|
| OpenAI | gpt-4o | Generación de imágenes nativa |
| Mistral | mistral-large-2512 | A través de API compatible con OpenAI |
| Google | gemini-2.5-flash, gemini-2.5-pro | A través de endpoint compatible con OpenAI |
| OpenRouter | google/gemini-2.5-flash-image | Completados de chat con modalidades |
| OpenRouter | black-forest-labs/flux.2-klein-4b | Modelo de imagen dedicado |
| Ollama | Modelos locales | A través del endpoint `/api/generate` |

---

## Cómo: Integración de Base de Datos

### Conectar y Consultar
```dsl
# Configurar base de datos
/estab_db knowledge_base

# Buscar información
/buscar_db "machine learning algorithms 2024"

# Cargar resultados
/cargar_var ml_results ALL

# Añadir contexto al prompt
/sistema "You are an AI expert with access to 2024 ML research."

Based on: ${ml_results}

What are the key developments in ML in 2024?

# Registrar chat en base de datos
/log_db
```

### Reordenar Resultados de Búsqueda (Rerank)
```dsl
# Realizar búsqueda y luego reordenar
/buscar_db "climate change economics"
/reordenar

# Cargar resultados reordenados
/cargar_var ranked_results TOP5
```

### Fuentes de Documentos para Reordenar

| Fuente | Sintaxis | Descripción |
|--------|----------|-------------|
| Base de datos | `/documentos db=<nombre>` | Base de datos TinyDB |
| Variable | `/documentos var=<nombre>` | Variable de script |
| Banco de Archivos | `/documentos filebank=<1-5>` | Contenido de banco de archivos |
| Directorio | `/documentos dir="<ruta>"` | Directorio de archivos |

### Comandos de Base de Datos

| Comando | Descripción |
|---------|-------------|
| `/estab_db <nombre>` | Crear/seleccionar base de datos |
| `/estab_db Null` | Desactivar base de datos |
| `/listar_db` | Listar todas las bases de datos |
| `/buscar_db <consulta>` | Buscar en base de datos |
| `/log_db` | Registrar último chat en base de datos |
| `/imprimir_db [archivo]` | Volcar contenidos de la base de datos |
| `/cargar_var <var> [ALL\|id\|rango]` | Cargar registros de BD en variable |
| `/guardar_var <var> <archivo>` | Guardar variable en archivo |
| `/estab_var <nombre> <valor>` | Establecer variable directamente |

---

## Cómo: Gestión de Perfiles

### Comandos de Perfil

```dsl
# Listar perfiles disponibles
/perfil list

# Usar un perfil
/perfil use mi_perfil

# Clonar sesión actual en un perfil nuevo
/perfil clone nuevo_perfil

# Eliminar un perfil
/perfil delete perfil_viejo

# Exportar perfil
/perfil export mi_perfil ruta_exportacion/

# Importar perfil
/perfil import ruta_importacion/

# Mostrar perfil actual
/perfil show

# Editar perfil en editor curses
/perfil edit
```

### Directorio de Perfiles
```bash
~/.config/chatybot/profiles/    # Perfiles de usuario
src/chatybot/profiles/          # Perfiles preestablecidos
```

---

## Cómo: Búsqueda en el Historial

```dsl
# Buscar en historial de comandos
! machine learning

# Buscar comando específico
! /modelo
```

---

# Referencia

# Referencia de Palabras Clave de ChatDSL

## Palabras Clave de Comandos

### Comandos del Sistema y de Interfaz

| Palabra Clave | Categoría | Sintaxis | Descripción |
|---------------|-----------|----------|-------------|
| `/ayuda` | General | `/ayuda [cmd\|palabra_clave]` | Mostrar interfaz de ayuda |
| `/salir` | General | `/salir` | Cerrar sesión y guardar historial |
| `/quit` | General | `/quit` | Cerrar sesión y guardar historial (alias) |
| `/repetir` | General | `/repetir texto` | Imprimir texto con evaluación de variables |
| `/origen` | General | `/origen archivo.dsl` | Cargar y ejecutar un archivo de script |
| `/script` | General | `/script archivo.dsl [x=v y=v z=v]` | Ejecutar script con parámetros |
| `/calcular` | General | `/calcular <expr>` | Evaluar expresión matemática |
| `/buscar_cadena` | General | `/buscar_cadena <texto> [fuente]` | Buscar subcadena en texto o búfer |
| `/procedimiento` | General | `/procedimiento <nombre> [args]` | Ejecutar procedimiento definido |
| `/sesion` | General | `/sesion <subcmd> [args]` | Gestionar sesiones de chat (guardar, listar, purgar, etc.) |
| `/reloadmacros` | General | `/reloadmacros [archivo]` | Recargar definiciones de macros |

### Comandos de Modelos y LLM

| Palabra Clave | Categoría | Sintaxis | Descripción |
|---------------|-----------|----------|-------------|
| `/modelo` | Modelo | `/modelo [alias]` | Cambiar de modelo o mostrar el actual |
| `/listar_modelos` | Modelo | `/listar_modelos` | Listar modelos disponibles |
| `/variables_entorno` | Modelo | `/variables_entorno [filtro]` | Mostrar variables de entorno y claves API (`set \| grep -i api`) |
| `/sistema` | Modelo | `/sistema [mensaje]` | Obtener/establecer mensaje de sistema |
| `/temp` | Modelo | `/temp [valor]` | Temperatura (0.0-2.0) |
| `/max_tokens` | Modelo | `/max_tokens [valor]` | Máximo de tokens de completado |
| `/limite_contexto` | Modelo | `/limite_contexto [tokens\|off]` | Establecer límite de tokens de contexto |
| `/auto_truncar` | Modelo | `/auto_truncar [on\|off\|10-100]` | Auto-truncar contexto sobre % de límite |
| `/top_p` | Modelo | `/top_p [valor]` | Muestreo de núcleo (0.0-1.0) |
| `/top_k` | Modelo | `/top_k [valor]` | Muestreo Top-K |
| `/penalidad_frec` | Modelo | `/penalidad_frec [valor]` | Penalidad de frecuencia (-2.0 a 2.0) |
| `/penalidad_pres` | Modelo | `/penalidad_pres [valor]` | Penalidad de presencia (-2.0 a 2.0) |
| `/seed` | Modelo | `/seed [valor]` | Semilla aleatoria |
| `/stream` | Modelo | `/stream` | Alternar transmisión de respuestas |
| `/razonamiento` | Modelo | `/razonamiento [on\|off]` | Alternar modo de razonamiento |
| `/esfuerzo` | Modelo | `/esfuerzo [low\|medium\|high\|none]` | Establecer esfuerzo de razonamiento |
| `/pensamiento` | Modelo | `/pensamiento [on\|off]` | Alternar visualización de bloques de pensamiento |
| `/estilo_pens` | Modelo | `/estilo_pens [estilo]` | Establecer estilo de formato de pensamiento |

### Comandos de Búfer de Archivos

| Palabra Clave | Categoría | Sintaxis | Descripción |
|---------------|-----------|----------|-------------|
| `/archivo` | Archivo | `/archivo ruta` | Cargar archivo de texto al búfer |
| `/mostrar_archivo` | Archivo | `/mostrar_archivo [all]` | Ver contenidos del búfer |
| `/limpiar_archivo` | Archivo | `/limpiar_archivo` | Limpiar búfer |
| `/banco_arch{1-5}` | Archivo | `/banco_archN ruta\|clear\|show [all]` | Gestionar bancos de archivos |
| `/banco_imag{1-5}` | Archivo | `/banco_imagN ruta\|clear\|show` | Gestionar bancos de imágenes |
| `/cargar_imagen` | Archivo | `/cargar_imagen ruta <imagebank>` | Cargar imagen con base64 al banco |
| `/modo_nota` | Archivo | `/modo_nota [on\|off]` | Extraer bloques de código al guardar |
| `/solo_codigo` | Archivo | `/solo_codigo` | Habilitar formato de salida de solo código |
| `/codigo_desact` | Archivo | `/codigo_desact` | Deshabilitar formato de salida de solo código |
| `/multilinea` | Archivo | `/multilinea` | Alternar modo de entrada multilinea |
| `/guardar` | Archivo | `/guardar archivo [all] [nothink\|withthink]` | Guardar última respuesta del LLM |
| `/prompt` | Archivo | `/prompt archivo` | Cargar y ejecutar archivo de prompt |

### Comandos de Generación de Imágenes

| Palabra Clave | Categoría | Sintaxis | Descripción |
|---------------|-----------|----------|-------------|
| `/imaginar` | Imagen | `/imaginar prompt` | Generar imagen a partir de texto |
| `/tamano_imagen` | Imagen | `/tamano_imagen [WxH]` | Establecer/obtener resolución de imagen |
| `/calidad_imagen` | Imagen | `/calidad_imagen [standard\|hd]` | Establecer/obtener calidad de imagen |
| `/saveimage` | Imagen | `/saveimage [ruta]` | Guardar última imagen generada |
| `/dir_imagen` | Imagen | `/dir_imagen [ruta]` | Establecer/obtener carpeta de salida de imágenes |
| `/listar_imagenes` | Imagen | `/listar_imagenes` | Listar todas las imágenes guardadas |
| `/mostrar_imagen` | Imagen | `/mostrar_imagen [fecha\|nombre]` | Mostrar metadatos de imagen |

### Comandos de Shell

| Palabra Clave | Categoría | Sintaxis | Descripción |
|---------------|-----------|----------|-------------|
| `/ejecutar` | Shell | `/ejecutar comando [argumentos]` | Ejecutar comando shell |
| `/ejecutar_seguro` | Shell | `/ejecutar_seguro` | Habilitar avisos de confirmación de seguridad |
| `/ejecutar_libre` | Shell | `/ejecutar_libre` | Deshabilitar confirmaciones de comandos shell |

### Comandos del Bucle de Herramientas

| Palabra Clave | Categoría | Sintaxis | Descripción |
|---------------|-----------|----------|-------------|
| `/herramienta` | Herramientas | `/herramienta [subcmd] [args]` | Gestión de modo herramienta |
| `/herramienta on` | Herramientas | `/herramienta on` | Cargar definiciones de herramientas en prompt |
| `/herramienta off` | Herramientas | `/herramienta off` | Deshabilitar esquemas de herramientas |
| `/herramienta listar` | Herramientas | `/herramienta listar` | Listar herramientas disponibles y su estado |
| `/herramienta habilitar` | Herramientas | `/herramienta habilitar <tool\|all>` | Habilitar herramienta específica o todas |
| `/herramienta deshab` | Herramientas | `/herramienta deshab <tool\|all>` | Deshabilitar herramienta específica o todas |
| `/herramienta auto` | Herramientas | `/herramienta auto` | Alternar bucle automático sobre salidas de herramientas |
| `/herramienta bucle` | Herramientas | `/herramienta bucle [turnos] [force]` | Ejecutar bucle con límite de turnos |
| `/herramienta max_turnos` | Herramientas | `/herramienta max_turnos [N]` | Obtener/establecer límite máximo de seguridad de turnos |
| `/herramienta limite_tasa` | Herramientas | `/herramienta limite_tasa [segundos]` | Establecer pausa de retraso entre turnos (segundos) |
| `/herramienta prompt` | Herramientas | `/herramienta prompt` | Ver prompt activo |

### Comandos de Diagnóstico

| Palabra Clave | Categoría | Sintaxis | Descripción |
|---------------|-----------|----------|-------------|
| `/rastreo` | Depuración | `/rastreo <subcmd> [on\|off]` | Alternar modos de rastreo |
| `/rastreo rawpayload` | Depuración | `/rastreo rawpayload [on\|off]` | Rastreo de payload de API crudo |
| `/rastreo tps` | Depuración | `/rastreo tps [on\|off]` | Rastreo de tokens por segundo |
| `/rastreo tpsperf` | Depuración | `/rastreo tpsperf [on\|off]` | Rastreo de rendimiento de TPS |
| `/rastreo imagedbg` | Depuración | `/rastreo imagedbg [on\|off]` | Depuración de generación de imágenes |
| `/rastreo rerank` | Depuración | `/rastreo rerank [on\|off]` | Rastreo de operación de rerank |
| `/rastreo agentic_loop` | Depuración | `/rastreo agentic_loop [on\|off]` | Rastreo de bucle agéntico |
| `/depurar` | Depuración | `/depurar <payload\|response\|vmem>` | Ajustes de modo de depuración |
| `/registro_log` | Depuración | `/registro_log [start\|end]` | Iniciar/detener registro de archivo |
| `/memoria` | Depuración | `/memoria [detail\|debug]` | Mostrar uso de memoria (alias de `/mem`) |
| `/dump` | Depuración | `/dump [nombrevar\|all]` | Volcar contenidos de variables |

### Comandos de Base de Datos

| Palabra Clave | Categoría | Sintaxis | Descripción |
|---------------|-----------|----------|-------------|
| `/estab_db` | Base de datos | `/estab_db <nombre\|Null>` | Conectar/inicializar/desactivar BD |
| `/listar_db` | Base de datos | `/listar_db` | Listar bases de datos vectoriales disponibles |
| `/buscar_db` | Base de datos | `/buscar_db <consulta>` | Ejecutar consulta vectorial |
| `/log_db` | Base de datos | `/log_db` | Registrar último chat en base de datos |
| `/imprimir_db` | Base de datos | `/imprimir_db [archivo]` | Volcar contenidos de la base de datos |
| `/documentos` | Base de datos | `/documentos <src>=<id>` | Establecer origen de documentos para rerank |
| `/reordenar` | Base de datos | `/reordenar "<consulta>" [opciones]` | Ejecutar reordenación semántica |

### Comandos de Variables

| Palabra Clave | Categoría | Sintaxis | Descripción |
|---------------|-----------|----------|-------------|
| `/estab_var` | Variable | `/estab_var <nombre> <valor>` | Establecer una variable de script |
| `/cargar_var` | Variable | `/cargar_var <nombre> [ALL\|id\|rango]` | Cargar registros de BD en variable |
| `/guardar_var` | Variable | `/guardar_var <nombre> <nombre_archivo>` | Guardar variable en archivo |

### Comandos de Perfil

| Palabra Clave | Categoría | Sintaxis | Descripción |
|---------------|-----------|----------|-------------|
| `/perfil` | Perfil | `/perfil <subcmd> [args]` | Gestión de perfiles |
| `/perfil list` | Perfil | `/perfil list` | Listar perfiles disponibles |
| `/perfil use` | Perfil | `/perfil use <nombre>` | Cargar un perfil |
| `/perfil clone` | Perfil | `/perfil clone <nombre>` | Clonar sesión actual |
| `/perfil delete` | Perfil | `/perfil delete <nombre>` | Eliminar un perfil |
| `/perfil export` | Perfil | `/perfil export <nombre> <ruta>` | Exportar perfil |
| `/perfil import` | Perfil | `/perfil import <ruta>` | Importar perfil |
| `/perfil show` | Perfil | `/perfil show` | Mostrar perfil actual |
| `/perfil edit` | Perfil | `/perfil edit` | Editar perfil en TUI |

### Comandos de Historial

| Palabra Clave | Categoría | Sintaxis | Descripción |
|---------------|-----------|----------|-------------|
| `!` | Historial | `! <búsqueda>` | Buscar en el historial de comandos |

## Palabras Clave de Scripting

| Inglés | Español | Sintaxis | Descripción |
|--------|---------|----------|-------------|
| `set` | `establecer` | `establecer nombre = valor` | Asignación de variable |
| `local` | `local` | `local nombre = valor` | Variable de ámbito de procedimiento |
| `if` | `si` | `si condición entonces comando` | Ejecución condicional |
| `then` | `entonces` | (parte de si) | Cuerpo condicional |
| `wait` | `wait` | `wait N` | Pausar N segundos |
| `defproc` | `defproc` | `defproc nombre(params)` | Definir procedimiento |
| `endproc` | `endproc` | `endproc` | Finalizar procedimiento |
| `foreach` | `paracada` | `paracada elem in array` | Bucle multilínea |
| `endfor` | `finpara` | `finpara` | Finalizar bucle |
| `break` | `romper` | `romper` | Salir del bucle |
| `range` | `rango` | `rango(1:10)` | Generador numérico |
| `lines` | `lineas` | `lineas(texto)` | Generador de líneas |
| `#` | `#` | `# comentario` | Comentario |
| `def` | `def` | `def nombre(parámetros) = "plantilla"` | Definir macro |
| `%` | `%` | `%nombre(args)` | Invocar macro |

## Sintaxis de Variables

| Sintaxis | Descripción |
|----------|-------------|
| `${nombre}` | Referencia de variable |
| `establecer nombre = "valor"` | Definición de variable |
| `"valor con espacios"` | Valor entre comillas dobles |
| `'valor con espacios'` | Valor entre comillas simples |
| `{filebankN}` | Referencia a banco de archivos en prompts |
| `{imagebankN}` | Referencia a banco de imágenes en prompts |

## Operadores

| Operador | Descripción | Ejemplo |
|----------|-------------|---------|
| `==` | Igual a | `if ${x} == "yes" then` |
| `!=` | No igual a | `if ${x} != "" then` |
| `>` | Mayor que | `si "${EDAD}" > 18 entonces` |
| `<` | Menor que | `si "${VAL}" < 10 entonces` |
| `>=` | Mayor o igual que | `si "${EDAD}" >= 18 entonces` |
| `<=` | Menor o igual que | `si "${VAL}" <= 5 entonces` |
| `not` | Negación | `if not ${debug} then` |

## Flujo de Control

| Comando | Sintaxis | Descripción |
|---------|----------|-------------|
| `if` | `if condición then comando` | Ejecución condicional |
| `wait` | `wait N` | Pausar N segundos |
| `establecer` | `establecer nombre = valor` | Definir variable |
| `#` | `# comentario` | Comentario |

## Sintaxis Multilinea

| Palabra Clave | Sintaxis | Descripción |
|---------------|----------|-------------|
| `/multilinea` | `/multilinea` | Iniciar bloque multilínea |
| `;;` | `;;` | Terminar bloque multilínea |

## Sintaxis de Macros

| Elemento | Sintaxis | Descripción |
|----------|----------|-------------|
| Definición | `def nombre(parámetros) = "plantilla"` | Definir macro |
| Sin parámetros | `def nombre() = "plantilla"` | Definir macro sin parámetros |
| Invocación | `%nombre(args)` | Llamar a una macro |
| Variable de plantilla | `{parámetro}` | Marcador de posición de parámetro |

### Ejemplos de Macros

```dsl
# Macros sin parámetros
def regen() = "Regenerate all source code"
def build() = "Build the project with optimized settings"

# Macros parametrizadas
def expert_prompt(topic) = "Act as an expert in {topic}. Provide detailed, accurate, and insightful information about {topic}."

def language_comparison(lang1, lang2) = "Compare {lang1} and {lang2} programming languages. Discuss their similarities, differences, syntax variations, performance characteristics, and typical use cases."
```

## Mensajes de Error

| Error | Inglés | Español | Francés | Chino | Italiano |
|-------|---------|---------|--------|---------|---------|
| Archivo no encontrado | "Error: File not found" | "Error: Archivo no encontrado" | "Erreur: Fichier introuvable" | "错误: 文件没有找到" | "Errore: File non trovato" |
| Macro no definida | "ERROR: Macro 'X' not defined" | "ERROR: Macro 'X' no definido" | "ERREUR: Macro 'X' non définie" | "错误: 宏 'X' 未定义" | "ERRORE: Macro 'X' non definita" |
| Argumentos incorrectos | "ERROR: Macro 'X' expects N arguments, got M" | "ERROR: Macro 'X' espera N argumentos, obtuvo M" | "ERREUR: Macro 'X' attend N arguments, reçu M" | "错误: 宏 'X' 需要 N 个参数，得到 M 个" | "ERRORE: Macro 'X' aspetta N argomenti, ottenuti M" |

---

# Mejores Prácticas

## Directrices de Escritura de Scripts

### 1. Nombramiento de Variables
- Utilice **snake_case** para nombres descriptivos: `numero_articulo`, `nombre_modelo`
- Letras individuales (`x`, `y`, `z`) solo para parámetros de script
- MAYÚSCULAS para constantes

### 2. Estilo de Comentarios
```dsl
# Comentario de línea completa
establecer var = "valor"  # Comentario en línea

# Encabezados de sección
# ============================================
# SECCIÓN DE TRADUCCIÓN
# ============================================
```

### 3. Estructura del Script
```dsl
# Encabezado con uso
# Script: descripción
# Uso: /script script.chatdsl [parámetros]

# Manejo de parámetros
if ${x} != "" then establecer param1 = ${x}
if ${param1} == "" then establecer param1 = "default"

# Configuración
establecer base_dir = "output"
/modelo gemini_flash

# Lógica principal
/archivo input.txt
process this...
/guardar output.txt

# Limpieza (opcional)
/limpiar_archivo
/repetir "Done"
```

### 4. Patrones Comunes

#### Parámetros Predeterminados
```dsl
if ${x} != "" then establecer var = ${x}
if ${var} == "" then establecer var = "default"
```

#### Selección Condicional de Modelo
```dsl
if ${fast} then /modelo gemini_flash
if not ${fast} then /modelo openai_gpt4
```

## Manejo de Errores

### Problemas Comunes y Soluciones

| Problema | Solución |
|----------|----------|
| Variable no se expande | Compruebe la sintaxis `${nombre}` (sin espacios) |
| Archivo no encontrado | Use `/repetir` para verificar la expansión de la ruta |
| Multilínea no termina | Asegúrese de tener `;;` en su propia línea, luego `/multilinea` |
| Establecer valor con espacios | Use comillas dobles: `establecer var = "valor con espacios"` |
| Barra invertida en valor | No permitida - use barras inclinadas hacia adelante |
| Comando no reconocido | Compruebe si hay errores tipográficos y el prefijo `/` |

## Consejos de Rendimiento

### Límite de Tasa de API (Rate Limiting)
```dsl
# Entre llamadas a modelos
/modelo gemini_flash
prompt 1
/guardar response1.txt
wait 2  # retraso de 2 segundos

/modelo openai_gpt4
prompt 2
/guardar response2.txt
```

### Gestión de Búfer
```dsl
# Limpiar búfer entre operaciones no relacionadas
/limpiar_archivo

# Prevenir contaminación de contexto
/archivo new_context.txt
```

### Reducir el Uso de Tokens
```dsl
# Usar /solo_codigo para la generación de código
/solo_codigo
Write Python code to solve this problem.
/codigo_desact
```

---

# Referencia Rápida

## Categorías de Comandos

### Sistema
- `/ayuda` - Mostrar ayuda
- `/repetir` - Imprimir texto
- `/salir` - Salir de la sesión
- `/script` - Ejecutar script
- `/origen` - Ejecutar archivo de script

### Modelo
- `/modelo [alias]` - Cambiar de modelo
- `/sistema [prompt]` - Establecer mensaje de sistema
- `/temp [valor]` - Establecer temperatura
- `/max_tokens [valor]` - Establecer máx tokens
- `/razonamiento [on|off]` - Alternar razonamiento
- `/esfuerzo [low|medium|high|none]` - Establecer esfuerzo de razonamiento

### Archivo
- `/archivo ruta` - Cargar a búfer
- `/banco_arch1-5` - Gestión de bancos de archivos
- `/guardar archivo [all] [nothink|withthink]` - Guardar respuesta
- `/multilinea` - Prompts complejos
- `/prompt archivo` - Ejecutar archivo de prompt

### Imagen
- `/imaginar prompt` - Generar imagen
- `/tamano_imagen WxH` - Establecer resolución
- `/saveimage [ruta]` - Guardar imagen generada
- `/banco_imag1-5` - Gestión de bancos de imágenes

### Base de Datos
- `/estab_db nombre` - Conectar almacenamiento
- `/buscar_db "query"` - Búsqueda vectorial
- `/log_db` - Registrar respuesta
- `/reordenar` - Reordenación semántica

### Herramienta
- `/herramienta on` - Habilitar herramientas
- `/herramienta bucle [turnos] [force]` - Ejecución autónoma
- `/herramienta listar` - Listar herramientas
- `/herramienta habilitar all` - Habilitar todas las herramientas

### Depuración
- `/rastreo <tipo> [on|off]` - Habilitar rastreo
- `/memoria [detail|debug]` - Uso de memoria
- `/dump [var|all]` - Volcar variables

### Perfil
- `/perfil list` - Listar perfiles
- `/perfil use nombre` - Cargar perfil
- `/perfil clone nombre` - Clonar sesión

## Elementos de Scripting

### Variables
```dsl
establecer nombre = "valor"
${nombre}
```

### Variables Locales (Procedimientos)
```dsl
local nombre = "valor"
```

### Condiciones
```dsl
if ${x} == "yes" then /comando
if not ${debug} then /repetir "quiet"
```

### Bucles Foreach
```dsl
foreach archivo in ${lista_archivos}
    /echo Procesando ${archivo}...
    # Lógica aquí
endfor
```

### Salida de Bucle con Break
```dsl
foreach num in range(1:10)
    if ${num} == "5" then break
    /echo ${num}
endfor
```

### Generadores
```dsl
# Rango de números (inclusivo)
foreach i in range(1:5)
    /echo ${i}
endfor

# Rango con paso
foreach i in range(1:10:2)
    /echo ${i}
endfor

# Líneas de texto
foreach linea in ${texto}
    /echo ${linea}
endfor
```

### Espera
```dsl
wait 2
```

### Multilínea
```dsl
/multilinea
Your prompt here
;;
/multilinea
```

### Macros
```dsl
# Definir
def expert_prompt(topic) = "Act as an expert in {topic}."

# Invocar
%expert_prompt(Python)
```

---

# Recursos

## Archivos de Documentación

- **Guía del Lenguaje ChatDSL** (`chatdsl_language.md`) - Referencia completa del lenguaje con asignaciones de comandos
- **Guía de Habilidades ChatDSL** (`chatdsl_skill.md`) - Patrones de scripting completos
- **Implementación de Macros ChatDSL** (`chatdsl_macro_implementation.md`) - Informe de implementación técnica

## Archivos de Configuración

- `~/.config/chatybot/chat_config.toml` - Configuración de modelos de usuario
- `~/.config/chatybot/profiles/` - Perfiles de usuario
- `src/chatybot/chat_config.toml` - Configuración de modelos predeterminada
- `src/chatybot/tools_config.toml` - Definiciones de herramientas
- `src/chatybot/macro.chatdsl` - Definiciones de macros predeterminadas
- `src/chatybot/translations.json` - Traducciones multilingües

## Archivos del Proyecto

- `chatdsl_bnf.txt` - Especificación de gramática formal
- `script_param_implementation.md` - Detalles de paso de parámetros
- `dsl_test/` - Scripts de prueba que demuestran todas las características

---

# Introducción

## Inicio Rápido

1. **Instalar Chatybot**
   ```bash
   pip install chatybot
   ```

2. **Configurar Claves API**
   ```bash
   # Copiar configuración predeterminada al directorio de usuario
   mkdir -p ~/.config/chatybot
   cp src/chatybot/chat_config.toml ~/.config/chatybot/
   
   # Editar con sus claves API
   chatybot-config
   ```

3. **Ejecutar Chatybot**
   ```bash
   chatybot
   ```

4. **Ejecutar un Script de ChatDSL**
   ```bash
   chat --> /script mi_script.chatdsl x=valor1 y=valor2
   ```

## Comandos Básicos

- `/ayuda` - Ver todos los comandos disponibles
- `/modelo` - Cambiar entre modelos
- `/archivo ruta` - Cargar archivos de contexto
- `/repetir "texto"` - Salida de depuración
- `/guardar ruta` - Guardar respuestas

## Scripts de Ejemplo

Consulte el directorio `dsl_test/` para ver ejemplos de trabajo:
- `translate.chatdsl` - Flujo de trabajo de traducción
- `compare.chatdsl` - Comparación de archivos
- `evaluate.chatdsl` - Evaluación multimodelo
- `batch.chatdsl` - Procesamiento por lotes

---

*(Fin de la Guía Completa de ChatDSL)*

---

## Historial de Versiones

| Versión | Fecha | Cambios |
|---------|-------|---------|
| 1.0 | 2025-07-23 | Versión corregida inicial basada en el código fuente v0.6.4 |

---

## Notas del Autor

Esta guía es la versión corregida basada en una revisión exhaustiva del código fuente de Chatybot v0.6.4. Toda la sintaxis de comandos, formatos de configuración y ejemplos de scripts se han verificado con la implementación real.
