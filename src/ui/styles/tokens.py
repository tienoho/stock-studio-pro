"""
Color tokens and UI theme styling for AutoStock Studio.
Provides unified enterprise design system tokens for Obsidian Dark & Electric Neon.
"""

import sys
from pathlib import Path
from typing import Optional

# Core Surface & Background Tokens
COLOR_BG_ROOT = "#080b11"         # Deep Obsidian window base
COLOR_BG_SURFACE = "#0c1018"      # Primary sidebar / container surface
COLOR_BG_CARD = "#111724"         # Elevated glass card
COLOR_BG_CARD_SUBTLE = "#0e131d"  # Secondary tool card
COLOR_BG_INPUT = "#090d15"        # Crisp input background
COLOR_BG_HOVER = "#172033"        # Interactive hover fill

# Border & Stroke Tokens
COLOR_BORDER_SUBTLE = "#192233"   # Dividers, subtle lines
COLOR_BORDER_CARD = "#1f2b3f"     # Cards, containers, groupboxes
COLOR_BORDER_HOVER = "#364663"    # Card / button hover highlight
COLOR_BORDER_FOCUS = "#6366f1"    # Active focus ring

# Text & Typography Tokens
COLOR_TEXT_PRIMARY = "#f8fafc"    # High contrast white headings & labels
COLOR_TEXT_SECONDARY = "#cbd5e1"  # Form labels, standard text
COLOR_TEXT_MUTED = "#94a3b8"      # Hint text, descriptions
COLOR_TEXT_DIM = "#64748b"        # Disabled / subtle captions

# Electric Neon Accents
COLOR_ACCENT = "#6366f1"          # Electric Indigo (Primary brand)
COLOR_VIOLET = "#8b5cf6"          # Radiant Violet
COLOR_CYAN = "#06b6d4"            # Neon Cyan
COLOR_EMERALD = "#10b981"         # Emerald Green (Success / Download)
COLOR_AMBER = "#f59e0b"           # Amber Gold (Auto / Warning)
COLOR_ROSE = "#ef4444"            # Ruby Crimson (Danger / Stop)
COLOR_TEAL = "#4ec9b0"            # Mint Teal

# High-End Glassmorphic Gradients
GRADIENT_PRIMARY = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:0.5 #6366f1, stop:1 #8b5cf6)"
GRADIENT_SUCCESS = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981)"
GRADIENT_DANGER = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #dc2626, stop:1 #ef4444)"
GRADIENT_CYAN = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #06b6d4)"
GRADIENT_CARD = "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #121826, stop:1 #0c101a)"

# Stat Box Gradients
STAT_COLOR_BLUE = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1e3a8a, stop:1 #1d4ed8)"
STAT_COLOR_PURPLE = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #4c1d95, stop:1 #6d28d9)"
STAT_COLOR_RED = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #831843, stop:1 #be123c)"
STAT_COLOR_GREEN = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #064e3b, stop:1 #047857)"


# Light Surface & Background Tokens (Crystal Light & Indigo Slate)
LIGHT_COLOR_BG_ROOT = "#f8fafc"
LIGHT_COLOR_BG_SURFACE = "#ffffff"
LIGHT_COLOR_BG_CARD = "#ffffff"
LIGHT_COLOR_BG_CARD_SUBTLE = "#f1f5f9"
LIGHT_COLOR_BG_INPUT = "#ffffff"
LIGHT_COLOR_BG_HOVER = "#f1f5f9"

# Light Border & Stroke Tokens
LIGHT_COLOR_BORDER_SUBTLE = "#e2e8f0"
LIGHT_COLOR_BORDER_CARD = "#e2e8f0"
LIGHT_COLOR_BORDER_HOVER = "#cbd5e1"
LIGHT_COLOR_BORDER_FOCUS = "#4f46e5"

# Light Text & Typography Tokens
LIGHT_COLOR_TEXT_PRIMARY = "#0f172a"
LIGHT_COLOR_TEXT_SECONDARY = "#334155"
LIGHT_COLOR_TEXT_MUTED = "#64748b"
LIGHT_COLOR_TEXT_DIM = "#94a3b8"


def load_stylesheet(theme: Optional[str] = None) -> str:
    """Load QSS stylesheet from disk with PyInstaller and ThemeManager support."""
    from .theme_manager import ThemeManager
    mgr = ThemeManager.get_instance()
    if isinstance(theme, str):
        return mgr.get_stylesheet(theme)
    return mgr.get_stylesheet()


