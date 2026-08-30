"""Image generation and management commands.

Migrated from chatybot_app.handle_escape_command elif chain:
  /imagine, /saveimage, /imagesize, /imagequality,
  /imagedir, /listimages, /showimage, /loadimage

Each handler is a byte-for-byte port of the legacy logic, accessing app
state via ``ctx.app`` during the phased migration.
"""

import base64
import json
import os
import traceback
from datetime import datetime

from chatybot.commands.registry import command, CommandResult, registry
from chatybot.commands.context import CommandContext


@command("/imagine", help="Generate an image from a text prompt", args="<prompt>", category="image")
async def cmd_imagine(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    if len(parts) < 2:
        print("Usage: /imagine <prompt>")
        print(f"  Current settings: size={app.image_size}, quality={app.image_quality}")
        print(f"  Current model: {app.config_manager.active_model_alias}")
        return CommandResult.ok()

    prompt = command.split(maxsplit=1)[1].strip()

    # Setup debug output if imagedbg trace is enabled
    debug_file = None
    debug_fd = None
    if app.image_debug_mode:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_file = os.path.abspath(f"imagine_debug_{timestamp}.txt")
        try:
            debug_fd = open(debug_file, "w")
            print(f"[IMAGE_DEBUG] Started debug logging to {debug_file}")
            debug_fd.write(f"[IMAGE_DEBUG] Started debug logging to {debug_file}\n")
            debug_fd.write(f"[IMAGE_DEBUG] Prompt: {prompt}\n")
            debug_fd.flush()
        except Exception as e:
            print(f"[IMAGE_DEBUG] ERROR: Failed to open debug file: {e}")
            debug_file = None
            debug_fd = None

    try:
        # Get current model config
        model_alias = app.config_manager.active_model_alias
        if debug_file:
            print(f"[IMAGE_DEBUG] Model alias: {model_alias}")
            debug_fd.write(f"[IMAGE_DEBUG] Model alias: {model_alias}\n")
        try:
            model_config = app.config_manager.get_model_config(model_alias)
        except ValueError as e:
            print(f"Error: {str(e)}")
            return CommandResult.ok()

        if debug_file:
            print(f"[IMAGE_DEBUG] Vendor: {model_config.get('vendor')}")
            print(f"[IMAGE_DEBUG] Model: {model_config.get('name')}")
            debug_fd.write(f"[IMAGE_DEBUG] Vendor: {model_config.get('vendor')}\n")
            debug_fd.write(f"[IMAGE_DEBUG] Model: {model_config.get('name')}\n")
            debug_fd.flush()

        # Check if model supports image generation
        if not model_config.get("image_generation", False):
            image_models = app.config_manager.list_image_capable_models()
            if image_models:
                print(f"Error: Current model '{model_alias}' does not support image generation.")
                print(f"  Image-capable models: {', '.join(image_models)}")
                print(f"  Switch to one of these first, e.g.: /model {image_models[0]}")
            else:
                print(f"Error: Current model '{model_alias}' does not support image generation.")
                print("  No image-capable models configured in chat_config.toml")
            return CommandResult.ok()

        try:
            # Get vendor info from model config
            vendor = model_config.get("vendor", "openai")
            model_name = model_config.get("name", model_alias)
            base_url = model_config.get("base_url", None)
            api_key_env = model_config.get("api_key", "")
            api_key = os.environ.get(api_key_env) if api_key_env else None
            image_endpoint = model_config.get("image_endpoint", "/images/generations")
            modalities = model_config.get("image_modalities", ["image", "text"])

            if debug_file:
                print(f"[IMAGE_DEBUG] Starting image generation")
                print(f"[IMAGE_DEBUG] Vendor: {vendor}, Model: {model_name}")
                print(f"[IMAGE_DEBUG] Size: {app.image_size}, Quality: {app.image_quality}")
                print(f"[IMAGE_DEBUG] Modalities: {modalities}")
                debug_fd.write(f"[IMAGE_DEBUG] Starting image generation\n")
                debug_fd.write(f"[IMAGE_DEBUG] Vendor: {vendor}, Model: {model_name}\n")
                debug_fd.write(f"[IMAGE_DEBUG] Size: {app.image_size}, Quality: {app.image_quality}\n")
                debug_fd.write(f"[IMAGE_DEBUG] Modalities: {modalities}\n")
                debug_fd.flush()

            file_path, image_data = await app.image_generator.generate_image(
                prompt,
                vendor=vendor,
                model_name=model_name,
                size=app.image_size,
                quality=app.image_quality,
                endpoint=image_endpoint,
                api_key=api_key,
                base_url=base_url,
                modalities=modalities,
                size_manual=app.image_size_manual,
            )
            app.image_generator.last_generated_image = (file_path, image_data)

            if debug_file:
                print(f"[IMAGE_DEBUG] Image generated successfully")
                print(f"[IMAGE_DEBUG] File path: {file_path}")
                print(f"[IMAGE_DEBUG] Image data length: {len(image_data)} bytes")
                debug_fd.write(f"[IMAGE_DEBUG] Image generated successfully\n")
                debug_fd.write(f"[IMAGE_DEBUG] File path: {file_path}\n")
                debug_fd.write(f"[IMAGE_DEBUG] Image data length: {len(image_data)} bytes\n")
                debug_fd.flush()

            print(f"Image generated and saved to: {file_path}")

        except Exception as e:
            if debug_file:
                print(f"[IMAGE_DEBUG] ERROR: {str(e)}")
                debug_fd.write(f"[IMAGE_DEBUG] ERROR: {str(e)}\n")
                traceback.print_exc()
                debug_fd.write(f"[IMAGE_DEBUG] Traceback:\n")
                traceback.print_exc(file=debug_fd)
                debug_fd.flush()
            print(f"Error generating image: {str(e)}")
        finally:
            if debug_fd:
                debug_fd.close()
                print(f"[IMAGE_DEBUG] Debug output saved to {os.path.abspath(debug_file)}")

    except Exception as e:
        if debug_fd:
            debug_fd.close()
        if debug_file:
            print(f"[IMAGE_DEBUG] Debug output saved to {os.path.abspath(debug_file)}")
        print(f"Error generating image: {str(e)}")
    return CommandResult.ok()


@command("/saveimage", help="Save the last generated image to a custom path", args="[<path>]", category="image")
async def cmd_saveimage(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    file_path = None
    image_data = None

    # First try /imagine generated image
    if hasattr(app.image_generator, 'last_generated_image') and app.image_generator.last_generated_image is not None:
        file_path, image_data = app.image_generator.last_generated_image
    # Then try to extract from last chat response
    elif app.chat_history:

        last_response = app.chat_history[-1][1]
        try:
            # Try to parse as JSON to find images
            response_data = json.loads(last_response)
            if response_data.get("choices"):
                for choice in response_data["choices"]:
                    message = choice.get("message", {})
                    if message.get("images"):
                        # Get first image
                        first_image = message["images"][0]
                        if first_image.get("image_url", {}).get("url"):
                            image_url = first_image["image_url"]["url"]
                            if image_url.startswith("data:image"):
                                # Extract base64 data
                                image_data = image_url.split(",", 1)[1]
                                break
        except (json.JSONDecodeError, KeyError, IndexError):
            pass

        if image_data is None:
            print("No image found in last chat response or /imagine output. Use /imagine to generate an image first.")
            return CommandResult.ok()
    else:
        print("No generated image to save. Use /imagine first.")
        return CommandResult.ok()

    if len(parts) < 2:
        if file_path:
            print(f"Image already saved to: {file_path}")
        else:
            # For chat response images, we need to generate a filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = os.path.join("~", f"chat_response_image_{timestamp}.png")
            print(f"Image extracted from chat response. Suggested save path: {file_path}")
            print("Please specify a path: /saveimage <filename.png>")
        return CommandResult.ok()
    else:
        custom_path = command.split(maxsplit=1)[1].strip(" \"'")
        try:
            # Expand ~ in path
            custom_path = os.path.expanduser(custom_path)
            os.makedirs(os.path.dirname(custom_path), exist_ok=True) if os.path.dirname(custom_path) else None
            image_bytes = base64.b64decode(image_data)
            with open(custom_path, "wb") as f:
                f.write(image_bytes)
            print(f"Image saved to: {custom_path}")
            # Update last_generated_image so future /saveimage without args works
            app.image_generator.last_generated_image = (custom_path, image_data)
        except Exception as e:
            print(f"Error saving image: {str(e)}")
    return CommandResult.ok()


@command("/imagesize", help="Set or view image resolution", args="[<size>]", category="image")
async def cmd_imagesize(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    if len(parts) < 2:
        print(f"Current image size: {app.image_size}")
        return CommandResult.ok()
    app.image_size = parts[1]
    app.image_size_manual = True
    print(f"Image size set to: {app.image_size}")
    return CommandResult.ok()


@command("/imagequality", help="Set or view image quality level", args="[<quality>]", category="image")
async def cmd_imagequality(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    if len(parts) < 2:
        print(f"Current image quality: {app.image_quality}")
        return CommandResult.ok()
    app.image_quality = parts[1]
    print(f"Image quality set to: {app.image_quality}")
    return CommandResult.ok()


@command("/imagedir", help="Set or view the default image directory", args="[<dir>]", category="image")
async def cmd_imagedir(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    if len(parts) < 2:
        print(f"Current image directory: {app.image_generator.get_image_directory()}")
    else:
        new_dir = command.split(maxsplit=1)[1].strip(" \"'")
        app.image_generator.set_directory(new_dir)
        app.image_manager.set_directory(new_dir)
        print(f"Image directory set to: {new_dir}")
    return CommandResult.ok()


@command("/listimages", help="List all saved images", args="", category="image")
async def cmd_listimages(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    images = app.image_generator.list_images()
    if not images:
        print("No images found.")
        return CommandResult.ok()

    for date, date_images in images.items():
        print(f"\n{date}:")
        for filename, info in date_images.items():
            prompt = info.get("prompt", "(external)")
            if len(prompt) > 60:
                prompt = prompt[:57] + "..."
            model = info.get("model", "unknown")
            vendor = info.get("vendor", "unknown")
            print(f"  {filename:25} | {vendor:10} | {model:20} | {prompt}")
    return CommandResult.ok()


@command("/showimage", help="Show info about a specific image", args="<date>/<filename> or <filename>", category="image")
async def cmd_showimage(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    if len(parts) < 2:
        print("Usage: /showimage <date>/<filename> or /showimage <filename>")
        return CommandResult.ok()

    image_path = command.split(maxsplit=1)[1].strip(" \"'")

    # Parse date/filename
    if "/" in image_path:
        date, filename = image_path.split("/", 1)
    else:
        # Search for image across all dates
        all_images = app.image_generator.list_images()
        found = None
        for date, date_images in all_images.items():
            if image_path in date_images:
                found = (date, image_path)
                break
        if not found:
            print(f"Image not found: {image_path}")
            return CommandResult.ok()
        date, filename = found

    info = app.image_generator.get_image_info(date, filename)
    if not info:
        print(f"Image not found: {image_path}")
        return CommandResult.ok()

    print(f"\nImage: {filename}")
    print(f"  Date: {date}")
    print(f"  Prompt: {info.get('prompt', 'N/A')}")
    print(f"  Vendor: {info.get('vendor', 'N/A')}")
    print(f"  Model: {info.get('model', 'N/A')}")
    print(f"  Timestamp: {info.get('timestamp', 'N/A')}")
    if info.get("size"):
        print(f"  Size: {info.get('size')}")
    if info.get("quality"):
        print(f"  Quality: {info.get('quality')}")

    file_path = os.path.join(app.image_generator.image_dir, date, filename)
    if os.path.exists(file_path):
        file_size_kb = os.path.getsize(file_path) / 1024
        print(f"  File size: {file_size_kb:.2f} KB")
    return CommandResult.ok()


@command("/loadimage", help="Load an image file into an image bank", args="<path> <imagebank1-5>", category="image")
async def cmd_loadimage(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    if len(parts) < 3:
        print("Usage: /loadimage <path> <imagebank1-5>")
        return CommandResult.ok()

    file_path = parts[1]
    bank_name = parts[2]

    # Extract bank number
    if bank_name.startswith("imagebank") and bank_name[9:].isdigit():
        bank_num = int(bank_name[9:])
    else:
        print("Invalid imagebank. Use imagebank1 through imagebank5.")
        return CommandResult.ok()

    try:
        mime_type, base64_data = app.image_manager.load_image_data(file_path)
        data_url = f"data:{mime_type};base64,{base64_data}"
        app.buffer_manager.image_banks[f"imagebank{bank_num}"] = data_url
        print(f"Image '{file_path}' loaded into {bank_name}.")
    except Exception as e:
        print(f"Error loading image: {str(e)}")
    return CommandResult.ok()
