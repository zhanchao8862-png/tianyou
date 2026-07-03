#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Apply module decoupling to tianyou_editor.py.
Creates EditorModule/TroopModule/ItemModule classes.
Uses __getattribute__/__setattr__ on TianyouEditor for transparent attr routing.
"""

import os, re, codecs, copy, shutil

SRC = u"tianyou_editor.py"
DST = u"tianyou_editor_v3.py"
BAK = u"tianyou_editor.py.bak_decouple"

# Module-specific attributes that get routed to active module
TROOP_ATTRS = set([
    'troops_header', 'troops_footer', 'troops_entries', 'troops_fields',
    '_dirty_upgrades', '_face_key_map', 'upgrade_tree',
    'selected_idx', '_undo_stack', '_redo_stack', '_undo_max',
    '_current_tab', '_guard',
    'troop_lb', 'eq_lb', '_info_text', '_raw_text', 'detail_title',
    '_tab_btns', '_tab_frames', 'search_var', '_save_btn',
    '_btn_add_eq', '_btn_rm_eq', '_btn_clr_eq', '_btn_move_up', '_btn_move_down',
    '_resize_handle', '_eq_height', '_resize_dragging', '_resize_start_y', '_resize_start_h',
    '_detail_vars', '_attr_vars', '_skill_vars', '_prof_vars',
    '_troops_panel', '_troops_loaded',
])

ITEM_ATTRS = set([
    'items_header', 'items_entries', 'items_footer', 'items_fields',
    '_items_undo_stack', '_items_redo_stack',
    'items_lb', 'items_search_var', 'items_info_text', 'items_raw_text',
    'items_detail_title', 'items_tab_btns', 'items_tab_frames',
    'items_selected_idx',
    '_items_panel', '_items_loaded',
])

# Ensure unicode on Python 2.7
def ustr(s):
    if isinstance(s, unicode):
        return s
    try:
        return s.decode('utf-8')
    except:
        return s.decode('utf-8', 'replace')

# Read source
with codecs.open(SRC, 'r', 'utf-8-sig') as f:
    src = f.read()
src = ustr(src)
lines = src.split(u'\n')

# Find "class TianyouEditor"
class_line = None
for i, line in enumerate(lines):
    if line.strip().startswith(u'class TianyouEditor'):
        class_line = i
        break

if class_line is None:
    print("ERROR: Cannot find class TianyouEditor")
    exit(1)

print("class TianyouEditor at line %d" % (class_line + 1))

# Find __init__ start
init_start = None
for i in range(class_line, len(lines)):
    if re.match(r'\s+def __init__\(self\):', lines[i]):
        init_start = i
        break

# Find __init__ end - find def _push_undo or _build_menubar
init_end = None
for i in range(init_start + 5, len(lines)):
    if re.match(r'\s+def _push_undo\(self\):', lines[i]):
        init_end = i - 1
        break

print("__init__: %d - %d" % (init_start + 1, init_end + 1))

if init_end is None:
    print("ERROR: Cannot find end of __init__")
    exit(1)

# Find key method positions
def find_method(name):
    for i in range(class_line, len(lines)):
        if re.match(r'\s+def ' + name + r'\(self', lines[i]):
            return i
    return None

def find_method_end(start_line):
    if start_line is None:
        return None
    base_indent = len(lines[start_line]) - len(lines[start_line].lstrip())
    for i in range(start_line + 1, min(start_line + 200, len(lines))):
        if lines[i].strip() and not lines[i].strip().startswith('#'):
            line_indent = len(lines[i]) - len(lines[i].lstrip())
            if line_indent <= base_indent and re.match(r'\s+def ', lines[i]):
                return i - 1
    return start_line + 100  # fallback

show_line = find_method(r'_show_module')
show_end = find_method_end(show_line)
reload_line = find_method(r'_reload')
reload_end = find_method_end(reload_line)
push_undo_line = find_method(r'_push_undo')
push_undo_end = find_method_end(push_undo_line)
undo_line = find_method(r'_undo')
undo_end = find_method_end(undo_line)
redo_line = find_method(r'_redo')
redo_end = find_method_end(redo_line)
build_troops_line = find_method(r'_build_troops_panel')
build_troops_end = find_method_end(build_troops_line)
build_items_line = find_method(r'_build_items_panel')
build_items_end = find_method_end(build_items_line)
build_menubar_line = find_method(r'_build_menubar')

print("_show_module: %d - %d" % (show_line + 1, show_end + 1))
print("_reload: %d - %d" % (reload_line + 1, reload_end + 1))
print("_push_undo -> _redo: %d - %d" % (push_undo_line + 1, redo_end + 1))
print("_build_troops_panel: %d - %d" % (build_troops_line + 1, build_troops_end + 1))
print("_build_items_panel: %d - %d" % (build_items_line + 1, build_items_end + 1))

# ============================================================
# Module classes text
# ============================================================
module_classes = u'''
# ============================================================
#  Module System - Independent editor modules
# ============================================================

class EditorModule(object):
    """Base class for editor modules (troops, items, etc.)."""
    def __init__(self, editor, name):
        self.editor = editor
        self.name = name
        self._undo_stack = []
        self._redo_stack = []
        self._undo_max = 50
        self.selected_idx = -1
        self._loaded = False
        self._built = False
        self.panel = None

    @property
    def mod_path(self):
        return self.editor.mod_path

    @property
    def source_path(self):
        return self.editor.source_path

    @property
    def root(self):
        return self.editor.root

    def push_undo(self, snapshot):
        self._undo_stack.append(snapshot)
        if len(self._undo_stack) > self._undo_max:
            self._undo_stack.pop(0)
        self._redo_stack = []

    def undo(self):
        raise NotImplementedError

    def redo(self):
        raise NotImplementedError

    def build_panel(self, parent):
        raise NotImplementedError

    def load(self):
        raise NotImplementedError

    def save(self):
        raise NotImplementedError

    def on_show(self):
        pass

    def on_hide(self):
        pass


class TroopModule(EditorModule):
    """Troop editor module."""
    def __init__(self, editor):
        super(TroopModule, self).__init__(editor, u'troops')
        self.troops_header = u""
        self.troops_footer = u""
        self.troops_entries = []
        self.troops_fields = []
        self._dirty_upgrades = set()
        self._face_key_map = {}
        self.upgrade_tree = {}
        self._current_tab = u'info'
        self._guard = False
        self.troop_lb = None
        self.eq_lb = None
        self._info_text = None
        self._raw_text = None
        self.detail_title = None
        self._tab_btns = {}
        self._tab_frames = {}
        self.search_var = None
        self._save_btn = None
        self._btn_add_eq = None
        self._btn_rm_eq = None
        self._btn_clr_eq = None
        self._btn_move_up = None
        self._btn_move_down = None
        self._resize_handle = None
        self._eq_height = None
        self._resize_dragging = False
        self._resize_start_y = 0
        self._resize_start_h = 0
        self._detail_vars = []
        self._attr_vars = []
        self._skill_vars = []
        self._prof_vars = []
        self._troops_panel = None
        self._troops_loaded = False


class ItemModule(EditorModule):
    """Item editor module."""
    def __init__(self, editor):
        super(ItemModule, self).__init__(editor, u'items')
        self.items_header = u""
        self.items_entries = []
        self.items_footer = u""
        self.items_fields = []
        self._items_undo_stack = []
        self._items_redo_stack = []
        self.items_lb = None
        self.items_search_var = None
        self.items_info_text = None
        self.items_raw_text = None
        self.items_detail_title = None
        self.items_tab_btns = {}
        self.items_tab_frames = {}
        self.items_selected_idx = -1
        self._items_panel = None
        self._items_loaded = False
'''

# ============================================================
# Module creation block (inserted in __init__)
# ============================================================
module_creation = [u''] + [
    u'        # ── Module instances ──',
    u'        self._troop_module = TroopModule(self)',
    u'        self._item_module = ItemModule(self)',
    u'        self._modules = {u\'troops\': self._troop_module, u\'items\': self._item_module}',
    u'        self._active_module = None',
    u'',
]

# ============================================================
# Attribute routing (inserted after __init__)
# ============================================================
attr_routing = u'''
    # ── Module Attribute Routing ──
    _ROUTED_ATTRS = frozenset([
        %s
    ])

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

''' % u'        '.join([u"'%s',\n" % a for a in sorted(TROOP_ATTRS.union(ITEM_ATTRS))])

# ============================================================
# New _show_module (panel caching + async loading)
# ============================================================
new_show_module = u'''    def _show_module(self, module_name):
        """Switch content panel. Panel caching + async loading."""
        if module_name not in (u'troops', u'items'):
            return
        if module_name == self._current_module:
            return

        # Hide current
        if self._active_module and self._active_module.panel:
            self._active_module.panel.pack_forget()
            self._active_module.on_hide()

        # Activate
        self._active_module = self._modules[module_name]
        self._current_module = module_name

        # Build panel if needed
        if not self._active_module._built:
            if module_name == u'troops':
                self._build_troops_panel(self.content_area)
                self._active_module.panel = self._active_module._troops_panel
            elif module_name == u'items':
                self._build_items_panel(self.content_area)
                self._active_module.panel = self._active_module._items_panel
            self._active_module._built = True

        # Show
        if self._active_module.panel:
            self._active_module.panel.pack(expand=1, fill=u'both')

        self._active_module.on_show()

        # Async load
        if not self._active_module._loaded:
            if module_name == u'troops':
                self.status.config(text=u"\\u52a0\\u8f7d\\u5175\\u79cd\\u6570\\u636e\\u4e2d...")
                self.root.after(50, self._load_troops_async)
            elif module_name == u'items':
                self.status.config(text=u"\\u52a0\\u8f7d\\u7269\\u54c1\\u6570\\u636e\\u4e2d...")
                self.root.after(50, self._load_items_async)

        # Highlight tree
        for child in self.nav_tree.get_children(''):
            for sub in self.nav_tree.get_children(child):
                tags = self.nav_tree.item(sub, u'tags')
                if tags and tags[0] == module_name:
                    self.nav_tree.selection_set(sub)

    def _load_troops_async(self):
        try:
            self._load_troops()
            self._active_module._loaded = True
        except Exception as e:
            self.status.config(text=u"\\u52a0\\u8f7d\\u5931\\u8d25: " + unicode(e))

    def _load_items_async(self):
        try:
            self._load_items()
            self._active_module._loaded = True
        except Exception as e:
            self.status.config(text=u"\\u52a0\\u8f7d\\u5931\\u8d25: " + unicode(e))
'''

# ============================================================
# New _reload
# ============================================================
new_reload = u'''    def _reload(self):
        """Reload current module."""
        if not self.source_path:
            return
        mod = self._active_module
        if mod is None:
            return
        mod._loaded = False
        if mod.name == u'troops':
            self._load_troops_async()
        elif mod.name == u'items':
            self._load_items_async()
'''

# ============================================================
# New undo/redo (dispatch to active module)
# ============================================================
new_undo = u'''    def _push_undo(self):
        mod = self._active_module
        if mod is None:
            return
        if mod.name == u'troops':
            snap = (copy.deepcopy(mod.troops_entries),
                    copy.deepcopy(mod.troops_fields),
                    mod.selected_idx)
            mod.push_undo(snap)
        elif mod.name == u'items':
            snap = (copy.deepcopy(mod.items_entries),
                    copy.deepcopy(mod.items_fields),
                    mod.items_selected_idx)
            mod.push_undo(snap)

    def _undo(self):
        mod = self._active_module
        if mod is None:
            return
        if mod.name == u'troops':
            self._undo_troops()
        elif mod.name == u'items':
            self._undo_items()

    def _undo_troops(self):
        mod = self._active_module
        if not mod._undo_stack:
            self.status.config(text=u"\\u6ca1\\u6709\\u53ef\\u4ee5\\u64a4\\u9500\\u7684\\u64cd\\u4f5c")
            return
        cur = (copy.deepcopy(mod.troops_entries),
               copy.deepcopy(mod.troops_fields),
               mod.selected_idx)
        mod._redo_stack.append(cur)
        entries, fields, sel = mod._undo_stack.pop()
        mod.troops_entries = entries
        mod.troops_fields = fields
        mod.selected_idx = sel
        sv = mod.search_var
        self._populate_list(sv.get() if sv else u'')
        if sel >= 0:
            self._show_detail()
            self._fill_equipment()
        else:
            self._clear_detail()
            self._clear_equipment()
        self._count_lbl.config(text=u"\\u5171 %d \\u4e2a\\u5175\\u79cd" % len(mod.troops_entries))
        self.status.config(text=u"\\u21a9 \\u5df2\\u64a4\\u9500 (\\u5269\\u4f59 %d \\u6b65)" % len(mod._undo_stack))

    def _undo_items(self):
        mod = self._active_module
        if not mod._undo_stack:
            self.status.config(text=u"\\u6ca1\\u6709\\u53ef\\u4ee5\\u64a4\\u9500\\u7684\\u64cd\\u4f5c")
            return
        cur = (copy.deepcopy(mod.items_entries),
               copy.deepcopy(mod.items_fields),
               mod.items_selected_idx)
        mod._redo_stack.append(cur)
        entries, fields, sel = mod._undo_stack.pop()
        mod.items_entries = entries
        mod.items_fields = fields
        mod.items_selected_idx = sel
        self._populate_items_list()
        if sel >= 0:
            self._show_items_detail()
        else:
            self._clear_items_detail()
        self.status.config(text=u"\\u21a9 \\u5df2\\u64a4\\u9500 (\\u5269\\u4f59 %d \\u6b65)" % len(mod._undo_stack))

    def _redo(self):
        mod = self._active_module
        if mod is None:
            return
        if mod.name == u'troops':
            self._redo_troops()
        elif mod.name == u'items':
            self._redo_items()

    def _redo_troops(self):
        mod = self._active_module
        if not mod._redo_stack:
            self.status.config(text=u"\\u6ca1\\u6709\\u53ef\\u4ee5\\u91cd\\u505a\\u7684\\u64cd\\u4f5c")
            return
        cur = (copy.deepcopy(mod.troops_entries),
               copy.deepcopy(mod.troops_fields),
               mod.selected_idx)
        mod._undo_stack.append(cur)
        entries, fields, sel = mod._redo_stack.pop()
        mod.troops_entries = entries
        mod.troops_fields = fields
        mod.selected_idx = sel
        sv = mod.search_var
        self._populate_list(sv.get() if sv else u'')
        if sel >= 0:
            self._show_detail()
            self._fill_equipment()
        else:
            self._clear_detail()
            self._clear_equipment()
        self._count_lbl.config(text=u"\\u5171 %d \\u4e2a\\u5175\\u79cd" % len(mod.troops_entries))
        self.status.config(text=u"\\u21aa \\u5df2\\u91cd\\u505a (\\u5269\\u4f59 %d \\u6b65)" % len(mod._redo_stack))

    def _redo_items(self):
        mod = self._active_module
        if not mod._redo_stack:
            self.status.config(text=u"\\u6ca1\\u6709\\u53ef\\u4ee5\\u91cd\\u505a\\u7684\\u64cd\\u4f5c")
            return
        cur = (copy.deepcopy(mod.items_entries),
               copy.deepcopy(mod.items_fields),
               mod.items_selected_idx)
        mod._undo_stack.append(cur)
        entries, fields, sel = mod._redo_stack.pop()
        mod.items_entries = entries
        mod.items_fields = fields
        mod.items_selected_idx = sel
        self._populate_items_list()
        if sel >= 0:
            self._show_items_detail()
        else:
            self._clear_items_detail()
        self.status.config(text=u"\\u21aa \\u5df2\\u91cd\\u505a (\\u5269\\u4f59 %d \\u6b65)" % len(mod._redo_stack))
'''

# ============================================================
# Panel cache lines
# ============================================================
panel_cache_troops = u'        self._active_module._troops_panel = main  # cache'
panel_cache_items = u'        self._active_module._items_panel = main  # cache'

# ============================================================
# Assemble output
# ============================================================
output_parts = []

# 1) Everything before class definition
for i in range(0, class_line):
    output_parts.append(lines[i])

# 2) Module classes
output_parts.append(module_classes)
output_parts.append(u'')  # blank line

# 3) class TianyouEditor declaration
output_parts.append(lines[class_line])

# 4) Modified __init__ body
# Rebuild __init__: skip module-specific state lines, add module creation
init_body = lines[init_start:init_end + 1]
new_init = []
for line in init_body:
    stripped = line.strip()
    skip = False
    for pat in [u'self.troops_header', u'self.troops_footer', u'self.troops_entries',
                u'self.troops_fields', u'self._dirty_upgrades', u'self._face_key_map',
                u'self._undo_stack = []', u'self._redo_stack = []', u'self._undo_max = 50']:
        if pat in stripped:
            skip = True
            break
    if not skip:
        new_init.append(line)
    # Insert module creation after source_path line
    if u'self.source_path' in stripped and u'_config' in stripped:
        new_init.extend(module_creation)

output_parts.append(u'\n'.join(new_init))

# 4) Attribute routing
output_parts.append(attr_routing)

# 5) Everything from after old __init__ to end, with replacements
i = init_end + 1
while i < len(lines):
    line = lines[i]
    # Replace old undo/redo section
    if i == push_undo_line:
        output_parts.append(new_undo)
        i = redo_end + 1
        continue
    # Replace old _show_module
    if i == show_line:
        output_parts.append(new_show_module)
        i = show_end + 1
        continue
    # Replace old _reload
    if i == reload_line:
        output_parts.append(new_reload)
        i = reload_end + 1
        continue
    # Add panel cache line at end of build methods
    if i == build_troops_end:
        output_parts.append(line)
        output_parts.append(panel_cache_troops)
        i += 1
        continue
    if i == build_items_end:
        output_parts.append(line)
        output_parts.append(panel_cache_items)
        i += 1
        continue
    output_parts.append(line)
    i += 1

output = u'\n'.join(output_parts)

# ============================================================
# Write and backup
# ============================================================
with codecs.open(DST, 'w', 'utf-8') as f:
    f.write(output)

shutil.copy2(SRC, BAK)

print("\nDone! Output: %s (%d bytes)" % (DST, len(output.encode('utf-8'))))
print("Backup: %s" % BAK)
