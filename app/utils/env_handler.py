"""
Environment variable and runtime configuration management.
Handles reading, writing back to .env, and reloading settings dynamically in-memory.
"""
import os
from app.config import config
from app.integrations.firefly.client import firefly_client
from app.settings.service import settings_service
from app.settings.models import UserSettings
from app.utils.logging import logger

def get_env_file_path() -> str:
    # Always relative to the workspace root where .env lives
    return ".env"

def read_all_env_values() -> dict:
    """Reads current key-value pairs from the .env file directly."""
    env_path = get_env_file_path()
    values = {}
    if not os.path.exists(env_path):
        return values
        
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                try:
                    key, val = stripped.split("=", 1)
                    values[key.strip()] = val.strip()
                except ValueError:
                    continue
    return values

def update_env_file(updates: dict):
    """
    Safely updates keys in the .env file.
    Preserves comments and spacing, appends new keys if they don't exist.
    """
    env_path = get_env_file_path()
    if not os.path.exists(env_path):
        with open(env_path, "w", encoding="utf-8") as f:
            pass
            
    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    updated_lines = []
    keys_updated = set()
    
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in line:
            parts = stripped.split("=", 1)
            key = parts[0].strip()
            if key in updates:
                updated_lines.append(f"{key}={updates[key]}\n")
                keys_updated.add(key)
            else:
                updated_lines.append(line)
        else:
            updated_lines.append(line)
            
    for key, val in updates.items():
        if key not in keys_updated:
            # Add line separator if necessary
            if updated_lines and not updated_lines[-1].endswith("\n"):
                updated_lines[-1] += "\n"
            updated_lines.append(f"{key}={val}\n")
            
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(updated_lines)
    logger.info(f"[EnvHandler] Successfully wrote updates to {env_path}")

def update_runtime_config(updates: dict):
    """
    Applies configuration changes to os.environ, config, firefly_client,
    and Gemini API configurations dynamically in-memory.
    """
    # 1. Update os.environ
    for key, val in updates.items():
        if val is not None:
            os.environ[key] = str(val)
            
    # 2. Update config object attributes
    for key, val in updates.items():
        if hasattr(config, key):
            setattr(config, key, val)
            logger.info(f"[EnvHandler] Updated config key in-memory: {key}")

    # 3. Dynamic refresh of firefly_client properties
    if "FIREFLY_BASE_URL" in updates or "FIREFLY_TOKEN" in updates:
        firefly_client.base_url = config.FIREFLY_BASE_URL.rstrip('/') if config.FIREFLY_BASE_URL else ""
        firefly_client.token = config.FIREFLY_TOKEN
        firefly_client.headers = {
            "Authorization": f"Bearer {firefly_client.token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        logger.info("[EnvHandler] Refreshed Firefly III client headers.")

    # 4. Dynamic refresh of Google Gemini configuration
    if "GEMINI_API_KEY" in updates and config.GEMINI_API_KEY:
        try:
            config.GEMINI_API_KEYS = [k.strip() for k in config.GEMINI_API_KEY.split(",")]
            import app.utils.parsers as parsers
            from my_logic.api_logics import GeminiDistributor
            parsers.gemini_distributor = GeminiDistributor(config.GEMINI_API_KEYS)
            logger.info("[EnvHandler] Refreshed Gemini Generative AI Distributor with multi-key support.")
        except Exception as e:
            logger.error(f"[EnvHandler] Failed to refresh Gemini Distributor: {e}")

    # 5. Dynamic refresh of UserSettings preferences in SettingsService
    current_settings = settings_service.get_settings()
    
    # Map from config values or updates directly
    preferred_crypto = updates.get("preferred_crypto_provider", current_settings.preferred_crypto_provider)
    preferred_stock = updates.get("preferred_stock_provider", current_settings.preferred_stock_provider)
    preferred_forex = updates.get("preferred_forex_provider", current_settings.preferred_forex_provider)
    preferred_cs2 = updates.get("preferred_cs2_provider", current_settings.preferred_cs2_provider)
    default_currency = updates.get("DEFAULT_CURRENCY", current_settings.default_currency)
    
    new_settings = UserSettings(
        default_currency=default_currency,
        preferred_crypto_provider=preferred_crypto,
        preferred_stock_provider=preferred_stock,
        preferred_forex_provider=preferred_forex,
        preferred_cs2_provider=preferred_cs2
    )
    settings_service.update_settings(new_settings)
    logger.info(f"[EnvHandler] Updated settings_service with dynamic UserSettings: {new_settings}")
