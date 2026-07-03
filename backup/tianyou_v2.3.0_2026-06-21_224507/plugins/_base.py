# -*- coding: utf-8 -*-
"""Base plugin class for Tianyou Editor. Inherit this to add features."""


class BasePlugin(object):
    """Subclass and override hook methods you need. None are mandatory."""

    # Plugin metadata (override in subclass)
    name = "unnamed"
    version = "0.0.0"
    author = ""
    description = ""

    def __init__(self):
        self._editor = None

    # ---- Lifecycle hooks ----

    def on_load(self, editor):
        """Called once when editor finishes init and loads a module."""
        self._editor = editor

    def on_troop_select(self, editor, troop, index):
        """Called every time a troop is selected in the list."""
        pass

    def on_save(self, editor):
        """Called after troops are saved to file."""
        pass

    def on_mod_open(self, editor, mod_path):
        """Called when a new MOD is opened."""
        pass

    # ---- Menu hooks ----

    def get_menu_items(self):
        """Return list of (label, callback) tuples for the 插件 menu."""
        return []

    # ---- Shortcut helpers ----

    @property
    def editor(self):
        return self._editor

    def status(self, msg):
        """Write to the editor status bar."""
        if self._editor and hasattr(self._editor, 'status'):
            self._editor.status.config(text=msg)
