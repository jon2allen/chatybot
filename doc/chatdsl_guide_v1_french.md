# Guide Complet ChatDSL

## Aperçu

ChatDSL (Chat Domain-Specific Language) est un langage de script puissant conçu pour automatiser les interactions avec les grands modèles de langage (LLM). Ce guide fournit une référence complète pour travailler avec ChatDSL, y compris des fonctionnalités, des tutoriels, des guides pratiques et une référence exhaustive des mots-clés.

> *Dernière mise à jour : 19 août 2026*
>
> *Version : 1.0*
>
> *Compatible avec Chatybot v0.7.9+*

---

# Fonctionnalités

## Capacités Principales

### 1. Support Multilingue
ChatDSL prend en charge 6 langues avec un aliasing complet des commandes :
- **Anglais (EN)** - Langue principale
- **Espagnol (ES)** - Traductions espagnoles de toutes les commandes
- **Français (FR)** - Traductions françaises de toutes les commandes
- **Chinois (ZH)** - Traductions chinoises de toutes les commandes
- **Italien (IT)** - Traductions italiennes de toutes les commandes
- **Arabe (AR)** - Traductions arabes de toutes les commandes

### 2. Fonctionnalités de Script
- **Système de Variables** : Variables à portée de script avec la syntaxe `${nom}`
- **Logique Conditionnelle** : Instructions `if` avec les opérateurs `==`, `!=` et `not` (utilisant `then` pour l'exécution)
- **Gestion des Tampons** : Tampon principal et 5 banques de fichiers pour un contexte persistant
- **Entrée Multiligne** : Prompts complexes s'étendant sur plusieurs lignes
- **Opérations sur Fichiers** : Charger, afficher, vider et sauvegarder des fichiers
- **Paramètres de Script** : Paramètres `x`, `y`, `z` pour les scripts personnalisés
- **Macros** : Modèles de prompts réutilisables avec analyse grammaticale Parsley PEG
- **Opérateur de Raccourci de Recherche** : L'opérateur `!` pour rechercher dans l'historique des commandes

### 3. Intégration des LLM
- **Gestion des Modèles** : Basculez entre plus de 20 modèles configurés chez 8 fournisseurs
- **Prompts Système** : Définissez les règles de comportement principales
- **Contrôle de la Température** : `0.0-2.0` pour le caractère aléatoire des réponses
- **Limites de Jetons** : Contrôlez la longueur de la complétion
- **Contrôle de l'Échantillonnage** : `top_p`, `top_k`, `freq_penalty`, `pres_penalty`
- **Contrôles du Raisonnement** : Modes `reasoning` (raisonnement), `effort` (effort) et `thinking` (réflexion)
- **Optimisations Spécifiques aux Fournisseurs** : Adaptations NVIDIA, Mistral, Google, OpenAI

### 4. Fonctionnalités Avancées
- **Boucles d'Outils** : Exécution autonome avec appel d'outils (local + MCP)
- **Génération d'Images** : Prise en charge d'OpenAI, Mistral, OpenRouter, Ollama
- **Intégration de Base de Données** : Stockage vectoriel TinyDB avec reclassement (reranking)
- **Système de Profils** : Fichiers `.chatdsl` comme profils de session persistants
- **Intégration MCP** : Prise en charge du protocole de contexte de modèle (Model Context Protocol)

### 5. Diagnostics et Surveillance
- **Sorties de Trace** : TPS (jetons par seconde), payload brut, débogage d'image, rerank, traçage de boucle agentique
- **Commandes de Débogage** : Afficher les réponses brutes et l'utilisation de la mémoire virtuelle
- **Journalisation (Logging)** : Journalisation des fichiers et suivi des erreurs
- **Inspection des Tampons** : Vérifier les états de la mémoire et des variables

---

# Structure du Projet

## Disposition des Sources

```
src/chatybot/                    # Paquet principal
├── __init__.py                  # Version : "0.6.4"
├── main.py                      # Point d'entrée → chatybot_app.run()
├── chatybot_app.py              # Application principale (5,887 lignes)
├── buffer_manager.py            # Banques de fichiers, banques d'images, variables de script
├── chatydb.py                   # Intégration de la base de données TinyDB
├── chaty_help.py                # Système d'aide structuré
├── chatdsl_parse.py             # Analyseur de grammaire ChatDSL
├── config_manager.py            # Chargement de la config TOML
├── config_model.py              # Validation de la config Pydantic
├── config_sync.py               # Synchronisation des fichiers de config
├── config_tui.py                # Interface utilisateur terminal (TUI) pour la config
├── dispatcher.py                # Passerelle d'exécution des outils
├── extract_code.py              # Extraction des blocs de code
├── image_generator.py           # Génération d'images multi-fournisseurs
├── image_manager.py             # Utilitaires de chargement d'images
├── localization.py              # Support i18n / multi-langue
├── logging_manager.py           # Journalisation du chat
├── macro.chatdsl                # Définitions de macros par défaut
├── mcp_client.py                # Intégration du protocole MCP
├── menu.chatdsl                 # Script du menu DSL
├── pattern.py                   # Comparateur de modèles de commandes
├── profile_editor.py            # Éditeur de profil Curses
├── profile_manager.py           # Opérations CRUD sur les profils
├── vendors.py                   # Définitions des préréglages des fournisseurs
├── chat_config.toml             # Configurations de modèles par défaut
├── tools_config.toml            # Définitions d'outils pour le mode agentique
├── translations.json            # Traductions multilingues
├── profiles/                    # Scripts de profils prédéfinis
├── tinydb1/corpus_manager.py    # Wrapper TinyDB
└── tools/
    ├── __init__.py
    ├── file_utils.py            # Outils de fichiers : list, read, write, grep, run, replace
    └── tool_config_tui.py       # TUI de configuration des outils
```

## Points d'Entrée

```bash
chatybot                  # Point d'entrée CLI principal
chatdsl_parse             # Utilitaire de l'analyseur DSL
chatybot-config           # Éditeur TUI de configuration
```

---

# Tutoriels

## Tutoriel 1 : Flux de Travail de Traduction de Base

Ce tutoriel montre comment traduire un fichier d'une langue à une autre à l'aide de ChatDSL.

### Prérequis
- Un fichier texte source (`english.txt`)
- Clés API configurées dans `~/.config/chatybot/chat_config.toml`

### Guide Étape par Étape

1. **Configurer les Paramètres**
   ```dsl
   # Usage : /script translate.chatdsl x=english.txt y=spanish z=output.txt
   if ${x} != "" then definir source_file = ${x}
   if ${source_file} == "" then definir source_file = "english.txt"
   
   if ${y} != "" then definir target_lang = ${y}
   if ${target_lang} == "" then definir target_lang = "spanish"
   
   if ${z} != "" then definir output_file = ${z}
   if ${output_file} == "" then definir output_file = "output.txt"
   ```

2. **Charger le Fichier Source**
   ```dsl
   /fichier ${source_file}
   ```

3. **Effectuer la Traduction**
   ```dsl
   /echo "Translating to ${target_lang}..."
   
   /modele gemini_flash
   Translate ${target_lang} :
   
   /sauvegarder ${output_file}
   ```

4. **Résultats**
   - Fichier créé à `${output_file}`
   - Traduction enregistrée dans la langue cible

### Script Complet

```dsl
# translate.chatdsl
# Usage : /script translate.chatdsl x=english.txt y=spanish z=output.txt

# Gestion des paramètres
if ${x} != "" then definir source_file = ${x}
if ${source_file} == "" then definir source_file = "english.txt"

if ${y} != "" then definir target_lang = ${y}
if ${target_lang} == "" then definir target_lang = "spanish"

if ${z} != "" then definir output_file = ${z}
if ${output_file} == "" then definir output_file = "output.txt"

# Charger la source
/fichier ${source_file}

# Traduire
/echo "Translating to ${target_lang}..."

/modele gemini_flash
Translate ${target_lang} :

/sauvegarder ${output_file}

/echo "Translation saved to ${output_file}"
```

---

## Tutoriel 2 : Comparaison de Fichiers avec ChatDSL

Découvrez comment comparer deux fichiers et identifier les différences clés.

### Utilisation
```bash
chatybot
chat --> /script compare_articles.chatdsl x=article1.txt y=article2.txt z=comparison.txt
```

### Script Complet

```dsl
# compare_articles.chatdsl
# Usage : /script compare_articles.chatdsl x=article1.txt y=article2.txt z=comparison.txt

# Gestion des paramètres
if ${x} != "" then definir file1 = ${x}
if ${file1} == "" then definir file1 = "default1.txt"

if ${y} != "" then definir file2 = ${y}
if ${file2} == "" then definir file2 = "default2.txt"

if ${z} != "" then definir output = ${z}
if ${output} == "" then definir output = "comparison.txt"

# Charger les fichiers dans les banques
/banque_fich1 ${file1}
/banque_fich2 ${file2}

/echo "Comparing ${file1} and ${file2}"

# Générer la comparaison
/systeme "You are a precise text comparison expert."

/multiligne
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
/multiligne

# Enregistrer le résultat
/sauvegarder ${output}

/echo "Comparison saved to ${output}"
```

### Résultats Attendus
Le script générera une comparaison détaillée couvrant :
- **Différences structurelles** : Ordre des sections, titres, mise en forme
- **Différences de contenu** : Faits, données, arguments principaux
- **Différences de style** : Vocabulaire, structure des phrases, ton

---

## Tutoriel 3 : Évaluation Multi-Modèle

Évaluez comment différents modèles répondent à la même invite (prompt).

### Utilisation
```bash
chatybot
chat --> /script evaluate.chatdsl x=prompt.txt y=output_dir
```

### Script Complet

```dsl
# evaluate.chatdsl
# Usage : /script evaluate.chatdsl x=prompt_file y=output_dir

definir prompt_file = ${x}
definir output_dir = ${y}

# Modèle 1 - GPT-4
/echo "Processing with GPT-4..."
/modele openai_gpt4
/prompt ${prompt_file}
/sauvegarder ${output_dir}/gpt4_response.txt

# Modèle 2 - Claude
/echo "Processing with Claude..."
/modele claude
/prompt ${prompt_file}
/sauvegarder ${output_dir}/claude_response.txt

# Comparer les réponses
/echo "Comparing models..."

/banque_fich1 ${output_dir}/gpt4_response.txt
/banque_fich2 ${output_dir}/claude_response.txt

/multiligne
Compare these two responses to the same prompt:

Model A (GPT-4):
{filebank1}

Model B (Claude):
{filebank2}

Which is better and why?
;;
/multiligne
/sauvegarder ${output_dir}/comparison.txt

/echo "Evaluation complete! Results in ${output_dir}"
```

### Fichiers de Sortie
- `${output_dir}/gpt4_response.txt` - Réponse de GPT-4
- `${output_dir}/claude_response.txt` - Réponse de Claude
- `${output_dir}/comparison.txt` - Comparaison côte à côte

---

# Guides Pratiques (HowTos)

## Comment : Configurer Chatybot

### Emplacement du Fichier de Configuration
```bash
~/.config/chatybot/chat_config.toml    # Configuration utilisateur (écrase les valeurs par défaut)
src/chatybot/chat_config.toml          # Configuration par défaut (intégrée)
```

### Format du Fichier de Configuration (TOML)

```toml
# ============================================================================
# PARAMÈTRES DE GÉNÉRATION D'IMAGES
# ============================================================================

[image_generation]
default_dir = "~/chatybot_images"
default_size = "1024x1024"
default_quality = "standard"

# ============================================================================
# MODÈLES DE CHAT
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

### Propriétés de Configuration des Modèles

| Propriété | Type | Description |
|-----------|------|-------------|
| `name` | chaîne | Identifiant du modèle (spécifique à l'API) |
| `temperature` | flottant | Caractère aléatoire des réponses (0.0-2.0) |
| `top_k` | entier | Nombre d'échantillonnage Top-K |
| `base_url` | chaîne | URL du point de terminaison de l'API |
| `api_key` | chaîne | Nom de la variable d'environnement pour la clé API |
| `image_generation` | booléen | Activer la génération d'images |
| `image_endpoint` | chaîne | Chemin de terminaison pour la génération d'images |
| `vendor` | chaîne | Identifiant du fournisseur |

### Fournisseurs Pris en Charge

| Fournisseur | Description |
|-------------|-------------|
| `mistral` | API Mistral AI |
| `google` | Google Generative AI |
| `openai` | API OpenAI |
| `openrouter` | API agrégée OpenRouter |
| `nvidia` | API NVIDIA NIM |
| `publicai` | API PublicAI |
| `bytez` | API Bytez |
| `ollama` | Serveur Ollama local |

### Configuration des Outils

Emplacement : `src/chatybot/tools_config.toml`

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

## Comment : Traiter des Fichiers par Lots

Puisque ChatDSL n'a pas de boucles, traitez les fichiers en répétant la logique manuellement :

### Modèle de Script

```dsl
# batch.chatdsl
# Usage : /script batch.chatdsl x=input_dir y=output_dir

definir input_dir = ${x}
definir output_dir = ${y}

# Fichier a
definir file = "a.txt"
/fichier ${input_dir}/${file}
Analyze ${file}
/sauvegarder ${output_dir}/${file}_processed.txt

# Fichier b
definir file = "b.txt"
/fichier ${input_dir}/${file}
Analyze ${file}
/sauvegarder ${output_dir}/${file}_processed.txt

# Fichier c
definir file = "c.txt"
/fichier ${input_dir}/${file}
Analyze ${file}
/sauvegarder ${output_dir}/${file}_processed.txt
```

---

## Comment : Configurer la Boucle d'Appel d'Outils

### Activer le Mode Outil
```dsl
# Charger les schémas d'outils dans l'invite système
/outil on

# Rendre tous les outils disponibles
/outil activer all

# Configurer pour l'exécution autonome
/outil auto

# Définir la limite de tours
/outil tours_max 10
```

### Exécuter la Boucle d'Outils
```dsl
/outil boucle 50 force
```

### Vérifier le Statut des Outils
```dsl
/outil lister
/outil prompt
```

### Outils Disponibles

| Outil | Description |
|-------|-------------|
| `list_directory` | Lister le contenu du répertoire |
| `read_file` | Lire le contenu du fichier |
| `find_files` | Trouver des fichiers par modèle |
| `run_command` | Exécuter une commande shell |
| `write_file` | Écrire ou ajouter à un fichier |
| `change_dir` | Changer le répertoire de travail |
| `grep_search` | Rechercher dans le contenu des fichiers |
| `replace_file_content` | Rechercher et remplacer dans un fichier |

### Intégration des Outils MCP

Les outils MCP sont nommés sous l'espace de noms `mcp__<serveur>__<outil>` :
```dsl
# Outils MCP découverts automatiquement sur les serveurs connectés
/outil lister

# Exécuter l'outil MCP
# (Automatique via la boucle d'outils - le LLM génère des appels JSON)
```

---

## Comment : Flux de Travail de Génération d'Images

### Génération d'Image de Base
```dsl
# Définir les paramètres de l'image
/dossier_images output/
/taille_image 1024x1024
/qualite_image hd

# Générer l'image
/imaginer a beautiful sunset over mountains

# Lister les images générées
/lister_images

# Afficher les détails de l'image
/afficher_image
```

### Enregistrer l'Image Générée
```dsl
# Générer et enregistrer
/imaginer a cat playing with yarn
/saveimage images/cat_toy.jpg
```

### Charger une Image dans une Banque
```dsl
# Charger une image pour l'utiliser dans les invites
/charger_image images/cat_toy.jpg imagebank1

# Référencer dans l'invite
Describe this image : {imagebank1}
```

### Gestion des Banques d'Images
```dsl
# Charger dans une banque spécifique
/banque_imag1 path/to/image.jpg

# Afficher le contenu de la banque
/banque_imag1 show

# Vider la banque
/banque_imag1 clear
```

### Fournisseurs d'Images Pris en Charge

| Fournisseur | Modèle | Notes |
|-------------|--------|-------|
| OpenAI | gpt-4o | Génération d'images native |
| Mistral | mistral-large-2512 | Via une API compatible OpenAI |
| Google | gemini-2.5-flash, gemini-2.5-pro | Via un point de terminaison compatible OpenAI |
| OpenRouter | google/gemini-2.5-flash-image | Complétions de chat avec modalités |
| OpenRouter | black-forest-labs/flux.2-klein-4b | Modèle d'image dédié |
| Ollama | Modèles locaux | Via le point de terminaison `/api/generate` |

---

## Comment : Intégration de la Base de Données

### Connecter et Interroger
```dsl
# Configurer la base de données
/definir_bd knowledge_base

# Rechercher des informations
/rechercher_bd "machine learning algorithms 2024"

# Charger les résultats
/loadvar ml_results ALL

# Ajouter du contexte à l'invite
/systeme "You are an AI expert with access to 2024 ML research."

Based on : ${ml_results}

What are the key developments in ML in 2024?

# Enregistrer la conversation en BD
/journal_bd
```

### Reclasser les Résultats de Recherche (Rerank)
```dsl
# Effectuer la recherche puis reclasser
/rechercher_bd "climate change economics"
/reclasser

# Charger les résultats reclassés
/loadvar ranked_results TOP5
```

### Sources de Documents pour le Reclassement

| Source | Syntaxe | Description |
|--------|---------|-------------|
| Base de données | `/documents db=<nom>` | Base de données TinyDB |
| Variable | `/documents var=<nom>` | Variable de script |
| Banque de fichiers | `/documents filebank=<1-5>` | Contenu de la banque de fichiers |
| Répertoire | `/documents dir="<chemin>"` | Répertoire de fichiers |

### Commandes de Base de Données

| Commande | Description |
|----------|-------------|
| `/definir_bd <nom>` | Créer/sélectionner une base de données |
| `/definir_bd Null` | Désactiver la base de données |
| `/lister_bd` | Lister toutes les bases de données |
| `/rechercher_bd <requete>` | Rechercher dans la base de données |
| `/journal_bd` | Enregistrer le dernier chat en base de données |
| `/imprimer_bd [fichier]` | Exporter le contenu de la base de données |
| `/loadvar <var> [ALL\|id\|plage]` | Charger les enregistrements en variable |
| `/savevar <var> <fichier>` | Sauvegarder la variable dans un fichier |
| `/setvar <nom> <valeur>` | Définir directement une variable |

---

## Comment : Gestion des Profils

### Commandes de Profil

```dsl
# Lister les profils disponibles
/profile list

# Utiliser un profil
/profile use mon_profil

# Cloner la session actuelle vers un nouveau profil
/profile clone nouveau_profil

# Supprimer un profil
/profile delete ancien_profil

# Exporter un profil
/profile export mon_profil export_path/

# Importer un profil
/profile import import_path/

# Afficher le profil actuel
/profile show

# Modifier le profil dans l'éditeur TUI
/profile edit
```

### Répertoire des Profils
```bash
~/.config/chatybot/profiles/    # Profils utilisateur
src/chatybot/profiles/          # Profils prédéfinis
```

---

## Comment : Recherche dans l'Historique

```dsl
# Rechercher dans l'historique des commandes
! machine learning

# Rechercher une commande spécifique
! /modele
```

---

# Référence

# Référence des Mots-Clés ChatDSL

## Mots-Clés de Commande

### Commandes Système et Interface

| Mot-Clé | Catégorie | Syntaxe | Description |
|---------|-----------|---------|-------------|
| `/aide` | Général | `/aide [cmd\|mot_cle]` | Afficher l'interface d'aide |
| `/quitter` | Général | `/quitter` | Fermer la session et sauvegarder l'historique |
| `/exit` | Général | `/exit` | Fermer la session et sauvegarder l'historique (alias) |
| `/echo` | Général | `/echo texte` | Afficher le texte avec évaluation des variables |
| `/source` | Général | `/source fichier.dsl` | Charger et exécuter un fichier de script |
| `/script` | Général | `/script fichier.dsl [x=v y=v z=v]` | Exécuter le script avec paramètres |
| `/calculer` | Général | `/calculer <expr>` | Évaluer une expression mathématique |
| `/chercher_texte` | Général | `/chercher_texte <recherche> [source]` | Chercher une sous-chaîne dans le texte |
| `/procedure` | Général | `/procedure <nom> [args]` | Exécuter une procédure définie |
| `/session` | Général | `/session <subcmd> [args]` | Gérer les sessions de chat (sauvegarder, lister, purger, etc.) |
| `/reloadmacros` | Général | `/reloadmacros [fichier]` | Recharger les définitions de macros |

### Commandes de Modèle et LLM

| Mot-Clé | Catégorie | Syntaxe | Description |
|---------|-----------|---------|-------------|
| `/modele` | Modèle | `/modele [alias]` | Changer de modèle ou afficher le modèle actuel |
| `/lister_modeles` | Modèle | `/lister_modeles` | Lister les modèles disponibles |
| `/variables_env` | Modèle | `/variables_env [filtre]` | Afficher les variables d'environnement et clés d'API (`set \| grep -i api`) |
| `/systeme` | Modèle | `/systeme [message]` | Obtenir/définir le message système |
| `/temp` | Modèle | `/temp [valeur]` | Température (0.0-2.0) |
| `/max_jetons` | Modèle | `/max_jetons [valeur]` | Maximum de jetons de complétion |
| `/limite_contexte` | Modèle | `/limite_contexte [jetons\|off]` | Définir la limite dure de jetons de contexte |
| `/auto_tronquer` | Modèle | `/auto_tronquer [on\|off\|10-100]` | Auto-tronquer le contexte au-delà de % de la limite |
| `/top_p` | Modèle | `/top_p [valeur]` | Échantillonnage de noyau (0.0-1.0) |
| `/top_k` | Modèle | `/top_k [valeur]` | Échantillonnage Top-K |
| `/penalite_freq` | Modèle | `/penalite_freq [valeur]` | Pénalité de fréquence (-2.0 à 2.0) |
| `/penalite_pres` | Modèle | `/penalite_pres [valeur]` | Pénalité de présence (-2.0 à 2.0) |
| `/seed` | Modèle | `/seed [valeur]` | Graine aléatoire |
| `/stream` | Modèle | `/stream` | Alterner la diffusion des réponses |
| `/raisonnement` | Modèle | `/raisonnement [on\|off]` | Alterner le mode de raisonnement |
| `/effort` | Modèle | `/effort [low\|medium\|high\|none]` | Définir l'effort de raisonnement |
| `/reflexion` | Modèle | `/reflexion [on\|off]` | Alterner l'affichage des blocs de réflexion |
| `/style_reflexion` | Modèle | `/style_reflexion [style]` | Définir le style de format de réflexion |

### Commandes de Tampon de Fichier

| Mot-Clé | Catégorie | Syntaxe | Description |
|---------|-----------|---------|-------------|
| `/fichier` | Fichier | `/fichier chemin` | Charger un fichier texte dans le tampon |
| `/afficher_fichier` | Fichier | `/afficher_fichier [all]` | Afficher le contenu du tampon |
| `/vider_fichier` | Fichier | `/vider_fichier` | Vider le tampon |
| `/banque_fich{1-5}` | Fichier | `/banque_fichN chemin\|clear\|show [all]` | Gérer les banques de fichiers |
| `/banque_imag{1-5}` | Fichier | `/banque_imagN chemin\|clear\|show` | Gérer les banques d'images |
| `/charger_image` | Fichier | `/charger_image chemin <imagebank>` | Charger l'image en base64 dans la banque |
| `/mode_note` | Fichier | `/mode_note [on\|off]` | Extraire les blocs de code lors de la sauvegarde |
| `/code_uniquement` | Fichier | `/code_uniquement` | Activer le formatage de sortie de code uniquement |
| `/code_desactive` | Fichier | `/code_desactive` | Désactiver le formatage de sortie de code uniquement |
| `/multiligne` | Fichier | `/multiligne` | Alterner le mode d'entrée multiligne |
| `/sauvegarder` | Fichier | `/sauvegarder fichier [all] [nothink\|withthink]` | Sauvegarder la dernière réponse du LLM |
| `/prompt` | Fichier | `/prompt fichier` | Charger et exécuter un fichier de prompt |

### Commandes de Génération d'Images

| Mot-Clé | Catégorie | Syntaxe | Description |
|---------|-----------|---------|-------------|
| `/imaginer` | Image | `/imaginer prompt` | Générer une image à partir de texte |
| `/taille_image` | Image | `/taille_image [WxH]` | Définir/obtenir la résolution de l'image |
| `/qualite_image` | Image | `/qualite_image [standard\|hd]` | Définir/obtenir la qualité de l'image |
| `/saveimage` | Image | `/saveimage [chemin]` | Enregistrer la dernière image générée |
| `/dossier_images` | Image | `/dossier_images [chemin]` | Définir/obtenir le dossier de sortie des images |
| `/lister_images` | Image | `/lister_images` | Lister toutes les images enregistrées |
| `/afficher_image` | Image | `/afficher_image [date\|nom]` | Afficher les métadonnées de l'image |

### Commandes Shell

| Mot-Clé | Catégorie | Syntaxe | Description |
|---------|-----------|---------|-------------|
| `/lancer` | Shell | `/lancer commande [args]` | Exécuter une commande shell |
| `/lancer_securise` | Shell | `/lancer_securise` | Activer les invites de confirmation de sécurité |
| `/lancer_libre` | Shell | `/lancer_libre` | Désactiver les confirmations d'exécution shell |

### Commandes de Boucle d'Outils

| Mot-Clé | Catégorie | Syntaxe | Description |
|---------|-----------|---------|-------------|
| `/outil` | Outils | `/outil [subcmd] [args]` | Gestion du mode outil |
| `/outil on` | Outils | `/outil on` | Charger les définitions d'outils dans l'invite |
| `/outil off` | Outils | `/outil off` | Désactiver les schémas d'outils |
| `/outil lister` | Outils | `/outil lister` | Lister les outils disponibles et leur état |
| `/outil activer` | Outils | `/outil activer <tool\|all>` | Activer un outil spécifique ou tous |
| `/outil desactiver` | Outils | `/outil desactiver <tool\|all>` | Désactiver un outil spécifique ou tous |
| `/outil auto` | Outils | `/outil auto` | Activer la boucle automatique sur les sorties d'outils |
| `/outil boucle` | Outils | `/outil boucle [tours] [force]` | Exécuter la boucle d'outils avec limite |
| `/outil tours_max` | Outils | `/outil tours_max [N]` | Définir/obtenir la limite de tours maximale |
| `/outil limite_taux` | Outils | `/outil limite_taux [secondes]` | Définir la pause de délai entre les tours (secondes) |
| `/outil prompt` | Outils | `/outil prompt` | Afficher l'invite active |

### Commandes de Diagnostic

| Mot-Clé | Catégorie | Syntaxe | Description |
|---------|-----------|---------|-------------|
| `/trace` | Débogage | `/trace <subcmd> [on\|off]` | Alterner les modes de trace |
| `/trace rawpayload` | Débogage | `/trace rawpayload [on\|off]` | Tracé brut du payload de l'API |
| `/trace tps` | Débogage | `/trace tps [on\|off]` | Tracé des jetons par seconde |
| `/trace tpsperf` | Débogage | `/trace tpsperf [on\|off]` | Tracé des performances de TPS |
| `/trace imagedbg` | Débogage | `/trace imagedbg [on\|off]` | Débogage de la génération d'images |
| `/trace rerank` | Débogage | `/trace rerank [on\|off]` | Tracé de l'opération de rerank |
| `/trace agentic_loop` | Débogage | `/trace agentic_loop [on\|off]` | Tracé de la boucle agentique |
| `/deboguer` | Débogage | `/deboguer <payload\|response\|vmem>` | Paramètres du mode débogage |
| `/journalisation` | Débogage | `/journalisation [start\|end]` | Démarrer/arrêter le fichier journal |
| `/memoire` | Débogage | `/memoire [detail\|debug]` | Afficher l'utilisation mémoire (alias `/mem`) |
| `/dump` | Débogage | `/dump [varname\|all]` | Exporter le contenu des variables |

### Commandes de Base de Données

| Mot-Clé | Catégorie | Syntaxe | Description |
|---------|-----------|---------|-------------|
| `/definir_bd` | Base de données | `/definir_bd <nom\|Null>` | Connecter/initialiser/désactiver la BD |
| `/lister_bd` | Base de données | `/lister_bd` | Lister les bases de données vectorielles |
| `/rechercher_bd` | Base de données | `/rechercher_bd <requete>` | Exécuter une requête vectorielle |
| `/journal_bd` | Base de données | `/journal_bd` | Enregistrer le dernier chat en base de données |
| `/imprimer_bd` | Base de données | `/imprimer_bd [fichier]` | Exporter le contenu de la base de données |
| `/documents` | Base de données | `/documents <src>=<id>` | Définir la source pour le rerank |
| `/reclasser` | Base de données | `/reclasser "<requete>" [options]` | Exécuter le reclassement sémantique |

### Commandes de Variables

| Mot-Clé | Catégorie | Syntaxe | Description |
|---------|-----------|---------|-------------|
| `/setvar` | Variable | `/setvar <nom> <valeur>` | Définir une variable de script |
| `/loadvar` | Variable | `/loadvar <nom> [ALL\|id\|plage]` | Charger les enregistrements dans la variable |
| `/savevar` | Variable | `/savevar <nom> <fichier>` | Sauvegarder la variable dans un fichier |

### Commandes de Profil

| Mot-Clé | Catégorie | Syntaxe | Description |
|---------|-----------|---------|-------------|
| `/profile` | Profil | `/profile <subcmd> [args]` | Gestion des profils |
| `/profile list` | Profil | `/profile list` | Lister les profils disponibles |
| `/profile use` | Profil | `/profile use <nom>` | Charger un profil |
| `/profile clone` | Profil | `/profile clone <nom>` | Cloner la session actuelle |
| `/profile delete` | Profil | `/profile delete <nom>` | Supprimer un profil |
| `/profile export` | Profil | `/profile export <nom> <chemin>` | Exporter un profil |
| `/profile import` | Profil | `/profile import <chemin>` | Importer un profil |
| `/profile show` | Profil | `/profile show` | Afficher le profil actuel |
| `/profile edit` | Profil | `/profile edit` | Modifier le profil dans la TUI |

### Commandes d'Historique

| Mot-Clé | Catégorie | Syntaxe | Description |
|---------|-----------|---------|-------------|
| `!` | Historique | `! <recherche>` | Rechercher dans l'historique des commandes |

## Mots-Clés de Scripting

| Anglais | Français | Syntaxe | Description |
|---------|----------|---------|-------------|
| `set` | `definir` | `definir nom = valeur` | Affectation de variable |
| `local` | `local` | `local nom = valeur` | Variable de portée procédure |
| `if` | `si` | `si condition alors commande` | Exécution conditionnelle |
| `then` | `alors` | (fait partie de si) | Corps du conditionnel |
| `wait` | `wait` | `wait N` | Pause de N secondes |
| `defproc` | `defproc` | `defproc nom(params)` | Définir une procédure |
| `endproc` | `endproc` | `endproc` | Terminer une procédure |
| `foreach` | `pourchaque` | `pourchaque elem in tableau` | Boucle multiligne |
| `endfor` | `finpour` | `finpour` | Terminer une boucle |
| `break` | `casser` | `casser` | Quitter la boucle |
| `range` | `plage` | `plage(1:10)` | Générateur numérique |
| `lines` | `lignes` | `lignes(texte)` | Générateur de lignes |
| `#` | `#` | `# commentaire` | Commentaire |
| `def` | `def` | `def nom(params) = "modele"` | Définir une macro |
| `%` | `%` | `%nom(args)` | Appeler une macro |

## Syntaxe des Variables

| Syntaxe | Description |
|----------|-------------|
| `${nom}` | Référence à une variable |
| `definir nom = "valeur"` | Définition de variable |
| `"valeur avec espaces"` | Valeur avec doubles guillemets |
| `'valeur avec espaces'` | Valeur avec simples guillemets |
| `{filebankN}` | Référence de banque de fichiers dans les prompts |
| `{imagebankN}` | Référence de banque d'images dans les prompts |

## Opérateurs

| Opérateur | Description | Exemple |
|-----------|-------------|---------|
| `==` | Égal à | `if ${x} == "yes" then` |
| `!=` | Différent de | `if ${x} != "" then` |
| `>` | Supérieur à | `si "${AGE}" > 18 alors` |
| `<` | Inférieur à | `si "${VAL}" < 10 alors` |
| `>=` | Supérieur ou égal à | `si "${AGE}" >= 18 alors` |
| `<=` | Inférieur ou égal à | `si "${VAL}" <= 5 alors` |
| `not` | Négation | `if not ${debug} then` |

## Flux de Contrôle

| Commande | Syntaxe | Description |
|----------|---------|-------------|
| `if` | `if condition then commande` | Exécution conditionnelle |
| `wait` | `wait N` | Pause de N secondes |
| `definir` | `definir nom = valeur` | Définir une variable |
| `#` | `# commentaire` | Commentaire |

## Syntaxe Multiligne

| Mot-Clé | Syntaxe | Description |
|---------|---------|-------------|
| `/multiligne` | `/multiligne` | Démarrer un bloc multiligne |
| `;;` | `;;` | Terminer un bloc multiligne |

## Syntaxe des Macros

| Élément | Syntaxe | Description |
|---------|---------|-------------|
| Définition | `def nom(params) = "modele"` | Définir une macro |
| Sans paramètre | `def nom() = "modele"` | Définir une macro sans paramètre |
| Invocation | `%nom(args)` | Appeler une macro |
| Variable de modèle | `{param}` | Emplacement de paramètre |

### Exemples de Macros

```dsl
# Macros sans paramètres
def regen() = "Regenerate all source code"
def build() = "Build the project with optimized settings"

# Macros paramétrées
def expert_prompt(topic) = "Act as an expert in {topic}. Provide detailed, accurate, and insightful information about {topic}."

def language_comparison(lang1, lang2) = "Compare {lang1} and {lang2} programming languages. Discuss their similarities, differences, syntax variations, performance characteristics, and typical use cases."
```

## Messages d'Erreur

| Erreur | Anglais | Espagnol | Français | Chinois | Italien |
|--------|---------|---------|--------|---------|---------|
| Fichier non trouvé | "Error: File not found" | "Error: Archivo no encontrado" | "Erreur: Fichier introuvable" | "错误: 文件没有找到" | "Errore: File non trovato" |
| Macro non définie | "ERROR: Macro 'X' not defined" | "ERROR: Macro 'X' no definido" | "ERREUR: Macro 'X' non définie" | "错误: 宏 'X' 未定义" | "ERRORE: Macro 'X' non definita" |
| Arguments incorrects | "ERROR: Macro 'X' expects N arguments, got M" | "ERROR: Macro 'X' espera N argumentos, obtuvo M" | "ERREUR: Macro 'X' attend N arguments, reçu M" | "错误: 宏 'X' 需要 N 个参数，得到 M 个" | "ERRORE: Macro 'X' aspetta N argomenti, ottenuti M" |

---

# Meilleures Pratiques

## Directives d'Écriture de Scripts

### 1. Nommage des Variables
- Utilisez le **snake_case** pour les noms descriptifs : `nombre_articles`, `nom_modele`
- Lettres uniques (`x`, `y`, `z`) réservées aux paramètres de script
- MAJUSCULES pour les constantes

### 2. Style des Commentaires
```dsl
# Commentaire sur toute une ligne
definir var = "valeur"  # Commentaire en ligne

# En-têtes de section
# ============================================
# SECTION DE TRADUCTION
# ============================================
```

### 3. Structure de Script
```dsl
# En-tête avec usage
# Script : description
# Usage : /script script.chatdsl [params]

# Gestion des paramètres
if ${x} != "" then definir param1 = ${x}
if ${param1} == "" then definir param1 = "default"

# Configuration
definir base_dir = "output"
/modele gemini_flash

# Logique principale
/fichier input.txt
process this...
/sauvegarder output.txt

# Nettoyage (optionnel)
/vider_fichier
/echo "Done"
```

### 4. Modèles Courants

#### Valeurs de Paramètres par Défaut
```dsl
if ${x} != "" then definir var = ${x}
if ${var} == "" then definir var = "default"
```

#### Sélection Conditionnelle de Modèle
```dsl
if ${fast} then /modele gemini_flash
if not ${fast} then /modele openai_gpt4
```

## Gestion des Erreres

### Problèmes Courants et Solutions

| Problème | Solution |
|----------|----------|
| Variable ne s'étend pas | Vérifier la syntaxe `${nom}` (sans espaces) |
| Fichier non trouvé | Utiliser `/echo` pour vérifier le chemin étendu |
| Multiligne ne s'arrête pas | S'assurer d'avoir `;;` sur sa propre ligne, puis `/multiligne` |
| Définir une valeur avec espaces | Utiliser des guillemets doubles : `definir var = "valeur avec espaces"` |
| Antislash dans une valeur | Non autorisé - utiliser des barres obliques classiques |
| Commande non reconnue | Vérifier les fautes de frappe et le préfixe `/` |

## Conseils de Performance

### Limites de Taux (Rate Limiting)
```dsl
# Entre les appels de modèle
/modele gemini_flash
prompt 1
/sauvegarder response1.txt
wait 2  # Pause de 2 secondes

/modele openai_gpt4
prompt 2
/sauvegarder response2.txt
```

### Gestion du Tampon
```dsl
# Vider le tampon entre les opérations non liées
/vider_fichier

# Prévenir la pollution de contexte
/fichier new_context.txt
```

### Réduire la Consommation de Jetons
```dsl
# Utiliser /code_uniquement pour la génération de code
/code_uniquement
Write Python code to solve this problem.
/code_desactive
```

---

# Référence Rapide

## Catégories de Commande

### Système
- `/aide` - Afficher l'aide
- `/echo` - Imprimer du texte
- `/quitter` - Quitter la session
- `/script` - Exécuter le script
- `/source` - Exécuter le fichier de script

### Modèle
- `/modele [alias]` - Basculer de modèle
- `/systeme [prompt]` - Définir le message système
- `/temp [valeur]` - Définir la température
- `/max_jetons [valeur]` - Définir le max de jetons
- `/raisonnement [on|off]` - Alterner le raisonnement
- `/effort [low|medium|high|none]` - Définir l'effort de raisonnement

### Fichier
- `/fichier chemin` - Charger dans le tampon
- `/banque_fich1-5` - Gestion des banques de fichiers
- `/sauvegarder fichier [all] [nothink|withthink]` - Enregistrer la réponse
- `/multiligne` - Prompts complexes
- `/prompt fichier` - Exécuter le fichier de prompt

### Image
- `/imaginer prompt` - Générer une image
- `/taille_image WxH` - Définir la résolution
- `/saveimage [chemin]` - Enregistrer l'image
- `/banque_imag1-5` - Gestion des banques d'images

### Base de Données
- `/definir_bd nom` - Connecter le stockage
- `/rechercher_bd "query"` - Recherche vectorielle
- `/journal_bd` - Enregistrer la réponse
- `/reclasser` - Reclassement sémantique

### Outil
- `/outil on` - Activer les outils
- `/outil boucle [tours] [force]` - Exécution autonome
- `/outil lister` - Lister les outils
- `/outil activer all` - Activer tous les outils

### Débogage
- `/trace <type> [on|off]` - Activer le traçage
- `/memoire [detail|debug]` - Utilisation de la mémoire
- `/dump [var|all]` - Exporter des variables

### Profil
- `/profile list` - Lister les profils
- `/profile use nom` - Charger le profil
- `/profile clone nom` - Cloner la session

## Éléments de Scripting

### Variables
```dsl
definir nom = "valeur"
${nom}
```

### Variables Locales (Procédures)
```dsl
local nom = "valeur"
```

### Conditions
```dsl
if ${x} == "yes" then /commande
if not ${debug} then /echo "quiet"
```

### Boucles Foreach
```dsl
pourchaque fichier in ${liste_fichiers}
    /echo Traitement de ${fichier}...
    # Logique ici
finpour
```

### Sortie de Boucle avec Break
```dsl
pourchaque num in range(1:10)
    if ${num} == "5" then casser
    /echo ${num}
finpour
```

### Générateurs
```dsl
# Plage de nombres (inclusif)
pourchaque i in range(1:5)
    /echo ${i}
finpour

# Plage avec pas
pourchaque i in range(1:10:2)
    /echo ${i}
finpour

# Lignes de texte
pourchaque ligne in ${texte}
    /echo ${ligne}
finpour
```

### Attente
```dsl
wait 2
```

### Multiligne
```dsl
/multiligne
Your prompt here
;;
/multiligne
```

### Macros
```dsl
# Définir
def expert_prompt(topic) = "Act as an expert in {topic}."

# Invocation
%expert_prompt(Python)
```

---

# Ressources

## Fichiers de Documentation

- **Guide du langage ChatDSL** (`chatdsl_language.md`) - Référence complète du langage avec les correspondances de commandes
- **Guide des compétences ChatDSL** (`chatdsl_skill.md`) - Modèles de script complets
- **Implémentation des macros ChatDSL** (`chatdsl_macro_implementation.md`) - Rapport d'implémentation technique

## Fichiers de Configuration

- `~/.config/chatybot/chat_config.toml` - Configuration modèle de l'utilisateur
- `~/.config/chatybot/profiles/` - Profils de l'utilisateur
- `src/chatybot/chat_config.toml` - Configuration modèle par défaut
- `src/chatybot/tools_config.toml` - Définitions des outils
- `src/chatybot/macro.chatdsl` - Définitions des macros par défaut
- `src/chatybot/translations.json` - Traductions multilingues

## Fichiers du Projet

- `chatdsl_bnf.txt` - Spécification de la grammaire formelle
- `script_param_implementation.md` - Détails sur le passage de paramètres
- `dsl_test/` - Scripts de test démontrant toutes les fonctionnalités

---

# Prise en Main

## Démarrage Rapide

1. **Installer Chatybot**
   ```bash
   pip install chatybot
   ```

2. **Configurer les Clés API**
   ```bash
   # Copier la configuration par défaut dans le répertoire utilisateur
   mkdir -p ~/.config/chatybot
   cp src/chatybot/chat_config.toml ~/.config/chatybot/
   
   # Modifier avec vos clés API
   chatybot-config
   ```

3. **Lancer Chatybot**
   ```bash
   chatybot
   ```

4. **Exécuter un Script ChatDSL**
   ```bash
   chat --> /script mon_script.chatdsl x=valeur1 y=valeur2
   ```

## Commandes de Base

- `/aide` - Voir toutes les commandes disponibles
- `/modele` - Basculer entre les modèles
- `/fichier chemin` - Charger des fichiers de contexte
- `/echo "texte"` - Sortie de débogage
- `/sauvegarder chemin` - Enregistrer les réponses

## Exemples de Scripts

Consultez le répertoire `dsl_test/` pour des exemples fonctionnels :
- `translate.chatdsl` - Processus de traduction
- `compare.chatdsl` - Comparaison de fichiers
- `evaluate.chatdsl` - Évaluation multi-modèle
- `batch.chatdsl` - Traitement par lots

---

*(Fin du Guide Complet ChatDSL)*

---

## Historique des Versions

| Version | Date | Changements |
|---------|------|-------------|
| 1.0 | 2025-07-23 | Version corrigée initiale basée sur le code source v0.6.4 |

---

## Notes de l'Auteur

Ce guide est la version corrigée basée sur une révision approfondie du code source de Chatybot v0.6.4. Toutes les syntaxes de commandes, formats de configuration et exemples de scripts ont été vérifiés par rapport à l'implémentation réelle.
