#!/usr/bin/env bash
# ==============================================================================
# Chatybot API Key Setup Script
# Interactively configure API keys for Chatybot and save to .env or shell profile.
# Compatible with macOS default bash 3.2, Linux bash 4/5, and zsh.
# ==============================================================================

set -e

# ANSI color codes
BOLD='\033[1m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${BOLD}${BLUE}======================================================${NC}"
echo -e "${BOLD}${BLUE}          Chatybot API Key Setup Assistant           ${NC}"
echo -e "${BOLD}${BLUE}======================================================${NC}"
echo -e "Chatybot reads API keys from environment variables or .env files."
echo -e "In ${CYAN}chat_config.toml${NC}, model definitions reference the ${BOLD}name${NC} of these"
echo -e "variables (e.g. api_key = \"MISTRAL_API_KEY\"), keeping secrets secure.\n"

# Array of supported keys: format is "VAR_NAME|Display Name|Default Preset?|Help URL"
KEYS=(
    "MISTRAL_API_KEY|Mistral AI|Default Preset|https://console.mistral.ai/"
    "OPENAI_API_KEY|OpenAI (GPT-4o, o1, o3)|Optional|https://platform.openai.com/api-keys"
    "OPENROUTER_API_KEY|OpenRouter (Claude, Llama, DeepSeek)|Optional|https://openrouter.ai/keys"
    "GEMINI_API_KEY|Google Gemini (2.5 Flash, 1.5 Pro)|Optional|https://aistudio.google.com/app/apikey"
    "ANTHROPIC_API_KEY|Anthropic (Claude 3.5)|Optional|https://console.anthropic.com/"
    "NVIDIA_API|NVIDIA NIM / Build|Optional|https://build.nvidia.com/"
    "GROQ_API_KEY|Groq (Llama, Mixtral)|Optional|https://console.groq.com/keys"
    "DEEPSEEK_API_KEY|DeepSeek|Optional|https://platform.deepseek.com/"
    "COHERE_API_KEY|Cohere|Optional|https://dashboard.cohere.com/api-keys"
    "HF_API_KEY|Hugging Face Token|Optional|https://huggingface.co/settings/tokens"
    "JINA_API_KEY|Jina AI (Search / Rerank)|Optional|https://jina.ai/"
)

# Load existing .env if present in current directory to prepopulate defaults
if [ -f ".env" ]; then
    while IFS='=' read -r key val || [ -n "$key" ]; do
        key=$(echo "$key" | tr -d '[:space:]')
        val=$(echo "$val" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/^["'"'"']//' -e 's/["'"'"']$//')
        if [[ ! "$key" =~ ^# && -n "$key" && -n "$val" ]]; then
            eval "val_existing=\"\${$key}\""
            if [ -z "$val_existing" ]; then
                eval "export $key=\"$val\""
            fi
        fi
    done < ".env"
fi

COLLECTED_NAMES=()
COLLECTED_VALS=()

mask_key() {
    local val="$1"
    local len=${#val}
    if [ "$len" -le 8 ]; then
        echo "********"
    else
        local prefix="${val:0:4}"
        local suffix="${val: -4}"
        echo "${prefix}...${suffix}"
    fi
}

echo -e "${YELLOW}Press [Enter] to keep current/blank value, or type a new key.${NC}\n"

for entry in "${KEYS[@]}"; do
    IFS='|' read -r var_name display_name status help_url <<< "$entry"
    eval "current_val=\"\${$var_name}\""
    
    if [ -n "$current_val" ]; then
        masked=$(mask_key "$current_val")
        echo -e "${GREEN}● ${display_name}${NC} (${CYAN}${var_name}${NC}) [${status}]"
        echo -e "  Key URL: ${help_url}"
        read -r -p "  Value [current: ${masked}]: " user_input || true
        if [ -n "$user_input" ]; then
            COLLECTED_NAMES+=("$var_name")
            COLLECTED_VALS+=("$user_input")
        else
            COLLECTED_NAMES+=("$var_name")
            COLLECTED_VALS+=("$current_val")
        fi
    else
        echo -e "${BOLD}○ ${display_name}${NC} (${CYAN}${var_name}${NC}) [${status}]"
        echo -e "  Key URL: ${help_url}"
        read -r -p "  Value [leave blank to skip]: " user_input || true
        if [ -n "$user_input" ]; then
            COLLECTED_NAMES+=("$var_name")
            COLLECTED_VALS+=("$user_input")
        fi
    fi
    echo ""
done

# Check if at least one key was set or retained
has_keys=false
for v in "${COLLECTED_VALS[@]}"; do
    if [ -n "$v" ]; then
        has_keys=true
        break
    fi
done

if [ "$has_keys" = false ]; then
    echo -e "${YELLOW}No API keys were provided or retained.${NC}"
    exit 0
fi

# Determine shell profile file
DEFAULT_SHELL_PROFILE="$HOME/.bashrc"
if [ -n "$ZSH_VERSION" ] || [ "$(basename "$SHELL")" = "zsh" ]; then
    DEFAULT_SHELL_PROFILE="$HOME/.zshrc"
fi

echo -e "${BOLD}${BLUE}------------------------------------------------------${NC}"
echo -e "${BOLD}Where would you like to save your API keys?${NC}"
echo -e "  1) ${GREEN}Local .env file${NC} (./.env) - Recommended for project workspace"
echo -e "  2) ${GREEN}Global Chatybot .env${NC} (~/.config/chatybot/.env) - Loaded everywhere"
echo -e "  3) ${GREEN}Shell startup profile${NC} (${DEFAULT_SHELL_PROFILE}) - Persistent exports"
echo -e "  4) ${GREEN}Export to current session only${NC} (Prints export commands)"
read -r -p "Select an option [1-4, default: 1]: " save_choice || true

case "$save_choice" in
    2)
        DEST_DIR="$HOME/.config/chatybot"
        mkdir -p "$DEST_DIR"
        TARGET_FILE="$DEST_DIR/.env"
        ;;
    3)
        TARGET_FILE="$DEFAULT_SHELL_PROFILE"
        ;;
    4)
        TARGET_FILE=""
        ;;
    *)
        TARGET_FILE=".env"
        ;;
esac

total_count=${#COLLECTED_NAMES[@]}

if [ "$save_choice" = "3" ]; then
    echo -e "\nAppending export statements to ${CYAN}${TARGET_FILE}${NC}..."
    {
        echo ""
        echo "# --- Chatybot API Keys (Added by setup_keys.sh) ---"
        for ((i=0; i<total_count; i++)); do
            k="${COLLECTED_NAMES[i]}"
            v="${COLLECTED_VALS[i]}"
            if [ -n "$v" ]; then
                echo "export ${k}=\"${v}\""
                eval "export ${k}=\"${v}\""
            fi
        done
    } >> "$TARGET_FILE"
    echo -e "${GREEN}✓ Successfully saved keys to ${TARGET_FILE}!${NC}"
    echo -e "Run ${CYAN}source ${TARGET_FILE}${NC} to activate in this terminal, or restart your shell."

elif [ -n "$TARGET_FILE" ]; then
    echo -e "\nWriting keys to ${CYAN}${TARGET_FILE}${NC}..."
    {
        echo "# Chatybot Environment Configuration"
        echo "# Generated by setup_keys.sh on $(date)"
        for ((i=0; i<total_count; i++)); do
            k="${COLLECTED_NAMES[i]}"
            v="${COLLECTED_VALS[i]}"
            if [ -n "$v" ]; then
                echo "${k}=\"${v}\""
                eval "export ${k}=\"${v}\""
            fi
        done
    } > "$TARGET_FILE"
    chmod 600 "$TARGET_FILE"
    echo -e "${GREEN}✓ Successfully created ${TARGET_FILE} (permissions set to 600)!${NC}"

else
    echo -e "\n${BOLD}Run these commands in your shell to activate:${NC}"
    for ((i=0; i<total_count; i++)); do
        k="${COLLECTED_NAMES[i]}"
        v="${COLLECTED_VALS[i]}"
        if [ -n "$v" ]; then
            echo "export ${k}=\"${v}\""
            eval "export ${k}=\"${v}\""
        fi
    done
fi

echo -e "\n${BOLD}${GREEN}Setup complete!${NC}"
echo -e "To verify your active keys inside Chatybot, start the app and run ${CYAN}/env${NC}:"
echo -e "  ${BOLD}chatybot${NC}"
echo -e "  chat --> ${CYAN}/env${NC}"
echo -e "  chat --> ${CYAN}/listmodels${NC}\n"
