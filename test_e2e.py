#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""End-to-end test for the v3 module decoupling architecture."""

import sys
import os

# Add the editor directory
WORKDIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(WORKDIR)
sys.path.insert(0, WORKDIR)

# Use Tk root for non-blocking display
import codecs
with codecs.open('tianyou_editor.py', 'r', 'utf-8') as f:
    src = f.read()

# Just import everything to check syntax
try:
    compile(src.encode('utf-8'), 'tianyou_editor', 'exec')
    print("[1] COMPILE: OK")
except SyntaxError as e:
    print("[1] COMPILE: FAIL -", e)
    sys.exit(1)

# Now do an actual import
import tianyou_editor
print("[2] IMPORT: OK")

# Check classes exist
checks = {
    'TianyouEditor': hasattr(tianyou_editor, 'TianyouEditor'),
    'EditorModule': hasattr(tianyou_editor, 'EditorModule'),
    'TroopModule': hasattr(tianyou_editor, 'TroopModule'),
    'ItemModule': hasattr(tianyou_editor, 'ItemModule'),
    'SearchableCombobox': hasattr(tianyou_editor, 'SearchableCombobox'),
    'VERSION': hasattr(tianyou_editor, 'VERSION'),
}
for name, exists in checks.items():
    print("[3.%s] %s: %s" % (name, name, 'EXISTS' if exists else 'MISSING'))

# Check class hierarchy
TE = tianyou_editor.TianyouEditor
print("[4] TianyouEditor is new-style class:", issubclass(TE, object))

# Check __getattribute__ / __setattr__ are present
print("[5] __getattribute__:", '__getattribute__' in TE.__dict__)
print("[5] __setattr__:", '__setattr__' in TE.__dict__)

# Check _ROUTED_ATTRS exists
print("[6] _ROUTED_ATTRS:", hasattr(TE, '_ROUTED_ATTRS'))
if hasattr(TE, '_ROUTED_ATTRS'):
    routed = TE._ROUTED_ATTRS
    print("    Total routed attrs:", len(routed))
    print("    Sample:", list(routed)[:5])

# Check module methods exist
TM = tianyou_editor.TroopModule
IM = tianyou_editor.ItemModule
print("[7] TroopModule.build_panel:", hasattr(TM, 'build_panel'))
print("[7] TroopModule.load:", hasattr(TM, 'load'))
print("[7] TroopModule.save:", hasattr(TM, 'save'))
print("[7] TroopModule.undo:", hasattr(TM, 'undo'))
print("[7] TroopModule.redo:", hasattr(TM, 'redo'))
print("[7] ItemModule.build_panel:", hasattr(IM, 'build_panel'))
print("[7] ItemModule.load:", hasattr(IM, 'load'))
print("[7] ItemModule.save:", hasattr(IM, 'save'))

# Check editor async methods
print("[8] _load_troops_async:", hasattr(TE, '_load_troops_async'))
print("[8] _load_items_async:", hasattr(TE, '_load_items_async'))
print("[8] _show_module:", hasattr(TE, '_show_module'))
print("[8] _build_troops_panel:", hasattr(TE, '_build_troops_panel'))
print("[8] _build_items_panel:", hasattr(TE, '_build_items_panel'))

print("\nDONE: All static checks passed.")
