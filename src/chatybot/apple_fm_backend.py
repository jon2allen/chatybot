"""Apple Foundation Model backend — on-device inference via apple-fm-sdk.

This module isolates all platform checks, import guards, and SDK session
management for the ``apple_fm`` model type. It is imported lazily only when
a user sends a prompt to an apple_fm model, so chatybot runs fine on
platforms where the SDK is unavailable.

Requirements (all checked at runtime, not install time):
  - macOS 26.0+ on Apple Silicon
  - Xcode 26.0+ with the SDK agreement accepted
  - apple-fm-sdk Python package (pip install chatybot[apple_fm])
  - Apple Intelligence turned on in System Settings
"""

import sys
import platform
import json
import logging
from typing import Optional, Tuple, List, Any

logger = logging.getLogger(__name__)


def is_platform_supported() -> bool:
    """True only on macOS 26+ on Apple Silicon."""
    if sys.platform != "darwin":
        return False
    try:
        version_str = platform.mac_ver()[0]
        parts = tuple(int(x) for x in version_str.split(".")[:2])
        return parts >= (26, 0)
    except Exception:
        return False


try:
    import apple_fm_sdk as fm
    _SDK_AVAILABLE = True
    _IMPORT_ERROR: Optional[str] = None
except ImportError as e:
    fm = None
    _SDK_AVAILABLE = False
    _IMPORT_ERROR = str(e)


def check_available() -> Tuple[bool, str]:
    """Check whether the Apple Foundation Model can be used on this system.

    Returns:
        (is_ready, reason) — if not ready, reason explains what to do.
    """
    if not is_platform_supported():
        return False, "Apple Foundation Model requires macOS 26+ on Apple Silicon."
    if not _SDK_AVAILABLE:
        return False, (
            "apple-fm-sdk is not installed. "
            "Install with: pip install apple-fm-sdk  "
            "(or: pip install 'chatybot[apple_fm]' — quotes needed in zsh).  "
            "Requires Xcode 26+ with the SDK agreement accepted."
        )
    return True, ""


# Cached model instance — SystemLanguageModel is heavy to create
_model = None

# Maps SystemLanguageModelUnavailableReason enum values to human-readable messages
_UNAVAILABLE_MESSAGES = {
    "APPLE_INTELLIGENCE_NOT_ENABLED": (
        "Apple Intelligence is not enabled. Turn it on in System Settings > Apple Intelligence."
    ),
    "DEVICE_NOT_ELIGIBLE": (
        "This device does not support Apple Foundation Models (requires Apple Silicon M1+)."
    ),
    "MODEL_NOT_READY": (
        "The model is still downloading. Wait for it to finish in System Settings > Apple Intelligence."
    ),
    "UNKNOWN": "Apple Foundation Model is unavailable for an unknown reason.",
}


def _format_unavailable_reason(reason) -> str:
    """Map a SystemLanguageModelUnavailableReason to a human-readable message."""
    if reason is None:
        return "Apple Foundation Model is not available."
    name = getattr(reason, "name", str(reason))
    return _UNAVAILABLE_MESSAGES.get(name, f"Apple Foundation Model is not available: {name}")


def get_model() -> Tuple[Optional[object], str]:
    """Get or create the cached SystemLanguageModel.

    Returns:
        (model, error) — if error is non-empty, model is None.
    """
    global _model
    if _model is not None:
        return _model, ""
    if not _SDK_AVAILABLE:
        return None, "apple-fm-sdk is not installed."

    model = fm.SystemLanguageModel()
    is_available, reason = model.is_available()
    if not is_available:
        return None, _format_unavailable_reason(reason)
    _model = model
    return _model, ""


def create_session(
    instructions: Optional[str] = None,
    tools: Optional[List[Any]] = None,
) -> Tuple[Optional[object], str]:
    """Create a new LanguageModelSession for a single completion.

    A fresh session is created per call so that conversation history is
    managed by chatybot (not accumulated by the SDK session).

    Args:
        instructions: System message / instructions for the session.
        tools: Optional list of fm.Tool instances for native tool calling.

    Returns:
        (session, error) — if error is non-empty, session is None.
    """
    model, err = get_model()
    if err:
        return None, err

    kwargs = {"model": model}
    if instructions:
        kwargs["instructions"] = instructions
    if tools:
        kwargs["tools"] = tools

    session = fm.LanguageModelSession(**kwargs)
    return session, ""


async def respond(session, prompt: str, options=None) -> str:
    """Send a prompt to the session and return the complete response text.

    Args:
        session: A LanguageModelSession.
        prompt: The prompt string.
        options: Optional GenerationOptions (temperature, max tokens, sampling).
    """
    kwargs = {"prompt": prompt}
    if options is not None:
        kwargs["options"] = options
    response = await session.respond(**kwargs)
    return str(response)


async def stream_response(session, prompt: str, options=None):
    """Yield text chunks from the model as they are generated.

    Args:
        session: A LanguageModelSession.
        prompt: The prompt string.
        options: Optional GenerationOptions (temperature, max tokens, sampling).

    Usage:
        async for chunk in stream_response(session, prompt):
            print(chunk, end="", flush=True)
    """
    kwargs = {"prompt": prompt}
    if options is not None:
        kwargs["options"] = options
    async for chunk in session.stream_response(**kwargs):
        yield chunk


def build_sampling_mode(top_k=None, top_p=None, seed=None):
    """Build a SamplingMode from chatybot's top_k, top_p, and seed settings.

    The SDK's SamplingMode.random() allows only one of top (top-k) or
    probability_threshold (top-p). If both are set, top_k takes precedence.

    Returns None if no sampling parameters are set (uses SDK default).
    """
    if not _SDK_AVAILABLE:
        return None

    has_top_k = top_k is not None and top_k not in ("off", "none", "disable", False)
    has_top_p = top_p is not None and top_p not in ("off", "none", "disable", False)
    has_seed = seed is not None

    if not has_top_k and not has_top_p and not has_seed:
        return None

    # Build SamplingMode.random() kwargs
    rand_kwargs = {}
    if has_top_k:
        rand_kwargs["top"] = int(top_k)
    elif has_top_p:
        rand_kwargs["probability_threshold"] = float(top_p)

    if has_seed:
        rand_kwargs["seed"] = int(seed)

    return fm.SamplingMode.random(**rand_kwargs)


def build_generation_options(temperature=None, maximum_response_tokens=None, sampling=None):
    """Build a GenerationOptions instance from chatybot parameters.

    Returns None if no options are set (uses SDK defaults).
    """
    if not _SDK_AVAILABLE:
        return None

    kwargs = {}
    if temperature is not None:
        kwargs["temperature"] = temperature
    if maximum_response_tokens is not None:
        kwargs["maximum_response_tokens"] = maximum_response_tokens
    if sampling is not None:
        kwargs["sampling"] = sampling

    if not kwargs:
        return None

    return fm.GenerationOptions(**kwargs)


# ---------------------------------------------------------------------------
# Native tool calling bridge
# ---------------------------------------------------------------------------

# Maps TOML parameter type strings to Python types
_TOML_TYPE_MAP = {
    "string": str,
    "integer": int,
    "boolean": bool,
    "number": float,
    "float": float,
}


def _create_generable_class(tool_name: str, parameters: dict) -> type:
    """Dynamically create an @fm.generable class from TOML parameter definitions.

    The resulting class has one field per parameter, each annotated with its
    Python type and described via fm.guide(). Optional parameters include
    "(optional)" in their description so the model knows it can omit them.
    """
    annotations = {}
    attrs = {}

    for param_name, param_meta in (parameters or {}).items():
        toml_type = param_meta.get("type", "string")
        py_type = _TOML_TYPE_MAP.get(toml_type, str)
        desc = param_meta.get("description", "")
        optional = param_meta.get("optional", False)

        if optional:
            desc_text = f"{desc} (optional)"
        else:
            desc_text = desc

        annotations[param_name] = py_type
        attrs[param_name] = fm.guide(desc_text)

    # @fm.generable requires at least one type-annotated field
    if not annotations:
        annotations["_no_params"] = str
        attrs["_no_params"] = fm.guide("This tool takes no parameters")

    attrs["__annotations__"] = annotations

    cls = type(f"{tool_name}_Args", (), attrs)
    cls = fm.generable(f"{tool_name} parameters")(cls)
    return cls


def _create_tool_wrapper(tool_name: str, tool_meta: dict, app) -> type:
    """Create an fm.Tool subclass that delegates to chatybot's dispatch_tool().

    Returns a class (not an instance) so the caller can instantiate it.
    """
    generable_cls = _create_generable_class(tool_name, tool_meta.get("parameters", {}))
    tool_desc = tool_meta.get("description", "No description")
    params_meta = tool_meta.get("parameters", {})

    class _ChatybotTool(fm.Tool):
        name = tool_name
        description = tool_desc

        @property
        def arguments_schema(self) -> fm.GenerationSchema:
            return generable_cls.generation_schema()

        async def call(self, args: fm.GeneratedContent) -> str:
            # Extract arguments from GeneratedContent
            arg_dict = {}
            for param_name in params_meta:
                param_type = _TOML_TYPE_MAP.get(
                    params_meta[param_name].get("type", "string"), str
                )
                try:
                    val = args.value(param_type, for_property=param_name)
                    if val is not None:
                        arg_dict[param_name] = val
                except Exception:
                    pass

            invocation = json.dumps({"tool": tool_name, "arguments": arg_dict})
            logger.debug("Apple FM tool call: %s", invocation)

            try:
                result = await app.dispatch_tool(invocation)
                return str(result) if result else ""
            except Exception as e:
                return f"Error: {e}"

    return _ChatybotTool


# Schema for the built-in ask_user tool (not in tools_config.toml)
_ASK_USER_SCHEMA = {
    "prompt": {"type": "string", "description": "The question to ask the user", "optional": False},
    "choices": {"type": "string", "description": "Comma-separated choices for the user", "optional": True},
    "question_type": {"type": "string", "description": "Type of question: 'text' or 'choice'", "optional": True},
    "target_variable": {"type": "string", "description": "Script variable name to store the answer", "optional": True},
}


def build_tools(app) -> List[Any]:
    """Build fm.Tool instances from chatybot's tool configuration.

    Reads tools_config.toml via app._load_tools_config(), creates an fm.Tool
    wrapper for each enabled tool, and includes the built-in ask_user tool.

    Returns a list of fm.Tool instances, or an empty list if the SDK is
    unavailable or no tools are configured.
    """
    if not _SDK_AVAILABLE:
        return []

    tools_config = app._load_tools_config()
    if tools_config is None:
        return []

    tool_overrides = getattr(app, "tool_overrides", {})
    tools_section = tools_config.get("tools", {})

    tool_instances: List[Any] = []

    for tool_name, tool_meta in tools_section.items():
        config_enabled = tool_meta.get("enabled", False)
        is_enabled = tool_overrides.get(tool_name, config_enabled)
        if not is_enabled:
            continue

        try:
            tool_cls = _create_tool_wrapper(tool_name, tool_meta, app)
            tool_instances.append(tool_cls())
        except Exception as e:
            logger.warning("Failed to build tool '%s': %s", tool_name, e)

    # Add built-in ask_user tool (only if not already defined in tools_config)
    if "ask_user" not in tools_section:
        ask_user_enabled = tool_overrides.get("ask_user", True)
        if ask_user_enabled:
            try:
                ask_user_meta = {
                    "description": "Prompt the user for input. Use when you need information from the user to proceed.",
                    "parameters": _ASK_USER_SCHEMA,
                }
                ask_user_cls = _create_tool_wrapper("ask_user", ask_user_meta, app)
                tool_instances.append(ask_user_cls())
            except Exception as e:
                logger.warning("Failed to build ask_user tool: %s", e)

    return tool_instances
