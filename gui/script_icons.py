"""
Script type icon generator for BindKit.

Generates simple colored icons for different script types (Python, PowerShell, Batch, Shell).
"""

from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QPen
from PyQt6.QtCore import Qt, QRect
from typing import Optional
import logging

logger = logging.getLogger('GUI.ScriptIcons')

class ScriptIconGenerator:
    """Generate icons for different script types."""

    # Color scheme for each script type
    COLORS = {
        'python': QColor(52, 101, 164),    # Blue
        'powershell': QColor(0, 120, 212),  # Azure Blue
        'batch': QColor(128, 128, 128),     # Gray
        'shell': QColor(76, 175, 80),       # Green
        'unknown': QColor(158, 158, 158)    # Light Gray
    }

    # Text labels for each script type
    LABELS = {
        'python': 'PY',
        'powershell': 'PS',
        'batch': 'BAT',
        'shell': 'SH',
        'unknown': '?'
    }

    @staticmethod
    def create_icon(script_type: str, size: int = 16) -> QIcon:
        """
        Create an icon for the given script type.

        Args:
            script_type: Type of script (python, powershell, batch, shell, unknown)
            size: Icon size in pixels (default: 16x16)

        Returns:
            QIcon object with the generated icon
        """
        script_type = script_type.lower()

        # Get color and label
        color = ScriptIconGenerator.COLORS.get(script_type, ScriptIconGenerator.COLORS['unknown'])
        label = ScriptIconGenerator.LABELS.get(script_type, ScriptIconGenerator.LABELS['unknown'])

        # Create pixmap
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)

        # Draw icon
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw rounded rectangle background
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, size, size, 2, 2)

        # Draw text label
        painter.setPen(QColor(255, 255, 255))  # White text
        font = QFont("Arial", max(6, size // 3), QFont.Weight.Bold)
        painter.setFont(font)

        # Center the text
        text_rect = QRect(0, 0, size, size)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, label)

        painter.end()

        return QIcon(pixmap)

    @staticmethod
    def get_icon_for_script_info(script_info) -> Optional[QIcon]:
        """
        Get an icon for a ScriptInfo object.

        Args:
            script_info: ScriptInfo object with script_type attribute

        Returns:
            QIcon object, or None if script_type is not available
        """
        try:
            from core.script_analyzer import ScriptType

            if not hasattr(script_info, 'script_type'):
                return None

            script_type = script_info.script_type

            if script_type == ScriptType.PYTHON:
                return ScriptIconGenerator.create_icon('python')
            elif script_type == ScriptType.POWERSHELL:
                return ScriptIconGenerator.create_icon('powershell')
            elif script_type == ScriptType.BATCH:
                return ScriptIconGenerator.create_icon('batch')
            elif script_type == ScriptType.SHELL:
                return ScriptIconGenerator.create_icon('shell')
            else:
                return ScriptIconGenerator.create_icon('unknown')

        except Exception as e:
            logger.error(f"Error creating icon for script: {e}")
            return None

    @staticmethod
    def get_icon_by_extension(file_extension: str) -> QIcon:
        """
        Get an icon based on file extension.

        Args:
            file_extension: File extension (e.g., '.py', '.ps1', '.bat', '.sh')

        Returns:
            QIcon object
        """
        extension = file_extension.lower().lstrip('.')

        extension_map = {
            'py': 'python',
            'ps1': 'powershell',
            'bat': 'batch',
            'cmd': 'batch',
            'sh': 'shell'
        }

        script_type = extension_map.get(extension, 'unknown')
        return ScriptIconGenerator.create_icon(script_type)
