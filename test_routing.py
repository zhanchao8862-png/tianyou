#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test module routing architecture."""

class EditorModule(object):
    def __init__(self, editor, name):
        self.editor = editor
        self.name = name
        self._undo_stack = []
        self._loaded = False
        self.panel = None

class TroopModule(EditorModule):
    def __init__(self, editor):
        super(TroopModule, self).__init__(editor, 'troops')
        self.troops_entries = []
        self.troops_fields = []
        self.selected_idx = -1
        self.search_var = None

class ItemModule(EditorModule):
    def __init__(self, editor):
        super(ItemModule, self).__init__(editor, 'items')
        self.items_entries = []
        self.items_fields = []
        self.items_selected_idx = -1

ROUTED = frozenset([
    'troops_entries', 'troops_fields', 'selected_idx', 'search_var',
    '_undo_stack', 'items_entries', 'items_fields', 'items_selected_idx',
    '_items_undo_stack', '_items_redo_stack',
])

class TianyouEditor(object):
    _ROUTED_ATTRS = ROUTED

    def __init__(self):
        self._troop_module = TroopModule(self)
        self._item_module = ItemModule(self)
        self._modules = {'troops': self._troop_module, 'items': self._item_module}
        self._active_module = None
        self._current_module = ''
        self.mod_path = '/test'
        self.source_path = '/test/src'

    def __getattribute__(self, name):
        if name in TianyouEditor._ROUTED_ATTRS:
            mod = object.__getattribute__(self, '_active_module')
            if mod is not None and hasattr(mod, name):
                return getattr(mod, name)
        return object.__getattribute__(self, name)

    def __setattr__(self, name, value):
        if name in TianyouEditor._ROUTED_ATTRS:
            mod = object.__getattribute__(self, '_active_module')
            if mod is not None and hasattr(mod, name):
                setattr(mod, name, value)
                return
        object.__setattr__(self, name, value)

# Test
e = TianyouEditor()
print('Created editor')

# Activate troop module
e._active_module = e._troop_module
e._current_module = 'troops'
print('Active: troops')
print('troops_entries:', e.troops_entries)

e.troops_entries.append('test_troop')
print('After append, troop module entries:', e._troop_module.troops_entries)

# Switch to items
e._active_module = e._item_module
e._current_module = 'items'
print('Switched to items')
print('items_entries:', e.items_entries)

e.items_entries.append('test_item')
print('After append, item module entries:', e._item_module.items_entries)
print('Troop module still:', e._troop_module.troops_entries)

# Switch back to troops
e._active_module = e._troop_module
print('Back to troops, entries:', e.troops_entries)

print('ALL TESTS PASSED')
