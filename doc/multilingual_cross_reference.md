# ChatyBot Multilingual Cross-Reference Specification

This document defines the canonical translation mappings, command aliases, and tool descriptions for ChatyBot across five core languages: **English**, **Spanish**, **French**, **Chinese**, and **Italian**. 

It reflects modern, natural developer discourse as used in tech blogs, AI repositories, and localized documentation in each country.

---

## 1. Core AI & Prompting Terminology

The table below maps the foundational concepts of the agentic ecosystem into local technical usage:

| Concept (EN) | Spanish (ES) | French (FR) | Chinese (ZH) | Italian (IT) |
| :--- | :--- | :--- | :--- | :--- |
| **Large Language Model (LLM)** | *Modelo de Lenguaje Grande*<br>*(or simply "LLM")* | *Grand modèle de langage*<br>*(or "LLM" / "GML")* | 大语言模型 / 大模型<br>*(Dà yǔyán móxíng / Dà móxíng)* | *Grande modello linguistico*<br>*(or "LLM")* |
| **System Prompt** | *Prompt del sistema*<br>*(or "Instrucción de sistema")* | *Prompt système*<br>*(or "Invite système")* | 系统提示词<br>*(Xìtǒng tíshì cí)* | *Prompt di sistema*<br>*(or "Istruzioni di sistema")* |
| **Tool Prompt** | *Prompt de herramienta*<br>*(or "Llamada a herramientas")* | *Prompt d'outil*<br>*(or "Appel d'outil")* | 工具提示词<br>*(Gōngjù tíshì cí)* | *Prompt dello strumento* |
| **Function Calling** | *Llamada a funciones* | *Appel de fonction* | 函数调用 / 工具调用<br>*(Hánshù / Gōngjù diàoyòng)* | *Chiamata di funzione* |
| **Agentic Loop** | *Bucle agéntico* | *Boucle agentique* | 智能体循环<br>*(Zhìnéngtǐ xúnhuán)* | *Ciclo agentico* |
| **Temperature** | *Temperatura* | *Température* | 温度<br>*(Wēndù)* | *Temperatura* |

---

## 2. Command Verbs Cross-Reference

This table lists all available slash commands in ChatyBot, providing localized command aliases, parameters, and descriptions.

### A. General & System Commands
| Canonical (EN) | Spanish (ES) | French (FR) | Chinese (ZH) | Italian (IT) | Purpose / Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `/help` | `/ayuda` | `/aide` | `/帮助` (or `/help`) | `/aiuto` | Display help interface |
| `/echo` | `/repetir` | `/echo` | `/回显` | `/eco` | Print text with variable evaluation |
| `/source` | `/origen` | `/source` | `/加载脚本` | `/sorgente` | Load and execute a script file |
| `/script` | `/script` | `/script` | `/脚本` | `/script` | Run script with variables (e.g. `x="val"`) |
| `/calc` | `/calcular` | `/calculer` | `/计算` | `/calcola` | Evaluate mathematical expression |
| `/str_search` | `/buscar_cadena` | `/recherche_texte` | `/查找文本` | `/str_search` | Search for substring within text or buffer |
| `/proc` | `/procedimiento` | `/procedure` | `/proc` | `/procedura` | Execute or inspect defined procedure |
| `/session` | `/sesion` | `/session` | `/会话` | `/sessione` | Manage conversational sessions (save, list, prune) |
| `/quit` / `/exit` | `/salir` | `/quitter` | `/退出` (or `/exit`) | `/esci` | Close session and save history |

### B. LLM Parameters & Model Selection
| Canonical (EN) | Spanish (ES) | French (FR) | Chinese (ZH) | Italian (IT) | Purpose / Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `/model` | `/modelo` | `/modele` | `/模型` | `/modello` | Set active model alias |
| `/listmodels` | `/listar_modelos` | `/lister_modeles` | `/列出模型` | `/elenco_modelli` | List configured chat models |
| `/env` | `/variables_entorno` | `/variables_env` | `/环境变量` | `/variabili_ambiente` | Display defined API keys & env vars |
| `/system` | `/sistema` | `/systeme` | `/系统提示` | `/sistema` | Set the core system message |
| `/temp` | `/temp` | `/temp` | `/温度` | `/temp` | Set generation temperature (0.0 - 2.0) |
| `/maxtokens` | `/max_tokens` | `/max_jetons` | `/最大Token` | `/max_token` | Set completion token length |
| `/context_limit` | `/limite_contexto` | `/limite_contexte` | `/上下文限制` | `/limite_contesto` | Set hard token context limit (`<tokens>\|off`) |
| `/auto_truncate` | `/auto_truncar` | `/auto_tronquer` | `/自动截断` | `/auto_tronca` | Auto-truncate context (`on\|off\|10-100%`) |
| `/top_p` | `/top_p` | `/top_p` | `/top_p` | `/top_p` | Nucleus sampling probability |
| `/top_k` | `/top_k` | `/top_k` | `/top_k` | `/top_k` | Top-K sampling token count |
| `/freq_penalty` | `/penalidad_frec` | `/penalite_freq` | `/频率惩罚` | `/penalita_freq` | Apply frequency repetition penalty |
| `/pres_penalty` | `/penalidad_pres` | `/penalite_pres` | `/存在惩罚` | `/penalita_pres` | Apply presence repetition penalty |

### C. Reasoning & Thinking Controls
| Canonical (EN) | Spanish (ES) | French (FR) | Chinese (ZH) | Italian (IT) | Purpose / Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `/reasoning` | `/razonamiento` | `/raisonnement` | `/推理模式` | `/ragionamento` | Toggle reasoning mode (on/off) |
| `/effort` | `/esfuerzo` | `/effort` | `/推理强度` | `/sforzo` | Reasoning level (low, medium, high, none) |
| `/thinking` | `/pensamiento` | `/reflexion` | `/显示思考` | `/pensiero` | Toggle thinking block visibility |
| `/thoughtstyle` | `/estilo_pens` | `/style_reflexion` | `/思考样式` | `/stile_pensiero` | Format (gemma4, nanbeige, etc.) |

### D. File Buffers & Banks
| Canonical (EN) | Spanish (ES) | French (FR) | Chinese (ZH) | Italian (IT) | Purpose / Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `/file` | `/archivo` | `/fichier` | `/文件` | `/file` | Load text file into the active buffer |
| `/clearfile` | `/limpiar_archivo`| `/vider_fichier` | `/清空文件` | `/svuota_file` | Clear the active file buffer |
| `/showfile` | `/mostrar_archivo`| `/afficher_fichier`| `/显示文件` | `/mostra_file` | View active buffer contents |
| `/filebank[1-5]` | `/banco_arch[1-5]`| `/banque_fich[1-5]`| `/文件库[1-5]` | `/archivio_file[1-5]`| Load, clear, or view file bank |
| `/imagebank[1-5]`| `/banco_imag[1-5]`| `/banque_imag[1-5]`| `/图片库[1-5]` | `/archivio_imm[1-5]` | Load, clear, or view image bank |
| `/loadimage` | `/cargar_imagen` | `/charger_image` | `/加载图片` | `/carica_immagine`| Load image into bank with base64 MIME |
| `/notemode` | `/modo_nota` | `/mode_note` | `/笔记模式` | `/modalita_note` | Extract code blocks when using `/save` |
| `/codeonly` | `/solo_codigo` | `/code_uniquement`| `/仅代码` | `/solo_codice` | Enable output-only code formatting |
| `/codeoff` | `/codigo_desact` | `/code_desactive` | `/关闭仅代码` | `/codice_off` | Disable code-only formatting |
| `/multiline` | `/multilinea` | `/multiligne` | `/多行输入` | `/multilinea` | Toggle block input mode ending with `;;` |
| `/save` | `/guardar` | `/sauvegarder` | `/保存` | `/salva` | Save response (all, nothink, withthink) |

### E. Image Generation Controls
| Canonical (EN) | Spanish (ES) | French (FR) | Chinese (ZH) | Italian (IT) | Purpose / Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `/imagine` | `/imaginar` | `/imaginer` | `/生图` | `/immagina` | Generate image from prompt |
| `/imagesize` | `/tamano_imagen` | `/taille_image` | `/图片尺寸` | `/dimensione_imm` | Set resolution (e.g. 1024x1024) |
| `/imagequality`| `/calidad_imagen` | `/qualite_image` | `/图片质量` | `/qualita_imm` | Set image quality (standard/hd) |
| `/imagedir` | `/dir_imagen` | `/dossier_images` | `/图片目录` | `/cartella_imm` | Set output folder for images |
| `/listimages` | `/listar_imagenes`| `/lister_images` | `/列出图片` | `/elenco_imm` | List generated images by date |
| `/showimage` | `/mostrar_imagen` | `/afficher_image`| `/显示图片信息`| `/mostra_imm` | View detailed image parameters |

### F. Shell Commands
| Canonical (EN) | Spanish (ES) | French (FR) | Chinese (ZH) | Italian (IT) | Purpose / Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `/run` | `/ejecutar` | `/lancer` | `/运行` | `/esegui` | Execute shell command with parameters |
| `/run_safe` | `/ejecutar_seguro`| `/lancer_securise`| `/安全运行` | `/esegui_sicuro` | Enable safety confirmation prompts |
| `/run_unsafe` | `/ejecutar_libre` | `/lancer_libre` | `/危险运行` | `/esegui_insicuro` | Disable shell execution confirmations |

### G. Autonomous Tool Loop
| Canonical (EN) | Spanish (ES) | French (FR) | Chinese (ZH) | Italian (IT) | Purpose / Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `/tool` | `/herramienta` | `/outil` | `/工具` | `/strumento` | Run tool calling loop from last completion |
| `/tool list` | `/herramienta listar`| `/outil lister` | `/工具列表` | `/strumento elenco` | Display available tools and active state |
| `/tool enable` | `/herramienta habilitar`| `/outil activer`| `/启用工具` | `/strumento abilita` | Enable specific tool or `all` |
| `/tool disable`| `/herramienta deshab`| `/outil desactiver`| `/禁用工具`| `/strumento disabilita`| Disable specific tool or `all` |
| `/tool on` | `/herramienta activar`| `/outil on` | `/开启工具模式` | `/strumento on` | Load tool definitions into prompt |
| `/tool off` | `/herramienta desc`| `/outil off` | `/关闭工具模式` | `/strumento off` | Disable tool schemas in system prompt |
| `/tool auto` | `/herramienta auto` | `/outil auto` | `/自动工具` | `/strumento auto` | Enable automated loop on tool outputs |
| `/tool loop` | `/herramienta bucle`| `/outil boucle` | `/工具循环` | `/strumento ciclo` | Run loop with limit (e.g. `max=50` `force`)|
| `/tool max_turns`| `/herramienta max_turnos`| `/outil tours_max`| `/最大工具轮次`| `/strumento max_turni`| Set/Get default maximum turn safety cap |
| `/tool rate_limit`| `/herramienta limite_tasa`| `/outil limite_taux`| `/工具 速率限制`| `/strumento limite_frequenza`| Set pause delay (seconds) between turns |
| `/tool prompt` | `/herramienta prompt`| `/outil prompt` | `/工具提示语` | `/strumento prompt` | View active prompt; use `live_edit` for TUI |
| `/tool scratch`| `/herramienta borrador`| `/outil brouillon`| `/工具 草稿` | `/strumento bozza` | Toggle/manage dedicated temporary scratchpad area |

### H. Diagnostics & Logging
| Canonical (EN) | Spanish (ES) | French (FR) | Chinese (ZH) | Italian (IT) | Purpose / Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `/trace` | `/rastreo` | `/trace` | `/追踪` | `/traccia` | Toggle trace outputs (tps, rerank, etc.) |
| `/debug` | `/depurar` | `/deboguer` | `/调试` | `/debug` | Set debug payload, response raw, or vmem |
| `/logging` | `/registro_log` | `/journalisation`| `/记录日志` | `/registro_log` | Enable/disable file logging |

### I. Database & Vector RAG
| Canonical (EN) | Spanish (ES) | French (FR) | Chinese (ZH) | Italian (IT) | Purpose / Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `/setdb` | `/estab_db` | `/definir_bd` | `/设置数据库` | `/imposta_db` | Connect to/initialize vector storage |
| `/dblist` | `/listar_db` | `/lister_bd` | `/数据库列表` | `/elenco_db` | List vector databases available |
| `/searchdb` | `/buscar_db` | `/rechercher_bd` | `/搜索数据库` | `/cerca_db` | Execute vector query |
| `/dblog` | `/log_db` | `/journal_bd` | `/数据库日志` | `/log_db` | View recent database transactions |
| `/dbprint` | `/imprimir_db` | `/imprimer_bd` | `/打印数据库` | `/stampa_db` | Dump vector storage content |
| `/documents` | `/documentos` | `/documents` | `/文档源` | `/documenti` | Set source (db, var, filebank, dir) |
| `/rerank` | `/reordenar` | `/reclasser` | `/重排` | `/riordina` | Execute Jina RAG rerank query on source |

---

## 3. Registered Tools Mappings

This section translates the JSON schema parameter keys, names, and descriptions for ChatyBot's core tool suite.

### A. `list_directory`
Lists files in directory.
* **Spanish:** `listar_directorio` (Parámetro: `path` -> `ruta` / "Ruta del directorio a listar")
* **French:** `lister_dossier` (Paramètre: `path` -> `chemin` / "Chemin du dossier à lister")
* **Chinese:** `list_directory` / `列出目录` (参数: `path` -> `路径` / "要列出的目录路径")
* **Italian:** `elenco_cartella` (Parametro: `path` -> `percorso` / "Percorso della cartella da elencare")

### B. `read_file`
Reads contents of a file (with optional line range window).
* **Spanish:** `leer_archivo` (Parámetros: `path` -> `ruta`, `start_line` -> `linea_inicio` / "Primera línea a leer", `end_line` -> `linea_fin` / "Última línea a leer")
* **French:** `lire_fichier` (Paramètres: `path` -> `chemin`, `start_line` -> `ligne_debut`, `end_line` -> `ligne_fin`)
* **Chinese:** `read_file` / `读取文件` (参数: `path` -> `路径`, `start_line` -> `起始行`, `end_line` -> `结束行`)
* **Italian:** `leggi_file` (Parametri: `path` -> `percorso`, `start_line` -> `riga_inizio`, `end_line` -> `riga_fine`)

### C. `find_files`
Finds files matching pattern, optionally checking inside them.
* **Spanish:** `buscar_archivos` (Parámetros: `path` -> `ruta`, `pattern` -> `patron` / "Patrón de búsqueda", `search_term` -> `termino_busqueda` / "Subcadena de texto")
* **French:** `rechercher_fichiers` (Paramètres: `path` -> `chemin`, `pattern` -> `motif`, `search_term` -> `terme_recherche`)
* **Chinese:** `find_files` / `查找文件` (参数: `path` -> `路径`, `pattern` -> `模式`, `search_term` -> `搜索词`)
* **Italian:** `trova_file` (Parametri: `path` -> `percorso`, `pattern` -> `pattern`, `search_term` -> `termine_ricerca`)

### D. `run_command`
Executes shell commands.
* **Spanish:** `ejecutar_comando` (Parámetro: `command` -> `comando` / "El comando de consola a ejecutar")
* **French:** `lancer_commande` (Paramètre: `command` -> `commande` / "La commande shell à exécuter")
* **Chinese:** `run_command` / `执行命令` (参数: `command` -> `命令` / "要执行的 Shell 命令")
* **Italian:** `esegui_comando` (Parametro: `command` -> `comando` / "Il comando di console da eseguire")

### E. `write_file`
Creates or appends text to a file.
* **Spanish:** `escribir_archivo` (Parámetros: `path` -> `ruta`, `content` -> `contenido`, `mode` -> `modo` / "escribir o anexar")
* **French:** `ecrire_fichier` (Paramètres: `path` -> `chemin`, `content` -> `contenu`, `mode` -> `mode`)
* **Chinese:** `write_file` / `写文件` (参数: `path` -> `路径`, `content` -> `内容`, `mode` -> `模式` / "写入或追加")
* **Italian:** `scrivi_file` (Parametri: `path` -> `percorso`, `content` -> `contenuto`, `mode` -> `modalita`)

### F. `replace_file_content`
Replaces targeted text in a file.
* **Spanish:** `reemplazar_contenido` (Parámetros: `path` -> `ruta`, `target` -> `objetivo` / "Texto a buscar", `replacement` -> `reemplazo`)
* **French:** `remplacer_contenu` (Paramètres: `path` -> `chemin`, `target` -> `cible`, `replacement` -> `remplacement`)
* **Chinese:** `replace_file_content` / `替换文件内容` (参数: `path` -> `路径`, `target` -> `目标内容`, `replacement` -> `替换内容`)
* **Italian:** `sostituisci_contenuto` (Parametri: `path` -> `percorso`, `target` -> `target`, `replacement` -> `sostituto`)

### G. `get_stock`
Retrieves stock prices.
* **Spanish:** `obtener_accion` (Parámetro: `symbol` -> `simbolo` / "Símbolo de cotización")
* **French:** `obtenir_action` (Paramètre: `symbol` -> `symbole`)
* **Chinese:** `get_stock` / `获取股票` (参数: `symbol` -> `代码` / "股票交易代码")
* **Italian:** `ottieni_azione` (Parametro: `symbol` -> `simbolo`)

### H. `get_context_metrics`
Inspects active context size, turn counts, byte budgets, and active context limits across session and agentic loop.
* **Spanish:** `obtener_metricas_contexto` / `metricas_contexto` (Parámetro: `scope` -> `alcance` / "all, session, agentic_loop, buffers")
* **French:** `obtenir_metriques_contexte` / `metriques_contexte` (Paramètre: `scope` -> `portee`)
* **Chinese:** `get_context_metrics` / `获取上下文指标` (参数: `scope` -> `范围` / "all, session, agentic_loop, buffers")
* **Italian:** `ottieni_metriche_contesto` / `metriche_contesto` (Parametro: `scope` -> `ambito`)

---

## 4. Localized Prompt Framing Templates

### A. System Prompt Headers
These headers initialize the LLM's behavioral rules when starting an agentic loop:

* **English:**
  > "You are an autonomous agent running in a multi-turn tool-calling loop. Execute commands precisely."
* **Spanish:**
  > "Eres un agente autónomo que se ejecuta en un bucle de llamada a herramientas de varios turnos. Ejecuta comandos con precisión."
* **French:**
  > "Vous êtes un agent autonome s'exécutant dans une boucle d'appels d'outils multi-tours. Exécutez les commandes avec précision."
* **Chinese:**
  > "你是一个运行在多轮工具调用循环中的自主智能体。请精准地执行命令。"
* **Italian:**
  > "Sei un agente autonomo che opera in un ciclo di chiamata di funzioni multi-turno. Esegui i comandi con precisione."

### B. Tool Framing Instructions
Guides the model's structural JSON payload generation:

* **English:**
  > "1. You can output one or more tool calls in a single turn if they can be executed in parallel or sequence. Use the JSON format enclosed in \`\`\`json ... \`\`\`.
  > 2. Do NOT output any conversational text, descriptions, planning thoughts, or explanations before or after the tool calls. Your entire response must be ONLY the JSON tool call block(s)."
* **Spanish:**
  > "1. Puedes emitir una o más llamadas a herramientas en un solo turno si pueden ejecutarse en paralelo o en secuencia. Utiliza el formato JSON encerrado en \`\`\`json ... \`\`\`.
  > 2. NO produzcas ningún texto conversacional, descripción, pensamiento de planificación o explicación antes o después de las llamadas a herramientas. Tu respuesta completa debe ser ÚNICAMENTE el bloque o bloques JSON de llamada a herramientas."
* **French:**
  > "1. Vous pouvez générer un ou plusieurs appels d'outils en un seul tour s'ils peuvent être exécutés en parallèle ou en séquence. Utilisez le format JSON entouré de \`\`\`json ... \`\`\`.
  > 2. Ne produisez AUCUN texte conversationnel, description, pensée de planification ou explication avant ou après les appels d'outils. Votre réponse entière doit être UNIQUEMENT le(s) bloc(s) JSON d'appel d'outil."
* **Chinese:**
  > "1. 如果可以并行或按顺序执行，你可以在单轮中输出一个或多个工具调用。请使用包含在 \`\`\`json ... \`\`\` 中的 JSON 格式。
  > 2. 切勿在工具调用前后输出任何对话式文本、描述、计划思考或解释。你的所有回答必须且仅包含 JSON 工具调用数据块。"
* **Italian:**
  > "1. Puoi emettere una o più chiamate di strumenti in un singolo turno se possono essere eseguite in parallelo o in sequenza. Utilizza il formato JSON racchiuso in \`\`\`json ... \`\`\`.
  > 2. NON produrre alcun testo conversazionale, descrizione, pensiero di pianificazione o spiegazione prima o dopo le chiamate di strumenti. La tua intera risposta deve essere ESCLUSIVAMENTE il blocco o i blocchi JSON di chiamata degli strumenti."
