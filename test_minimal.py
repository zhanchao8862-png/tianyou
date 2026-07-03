#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Reproduce __setattr__ crash in isolation."""

# Reproduce the exact pattern from the decoupled tianyou_editor
class EditorModule(object):
    def __init__(self):
        self.panel = None
        self._undo_stack = []
        self._built = False
        self._loaded = False

class TianyouEditor(object):
    _ROUTED_ATTRS = frozenset(['_undo_stack', '_built', '_loaded', 'panel'])

    def __init__(self):
        # Test 1: regular setattr (NOT in _ROUTED_ATTRS)
        print("Setting self.root (not routed)...")
        # Use a dummy object to mimic tk.Tk()
        self.root = "FAKE_TK_ROOT"
        print("self.root OK")
        # Test 2: setattr for routed attr BEFORE _active_module is set
        print("Setting self._active_module...")
        self._active_module = None
        print("self._active_module OK")
        # Test 3: setting a routed attr when _active_module is None
        print("Setting self._undo_stack (routed but no active module)...")
        # _undo_stack IS in _ROUTED_ATTRS, but _active_module is None
        # The code does: if mod is not None and hasattr(mod, name): ...
        # So it should fall through to object.__setattr__
        self._undo_stack = []  # This goes through __setattr__ since _undo_stack is in ROUTED
        print("self._undo_stack OK")

e = TianyouEditor()
print("ALL OK")
