import logging
import os
from typing import Optional

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

logger = logging.getLogger('Core.ThemeManager')


class ThemeManager:
    """
    Load and apply application QSS themes with safe fallback.

    - Supports named themes located under `resources/themes/<name>.qss`
    - Applies instantly across the app via QApplication.setStyleSheet
    """

    THEMES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'resources', 'themes')
    DEFAULT_THEME_NAME = 'Slate'

    FONT_MIN = 9
    FONT_MAX = 18
    PADDING_MIN = 0.8
    PADDING_MAX = 1.4

    def __init__(self):
        # Preload theme cache for quick switching
        self._cache: dict[str, str] = {}
        self._base_font_family: Optional[str] = None

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

    def resolve_effective_theme(self, preferred_theme: str) -> str:
        """Resolve the effective theme name from user preference."""
        return preferred_theme or self.DEFAULT_THEME_NAME

    def apply_theme(
        self,
        theme_name: str,
        *,
        font_size: Optional[int] = None,
        padding_scale: Optional[float] = None
    ) -> bool:
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
                stylesheet = self._compose_stylesheet(qss, font_size, padding_scale)
                app.setStyleSheet(stylesheet)
                self._apply_font_override(font_size)
                logger.info(
                    f"Applied theme: {theme_name} (font_size={font_size}, padding_scale={padding_scale})"
                )
                return True
            except Exception as e:
                logger.warning(f"Failed to apply theme '{theme_name}': {e}")

        # Fallbacks
        try:
            root = os.path.dirname(os.path.dirname(__file__))
            style_path = os.path.join(root, 'style.qss')
            if os.path.exists(style_path):
                with open(style_path, 'r', encoding='utf-8') as f:
                    stylesheet = self._compose_stylesheet(f.read(), font_size, padding_scale)
                    app.setStyleSheet(stylesheet)
                self._apply_font_override(font_size)
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

    def _compose_stylesheet(
        self,
        base: str,
        font_size: Optional[int],
        padding_scale: Optional[float]
    ) -> str:
        """Append dynamic overrides for font size and spacing if requested."""
        overrides: list[str] = []
        normalized_font = self._normalize_font_size(font_size)
        normalized_padding = self._normalize_padding_scale(padding_scale)

        if normalized_font:
            overrides.append(f"QWidget {{ font-size: {normalized_font}pt; }}")

        if normalized_padding:
            pad_v = max(2, round(6 * normalized_padding))
            pad_h = max(8, round(12 * normalized_padding))
            header_v = max(2, pad_v - 2)
            header_h = max(4, pad_h - 4)
            min_height = max(24, pad_v * 2 + 12)
            controls = (
                "QPushButton, QToolButton, QComboBox, QLineEdit, QSpinBox, "
                "QDoubleSpinBox, QAbstractSpinBox, QTextEdit, QListWidget, "
                "QTreeWidget, QTableWidget, QTableView, QListView"
            )
            overrides.append(
                f"""{controls} {{
    padding: {pad_v}px {pad_h}px;
    min-height: {min_height}px;
}}"""
            )
            overrides.append(
                f"""QHeaderView::section {{
    padding: {header_v}px {header_h}px;
}}"""
            )

        if overrides:
            return f"{base}\n\n/* Dynamic appearance overrides */\n" + "\n".join(overrides)
        return base

    def _apply_font_override(self, font_size: Optional[int]) -> None:
        """Apply a global font override if requested."""
        app = QApplication.instance()
        if not app:
            return

        target_size = self._normalize_font_size(font_size)
        if not target_size:
            return

        current_font = app.font()
        if self._base_font_family is None:
            self._base_font_family = current_font.family()

        if current_font.pointSize() == target_size:
            return

        new_font = QFont(self._base_font_family or current_font.family(), target_size)
        app.setFont(new_font)

    def _normalize_font_size(self, size: Optional[int]) -> Optional[int]:
        if size is None:
            return None
        try:
            value = int(size)
        except (TypeError, ValueError):
            return None
        return max(self.FONT_MIN, min(self.FONT_MAX, value))

    def _normalize_padding_scale(self, scale: Optional[float]) -> Optional[float]:
        if scale is None:
            return None
        try:
            value = float(scale)
        except (TypeError, ValueError):
            return None
        return max(self.PADDING_MIN, min(self.PADDING_MAX, value))
