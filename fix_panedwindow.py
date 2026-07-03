#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Fix v3: make content_area a Frame (not PanedWindow) for proper panel caching."""

import codecs, shutil

SRC = u"tianyou_editor_v3.py"
BAK2 = u"tianyou_editor_v3.py.bak_pwfix"

with codecs.open(SRC, 'r', 'utf-8') as f:
    content = f.read()

if isinstance(content, str):
    content = content.decode('utf-8')

shutil.copy2(SRC, BAK2)
changes = 0

# 1) Change content_area from PanedWindow to Frame
old1 = (
    '        # Content area (will hold troops/items panels)\n'
    '        self.content_area = tk.PanedWindow(outer, orient=\'horizontal\',\n'
    '                                           sashrelief=\'raised\', sashwidth=4)\n'
    '        outer.add(self.content_area, minsize=400)'
)
new1 = (
    '        # Content area (will hold troops/items panels)\n'
    '        # Use Frame for easy show/hide caching; each module creates its own PanedWindow\n'
    '        self.content_area = tk.Frame(outer)\n'
    '        outer.add(self.content_area, minsize=400)'
)
if old1 in content:
    content = content.replace(old1, new1)
    changes += 1
    print("1) content_area Frame fix: OK")
else:
    print("1) content_area Frame fix: NOT FOUND")

# 2) _build_troops_panel: wrap in Frame with internal PanedWindow
old2 = (
    '    def _build_troops_panel(self, main):\n'
    '        """Build troops editor panel."""\n'
    '        left = tk.Frame(main, width=350)\n'
    '        left.pack_propagate(False)\n'
    '        main.add(left, minsize=250)'
)
new2 = (
    '    def _build_troops_panel(self, parent):\n'
    '        """Build troops editor panel."""\n'
    '        # Wrap panel in root Frame for easy show/hide caching\n'
    '        root_frame = tk.Frame(parent)\n'
    '        self._active_module._troops_panel = root_frame\n'
    '        # Internal PanedWindow for left/right split\n'
    '        main = tk.PanedWindow(root_frame, orient=\'horizontal\',\n'
    '                               sashrelief=\'raised\', sashwidth=4)\n'
    '        main.pack(expand=1, fill=\'both\')\n'
    '        left = tk.Frame(main, width=350)\n'
    '        left.pack_propagate(False)\n'
    '        main.add(left, minsize=250)'
)
if old2 in content:
    content = content.replace(old2, new2)
    changes += 1
    print("2) _build_troops_panel wrap: OK")
else:
    print("2) _build_troops_panel wrap: NOT FOUND")

# 3) _build_items_panel: wrap in Frame with internal PanedWindow
old3 = (
    '    def _build_items_panel(self, main):\n'
    '        """Build the items editor panel."""\n'
    '        left = tk.Frame(main, width=350)\n'
    '        left.pack_propagate(False)\n'
    '        main.add(left, minsize=250)'
)
new3 = (
    '    def _build_items_panel(self, parent):\n'
    '        """Build the items editor panel."""\n'
    '        root_frame = tk.Frame(parent)\n'
    '        self._active_module._items_panel = root_frame\n'
    '        main = tk.PanedWindow(root_frame, orient=\'horizontal\',\n'
    '                               sashrelief=\'raised\', sashwidth=4)\n'
    '        main.pack(expand=1, fill=\'both\')\n'
    '        left = tk.Frame(main, width=350)\n'
    '        left.pack_propagate(False)\n'
    '        main.add(left, minsize=250)'
)
if old3 in content:
    content = content.replace(old3, new3)
    changes += 1
    print("3) _build_items_panel wrap: OK")
else:
    print("3) _build_items_panel wrap: NOT FOUND")

# 4) Remove old panel cache lines
for old_cache in [
    '        self._active_module._troops_panel = main  # cache\n',
    '        self._active_module._items_panel = main  # cache\n',
]:
    if old_cache in content:
        content = content.replace(old_cache, '')
        changes += 1
        print("4) Removed cache line")

# 5) Fix _show_module: remove the `self._active_module.panel = self._active_module._troops_panel` lines
# because the panel is now set inside _build_*_panel directly
old_sm = (
    '            if module_name == u\'troops\':\n'
    '                self._build_troops_panel(self.content_area)\n'
    '                self._active_module.panel = self._active_module._troops_panel\n'
    '            elif module_name == u\'items\':\n'
    '                self._build_items_panel(self.content_area)\n'
    '                self._active_module.panel = self._active_module._items_panel'
)
new_sm = (
    '            if module_name == u\'troops\':\n'
    '                self._build_troops_panel(self.content_area)\n'
    '            elif module_name == u\'items\':\n'
    '                self._build_items_panel(self.content_area)'
)
if old_sm in content:
    content = content.replace(old_sm, new_sm)
    changes += 1
    print("5) _show_module simplify: OK")
else:
    print("5) _show_module simplify: NOT FOUND")

if changes == 0:
    print("\nERROR: No changes applied!")
else:
    with codecs.open(SRC, 'w', 'utf-8') as f:
        f.write(content)
    print("\nApplied %d changes." % changes)
    # Syntax check
    try:
        compile(content.encode('utf-8'), 'test', 'exec')
        print("Syntax OK!")
    except SyntaxError as e:
        print("SYNTAX ERROR: %s" % e)
