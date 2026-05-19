"""
Settings service.
Reads, validates, updates, and applies user settings across the app.
"""
from app.settings.models import UserSettings
from app.settings.defaults import DEFAULT_SETTINGS

class SettingsService:
    def __init__(self):
        # In a real app, this would load from a database
        self._current_settings = DEFAULT_SETTINGS

    def get_settings(self) -> UserSettings:
        return self._current_settings

    def update_settings(self, new_settings: UserSettings):
        self._current_settings = new_settings
        # Persist to database here

settings_service = SettingsService()
