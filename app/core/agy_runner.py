import asyncio
import json
import logging
import os
import shutil

logger = logging.getLogger(__name__)

def get_agy_bin() -> str:
    """
    Resolves the agy binary path:
    1. Checks AGY_PATH environment variable if specified.
    2. Checks system PATH via shutil.which("agy").
    3. Checks common fallback and mount locations:
       - /usr/local/bin/agy
       - /root/.local/bin/agy
       - ~/.local/bin/agy
       - /usr/bin/agy
    """
    env_bin = os.getenv("AGY_PATH")
    if env_bin:
        resolved = shutil.which(env_bin)
        if resolved:
            return resolved
        if os.path.isfile(env_bin) and os.access(env_bin, os.X_OK):
            return env_bin

    which_bin = shutil.which("agy")
    if which_bin:
        return which_bin

    fallbacks = [
        "/usr/local/bin/agy",
        "/root/.local/bin/agy",
        os.path.expanduser("~/.local/bin/agy"),
        "/usr/bin/agy",
    ]
    for path in fallbacks:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path

    return env_bin or "agy"

async def run_agy_prompt(prompt: str, model: str = None, output_format: str = "json", files: list[str] = None):
    """
    Safely executes the `agy` CLI using asyncio subprocess to avoid blocking.
    """
    agy_bin = get_agy_bin()
    cmd = [
        agy_bin,
        "--print", prompt,
        "--output-format", output_format,
        "--dangerously-skip-permissions",
        "--print-timeout", "10m"
    ]

    if model:
        cmd.extend(["--model", model])

    if files:
        for f in files:
            # We can pass files by injecting their paths into the prompt,
            # or if `agy` supports --add-dir, we could use that.
            # Assuming we inject them in the prompt for context:
            pass # We will handle file prompt formatting at the caller level

    safe_cmd_log = ' '.join(cmd).replace('\n', ' ')
    logger.info(f"Executing AGY command: {safe_cmd_log}")

    # Run the subprocess
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
    except FileNotFoundError:
        error_msg = (
            f"Executable '{agy_bin}' not found. "
            "If running inside Docker, ensure ~/.local/bin is mounted into the container "
            "(e.g. in docker-compose.yml: - ~/.local/bin:/root/.local/bin:ro or - ~/.local/bin/agy:/usr/local/bin/agy:ro) "
            "or set AGY_PATH environment variable."
        )
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    stdout, stderr = await process.communicate()
    
    if process.returncode != 0:
        error_msg = stderr.decode().strip()
        if not error_msg:
            error_msg = stdout.decode().strip()
        logger.error(f"AGY Error: {error_msg}")
        raise RuntimeError(f"AGY CLI execution failed: {error_msg}")
        
    output_str = stdout.decode().strip()
    
    # Try to parse JSON output to ensure it's valid
    try:
        # AGY might print some extra logs, we'll try to find the first '{' and last '}'
        start_idx = output_str.find('{')
        end_idx = output_str.rfind('}')
        if start_idx != -1 and end_idx != -1 and end_idx >= start_idx:
            json_str = output_str[start_idx:end_idx+1]
            return json.loads(json_str)
        else:
            # Fallback
            return json.loads(output_str)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AGY JSON output: {output_str}")
        # If we asked for json but didn't get it, wrap it in a fallback JSON
        return {"text": output_str}

