# ChatDSL Language Guide

This guide documents the ChatDSL language for all supported languages, providing detailed mappings back to English for each language.

---

## Table of Contents

1. [Introduction](#introduction)
2. [Language Support](#language-support)
3. [Command Mappings](#command-mappings)
   - [General & System Commands](#general--system-commands)
   - [LLM Parameters & Model Selection](#llm-parameters--model-selection)
   - [Reasoning & Thinking Controls](#reasoning--thinking-controls)
   - [File Buffers & Banks](#file-buffers--banks)
   - [Image Generation Controls](#image-generation-controls)
   - [Shell Commands](#shell-commands)
   - [Autonomous Tool Loop](#autonomous-tool-loop)
   - [Diagnostics & Logging](#diagnostics--logging)
   - [Database & Vector RAG](#database--vector-rag)
4. [Scripting Keywords](#scripting-keywords)
5. [UI Elements & Prompts](#ui-elements--prompts)
6. [Help Catalog Translations](#help-catalog-translations)
7. [Registered Tools Mappings](#registered-tools-mappings)
8. [Localized Prompt Framing Templates](#localized-prompt-framing-templates)

---

## Introduction

**ChatDSL** (Chat Domain-Specific Language) is a powerful scripting language designed for automating interactions with Large Language Models (LLMs). It supports multiple languages, allowing users to write scripts in their preferred language while ensuring compatibility and consistency across different locales.

---

## Language Support

ChatDSL currently supports the following languages:

- **English (EN)**
- **Spanish (ES)**
- **French (FR)**
- **Chinese (ZH)**
- **Italian (IT)**

---

## Command Mappings

### General & System Commands

| English (EN) | Spanish (ES) | French (FR) | Chinese (ZH) | Italian (IT) | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `/help` | `/ayuda` | `/aide` | `/帮助` | `/aiuto` | Display help interface |
| `/echo` | `/repetir` | `/echo` | `/回显` | `/eco` | Print text with variable evaluation |
| `/source` | `/origen` | `/source` | `/加载脚本` | `/sorgente` | Load and execute a script file |
| `/script` | `/script` | `/script` | `/脚本` | `/script` | Run script with variables (e.g. `x="val"`) |
| `/quit` / `/exit` | `/salir` | `/quitter` | `/退出` | `/esci` | Close session and save history |

### LLM Parameters & Model Selection

| English (EN) | Spanish (ES) | French (FR) | Chinese (ZH) | Italian (IT) | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `/model` | `/modelo` | `/modele` | `/模型` | `/modello` | Set active model alias |
| `/listmodels` | `/listar_modelos` | `/lister_modeles` | `/列出模型` | `/elenco_modelli` | List configured chat models |
| `/env` | `/variables_entorno` | `/variables_env` | `/环境变量` | `/variabili_ambiente` | Display defined API keys & env vars |
| `/system` | `/sistema` | `/systeme` | `/系统提示` | `/sistema` | Set the core system message |
| `/temp` | `/temp` | `/temp` | `/温度` | `/temp` | Set generation temperature (0.0 - 2.0) |
| `/maxtokens` | `/max_tokens` | `/max_jetons` | `/最大Token` | `/max_token` | Set completion token length |
| `/top_p` | `/top_p` | `/top_p` | `/top_p` | `/top_p` | Nucleus sampling probability |
| `/top_k` | `/top_k` | `/top_k` | `/top_k` | `/top_k` | Top-K sampling token count |
| `/freq_penalty` | `/penalidad_frec` | `/penalite_freq` | `/频率惩罚` | `/penalita_freq` | Apply frequency repetition penalty |
| `/pres_penalty` | `/penalidad_pres` | `/penalite_pres` | `/存在惩罚` | `/penalita_pres` | Apply presence repetition penalty |

### Reasoning & Thinking Controls

| English (EN) | Spanish (ES) | French (FR) | Chinese (ZH) | Italian (IT) | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `/reasoning` | `/razonamiento` | `/raisonnement` | `/推理模式` | `/ragionamento` | Toggle reasoning mode (on/off) |
| `/effort` | `/esfuerzo` | `/effort` | `/推理强度` | `/sforzo` | Reasoning level (low, medium, high, none) |
| `/thinking` | `/pensamiento` | `/reflexion` | `/显示思考` | `/pensiero` | Toggle thinking block visibility |
| `/thoughtstyle` | `/estilo_pens` | `/style_reflexion` | `/思考样式` | `/stile_pensiero` | Format (gemma4, nanbeige, etc.) |

### File Buffers & Banks

| English (EN) | Spanish (ES) | French (FR) | Chinese (ZH) | Italian (IT) | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `/file` | `/archivo` | `/fichier` | `/文件` | `/file` | Load text file into the active buffer |
| `/clearfile` | `/limpiar_archivo` | `/vider_fichier` | `/清空文件` | `/svuota_file` | Clear the active file buffer |
| `/showfile` | `/mostrar_archivo` | `/afficher_fichier` | `/显示文件` | `/mostra_file` | View active buffer contents |
| `/filebank[1-5]` | `/banco_arch[1-5]` | `/banque_fich[1-5]` | `/文件库[1-5]` | `/archivio_file[1-5]` | Load, clear, or view file bank |
| `/imagebank[1-5]` | `/banco_imag[1-5]` | `/banque_imag[1-5]` | `/图片库[1-5]` | `/archivio_imm[1-5]` | Load, clear, or view image bank |
| `/loadimage` | `/cargar_imagen` | `/charger_image` | `/加载图片` | `/carica_immagine` | Load image into bank with base64 MIME |
| `/notemode` | `/modo_nota` | `/mode_note` | `/笔记模式` | `/modalita_note` | Extract code blocks when using `/save` |
| `/codeonly` | `/solo_codigo` | `/code_uniquement` | `/仅代码` | `/solo_codice` | Enable output-only code formatting |
| `/codeoff` | `/codigo_desact` | `/code_desactive` | `/关闭仅代码` | `/codice_off` | Disable code-only formatting |
| `/multiline` | `/multilinea` | `/multiligne` | `/多行输入` | `/multilinea` | Toggle block input mode ending with `;;` |
| `/save` | `/guardar` | `/sauvegarder` | `/保存` | `/salva` | Save response (all, nothink, withthink) |

### Image Generation Controls

| English (EN) | Spanish (ES) | French (FR) | Chinese (ZH) | Italian (IT) | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `/imagine` | `/imaginar` | `/imaginer` | `/生图` | `/immagina` | Generate image from prompt |
| `/imagesize` | `/tamano_imagen` | `/taille_image` | `/图片尺寸` | `/dimensione_imm` | Set resolution (e.g. 1024x1024) |
| `/imagequality` | `/calidad_imagen` | `/qualite_image` | `/图片质量` | `/qualita_imm` | Set image quality (standard/hd) |
| `/imagedir` | `/dir_imagen` | `/dossier_images` | `/图片目录` | `/cartella_imm` | Set output folder for images |
| `/listimages` | `/listar_imagenes` | `/lister_images` | `/列出图片` | `/elenco_imm` | List generated images by date |
| `/showimage` | `/mostrar_imagen` | `/afficher_image` | `/显示图片信息` | `/mostra_imm` | View detailed image parameters |

### Shell Commands

| English (EN) | Spanish (ES) | French (FR) | Chinese (ZH) | Italian (IT) | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `/run` | `/ejecutar` | `/lancer` | `/运行` | `/esegui` | Execute shell command with parameters |
| `/run_safe` | `/ejecutar_seguro` | `/lancer_securise` | `/安全运行` | `/esegui_sicuro` | Enable safe mode (block dangerous commands) |
| `/run_unsafe` | `/ejecutar_libre` | `/lancer_libre` | `/危险运行` | `/esegui_insicuro` | Disable safe mode (runs directly; `askfirst` enables Y/N prompt) |

### Autonomous Tool Loop

| English (EN) | Spanish (ES) | French (FR) | Chinese (ZH) | Italian (IT) | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `/tool` | `/herramienta` | `/outil` | `/工具` | `/strumento` | Run tool calling loop from last completion |
| `/tool list` | `/herramienta listar` | `/outil lister` | `/工具列表` | `/strumento elenco` | Display available tools and active state |
| `/tool enable` | `/herramienta habilitar` | `/outil activer` | `/启用工具` | `/strumento abilita` | Enable specific tool or `all` |
| `/tool disable` | `/herramienta deshab` | `/outil desactiver` | `/禁用工具` | `/strumento disabilita` | Disable specific tool or `all` |
| `/tool on` | `/herramienta activar` | `/outil on` | `/开启工具模式` | `/strumento on` | Load tool definitions into prompt |
| `/tool off` | `/herramienta desc` | `/outil off` | `/关闭工具模式` | `/strumento off` | Disable tool schemas in system prompt |
| `/tool auto` | `/herramienta auto` | `/outil auto` | `/自动工具` | `/strumento auto` | Enable automated loop on tool outputs |
| `/tool loop` | `/herramienta bucle` | `/outil boucle` | `/工具循环` | `/strumento ciclo` | Run loop with limit (e.g. `max=50` `force`) |
| `/tool max_turns` | `/herramienta max_turnos` | `/outil tours_max` | `/最大工具轮次` | `/strumento max_turni` | Set/Get default maximum turn safety cap |
| `/tool prompt` | `/herramienta prompt` | `/outil prompt` | `/工具提示语` | `/strumento prompt` | View active prompt; use `live_edit` for TUI |
| `/tool scratch` | `/herramienta borrador` | `/outil brouillon` | `/工具 草稿` | `/strumento bozza` | Toggle/manage dedicated temporary scratchpad area |

### Diagnostics & Logging

| English (EN) | Spanish (ES) | French (FR) | Chinese (ZH) | Italian (IT) | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `/trace` | `/rastreo` | `/trace` | `/追踪` | `/traccia` | Toggle trace outputs (tps, rerank, etc.) |
| `/debug` | `/depurar` | `/deboguer` | `/调试` | `/debug` | Set debug payload, response raw, or vmem |
| `/logging` | `/registro_log` | `/journalisation` | `/记录日志` | `/registro_log` | Enable/disable file logging |

### Database & Vector RAG

| English (EN) | Spanish (ES) | French (FR) | Chinese (ZH) | Italian (IT) | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `/setdb` | `/estab_db` | `/definir_bd` | `/设置数据库` | `/imposta_db` | Connect to/initialize vector storage |
| `/dblist` | `/listar_db` | `/lister_bd` | `/数据库列表` | `/elenco_db` | List vector databases available |
| `/searchdb` | `/buscar_db` | `/rechercher_bd` | `/搜索数据库` | `/cerca_db` | Execute vector query |
| `/dblog` | `/log_db` | `/journal_bd` | `/数据库日志` | `/log_db` | View recent database transactions |
| `/dbprint` | `/imprimir_db` | `/imprimer_bd` | `/打印数据库` | `/stampa_db` | Dump vector storage content |
| `/documents` | `/documentos` | `/documents` | `/文档源` | `/documenti` | Set source (db, var, filebank, dir) |
| `/rerank` | `/reordenar` | `/reclasser` | `/重排` | `/riordina` | Execute Jina RAG rerank query on source |
| `/calc` | `/calcular` | `/calculer` | `/计算` | `/calcola` | Evaluate math expression using mathparse |
| `/str_search` | `/buscar_cadena` / `/buscar_texto` | `/recherche_texte` / `/chercher_texte` | `/查找文本` / `/搜索字符串` | `/cerca_testo` / `/cerca_str` | Substring search pattern in script variables |

---

## Scripting Keywords

| English (EN) | Spanish (ES) | French (FR) | Chinese (ZH) | Italian (IT) | Arabic (AR) | Description |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `set` | `establecer` | `definir` | `设置` | `imposta` | `حط` | Variable assignment |
| `local` | `local` | `local` | `局部` | `locale` | `محلي` | Procedure-scoped variable |
| `if` | `si` | `si` | `如果` | `se` | `اذا` / `اذا_كان` | Conditional execution (supports `==`, `!=`, `<`, `>`, `<=`, `>=`) |
| `then` | `entonces` | `alors` | `则` | `allora` | `اذن` | Conditional body execution |
| `wait` | `wait` | `wait` | `等待` | `wait` | `انتظر` | Pause N seconds |
| `defproc` | `defproc` | `defproc` | `定义过程` | `defproc` | `تعريف_إجراء` | Define procedure |
| `endproc` | `endproc` | `endproc` | `结束过程` | `endproc` | `نهاية_إجراء` | End procedure |
| `foreach` | `paracada` | `pourchaque` | `循环` | `perogni` | `لكل` | Begin foreach loop |
| `endfor` | `finpara` | `finpour` | `结束循环` | `finper` | `نهاية_الحلقة` | End foreach loop |
| `break` | `romper` | `casser` | `中断` | `rompere` | `كسر` | Exit foreach loop early |
| `range` | `rango` | `plage` | `范围` | `intervallo` | `مدى` | Generate number sequence |
| `lines` | `lineas` | `lignes` | `行` | `linee` | `أسطر` | Split text into lines |
| `#` | `#` | `#` | `#` | `#` | `#` | Comment |
| `def` | `def` | `def` | `定义` | `def` | `تعريف` | Define macro |
| `%` | `%` | `%` | `%` | `%` | `%` | Invoke macro |

---

## UI Elements & Prompts

| Key | English (EN) | Spanish (ES) | French (FR) | Chinese (ZH) | Italian (IT) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `language_changed` | "Language set to: {lang}" | "Idioma establecido en: {lang}" | "Langue définie sur: {lang}" | "语言已设置为: {lang}" | "Lingua impostata su: {lang}" |
| `tool_enabled` | "Tool enabled: {tool}" | "Herramienta habilitada: {tool}" | "Outil activé: {tool}" | "工具已启用: {tool}" | "Strumento abilitato: {tool}" |
| `error_file_missing` | "Error: File not found" | "Error: Archivo no encontrado" | "Erreur: Fichier introuvable" | "错误: 文件没有找到" | "Errore: File non trovato" |
| `script_error_header` | "Script Error:" | "Error de script:" | "Erreur de script:" | "脚本错误:" | "Errore di script:" |
| `native_lang_display` | "Language: English" | "Idioma: Español" | "Langue: Français" | "语言: 中文" | "Lingua: Italiano" |
| `chat_prompt` | "chat --> " | "charla --> " | "discussion --> " | "聊天 --> " | "chat --> " |
| `active_model_info` | "Active model: {model} (alias: {alias})" | "Modelo activo: {model} (alias: {alias})" | "Modèle actif: {model} (alias: {alias})" | "激活模型: {model} (替代名: {alias})" | "Modello attivo: {model} (alias: {alias})" |
| `goodbye_message` | "Goodbye!" | "¡Adiós!" | "Au revoir!" | "再见!" | "Arrivederci!" |
| `goodbye_short` | "Bye!" | "¡Adiós!" | "Bye!" | "再见!" | "Ciao!" |

---

## Help Catalog Translations

### Headers

| Key | English (EN) | Spanish (ES) | French (FR) | Chinese (ZH) | Italian (IT) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `category` | "Category" | "Categoría" | "Catégorie" | "类别" | "Categoria" |
| `usage` | "Usage" | "Uso" | "Utilisation" | "用法" | "Utilizzo" |
| `parameters` | "Parameters" | "Parámetros" | "Paramètres" | "参数" | "Parametri" |
| `examples` | "Examples" | "Ejemplos" | "Exemples" | "示例" | "Esempi" |
| `aliases` | "Aliases" | "Alias" | "Alias" | "别名" | "Alias" |
| `see_also` | "See Also" | "Ver también" | "Voir aussi" | "参考" | "Vedi anche" |
| `no_commands` | "No commands found" | "No se encontraron comandos" | "Aucune commande trouvée" | "没有找到命令" | "Nessun comando trovato" |

### Category Names

| Key | English (EN) | Spanish (ES) | French (FR) | Chinese (ZH) | Italian (IT) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `file` | "File" | "Archivo" | "Fichier" | "文件" | "File" |
| `system` | "System" | "Sistema" | "Système" | "系统" | "Sistema" |
| `tool` | "Tool" | "Herramienta" | "Outil" | "工具" | "Strumento" |
| `image` | "Image" | "Imagen" | "Image" | "图片" | "Immagine" |
| `database` | "Database" | "Base de datos" | "Base de données" | "数据库" | "Database" |
| `rerank` | "Rerank" | "Reordenar" | "Reclasser" | "重排" | "Riordina" |
| `debug` | "Debug" | "Depurar" | "Déboguer" | "调试" | "Debug" |
| `history` | "History" | "Historial" | "Historique" | "历史" | "Cronologia" |
| `input` | "Input" | "Entrada" | "Entrée" | "输入" | "Input" |
| `model` | "Model" | "Modelo" | "Modèle" | "模型" | "Modello" |
| `output` | "Output" | "Salida" | "Sortie" | "输出" | "Output" |
| `script` | "Script" | "Script" | "Script" | "脚本" | "Script" |
| `scripting` | "Scripting" | "Scripting" | "Scripting" | "脚本化" | "Scripting" |
| `utility` | "Utility" | "Utilidad" | "Utilitaire" | "工具" | "Utility" |
| `variable` | "Variable" | "Variable" | "Variable" | "变量" | "Variabile" |

---

## Registered Tools Mappings

### A. `list_directory`

Lists files in directory.

| Language | Command | Parameter | Description |
| :--- | :--- | :--- | :--- |
| Spanish | `listar_directorio` | `ruta` | "Ruta del directorio a listar" |
| French | `lister_dossier` | `chemin` | "Chemin du dossier à lister" |
| Chinese | `list_directory` / `列出目录` | `路径` | "要列出的目录路径" |
| Italian | `elenco_cartella` | `percorso` | "Percorso della cartella da elencare" |

### B. `read_file`

Reads contents of a file.

| Language | Command | Parameter | Description |
| :--- | :--- | :--- | :--- |
| Spanish | `leer_archivo` | `ruta` | "Ruta del archivo a leer" |
| French | `lire_fichier` | `chemin` | "Chemin du fichier à lire" |
| Chinese | `read_file` / `读取文件` | `路径` | "要读取的文件路径" |
| Italian | `leggi_file` | `percorso` | "Percorso del file da leggere" |

### C. `find_files`

Finds files matching pattern, optionally checking inside them.

| Language | Command | Parameters | Description |
| :--- | :--- | :--- | :--- |
| Spanish | `buscar_archivos` | `ruta`, `patron`, `termino_busqueda` | "Patrón de búsqueda", "Subcadena de texto" |
| French | `rechercher_fichiers` | `chemin`, `motif`, `terme_recherche` | "Chemin du dossier à lister" |
| Chinese | `find_files` / `查找文件` | `路径`, `模式`, `搜索词` | "要列出的目录路径" |
| Italian | `trova_file` | `percorso`, `pattern`, `termine_ricerca` | "Percorso della cartella da elencare" |

### D. `run_command`

Executes shell commands.

| Language | Command | Parameter | Description |
| :--- | :--- | :--- | :--- |
| Spanish | `ejecutar_comando` | `comando` | "El comando de consola a ejecutar" |
| French | `lancer_commande` | `commande` | "La commande shell à exécuter" |
| Chinese | `run_command` / `执行命令` | `命令` | "要执行的 Shell 命令" |
| Italian | `esegui_comando` | `comando` | "Il comando di console da eseguire" |

### E. `write_file`

Creates or appends text to a file.

| Language | Command | Parameters | Description |
| :--- | :--- | :--- | :--- |
| Spanish | `escribir_archivo` | `ruta`, `contenido`, `modo` | "escribir o anexar" |
| French | `ecrire_fichier` | `chemin`, `contenu`, `mode` | "Chemin du dossier à lister" |
| Chinese | `write_file` / `写文件` | `路径`, `内容`, `模式` | "写入或追加" |
| Italian | `scrivi_file` | `percorso`, `contenuto`, `modalita` | "Percorso della cartella da elencare" |

### F. `replace_file_content`

Replaces targeted text in a file.

| Language | Command | Parameters | Description |
| :--- | :--- | :--- | :--- |
| Spanish | `reemplazar_contenido` | `ruta`, `objetivo`, `reemplazo` | "Texto a buscar" |
| French | `remplacer_contenu` | `chemin`, `cible`, `remplacement` | "Chemin du dossier à lister" |
| Chinese | `replace_file_content` / `替换文件内容` | `路径`, `目标内容`, `替换内容` | "要列出的目录路径" |
| Italian | `sostituisci_contenuto` | `percorso`, `target`, `sostituto` | "Percorso della cartella da elencare" |

### G. `get_stock`

Retrieves stock prices.

| Language | Command | Parameter | Description |
| :--- | :--- | :--- | :--- |
| Spanish | `obtener_accion` | `simbolo` | "Símbolo de cotización" |
| French | `obtenir_action` | `symbole` | "Chemin du dossier à lister" |
| Chinese | `get_stock` / `获取股票` | `代码` | "股票交易代码" |
| Italian | `ottieni_azione` | `simbolo` | "Percorso della cartella da elencare" |

---

## Localized Prompt Framing Templates

### A. System Prompt Headers

These headers initialize the LLM's behavioral rules when starting an agentic loop:

| Language | Prompt |
| :--- | :--- |
| English | "You are an autonomous agent running in a multi-turn tool-calling loop. Execute commands precisely." |
| Spanish | "Eres un agente autónomo que se ejecuta en un bucle de llamada a herramientas de varios turnos. Ejecuta comandos con precisión." |
| French | "Vous êtes un agent autonome s'exécutant dans une boucle d'appels d'outils multi-tours. Exécutez les commandes avec précision." |
| Chinese | "你是一个运行在多轮工具调用循环中的自主智能体。请精准地执行命令。" |
| Italian | "Sei un agente autonomo che opera in un ciclo di chiamata di funzioni multi-turno. Esegui i comandi con precisione." |

### B. Tool Framing Instructions

Guides the model's structural JSON payload generation:

| Language | Prompt |
| :--- | :--- |
| English | "1. You can output one or more tool calls in a single turn if they can be executed in parallel or sequence. Use the JSON format enclosed in \`\`\`json ... \`\`\`.\n2. Do NOT output any conversational text, descriptions, planning thoughts, or explanations before or after the tool calls. Your entire response must be ONLY the JSON tool call block(s)." |
| Spanish | "1. Puedes emitir una o más llamadas a herramientas en un solo turno si pueden ejecutarse en paralelo o en secuencia. Utiliza el formato JSON encerrado en \`\`\`json ... \`\`\`.\n2. NO produzcas ningún texto conversacional, descripción, pensamiento de planificación o explicación antes o después de las llamadas a herramientas. Tu respuesta completa debe ser ÚNICAMENTE el bloque o bloques JSON de llamada a herramientas." |
| French | "1. Vous pouvez générer un ou plusieurs appels d'outils en un seul tour s'ils peuvent être exécutés en parallèle ou en séquence. Utilisez le format JSON entouré de \`\`\`json ... \`\`\`.\n2. Ne produisez AUCUN texte conversationnel, description, pensée de planification ou explication avant ou après les appels d'outils. Votre réponse entière doit être UNIQUEMENT le(s) bloc(s) JSON d'appel d'outil." |
| Chinese | "1. 如果可以并行或按顺序执行，你可以在单轮中输出一个或多个工具调用。请使用包含在 \`\`\`json ... \`\`\` 中的 JSON 格式。\n2. 切勿在工具调用前后输出任何对话式文本、描述、计划思考或解释。你的所有回答必须且仅包含 JSON 工具调用数据块。" |
| Italian | "1. Puoi emettere una o più chiamate di strumenti in un singolo turno se possono essere eseguite in parallelo o in sequenza. Utilizza il formato JSON racchiuso in \`\`\`json ... \`\`\`.\n2. NON produrre alcun testo conversazionale, descrizione, pensiero di pianificazione o spiegazione prima o dopo le chiamate di strumenti. La tua intera risposta deve essere ESCLUSIVAMENTE il blocco o i blocchi JSON di chiamata degli strumenti." |

---

## Conclusion

This guide provides a comprehensive overview of the ChatDSL language for all supported languages. Use the mappings provided to write scripts in your preferred language while ensuring compatibility with the ChatDSL engine.