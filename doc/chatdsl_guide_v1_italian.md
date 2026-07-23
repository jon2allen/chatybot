# Guida Completa a ChatDSL

## Panoramica

ChatDSL (Chat Domain-Specific Language) è un potente linguaggio di scripting progettato per automatizzare le interazioni con i modelli linguistici di grandi dimensioni (LLM). Questa guida fornisce un riferimento completo per lavorare con ChatDSL, inclusi funzionalità, tutorial, guide pratiche e un riferimento esaustivo delle parole chiave.

> *Ultimo aggiornamento: 23 luglio 2026*
>
> *Versione: 1.0*
>
> *Compatibile con Chatybot v0.6.4+*

---

# Funzionalità

## Capacità Principali

### 1. Supporto Multilingua
ChatDSL supporta 5 lingue con aliasing completo dei comandi:
- **Inglese (EN)** - Lingua principale
- **Spagnolo (ES)** - Traduzione spagnola di tutti i comandi
- **Francese (FR)** - Traduzione francese di tutti i comandi
- **Cinese (ZH)** - Traduzione cinese di tutti i comandi
- **Italiano (IT)** - Traduzione italiana di tutti i comandi

### 2. Funzionalità di Scrittura Script
- **Sistema di Variabili**: Variabili con ambito dello script con sintassi `${nome}`
- **Logica Condizionale**: Istruzioni `if` con operatori `==`, `!=` e `not` (utilizzando `then` per eseguire il comando)
- **Gestione dei Buffer**: Buffer principale e 5 archivi file per un contesto persistente
- **Input Multilinea**: Prompt complessi che si estendono su più righe
- **Operazioni sui File**: Caricare, visualizzare, svuotare e salvare file
- **Parametri dello Script**: Parametri `x`, `y`, `z` per script personalizzati
- **Macro**: Modelli di prompt riutilizzabili con analisi grammaticale Parsley PEG
- **Operatore di Ricerca Storico**: L'operatore `!` per cercare nella cronologia dei comandi

### 3. Integrazione dei LLM
- **Gestione dei Modelli**: Passa tra oltre 20 modelli configurati attraverso 8 provider
- **Prompt di Sistema**: Imposta le regole di comportamento principali
- **Controllo della Temperatura**: `0.0-2.0` per la casualità delle risposte
- **Limiti di Token**: Controlla la lunghezza del completamento
- **Controllo del Campionamento**: `top_p`, `top_k`, `freq_penalty`, `pres_penalty`
- **Controlli del Ragionamento**: Modalità `reasoning` (ragionamento), `effort` (sforzo) e `thinking` (pensiero)
- **Ottimizzazioni Specifiche del Vendor**: Adattamenti NVIDIA, Mistral, Google, OpenAI

### 4. Funzionalità Avanzate
- **Ciclo degli Strumenti**: Esecuzione autonoma con chiamata di strumenti (locale + MCP)
- **Generazione di Immagini**: Supporto per OpenAI, Mistral, OpenRouter, Ollama
- **Integrazione Database**: Archiviazione vettoriale TinyDB con riordinamento (reranking)
- **Sistema di Profili**: File `.chatdsl` come profili di sessione persistenti
- **Integrazione MCP**: Supporto del server Model Context Protocol

### 5. Diagnostica e Monitoraggio
- **Uscite di Traccia**: TPS (token al secondo), payload grezzo, debug delle immagini, rerank, tracciamento del ciclo agentico
- **Comandi di Debug**: Visualizza le risposte grezze e l'uso della memoria virtuale
- **Registro di Log (Logging)**: Registrazione su file e tracciamento degli errori
- **Ispezione del Buffer**: Controlla lo stato della memoria e delle variabili

---

# Struttura del Progetto

## Layout dei File Sorgente

```
src/chatybot/                    # Pacchetto principale
├── __init__.py                  # Versione: "0.6.4"
├── main.py                      # Punto di ingresso → chatybot_app.run()
├── chatybot_app.py              # Applicazione principale (5.887 righe)
├── buffer_manager.py            # Archivi file, archivi immagini, variabili di script
├── chatydb.py                   # Integrazione del database TinyDB
├── chaty_help.py                # Sistema di aiuto strutturato
├── chatdsl_parse.py             # Analizzatore della grammatica ChatDSL
├── config_manager.py            # Caricamento della configurazione TOML
├── config_model.py              # Validazione della configurazione Pydantic
├── config_sync.py               # Sincronizzazione dei file di configurazione
├── config_tui.py                # Interfaccia utente terminale (TUI) per la configurazione
├── dispatcher.py                # Gateway di esecuzione degli strumenti
├── extract_code.py              # Estrazione dei blocchi di codice
├── image_generator.py           # Generazione di immagini multi-vendor
├── image_manager.py             # Utilità di caricamento delle immagini
├── localization.py              # Supporto i18n / multilingua
├── logging_manager.py           # Registro di log della chat
├── macro.chatdsl                # Definizioni delle macro predefinite
├── mcp_client.py                # Integrazione del protocollo MCP
├── menu.chatdsl                 # Script del menu DSL
├── pattern.py                   # Corrispondente del modello di comando
├── profile_editor.py            # Editor di profili Curses
├── profile_manager.py           # Operazioni CRUD sui profili
├── vendors.py                   # Definizioni dei predefiniti dei vendor
├── chat_config.toml             # Configurazioni dei modelli predefiniti
├── tools_config.toml            # Definizioni degli strumenti per la modalità agentica
├── translations.json            # Traduzioni multilingue
├── profiles/                    # Script dei profili preimpostati
├── tinydb1/corpus_manager.py    # Wrapper TinyDB
└── tools/
    ├── __init__.py
    ├── file_utils.py            # Strumenti file: list, read, write, grep, run, replace
    └── tool_config_tui.py       # TUI di configurazione degli strumenti
```

## Punti di Ingresso

```bash
chatybot                  # Punto di ingresso CLI principale
chatdsl_parse             # Utilità dell'analizzatore DSL
chatybot-config           # Editor TUI della configurazione
```

---

# Tutorial

## Tutorial 1: Flusso di Lavoro di Traduzione di Base

Questo tutorial mostra come tradurre un file tra due lingue utilizzando ChatDSL.

### Prerequisiti
- Un file di testo sorgente (`english.txt`)
- Chiavi API configurate in `~/.config/chatybot/chat_config.toml`

### Guida Passo-Passo

1. **Configurare i Parametri**
   ```dsl
   # Uso: /script translate.chatdsl x=english.txt y=spanish z=output.txt
   if ${x} != "" then imposta sorgente = ${x}
   if ${sorgente} == "" then imposta sorgente = "english.txt"
   
   if ${y} != "" then imposta target_lang = ${y}
   if ${target_lang} == "" then imposta target_lang = "spanish"
   
   if ${z} != "" then imposta output_file = ${z}
   if ${output_file} == "" then imposta output_file = "output.txt"
   ```

2. **Caricare il File Sorgente**
   ```dsl
   /file ${sorgente}
   ```

3. **Eseguire la Traduzione**
   ```dsl
   /eco "Translating to ${target_lang}..."
   
   /modello gemini_flash
   Translate ${target_lang}:
   
   /salva ${output_file}
   ```

4. **Risultati**
   - File creato in `${output_file}`
   - Traduzione salvata nella lingua di destinazione

### Script Completo

```dsl
# translate.chatdsl
# Uso: /script translate.chatdsl x=english.txt y=spanish z=output.txt

# Gestione dei parametri
if ${x} != "" then imposta sorgente = ${x}
if ${sorgente} == "" then imposta sorgente = "english.txt"

if ${y} != "" then imposta target_lang = ${y}
if ${target_lang} == "" then imposta target_lang = "spanish"

if ${z} != "" then imposta output_file = ${z}
if ${output_file} == "" then imposta output_file = "output.txt"

# Caricare la sorgente
/file ${sorgente}

# Tradurre
/eco "Translating to ${target_lang}..."

/modello gemini_flash
Translate ${target_lang}:

/salva ${output_file}

/eco "Translation saved to ${output_file}"
```

---

## Tutorial 2: Confronto di File con ChatDSL

Scopri come confrontare due file e identificare le differenze chiave.

### Utilizzo
```bash
chatybot
chat --> /script compare_articles.chatdsl x=articolo1.txt y=articolo2.txt z=confronto.txt
```

### Script Completo

```dsl
# compare_articles.chatdsl
# Uso: /script compare_articles.chatdsl x=articolo1.txt y=articolo2.txt z=confronto.txt

# Gestione dei parametri
if ${x} != "" then imposta file1 = ${x}
if ${file1} == "" then imposta file1 = "default1.txt"

if ${y} != "" then imposta file2 = ${y}
if ${file2} == "" then imposta file2 = "default2.txt"

if ${z} != "" then imposta output = ${z}
if ${output} == "" then imposta output = "confronto.txt"

# Caricare i file negli archivi
/archivio_file1 ${file1}
/archivio_file2 ${file2}

/eco "Comparing ${file1} and ${file2}"

# Generare il confronto
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

# Salvare il risultato
/salva ${output}

/eco "Comparison saved to ${output}"
```

### Risultati Attesi
Lo script genererà un confronto dettagliato che copre:
- **Differenze strutturali**: Ordine delle sezioni, intestazioni, formattazione
- **Differenze di contenuto**: Fatti, dati, argomenti principali
- **Differenze di stile**: Vocabolario, struttura delle frasi, tono

---

## Tutorial 3: Valutazione Multi-Modello

Valuta come diversi modelli rispondono allo stesso prompt.

### Utilizzo
```bash
chatybot
chat --> /script evaluate.chatdsl x=prompt.txt y=output_dir
```

### Script Completo

```dsl
# evaluate.chatdsl
# Uso: /script evaluate.chatdsl x=prompt_file y=output_dir

imposta prompt_file = ${x}
imposta output_dir = ${y}

# Modello 1 - GPT-4
/eco "Processing with GPT-4..."
/modello openai_gpt4
/prompt ${prompt_file}
/salva ${output_dir}/gpt4_response.txt

# Modello 2 - Claude
/eco "Processing with Claude..."
/modello claude
/prompt ${prompt_file}
/salva ${output_dir}/claude_response.txt

# Confrontare le risposte
/eco "Comparing models..."

/archivio_file1 ${output_dir}/gpt4_response.txt
/archivio_file2 ${output_dir}/claude_response.txt

/multilinea
Compare these two responses to the same prompt:

Model A (GPT-4):
{filebank1}

Model B (Claude):
{filebank2}

Which is better and why?
;;
/multilinea
/salva ${output_dir}/comparison.txt

/eco "Evaluation complete! Results in ${output_dir}"
```

### File di Output
- `${output_dir}/gpt4_response.txt` - Risposta di GPT-4
- `${output_dir}/claude_response.txt` - Risposta di Claude
- `${output_dir}/comparison.txt` - Confronto affiancato

---

# Guide Pratiche (HowTos)

## Come: Configurare Chatybot

### Posizione del File di Configurazione
```bash
~/.config/chatybot/chat_config.toml    # Configurazione utente (sovrascrive i valori predefiniti)
src/chatybot/chat_config.toml          # Configurazione predefinita (inclusa)
```

### Formato del File di Configurazione (TOML)

```toml
# ============================================================================
# IMPOSTAZIONI DI GENERAZIONE DELLE IMMAGINI
# ============================================================================

[image_generation]
default_dir = "~/chatybot_images"
default_size = "1024x1024"
default_quality = "standard"

# ============================================================================
# MODELLI DI CHAT
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

### Proprietà di Configurazione dei Modelli

| Proprietà | Tipo | Descrizione |
|-----------|------|-------------|
| `name` | string | Identificatore del modello (specifico dell'API) |
| `temperature` | float | Casualità della risposta (0.0-2.0) |
| `top_k` | intero | Numero di campionamento Top-K |
| `base_url` | string | URL del punto di terminazione dell'API |
| `api_key` | string | Nome della variabile di ambiente per la chiave API |
| `image_generation` | booleano | Abilita la capacità di generazione di immagini |
| `image_endpoint` | string | Percorso del punto di terminazione della generazione |
| `vendor` | string | Identificatore del fornitore |

### Vendor Supportati

| Vendor | Descrizione |
|--------|-------------|
| `mistral` | API di Mistral AI |
| `google` | Google Generative AI |
| `openai` | API di OpenAI |
| `openrouter` | API aggregata di OpenRouter |
| `nvidia` | API di NVIDIA NIM |
| `publicai` | API di PublicAI |
| `bytez` | API di Bytez |
| `ollama` | Server Ollama locale |

### Configurazione degli Strumenti

Posizione: `src/chatybot/tools_config.toml`

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

## Come: Elaborare Fichieri in Lotto

Poiché ChatDSL non dispone di cicli, elabora i file ripetendo manualmente la logica:

### Modello di Script

```dsl
# batch.chatdsl
# Uso: /script batch.chatdsl x=input_dir y=output_dir

imposta input_dir = ${x}
imposta output_dir = ${y}

# File a
imposta file = "a.txt"
/file ${input_dir}/${file}
Analyze ${file}
/salva ${output_dir}/${file}_processed.txt

# File b
imposta file = "b.txt"
/file ${input_dir}/${file}
Analyze ${file}
/salva ${output_dir}/${file}_processed.txt

# File c
imposta file = "c.txt"
/file ${input_dir}/${file}
Analyze ${file}
/salva ${output_dir}/${file}_processed.txt
```

---

## Come: Configurare il Ciclo degli Strumenti

### Abilitare la Modalità Strumento
```dsl
# Abilitare gli schemi degli strumenti nel prompt di sistema
/strumento on

# Rendere disponibili tutti gli strumenti
/strumento abilita all

# Configurare per l'esecuzione autonoma
/strumento auto

# Impostare il limite dei turni
/strumento max_turni 10
```

### Eseguire il Ciclo degli Strumenti
```dsl
/strumento ciclo 50 force
```

### Controllare lo Stato degli Strumenti
```dsl
/strumento elenco
/strumento prompt
```

### Strumenti Disponibili

| Strumento | Descrizione |
|-----------|-------------|
| `list_directory` | Elenca il contenuto della directory |
| `read_file` | Leggi il contenuto del file |
| `find_files` | Trova i file per modello |
| `run_command` | Esegui il comando shell |
| `write_file` | Scrivi o aggiungi al file |
| `change_dir` | Cambia la directory di lavoro |
| `grep_search` | Cerca all'interno dei file |
| `replace_file_content` | Trova e sostituisci nel file |

### Integrazione Strumenti MCP

Gli strumenti MCP sono registrati sotto lo spazio dei nomi `mcp__<server>__<strumento>`:
```dsl
# Strumenti MCP rilevati automaticamente dai server connessi
/strumento elenco

# Eseguire lo strumento MCP
# (Automatico tramite ciclo strumento - il LLM genera chiamate JSON)
```

---

## Come: Flusso di Lavoro per la Generazione di Immagini

### Generazione di Immagini di Base
```dsl
# Impostare i parametri dell'immagine
/cartella_imm output/
/dimensione_imm 1024x1024
/qualita_imm hd

# Generare l'immagine
/immagina a beautiful sunset over mountains

# Elencare le immagini generate
/elenco_imm

# Mostrare i dettagli dell'immagine
/mostra_imm
```

### Salvare l'Immagine Generata
```dsl
# Generare e salvare
/immagina a cat playing with yarn
/saveimage images/cat_toy.jpg
```

### Caricare un'Immagine in un Archivio
```dsl
# Caricare l'immagine per l'uso nei prompt
/carica_immagine images/cat_toy.jpg imagebank1

# Fare riferimento nel prompt
Describe this image: {imagebank1}
```

### Gestione dell'Archivio Immagini
```dsl
# Caricare nell'archivio specifico
/archivio_imm1 path/to/image.jpg

# Mostrare il contenuto dell'archivio
/archivio_imm1 show

# Svuotare l'archivio
/archivio_imm1 clear
```

### Vendor di Immagini Supportati

| Vendor | Modello | Note |
|--------|---------|------|
| OpenAI | gpt-4o | Generazione di immagini nativa |
| Mistral | mistral-large-2512 | Tramite API compatibile con OpenAI |
| Google | gemini-2.5-flash, gemini-2.5-pro | Tramite endpoint compatibile con OpenAI |
| OpenRouter | google/gemini-2.5-flash-image | Completamento chat con modalità |
| OpenRouter | black-forest-labs/flux.2-klein-4b | Modello di immagine dedicato |
| Ollama | Modelli locali | Tramite endpoint `/api/generate` |

---

## Come: Integrazione Database

### Connettersi e Interrogare
```dsl
# Configurare il database
/imposta_db knowledge_base

# Cercare informazioni
/cerca_db "machine learning algorithms 2024"

# Caricare i risultati
/loadvar ml_results ALL

# Aggiungere contesto al prompt
/sistema "You are an AI expert with access to 2024 ML research."

Based on: ${ml_results}

What are the key developments in ML in 2024?

# Registrare la chat nel database
/log_db
```

### Riordinare i Risultati della Ricerca (Rerank)
```dsl
# Eseguire la ricerca, quindi il riordinamento
/cerca_db "climate change economics"
/riordina

# Caricare i risultati riordinati
/loadvar ranked_results TOP5
```

### Fonti dei Documenti per il Riordinamento

| Fonte | Sintassi | Descrizione |
|-------|----------|-------------|
| Database | `/documenti db=<nome>` | Database TinyDB |
| Variabile | `/documenti var=<nome>` | Variabile di script |
| Archivio File | `/documenti filebank=<1-5>` | Contenuto dell'archivio file |
| Directory | `/documenti dir="<percorso>"` | Directory di file |

### Comandi del Database

| Comando | Descrizione |
|---------|-------------|
| `/imposta_db <nome>` | Crea/seleziona il database |
| `/imposta_db Null` | Disattiva il database |
| `/elenco_db` | Elenca tutti i database |
| `/cerca_db <query>` | Cerca nel database |
| `/log_db` | Registra l'ultima chat nel database |
| `/stampa_db [file]` | Scarica il contenuto del database |
| `/loadvar <var> [ALL\|id\|intervallo]` | Carica i record nella variabile |
| `/savevar <var> <file>` | Salva la variabile su file |
| `/setvar <nome> <valore>` | Imposta direttamente la variabile |

---

## Come: Gestione dei Profili

### Comandi del Profilo

```dsl
# Elencare i profils disponibili
/profile list

# Usare un profilo
/profile use mio_profilo

# Clonare la sessione attuale in un nuovo profilo
/profile clone nuovo_profilo

# Eliminare un profilo
/profile delete vecchio_profilo

# Esportare un profilo
/profile export mio_profilo export_path/

# Importare un profilo
/profile import import_path/

# Mostrare il profilo attuale
/profile show

# Modificare il profilo nell'editor TUI
/profile edit
```

### Directory dei Profili
```bash
~/.config/chatybot/profiles/    # Profili utente
src/chatybot/profiles/          # Profili predefiniti
```

---

## Come: Ricerca nella Cronologia

```dsl
# Cercare nella cronologia dei comandi
! machine learning

# Cercare un comando specifico
! /modello
```

---

# Riferimento

# Riferimento delle Parole Chiave ChatDSL

## Parole Chiave dei Comandi

### Comandi di Sistema e Interfaccia

| Parola Chiave | Categoria | Sintassi | Descrizione |
|---------------|-----------|----------|-------------|
| `/aiuto` | Generale | `/aiuto [cmd\|parola_chiave]` | Mostra l'interfaccia di aiuto |
| `/esci` | Generale | `/esci` | Chiude la sessione e salva la cronologia |
| `/quit` | Generale | `/quit` | Chiude la sessione e salva la cronologia (alias) |
| `/eco` | Generale | `/eco testo` | Stampa il testo con la valutazione delle variabili |
| `/sorgente` | Generale | `/sorgente file.dsl` | Carica ed esegue un file di script |
| `/script` | Generale | `/script file.dsl [x=v y=v z=v]` | Esegue lo script con parametri |
| `/reloadmacros` | Generale | `/reloadmacros [file]` | Ricarica le definizioni delle macro |

### Comandi dei Modelli e LLM

| Parola Chiave | Categoria | Sintassi | Descrizione |
|---------------|-----------|----------|-------------|
| `/modello` | Modello | `/modello [alias]` | Cambia modello o mostra quello corrente |
| `/elenco_modelli` | Modello | `/elenco_modelli` | Elenca i modelli disponibili |
| `/sistema` | Modello | `/sistema [messaggio]` | Ottiene/imposta il messaggio di sistema |
| `/temp` | Modello | `/temp [valore]` | Temperatura (0.0-2.0) |
| `/max_token` | Modello | `/max_token [valore]` | Token di completamento massimi |
| `/top_p` | Modello | `/top_p [valore]` | Campionamento nucleo (0.0-1.0) |
| `/top_k` | Modello | `/top_k [valore]` | Campionamento Top-K |
| `/penalita_freq` | Modello | `/penalita_freq [valore]` | Penalità di frequenza (da -2.0 a 2.0) |
| `/penalita_pres` | Modello | `/penalita_pres [valore]` | Penalità di presenza (da -2.0 a 2.0) |
| `/seed` | Modello | `/seed [valore]` | Seed casuale |
| `/stream` | Modello | `/stream` | Attiva/disattiva le risposte in streaming |
| `/ragionamento` | Modello | `/ragionamento [on\|off]` | Attiva/disattiva modalità ragionamento |
| `/sforzo` | Modello | `/sforzo [low\|medium\|high\|none]` | Imposta lo sforzo di ragionamento |
| `/pensiero` | Modello | `/pensiero [on\|off]` | Attiva/disattiva la visualizzazione dei pensieri |
| `/stile_pensiero` | Modello | `/stile_pensiero [stile]` | Imposta lo stile di formattazione del pensiero |

### Comandi del Buffer dei File

| Parola Chiave | Categoria | Sintassi | Descrizione |
|---------------|-----------|----------|-------------|
| `/file` | File | `/file percorso` | Carica il file di testo nel buffer |
| `/mostra_file` | File | `/mostra_file [all]` | Visualizza il contenuto del buffer |
| `/svuota_file` | File | `/svuota_file` | Svuota il buffer |
| `/archivio_file{1-5}` | File | `/archivio_fileN percorso\|clear\|show [all]` | Gestisci gli archivi file |
| `/archivio_imm{1-5}` | File | `/archivio_immN percorso\|clear\|show` | Gestisci gli archivi immagini |
| `/carica_immagine` | File | `/carica_immagine percorso <imagebank>` | Carica l'immagine base64 nell'archivio |
| `/modalita_note` | File | `/modalita_note [on\|off]` | Estrai blocchi di codice con il salvataggio |
| `/solo_codice` | File | `/solo_codice` | Abilita la formattazione solo codice |
| `/codice_off` | File | `/codice_off` | Disabilita la formattazione solo codice |
| `/multilinea` | File | `/multilinea` | Attiva/disattiva la modalità input multilinea |
| `/salva` | File | `/salva file [all] [nothink\|withthink]` | Salva l'ultima risposta del LLM |
| `/prompt` | File | `/prompt file` | Carica ed esegue il file di prompt |

### Comandi di Generazione delle Immagini

| Parola Chiave | Categoria | Sintassi | Descrizione |
|---------------|-----------|----------|-------------|
| `/immagina` | Immagine | `/immagina prompt` | Genera immagine dal testo |
| `/dimensione_imm` | Immagine | `/dimensione_imm [WxH]` | Imposta/ottiene la risoluzione dell'immagine |
| `/qualita_imm` | Immagine | `/qualita_imm [standard\|hd]` | Imposta/ottiene la qualità dell'immagine |
| `/saveimage` | Immagine | `/saveimage [percorso]` | Salva l'ultima immagine generata |
| `/cartella_imm` | Immagine | `/cartella_imm [percorso]` | Imposta/ottiene la cartella di output delle immagini |
| `/elenco_imm` | Immagine | `/elenco_imm` | Elenca tutte le immagini salvate |
| `/mostra_imm` | Immagine | `/mostra_imm [data\|filename]` | Mostra i metadati dell'immagine |

### Comandi Shell

| Parola Chiave | Categoria | Sintassi | Descrizione |
|---------------|-----------|----------|-------------|
| `/esegui` | Shell | `/esegui comando [args]` | Esegue un comando shell |
| `/esegui_sicuro` | Shell | `/esegui_sicuro` | Abilita i prompt di conferma di sicurezza |
| `/esegui_insicuro` | Shell | `/esegui_insicuro` | Disabilita le conferme di esecuzione shell |

### Comandi del Ciclo degli Strumenti

| Parola Chiave | Categoria | Sintassi | Descrizione |
|---------------|-----------|----------|-------------|
| `/strumento` | Strumenti | `/strumento [subcmd] [args]` | Gestione modalità strumenti |
| `/strumento on` | Strumenti | `/strumento on` | Carica le definizioni degli strumenti nel prompt |
| `/strumento off` | Strumenti | `/strumento off` | Disabilita gli schemi degli strumenti |
| `/strumento elenco` | Strumenti | `/strumento elenco` | Elenca gli strumenti disponibili e il loro stato |
| `/strumento abilita` | Strumenti | `/strumento abilita <tool\|all>` | Abilita uno strumento specifico o tutti |
| `/strumento disabilita`| Strumenti | `/strumento disabilita <tool\|all>`| Disabilita uno strumento specifico o tutti |
| `/strumento auto` | Strumenti | `/strumento auto` | Attiva il ciclo automatico sulle risposte |
| `/strumento ciclo` | Strumenti | `/strumento ciclo [turni] [force]` | Esegue il ciclo con un limite di turni |
| `/strumento max_turni`| Strumenti | `/strumento max_turni [N]` | Ottiene/imposta il limite massimo di turni |
| `/strumento prompt` | Strumenti | `/strumento prompt` | Mostra il prompt attivo |

### Comandi di Diagnostica

| Parola Chiave | Categoria | Sintassi | Descrizione |
|---------------|-----------|----------|-------------|
| `/traccia` | Debug | `/traccia <subcmd> [on\|off]` | Attiva/disattiva le modalità di traccia |
| `/traccia rawpayload` | Debug | `/traccia rawpayload [on\|off]` | Traccia del payload API grezzo |
| `/traccia tps` | Debug | `/traccia tps [on\|off]` | Traccia dei token al secondo |
| `/traccia tpsperf` | Debug | `/traccia tpsperf [on\|off]` | Traccia delle prestazioni di TPS |
| `/traccia imagedbg` | Debug | `/traccia imagedbg [on\|off]` | Debug della generazione di immagini |
| `/traccia rerank` | Debug | `/traccia rerank [on\|off]` | Traccia dell'operazione di rerank |
| `/traccia agentic_loop` | Debug | `/traccia agentic_loop [on\|off]` | Traccia del ciclo agentico |
| `/debug` | Debug | `/debug <payload\|response\|vmem>` | Impostazioni della modalità debug |
| `/registro_log` | Debug | `/registro_log [start\|end]` | Avvia/arresta la registrazione su file |
| `/memoria` | Debug | `/memoria [detail\|debug]` | Mostra l'uso della memoria (alias `/mem`) |
| `/dump` | Debug | `/dump [varname\|all]` | Scarica il contenuto delle variabili |

### Comandi del Database

| Parola Chiave | Categoria | Sintassi | Descrizione |
|---------------|-----------|----------|-------------|
| `/imposta_db` | Database | `/imposta_db <nome\|Null>` | Connetti/inizializza/disattiva il database |
| `/elenco_db` | Database | `/elenco_db` | Elenca i database vettoriali disponibili |
| `/cerca_db` | Database | `/cerca_db <query>` | Esegue una query vettoriale |
| `/log_db` | Database | `/log_db` | Registra l'ultima chat nel database |
| `/stampa_db` | Database | `/stampa_db [file]` | Scarica il contenuto del database |
| `/documenti` | Database | `/documenti <src>=<id>` | Imposta la sorgente dei documenti per il rerank |
| `/riordina` | Database | `/riordina "<query>" [opzioni]` | Esegue il riordinamento semantico |

### Comandi delle Variabili

| Parola Chiave | Categoria | Sintassi | Descrizione |
|---------------|-----------|----------|-------------|
| `/setvar` | Variabile | `/setvar <nome> <valore>` | Imposta una variabile di script |
| `/loadvar` | Variabile | `/loadvar <nome> [ALL\|id\|intervallo]` | Carica i record del DB nella variabile |
| `/savevar` | Variabile | `/savevar <nome> <nome_file>` | Salva la variabile su file |

### Comandi del Profilo

| Parola Chiave | Categoria | Sintassi | Descrizione |
|---------------|-----------|----------|-------------|
| `/profile` | Profilo | `/profile <subcmd> [args]` | Gestione del profilo |
| `/profile list` | Profilo | `/profile list` | Elenca i profili disponibili |
| `/profile use` | Profilo | `/profile use <nome>` | Carica un profilo |
| `/profile clone` | Profilo | `/profile clone <nome>` | Clona la sessione corrente |
| `/profile delete` | Profilo | `/profile delete <nome>` | Elimina un profilo |
| `/profile export` | Profilo | `/profile export <nome> <percorso>` | Esporta il profilo |
| `/profile import` | Profilo | `/profile import <percorso>` | Importa il profilo |
| `/profile show` | Profilo | `/profile show` | Mostra il profilo corrente |
| `/profile edit` | Profilo | `/profile edit` | Modifica il profilo nella TUI |

### Comandi della Cronologia

| Parola Chiave | Categoria | Sintassi | Descrizione |
|---------------|-----------|----------|-------------|
| `!` | Cronologia | `! <ricerca>` | Cerca nella cronologia dei comandi |

## Parole Chiave di Scripting

| Inglese | Italiano | Sintassi | Descrizione |
|---------|----------|----------|-------------|
| `set` | `imposta` | `imposta nome = valore` | Assegnazione di una variabile |
| `if` | `if` | `if condizione then comando` | Esecuzione condizionale |
| `then` | `then` | (parte di if) | Corpo condizionale |
| `wait` | `wait` | `wait N` | Sospende per N secondi |
| `#` | `#` | `# commento` | Commento |
| `def` | `def` | `def nome(params) = "modello"` | Definisce una macro |
| `%` | `%` | `%nome(args)` | Invoca una macro |

## Sintassi delle Variabili

| Sintassi | Descrizione |
|----------|-------------|
| `${nome}` | Riferimento alla variabile |
| `imposta nome = "valore"` | Definizione della variabile |
| `"valore con spazi"` | Valore tra virgolette doppie |
| `'valore con espaces'` | Valore tra virgolette singole |
| `{filebankN}` | Riferimento all'archivio file nei prompt |
| `{imagebankN}` | Riferimento all'archivio immagini nei prompt |

## Operatori

| Operatore | Descrizione | Esempio |
|-----------|-------------|---------|
| `==` | Uguale a | `if ${x} == "yes" then` |
| `!=` | Diverso da | `if ${x} != "" then` |
| `not` | Negazione | `if not ${debug} then` |

## Flusso di Controllo

| Comando | Sintassi | Descrizione |
|----------|---------|-------------|
| `if` | `if condizione then comando` | Esecuzione condizionale |
| `wait` | `wait N` | Sospende per N secondi |
| `imposta` | `imposta nome = valore` | Definisce una variabile |
| `#` | `# commento` | Commento |

## Sintaxis Multilinea

| Parola Chiave | Sintassi | Descrizione |
|---------------|----------|-------------|
| `/multilinea` | `/multilinea` | Inizia blocco multilinea |
| `;;` | `;;` | Termina blocco multilinea |

## Sintassi delle Macro

| Elemento | Sintassi | Descrizione |
|----------|----------|-------------|
| Definizione | `def nome(params) = "modello"` | Definisce una macro |
| Senza parametri | `def nome() = "modello"` | Definisce una macro senza parametri |
| Invocazione | `%nome(args)` | Chiama una macro |
| Variabile modello | `{param}` | Segnaposto parametro |

### Esempi di Macro

```dsl
# Macro senza parametri
def regen() = "Regenerate all source code"
def build() = "Build the project with optimized settings"

# Macro parametrizzate
def expert_prompt(topic) = "Act as an expert in {topic}. Provide detailed, accurate, and insightful information about {topic}."

def language_comparison(lang1, lang2) = "Compare {lang1} and {lang2} programming languages. Discuss their similarities, differences, syntax variations, performance characteristics, and typical use cases."
```

## Messaggi di Errore

| Errore | Inglese | Spagnolo | Francese | Cinese | Italiano |
|-------|---------|---------|--------|---------|---------|
| File non trovato | "Error: File not found" | "Error: Archivo no encontrado" | "Erreur: Fichier introuvable" | "错误: 文件没有找到" | "Errore: File non trovato" |
| Macro non definita | "ERROR: Macro 'X' not defined" | "ERROR: Macro 'X' no definido" | "ERREUR: Macro 'X' non définie" | "错误: 宏 'X' 未定义" | "ERRORE: Macro 'X' non definita" |
| Argomenti errati | "ERROR: Macro 'X' expects N arguments, got M" | "ERROR: Macro 'X' espera N argumentos, obtuvo M" | "ERREUR: Macro 'X' attend N arguments, reçu M" | "错误: 宏 'X' 需要 N 个参数，得到 M 个" | "ERRORE: Macro 'X' aspetta N argomenti, ottenuti M" |

---

# Migliori Pratiche

## Linee Guida per la Scrittura di Script

### 1. Nomi delle Variabili
- Usa **snake_case** per nomi descrittivi: `numero_articoli`, `nome_modello`
- Lettere singole (`x`, `y`, `z`) riservate solo ai parametri dello script
- MAIUSCOLO per le costanti

### 2. Stile dei Commenti
```dsl
# Commento a riga intera
imposta var = "valore"  # Commento in linea

# Intestazioni di sezione
# ============================================
# SEZIONE DI TRADUZIONE
# ============================================
```

### 3. Struttura dello Script
```dsl
# Intestazione con utilizzo
# Script: descrizione
# Uso: /script script.chatdsl [parametri]

# Gestione dei parametri
if ${x} != "" then imposta param1 = ${x}
if ${param1} == "" then imposta param1 = "default"

# Configurazione
imposta base_dir = "output"
/modello gemini_flash

# Logica principale
/file input.txt
process this...
/salva output.txt

# Pulizia (opzionale)
/svuota_file
/eco "Done"
```

### 4. Modelli Comuni

#### Valori Parametri Predefiniti
```dsl
if ${x} != "" then imposta var = ${x}
if ${var} == "" then imposta var = "default"
```

#### Selezione Condizionale del Modello
```dsl
if ${fast} then /modello gemini_flash
if not ${fast} then /modello openai_gpt4
```

## Gestione degli Errori

### Problemi Comuni e Soluzioni

| Problema | Soluzione |
|----------|----------|
| Variabile non si espande | Controlla la sintassi `${nome}` (senza spazi) |
| File non trovato | Usa `/eco` per verificare l'espansione del percorso |
| Multilinea non termina | Assicurati che `;;` sia su una riga a sé stante, poi `/multilinea` |
| Impostare valore con spazi | Usa virgolette doppie: `imposta var = "valore con spazi"` |
| Backslash nel valore | Non consentito - usa barre diagonali in avanti (`/`) |
| Comando non riconosciuto | Controlla eventuali errori di battitura e il prefisso `/` |

## Consigli sulle Prestazioni

### Limiti di Frequenza (Rate Limiting)
```dsl
# Tra le chiamate al modello
/modello gemini_flash
prompt 1
/salva response1.txt
wait 2  # Ritardo di 2 secondi

/modello openai_gpt4
prompt 2
/salva response2.txt
```

### Gestione del Buffer
```dsl
# Svuotare il buffer tra operazioni non correlate
/svuota_file

# Prevenire l'inquinamento del contesto
/file new_context.txt
```

### Ridurre l'Uso dei Token
```dsl
# Usare /solo_codice per la generazione del codice
/solo_codice
Write Python code to solve this problem.
/codice_off
```

---

# Riferimento Rapido

## Categorie di Comandi

### Sistema
- `/aiuto` - Mostra aiuto
- `/eco` - Stampa testo
- `/esci` - Esci dalla sessione
- `/script` - Esegui script
- `/sorgente` - Esegui file di script

### Modello
- `/modello [alias]` - Cambia modello
- `/sistema [prompt]` - Imposta messaggio di sistema
- `/temp [valore]` - Imposta temperatura
- `/max_token [valore]` - Imposta token massimi
- `/ragionamento [on|off]` - Attiva/disattiva ragionamento
- `/sforzo [low|medium|high|none]` - Imposta lo sforzo

### File
- `/file percorso` - Carica nel buffer
- `/archivio_file1-5` - Gestione archivi file
- `/salva file [all] [nothink|withthink]` - Salva risposta
- `/multilinea` - Prompt complessi
- `/prompt file` - Esegui file di prompt

### Immagine
- `/immagina prompt` - Genera immagine
- `/dimensione_imm WxH` - Imposta risoluzione
- `/saveimage [percorso]` - Salva immagine generata
- `/archivio_imm1-5` - Gestione archivi immagini

### Database
- `/imposta_db nome` - Connetti database
- `/cerca_db "query"` - Ricerca vettoriale
- `/log_db` - Registra risposta
- `/riordina` - Riordinamento semantico

### Strumento
- `/strumento on` - Abilita strumenti
- `/strumento ciclo [turni] [force]` - Esecuzione autonoma
- `/strumento elenco` - Elenca gli strumenti
- `/strumento abilita all` - Abilita tutti gli strumenti

### Debug
- `/traccia <tipo> [on|off]` - Abilita traccia
- `/memoria [detail|debug]` - Uso memoria
- `/dump [var|all]` - Scarica variabili

### Profilo
- `/profile list` - Elenca profili
- `/profile use nome` - Carica profilo
- `/profile clone nome` - Clona sessione

## Elementi di Scripting

### Variabili
```dsl
imposta nome = "valore"
${nome}
```

### Condizioni
```dsl
if ${x} == "yes" then /comando
if not ${debug} then /eco "quiet"
```

### Attesa
```dsl
wait 2
```

### Multilinea
```dsl
/multilinea
Your prompt here
;;
/multilinea
```

### Macro
```dsl
# Definire
def expert_prompt(topic) = "Act as an expert in {topic}."

# Invoking
%expert_prompt(Python)
```

---

# Risorse

## File di Documentazione

- **Guida al linguaggio ChatDSL** (`chatdsl_language.md`) - Riferimento completo con mappatura dei comandi
- **Guía delle competenze ChatDSL** (`chatdsl_skill.md`) - Modelli di scripting completi
- **Implementazione delle Macro ChatDSL** (`chatdsl_macro_implementation.md`) - Relazione tecnica di implementazione

## File di Configurazione

- `~/.config/chatybot/chat_config.toml` - Configurazione modelli utente
- `~/.config/chatybot/profiles/` - Profili utente
- `src/chatybot/chat_config.toml` - Configurazione modelli predefinita
- `src/chatybot/tools_config.toml` - Definizioni degli strumenti
- `src/chatybot/macro.chatdsl` - Definizioni delle macro predefinite
- `src/chatybot/translations.json` - Traduzioni multilingue

## File di Progetto

- `chatdsl_bnf.txt` - Specifiche formali della grammatica
- `script_param_implementation.md` - Dettagli sul passaggio dei parametri
- `dsl_test/` - Script di test che dimostrano tutte le funzionalità

---

# Guida all'Avvio

## Avvio Rapido

1. **Installare Chatybot**
   ```bash
   pip install chatybot
   ```

2. **Configurare le Chiavi API**
   ```bash
   # Copiare la configurazione predefinita nella directory utente
   mkdir -p ~/.config/chatybot
   cp src/chatybot/chat_config.toml ~/.config/chatybot/
   
   # Modificare con le chiavi API
   chatybot-config
   ```

3. **Eseguire Chatybot**
   ```bash
   chatybot
   ```

4. **Eseguire uno Script ChatDSL**
   ```bash
   chat --> /script mio_script.chatdsl x=valore1 y=valore2
   ```

## Comandi di Base

- `/aiuto` - Visualizza tutti i comandi disponibili
- `/modello` - Passa da un modello all'altro
- `/file percorso` - Carica file di contesto
- `/eco "testo"` - Output di debug
- `/salva percorso` - Salva le risposte

## Script di Esempio

Controllare la directory `dsl_test/` per esempi di lavoro:
- `translate.chatdsl` - Flusso di traduzione
- `compare.chatdsl` - Confronto file
- `evaluate.chatdsl` - Valutazione multi-modello
- `batch.chatdsl` - Elaborazione batch

---

*(Fine della Guida Completa a ChatDSL)*

---

## Cronologia delle Versioni

| Versione | Data | Modifiche |
|---------|------|-----------|
| 1.0 | 2025-07-23 | Versione iniziale basata sul codice sorgente v0.6.4 |

---

## Note dell'Autore

Questa guida è la versione corretta basata su un esame approfondito del codice sorgente di Chatybot v0.6.4. Tutta la sintassi dei comandi, i formati di configurazione e gli esempi di script sono stati verificati rispetto all'effettiva implementazione.
