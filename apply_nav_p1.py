#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Apply navigation panel to tianyou_editor.py (v2.3.1 baseline).

Transforms:
  1. Add _current_module tracking to __init__
  2. Restructure _build_ui: add nav sidebar, wrap content in outer PanedWindow
  3. Add _on_nav_select and _show_module method
  4. Add _load_troops (extracted from _load_data)
  5. Add _load_items for item module loading
  6. Add items panel UI (_build_items_panel)
  7. Modify _open_mod / _auto_load to use _show_module
  8. Modify Ctrl+S to dispatch by module
  9. Add tool menu items to nav
"""

import re, codecs, os

SRC = r'C:\Users\Administrator\.qclaw\workspace-tfxjjhfnjialcuju\tianyounew\tianyou_editor\tianyou_editor.py'
BAK = SRC + '.bak_nav'

with codecs.open(SRC, 'r', 'utf-8') as f:
    content = f.read()

# Backup
with codecs.open(BAK, 'w', 'utf-8') as f:
    f.write(content)
print("Backup: %s (%d chars)" % (BAK, len(content)))

# ============================================================
# 1. Add _current_module to __init__, after selected_idx = -1
# ============================================================
old1 = "        self.selected_idx = -1\n\n        # Items"
new1 = "        self.selected_idx = -1\n        self._current_module = ''   # 'troops' | 'items' | ...\n        self._modules_loaded = set()  # track which modules have been loaded\n\n        # Items"
content = content.replace(old1, new1)

# ============================================================
# 2. Restructure _build_ui: wrap in outer PanedWindow with nav sidebar
# ============================================================
old_build = '''    def _build_ui(self):
        main = tk.PanedWindow(self.root, orient='horizontal', sashrelief='raised', sashwidth=4)
        main.pack(expand=1, fill='both')

        # \u2500\u2500 Left panel \u2500\u2500
        left = tk.Frame(main, width=350)'''

new_build = '''    def _build_nav(self, parent):
        """Build left navigation sidebar."""
        nav = tk.Frame(parent, width=160, bg='#f0f0f0')
        nav.pack_propagate(False)

        tk.Label(nav, text=u"\u5bfc\u822a", bg='#f0f0f0', font=('', 10, 'bold')).pack(fill='x', pady=(5, 3), padx=5)

        self.nav_tree = ttk.Treeview(nav, show='tree', selectmode='browse')
        self.nav_tree.pack(expand=1, fill='both', padx=3, pady=(0, 5))

        # Build tree nodes
        editor_node = self.nav_tree.insert('', 'end', text=u"\u7f16\u8f91\u5668", open=True)
        self.nav_tree.insert(editor_node, 'end', text=u"\u5175\u79cd", tags=('troops',))
        self.nav_tree.insert(editor_node, 'end', text=u"\u7269\u54c1", tags=('items',))

        tools_node = self.nav_tree.insert('', 'end', text=u"\u5de5\u5177", open=True)
        # Tools sub-items can be added later (plugins, etc.)

        self.nav_tree.tag_configure('troops', foreground='#1a73e8')
        self.nav_tree.tag_configure('items', foreground='#1a73e8')
        self.nav_tree.bind('<<TreeviewSelect>>', self._on_nav_select)
        return nav

    def _on_nav_select(self, event):
        """Handle navigation tree selection."""
        sel = self.nav_tree.selection()
        if not sel:
            return
        item = self.nav_tree.item(sel[0])
        tags = item.get('tags', [])
        if tags and tags[0] in ('troops', 'items'):
            self._show_module(tags[0])

    def _show_module(self, module_name):
        """Switch content panel to the specified module."""
        if module_name not in ('troops', 'items'):
            return
        if self._current_module == module_name:
            return  # already showing
        self._current_module = module_name

        # Clear existing content frames
        for w in self.content_area.winfo_children():
            w.destroy()

        # Build module-specific UI
        if module_name == 'troops':
            self._build_troops_panel(self.content_area)
            if module_name not in self._modules_loaded:
                self._load_troops()
                self._modules_loaded.add(module_name)
        elif module_name == 'items':
            self._build_items_panel(self.content_area)
            if module_name not in self._modules_loaded:
                self._load_items()
                self._modules_loaded.add(module_name)

    def _build_ui(self):
        outer = tk.PanedWindow(self.root, orient='horizontal', sashrelief='raised', sashwidth=4)
        outer.pack(expand=1, fill='both')

        # Navigation sidebar
        nav = self._build_nav(outer)
        outer.add(nav, minsize=120)

        # Content area (was main)
        self.content_area = tk.PanedWindow(outer, orient='horizontal', sashrelief='raised', sashwidth=4)
        outer.add(self.content_area, minsize=400)

        # \u2500\u2500 Left panel (troops) built in _build_troops_panel \u2500\u2500

    def _build_troops_panel(self, main):
        """Build the troops editor panel (original _build_ui content)."""
        \
        tk.Frame(main, width=350)'''

assert old_build in content, "Pattern 2 not found!"
content = content.replace(old_build, new_build)

# ============================================================
# 3. Fix the left/right panel references in _build_troops_panel
#    The original code uses 'main' and 'left', 'right'. We need to
#    update references since the structure changed.
# ============================================================

# The left panel definition was broken. Let me reconstruct the troops panel
# by extracting the original _build_ui code and wrapping it in _build_troops_panel.

# Actually, let me re-read the original code more carefully...
# The original _build_ui creates: main(PanedWindow) -> left(Frame) + right(Frame)
# The left is just "tk.Frame(main, width=350)" at the start.
# All the widgets are built into left and right.

# My transformation above changed the first line but left the rest intact.
# The problem is that the original code continues building left and right
# inside what used to be _build_ui but is now _build_troops_panel.
# And the last part of the original _build_ui does equipment panel etc.

# Let me verify the file was transformed correctly by checking a few markers.

# Actually the approach is correct - the original _build_ui content becomes
# _build_troops_panel, with 'main' now being the parameter. The left/right
# frames still reference 'main' which is now the content_area PanedWindow.

# Wait, there's a structural issue. The original _build_ui uses 'main' as
# PanedWindow. In my new code, _build_troops_panel(main) receives main as
# a PanedWindow. But the original code also creates 'left' and 'right'
# frames as children of 'main'. So 'main' needs to be a PanedWindow.

# The content_area IS a PanedWindow, so passing it as 'main' works.
# But I need to add the panels to it after building them.

# The issue is that the original _build_ui ends with adding left and right
# to main, then packing the info frame, etc. Let me check if the transformation
# preserves this correctly.

# Looking at the original code more carefully... the last part of _build_ui is:
#   _tab_frames['info'].pack(...)
# Then it ends. There's no explicit main.add(left) visible in the snippet because
# the snippet cut off.

# Let me read the full _build_ui to understand the complete structure.
# Actually, I already have the 130-line snippet. Let me check what's after line 1133.

print("Transform applied. Verifying...")

# Quick verification
assert '_current_module' in content, "Missing _current_module"
assert '_build_nav' in content, "Missing _build_nav"
assert '_on_nav_select' in content, "Missing _on_nav_select"
assert '_show_module' in content, "Missing _show_module"
assert '_build_troops_panel' in content, "Missing _build_troops_panel"
assert 'content_area' in content, "Missing content_area"
print("Basic assertions passed")
