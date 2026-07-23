# Profile Manager System Design

## Overview
Create a comprehensive profile management system for chatybot that simplifies the creation and management of ChatDSL profile scripts. The system provides preset templates, a guided TUI editor, and full profile lifecycle management (create, edit, clone, export, import, delete).

## Features

### 1. Profile Management Commands
- `/profile edit [name]` - Open TUI to create/edit ChatDSL profiles
- `/profile list` - List available profiles
- `/profile use [name]` - Set profile as default
- `/profile clone [name]` - Copy profile with modifications
- `/profile delete [name]` - Remove profile
- `/profile export [name]` - Save profile to file
- `/profile import <file>` - Load profile from file

### 2. Three Preset Templates
- **Coding Profile**: Development-focused with tools enabled and TPS trace
- **General Profile**: Balanced assistance with tool restrictions
- **Explorer Profile**: Read-only exploration mode for safe browsing

## File Structure

```
.config/
  chatybot/
    profiles/           # Profile scripts directory
      coding.chatdsl    # Development profile
      general.chatdsl   # General assistance profile
      explorer.chatdsl  # Read-only exploration profile
      user1.chatdsl    # User-customized profile
    tools_config.toml   # Enhanced with profile management
    chat_config.toml    # Existing model configuration
```

## Configuration Format

### tools_config.toml (Enhanced)
```toml
[config]
default_profile = ""        # Empty for no default, or "coding" for preset
profile_dir = "~/.config/chatybot/profiles"
enable_profile_edit = true

[profiles.templates]
coding.model = "devstral_1"
coding.tools_enabled = "auto"
coding.trace_tps = true

general.model = "mistral_1"
general.tools_enabled = "off"
general.trace_tps = false

explorer.model = "mistral_1"
explorer.tools_enabled = "read_only"
explorer.trace_tps = false
```

### Profile Structure
```bash
---
name: "Profile Name"
description: "Brief description"
model: "devstral_1"
tools_enabled: "auto"/"on"/"off"/"read_only"
trace_tps: true/false
reasoning_mode: true/false
show_thinking: true/false
tool_mode: true/false

# Optional Settings
reasoning_effort: "auto"/"low"/"medium"/"high"
max_tool_calls: 25
temperature: 0.7
```

## Profile Templates

### 1. Coding Profile (`coding.chatdsl`)
```bash
# coding.chatdsl
---
name: "Development Profile"
description: "Optimized for coding, debugging, and technical assistance"
model: "devstral_1"
tools_enabled: "auto"
trace_tps: true
reasoning_mode: true
reasoning_effort: "medium"

# Auto-commands
tool auto
tool loop on
reasoning effort medium
trace tps trace_tps
tool prompt
tool max_turns 25

%s setup_python {
  tool enable python_execute
  tool enable file_edit
}

%s setup_debug {
  tool auto
  tool loop on
  trace agentic_loop trace_rerank
}

%s setup_profile {
  %s setup_debug
  tool auto
}
```

### 2. General Profile (`general.chatdsl`)
```bash
# general.chatdsl
---
name: "General Assistance Profile"
description: "Balanced assistance with restricted tool access"
model: "mistral_1"
tools_enabled: "off"
trace_tps: false
reasoning_mode: false
tool_mode: false

# Restricted tools
tool off

# Basic commands
reasoning off

%s basic_assist {
  tool auto
}
```

### 3. Explorer Profile (`explorer.chatdsl`)
```bash
# explorer.chatdsl
---
name: "Explorer Mode"
description: "Safe read-only exploration for browsing and querying"
model: "mistral_1"
tools_enabled: "read_only"
trace_tps: false
reasoning_mode: false
tool_mode: false

# Read-only tools
tool only read
tool disallow execute_shell
tool disallow file_edit

%s browse_directory {
  filebank list
  document list
}

%s explore_context {
  echo "Explorer mode: Analysis mode enabled"
  tool auto
}
```

## TUI Profile Editor

### Screen Layout

#### Main Menu
- **Header**: Mode indicator (Create/Edit), profile name input
- **Preset Selection**: 3 preset buttons with preview
- **Settings Section**: 
  - Model dropdown (from chat_config.toml)
  - Tools configuration (Auto/On/Off/Read-only)
  - Trace options (TPS, Agentic, Response, etc.)
  - Reasoning configuration
  - Additional parameters (Temp, max_calls)
- **Macros Section**: List/edit ChatDSL macros
- **Preview Section**: Shows generated profile
- **Action Buttons**: Save, Apply, Cancel, Reset

#### Preset Selection Screen
```
[Coding]    Auto tools, TPS enabled, Reasoning on
[General]   Tools off, All traces disabled, Reasoning off  
[Explorer]  Read-only only, All traces disabled, Reasoning off
```

### TUI Navigation
- **Arrow Keys**: Navigate between fields
- **Enter/Space**: Select/activate items
- **Tab**: Move to next field group
- **Escape**: Return to previous screen
- **Ctrl+S**: Save current changes

## Integration Points

### Command Line Arguments (chatybot_app.py)

```python
# Added to argument parser
parser.add_argument(
    "--profile-edit",
    help="Open profile editor to create/edit ChatDSL profiles",
    action="store_true"
)
parser.add_argument(
    "--profile-list",
    help="List all available profiles",
    action="store_true"
)
```

### Profile Loading Logic (chatybot_app.py:5070-5105)

```python
# Enhanced profile loading
if profile_path:
    expanded_path = os.path.expanduser(profile_path)
    
    # Check if it's a profile directory
    if os.path.isdir(expanded_path):
        app.load_profile_directory(expanded_path)
    # Handle regular profile file
    elif profile_path.endswith('.chatdsl'):
        app.execute_profile_from_file(expanded_path)
    # Continue with existing file loading logic...
```

### Profile System (profile_manager.py - New)

```python
class Profile:
    def __init__(self, name, description, model, tools_enabled, trace_tps):
        self.name = name
        self.description = description
        self.model = model
        self.tools_enabled = tools_enabled
        self.trace_tps = trace_tps
        self.reasoning_mode = True
        self.show_thinking = True
        self.tool_mode = False
        self.macros = []
        self.settings = {}
    
    def apply_to_app(self, app):
        """Apply profile settings to the application"""
        app.config_manager.set_active_model(self.model)
        app.tool_mode = (self.tools_enabled in ["on", "auto"])
        app.reasoning_mode = getattr(self, 'reasoning_mode', True)
        app.show_thinking = getattr(self, 'show_thinking', True)
        
        if self.trace_tps:
            app.trace_tps = True
```

## Profile Editor Flow

### Step 1: Preset Selection
1. Display preset options with brief descriptions
2. User selects template or chooses "Custom" for blank profile
3. System loads preset values into editor

### Step 2: Basic Settings
1. Model selection from existing chat_config.toml models
2. Tools configuration with validation
3. Trace settings options
4. Reasoning configuration
5. Additional parameters (validated ranges)

### Step 3: Macro Management
1. List existing macros
2. Add new macros using guided input
3. Edit/delete existing macros
4. Preview macro usage

### Step 4: Validation
1. Profile name uniqueness check
2. Settings compatibility validation
3. Syntax validation for ChatDSL code
4. Tool configuration validation

### Step 5: Save/Apply
1. Save as new profile
2. Apply to current session
3. Export to file
4. Return to main menu

## Implementation Files

### 1. tools_config.toml (src/chatybot/)
```toml
[config]
default_profile = ""
profile_dir = "profiles"
enable_profile_edit = true

[profiles.templates]
coding.model = "devstral_1"
coding.tools_enabled = "auto"
coding.trace_tps = true
coding.reasoning_effort = "medium"

general.model = "mistral_1"
general.tools_enabled = "off"
general.trace_tps = false
general.reasoning_mode = false

explorer.model = "mistral_1"
explorer.tools_enabled = "read_only"
explorer.trace_tps = false
explorer.reasoning_mode = false
explorer.tool_mode = false
```

### 2. profile_manager.py (New - src/chatybot/)
- Profile class definition
- Profile loading/saving functions
- TUI profile editor class
- Integration with chatybot_app.py

### 3. profile_editor.tui (New - src/chatybot/)
- curses-based TUI for profile editing
- Screen managers
- Input handlers
- Profile validation logic

## Usage Examples

### Create a Profile
```
# First run - open TUI
chatybot --profile-edit

# During TUI:
# Select "Coding" preset
# Customize settings as needed
# Add ChatDSL macros
# Save profile as "my_coding_profile"

# Use the profile
chatybot --profile ~/config/chatybot/profiles/my_coding_profile.chatdsl
```

### List Profiles
```
chatybot --profile-list

Available Profiles:
- coding.chatdsl (Development Profile)
- general.chatdsl (General Assistance)  
- explorer.chatdsl (Read-only Explorer)
- my_coding_profile.chatdsl (Custom)
```

### Clone and Modify
```
# Clone existing profile
chatybot --profile-edit cloned_profile --clone coding

# Export profile
chatybot --profile-export my_profile ~/path/to/export.chatdsl

# Import profile
chatybot --profile-import ~/path/to/imported.chatdsl
```

## Testing

### Profile Validation Tests
- Profile name uniqueness
- File format validation
- Tool configuration compatibility
- Model availability checks

### TUI Navigation Tests
- Screen transitions
- Input handling
- Focus management
- Error display

### Integration Tests
- Profile loading
- Profile application to app state
- Export/import round-trip
- Default profile behavior

### Preset Template Tests
- Template value validation
- Compatibility with app settings
- Macro injection
- Override handling
```