#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test module switching with real Tkinter app."""

import sys, os
WORKDIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(WORKDIR)
sys.path.insert(0, WORKDIR)

import tianyou_editor as M

# Init creates its own root
app = M.TianyouEditor()
app.root.withdraw()
app.root.update_idletasks()

# Check module instances
print("_troop_module:", app._troop_module is not None)
print("_item_module:", app._item_module is not None)

# Test attribute routing - troops_entries should go to _troop_module
app.troops_entries = ["test1", "test2"]
app.root.update_idletasks()
print("app.troops_entries:", app.troops_entries)
print("_troop_module.troops_entries:", app._troop_module.troops_entries)
print("hasattr(_item_module, troops_entries):", hasattr(app._item_module, 'troops_entries'))

# Test attribute routing - items_entries should go to _item_module
app.items_entries = ["item1", "item2"]
print("app.items_entries:", app.items_entries)
print("_item_module.items_entries:", app._item_module.items_entries)
print("hasattr(_troop_module, items_entries):", hasattr(app._troop_module, 'items_entries'))

# Test module switching
print("\n--- Module switching test ---")
try:
    app._show_module('troops')
    app.root.update_idletasks()
    print("Switch to troops: active=%s, panel=%s" % (
        app._active_module.name, app._troop_module.panel is not None))
except Exception as e:
    import traceback
    traceback.print_exc()
    print("Switch to troops FAILED:", e)

try:
    app._show_module('items')
    app.root.update_idletasks()
    print("Switch to items: active=%s, panel=%s" % (
        app._active_module.name, app._item_module.panel is not None))
except Exception as e:
    import traceback
    traceback.print_exc()
    print("Switch to items FAILED:", e)

# Switch back - state should be preserved
try:
    app._show_module('troops')
    app.root.update_idletasks()
    print("Switch back to troops: troops_entries preserved=%s" % (
        app.troops_entries == ["test1", "test2"]))
except Exception as e:
    import traceback
    traceback.print_exc()
    print("Switch back FAILED:", e)

app.root.destroy()
print("\nDONE")
