import logging
import os
from typing import Optional

from PyQt6.QtWidgets import QApplication

logger = logging.getLogger('Core.ThemeManager')


class ThemeManager:
    """
    Load and apply application QSS themes with safe fallback.

    - Supports named themes located under `resources/themes/<name>.qss`
    - Optional system theme mapping when "follow system" is enabled
    - Applies instantly across the app via QApplication.setStyleSheet
    """

    THEMES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'resources', 'themes')
    DEFAULT_THEME_NAME = 'Slate'

    # Mapping for system theme preference to named themes
    SYSTEM_MAP = {
        'dark': 'Onyx',
        'light': 'Quartz',
    }

    def __init__(self):
        # Preload theme cache for quick switching
        self._cache: dict[str, str] = {}

    def available_themes(self) -> list[str]:
        names = []
        try:
            if os.path.isdir(self.THEMES_DIR):
                for fname in os.listdir(self.THEMES_DIR):
                    if fname.lower().endswith('.qss'):
                        names.append(os.path.splitext(fname)[0])
        except Exception as e:
            logger.debug(f"Failed to list themes: {e}")
        return sorted(names)

    def _read_qss(self, theme_name: str) -> Optional[str]:
        if theme_name in self._cache:
            return self._cache[theme_name]
        path = os.path.join(self.THEMES_DIR, f"{theme_name}.qss")
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                self._cache[theme_name] = content
                return content
        except Exception as e:
            logger.warning(f"Failed to load theme '{theme_name}': {e}")
            return None

    def detect_system_mode(self) -> str:
        """Return 'dark' or 'light' based on Windows AppsUseLightTheme registry.

        Defaults to 'light' if detection fails.
        """
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                value, _ = winreg.QueryValueEx(key, 'AppsUseLightTheme')
                return 'light' if int(value) == 1 else 'dark'
        except Exception as e:
            logger.debug(f"System theme detection failed: {e}")
            return 'light'

    def resolve_effective_theme(self, preferred_theme: str, follow_system: bool) -> str:
        if follow_system:
            mode = self.detect_system_mode()
            mapped = self.SYSTEM_MAP.get(mode)
            if mapped:
                return mapped
        return preferred_theme or self.DEFAULT_THEME_NAME

    def apply_theme(self, theme_name: str) -> bool:
        """Apply a specific theme by name. Returns True on success.

        Falls back to `style.qss` at project root, then clears stylesheet if all fail.
        """
        app = QApplication.instance()
        if not app:
            logger.debug("No QApplication instance; cannot apply theme")
            return False

        qss = self._read_qss(theme_name)
        if qss is not None:
            try:
                app.setStyleSheet(qss)
                logger.info(f"Applied theme: {theme_name}")
                return True
            except Exception as e:
                logger.warning(f"Failed to apply theme '{theme_name}': {e}")

        # Fallbacks
        try:
            root = os.path.dirname(os.path.dirname(__file__))
            style_path = os.path.join(root, 'style.qss')
            if os.path.exists(style_path):
                with open(style_path, 'r', encoding='utf-8') as f:
                    app.setStyleSheet(f.read())
                logger.info("Applied fallback stylesheet: style.qss")
                return True
        except Exception as e:
            logger.warning(f"Failed applying fallback stylesheet: {e}")

        # Last resort: clear stylesheet
        try:
            app.setStyleSheet("")
        except Exception:
            pass
        logger.warning("Cleared stylesheet; theme application failed")
        return False

