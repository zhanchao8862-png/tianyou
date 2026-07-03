#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
天佑战团源码编辑器 v3 - Module-based Architecture
Mount & Blade Warband Module System Source Editor
Developer: 李天佑  电话: 15628308654

v3 Changes:
  - Module classes (EditorModule, TroopModule, ItemModule),完全独立状态
  - 面板缓存: show/hide 替代 destroy/recreate
  - 异步加载: root.after() 非阻塞数据加载,消除UI冻结
  - 每个模块独立的撤销/重做栈
"""

VERSION = "2.4.0"

CHANGELOG = [
    {
        "version": "2.4.0",
        "date": "2026-06-26",
        "changes": [
            u"v3 架构重构: 模块化类(EditorModule/TroopModule/ItemModule),完全独立状态",
            u"面板缓存: 导航切换时 show/hide 替代 destroy/recreate",
            u"异步加载: root.after() 非阻塞数据加载,消除UI冻结",
            u"独立撤销栈: 兵种/物品各自独立 undo/redo,互不干扰",
        ]
    },
]

import os, sys, re, codecs, shutil, subprocess, copy, json
reload(sys)
sys.setdefaultencoding('utf-8')

try:
    import Tkinter as tk
    import tkFileDialog
    import tkMessageBox
    import ttk
except ImportError:
    import tkinter as tk
    from tkinter import filedialog as tkFileDialog
    from tkinter import messagebox as tkMessageBox
    from tkinter import ttk


# ============================================================
#  Translation loader
# ============================================================

def load_translations(csv_path):
    """Load pipe-separated CSV translations -> {key: value}."""
    trans = {}
    if not os.path.isfile(csv_path):
        return trans
    with codecs.open(csv_path, 'r', 'utf-8-sig', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split('|', 1)
            if len(parts) >= 2:
                trans[parts[0].strip()] = parts[1].strip()
    return trans


def parse_inventory(inv_raw):
    """Extract item IDs from inventory field string like '[itm_sword, itm_shield]'."""
    if isinstance(inv_raw, str):
        inv_raw = inv_raw.decode('utf-8')
    return re.findall(r'itm_\w+', inv_raw)


# ============================================================
#  Troop Field Constants
# ============================================================

FLAG_OTHER = [
    (0x00000001, u"男性"), (0x00000002, u"女性"), (0x00000004, u"不死"),
    (0x00000010, u"NPC英雄"), (0x00000020, u"无生命的"), (0x00000040, u"只能击晕"),
    (0x00000080, u"倒下必死"), (0x00000100, u"无法活捉"),
    (0x00000400, u"骑马的"), (0x00001000, u"商队"), (0x00008000, u"随机面貌"),
    (0x10000000, u"不能作为驻兵"),
]

FLAG_WEAPON = [
    (0x00100000, u"保证有鞋子"), (0x00200000, u"保证穿盔甲"), (0x00400000, u"保证有头盔"),
    (0x00800000, u"保证有手套"), (0x01000000, u"保证有马"), (0x02000000, u"保证有盾"),
    (0x04000000, u"保证远程武器"), (0x08000000, u"保证长杆武器"),
]

ATTR_LABELS = [u"力量 (Str)", u"敏捷 (Agi)", u"智力 (Int)", u"魅力 (Cha)", u"等级 (Level)"]

SKILL_LABELS = [
    u"交易", u"统御", u"俘虏管理", u"预留1", u"预留2", u"预留3", u"预留4",
    u"说服力", u"工程学", u"急救", u"手术", u"疗伤", u"物品管理", u"侦察",
    u"向导", u"战术", u"跟踪", u"教练", u"预留5", u"预留6", u"预留7", u"预留8",
    u"掠夺", u"骑射", u"骑术", u"跑动", u"盾防", u"武器掌握",
    u"预留9", u"预留10", u"预留11", u"预留12", u"预留13",
    u"强弓", u"强掷", u"强击", u"铁骨",
    u"预留14", u"预留15", u"预留16", u"预留17", u"预留18",
]

PROF_LABELS = [u"单手", u"双手", u"长杆", u"弓", u"弩", u"投掷", u"火器"]

SLOT_LABELS = [u"头部防具", u"身体防具", u"腿部防具", u"手部防具",
               u"主武器", u"副武器", u"武器3", u"武器4", u"马匹", u"马甲"]


# ============================================================
#  Line-based Entry Parser
# ============================================================

def parse_array_by_lines(filepath, array_name):
    """Parse a module_*.py file using line-based entry detection."""
    with codecs.open(filepath, 'r', 'utf-8', errors='replace') as f:
        lines = f.readlines()

    arr_start = -1
    for i, line in enumerate(lines):
        if re.match(r'^\s*' + re.escape(array_name) + r'\s*=\s*\[', line):
            arr_start = i
            break
    if arr_start < 0:
        raise ValueError("'%s = [' not found in %s" % (array_name, filepath))

    base_indent = len(lines[arr_start]) - len(lines[arr_start].lstrip())

    arr_close = -1
    for i in range(arr_start + 1, len(lines)):
        stripped = lines[i].rstrip('\r\n')
        line_indent = len(lines[i]) - len(lines[i].lstrip())
        if stripped == ']' and line_indent == base_indent:
            arr_close = i
            break
    if arr_close < 0:
        raise ValueError("Array close ']' not found for '%s = ['" % array_name)

    entries_raw = []
    current_lines = []
    in_entry = False

    for i in range(arr_start + 1, arr_close):
        line = lines[i]
        stripped = line.lstrip()
        if not stripped:
            continue
        is_entry_start = (stripped.startswith('[') and
                          len(stripped) > 2 and
                          stripped[1] in '"\'')
        if is_entry_start:
            if in_entry:
                entries_raw.append(''.join(current_lines))
                current_lines = []
            in_entry = True
            current_lines.append(line)
        elif in_entry:
            current_lines.append(line)

    if current_lines:
        entries_raw.append(''.join(current_lines))

    header = ''.join(lines[:arr_start + 1])
    footer = ''.join(lines[arr_close:])

    entries = []
    for e in entries_raw:
        e = e.rstrip('\r\n ')
        e = e.rstrip(',')
        e = e.rstrip()
        if e.endswith(']]'):
            e = e[:-1]
        entries.append(e)

    return header, entries, footer


def parse_fields_in_entry(entry):
    """Parse a single entry's [...] content into a list of field strings."""
    s = entry.strip()
    s = re.sub(r'^##\s*', '', s)
    if not (s.startswith('[') and s.endswith(']')):
        return [s]
    s_body = s[1:-1]

    fields = []
    depth = 0
    in_string = False
    string_char = None
    prev = 0
    j = 0

    while j < len(s_body):
        c = s_body[j]
        if not in_string:
            if c in '"\'':
                in_string = True
                string_char = c
            elif c in '([':
                depth += 1
            elif c in ')]':
                depth -= 1
            elif c == ',' and depth == 0:
                fields.append(s_body[prev:j].strip())
                prev = j + 1
        else:
            if c == string_char and (j == 0 or s_body[j - 1] != '\\'):
                in_string = False
                string_char = None
        j += 1

    if prev < len(s_body):
        fields.append(s_body[prev:].strip())

    return fields


# ============================================================
#  EditorModule — Base class for editor modules
# ============================================================

class EditorModule(object):
    """Base class for troops/items editor modules.
    Each module owns its data, undo/redo stacks, and widget tree."""

    def __init__(self, editor):
        self.editor = editor  # TianyouEditor instance
        self.panel = None     # root Frame for this module
        self._undo_stack = []
        self._redo_stack = []
        self._undo_max = 50
        self.selected_idx = -1
        self._loaded = False
        self._built = False

    # ── Shared editor state access ──
    @property
    def mod_path(self):
        return self.editor.mod_path

    @property
    def source_path(self):
        return self.editor.source_path

    @property
    def translation_path(self):
        return self.editor.translation_path

    @property
    def root(self):
        return self.editor.root

    @property
    def status_label(self):
        return self.editor.status

    @property
    def troop_cn(self):
        return self.editor.troop_cn

    @property
    def troop_cn_pl(self):
        return self.editor.troop_cn_pl

    @property
    def item_cn(self):
        return self.editor.item_cn

    @property
    def item_lookup(self):
        return self.editor.item_lookup

    @property
    def item_list(self):
        return self.editor.item_list

    @property
    def item_category(self):
        return self.editor.item_category

    @property
    def faction_data(self):
        return self.editor.faction_data

    @property
    def faction_cn(self):
        return self.editor.faction_cn

    @property
    def plugins(self):
        return self.editor.plugins

    # ── Must override ──
    def build_panel(self, parent):
        raise NotImplementedError

    def load(self):
        raise NotImplementedError

    def save(self):
        raise NotImplementedError

    # ── Optional overrides ──
    def on_show(self):
        pass

    def on_hide(self):
        pass

    def handle_global_wheel(self, widget, event):
        """Handle mouse wheel for this module's scrollable regions.
        Returns 'break' if handled, None otherwise."""
        return None

    # ── Undo/Redo ──
    def push_undo(self, snap):
        """Save a state snapshot before a modification."""
        self._undo_stack.append(snap)
        if len(self._undo_stack) > self._undo_max:
            self._undo_stack.pop(0)
        self._redo_stack = []

    def undo(self):
        """Undo last action. Override in subclass."""
        pass

    def redo(self):
        """Redo last undone action. Override in subclass."""
        pass

    def check_unsaved_changes(self):
        """Return True if there are unsaved changes."""
        return len(self._undo_stack) > 0


# ============================================================
#  TianyouEditor — Main Application (Refactored)
# ============================================================

class TianyouEditor:
    def __init__(self):
        self.root = tk.Tk()
        try:
            self.root.geometry("1280x850+100+50")
        except:
            self.root.geometry("1280x850")

        # ── Config ──
        if hasattr(sys, 'frozen'):
            self._config_path = os.path.join(os.path.dirname(sys.executable), 'tianyou_config.json')
        else:
            self._config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tianyou_config.json')
        self._config = self._load_config()

        # ── Project State (shared) ──
        self.mod_path = self._config.get('mod_path', '')
        self.source_path = self._config.get('source_path', '')
        self.translation_path = self._config.get('translation_path', '')
        self.module_info_path = self._config.get('module_info_path', '')
        self.build_bat_path = self._config.get('build_bat_path', '')
        self.font_size = self._config.get('font_size', 10)

        # Shared translation & lookup data (loaded once)
        self.troop_cn = {}
        self.troop_cn_pl = {}
        self.item_cn = {}
        self.item_lookup = {}
        self.item_list = []
        self.item_category = {}
        self.faction_data = []
        self.faction_cn = {}

        # ── Modules ──
        self._troop_module = TroopModule(self)
        self._item_module = ItemModule(self)
        self.modules = {
            'troops': self._troop_module,
            'items': self._item_module,
        }
        self._active_module = None

        # ── Build UI ──
        self._build_menubar()
        self._build_ui()
        self._build_statusbar()

        # Global wheel dispatch
        self.root.bind_class('Listbox', '<MouseWheel>', lambda e: None)
        self.root.bind_class('Canvas', '<MouseWheel>', lambda e: None)
        self.root.bind_all('<MouseWheel>', self._on_global_wheel)

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.status.config(text=u"就绪 - [文件] → [打开MOD] 加载项目")
        self._update_title()

        # Apply saved appearance
        if self._config.get('bg_color'):
            self._apply_bg_color(self.root, self._config['bg_color'])
        self._apply_font_size(self.font_size)

        if self.mod_path and os.path.isdir(self.mod_path):
            self.root.after(100, self._auto_load)

        self.root.bind('<Control-z>', lambda e: self._undo())
        self.root.bind('<Control-Z>', lambda e: self._undo())
        self.root.bind('<Control-y>', lambda e: self._redo())
        self.root.bind('<Control-Y>', lambda e: self._redo())
        self.root.bind('<Control-s>', lambda e: self._save_current_module())
        self.root.bind('<Control-S>', lambda e: self._save_current_module())

        # ── Load plugins ──
        self.plugins = []
        self._load_plugins()

    # ================================================================
    #  Shared Data Loading
    # ================================================================

    def _load_shared_resources(self):
        """Load translations, item lookup, factions, item categories once."""
        if not self.source_path:
            return

        self.troop_cn = {}
        self.troop_cn_pl = {}
        self.item_cn = {}
        self.item_lookup = {}
        self.item_list = []
        self.item_category = {}
        self.faction_data = []
        self.faction_cn = {}

        # Load items for lookup
        ip = os.path.join(self.source_path, 'module_items.py')
        items = []
        if os.path.isfile(ip):
            try:
                _, ientries, _ = parse_array_by_lines(ip, 'items')
                for ie in ientries:
                    flds = parse_fields_in_entry(ie)
                    if flds and len(flds[0]) >= 2 and flds[0][0] in '"\'':
                        iid_raw = flds[0].strip('"').strip("'")
                        full_id = 'itm_' + iid_raw if not iid_raw.startswith('itm_') else iid_raw
                        item_name = flds[1].strip('"').strip("'") if len(flds) > 1 else ''
                        d = {'id': full_id, 'name': item_name, 'raw': ie}
                        items.append(d)
                        self.item_lookup[full_id] = d
            except:
                pass

        # Item categories
        _ARMOR_TYPES = set(['itp_type_head_armor', 'itp_type_body_armor',
                            'itp_type_foot_armor', 'itp_type_hand_armor',
                            'itp_type_horse', 'itp_type_horse_harness',
                            'itp_type_shield'])
        _WEAPON_TYPES = set(['itp_type_one_handed_wpn', 'itp_type_two_handed_wpn',
                             'itp_type_polearm', 'itp_type_bow',
                             'itp_type_crossbow', 'itp_type_thrown',
                             'itp_type_pistol', 'itp_type_musket',
                             'itp_type_arrows', 'itp_type_bolts'])
        for it in items:
            raw = it.get('raw', '')
            found_types = set(re.findall(r'itp_type_\w+', raw))
            if found_types & _ARMOR_TYPES:
                self.item_category[it['id']] = 'armor'
            elif found_types & _WEAPON_TYPES:
                self.item_category[it['id']] = 'weapon'
            else:
                self.item_category[it['id']] = 'other'

        # Load translations
        if self.translation_path:
            tcp = os.path.join(self.translation_path, 'troops.csv')
            if os.path.isfile(tcp):
                raw = load_translations(tcp)
                for k, v in raw.items():
                    if k.endswith('_pl'):
                        self.troop_cn_pl[k] = v
                    else:
                        self.troop_cn[k] = v
            icp = os.path.join(self.translation_path, 'item_kinds.csv')
            if os.path.isfile(icp):
                self.item_cn = load_translations(icp)
            fcp = os.path.join(self.translation_path, 'factions.csv')
            if os.path.isfile(fcp):
                self.faction_cn = load_translations(fcp)

        # Parse factions
        fac_path = os.path.join(self.source_path, 'module_factions.py')
        if os.path.isfile(fac_path):
            try:
                with codecs.open(fac_path, 'r', 'utf-8', errors='replace') as ff:
                    fac_text = ff.read()
                # Simplified faction parsing
                for m in re.finditer(r'\("[^"]+",\s*"([^"]*)"', fac_text):
                    fid = m.group(1)
                    fname = m.group(2).replace('{!}', '')
                    cn = self.faction_cn.get('fac_' + fid, '')
                    self.faction_data.append(('fac_' + fid, fname, cn))
            except:
                pass

        # Build item display list
        for it in items:
            zh = self.item_cn.get(it['id'], '') or it.get('name', '')
            self.item_list.append((it['id'], zh))

    # ================================================================
    #  Undo / Redo dispatch
    # ================================================================

    def _undo(self):
        """Dispatch undo to active module."""
        if self._active_module:
            self._active_module.undo()

    def _redo(self):
        """Dispatch redo to active module."""
        if self._active_module:
            self._active_module.redo()

    def _save_current_module(self, event=None):
        """Ctrl+S: delegate to active module."""
        if self._active_module:
            self._active_module.save()

    # ================================================================
    #  UI Building
    # ================================================================

    def _build_ui(self):
        """Build main layout: nav sidebar + content area (Frame for module panels)."""
        outer = tk.PanedWindow(self.root, orient='horizontal',
                               sashrelief='raised', sashwidth=4)
        outer.pack(expand=1, fill='both')

        nav = self._build_nav(outer)
        outer.add(nav, minsize=120)

        # Content area: a simple Frame that holds the active module's panel
        self.content_area = tk.Frame(outer)
        outer.add(self.content_area, minsize=400)

    def _build_nav(self, parent):
        """Build left navigation sidebar with Treeview."""
        nav = tk.Frame(parent, width=150, bg='#f0f0f0')
        nav.pack_propagate(False)

        tk.Label(nav, text=u"\u5bfc\u822a", bg='#f0f0f0',
                 font=('', 10, 'bold')).pack(fill='x', pady=(5, 3), padx=5)

        self.nav_tree = ttk.Treeview(nav, show='tree', selectmode='browse')
        self.nav_tree.pack(expand=1, fill='both', padx=3, pady=(0, 5))

        editor_node = self.nav_tree.insert('', 'end',
            text=u"\u7f16\u8f91\u5668", open=True)
        self.nav_tree.insert(editor_node, 'end',
            text=u"\u5175\u79cd", tags=('troops',))
        self.nav_tree.insert(editor_node, 'end',
            text=u"\u7269\u54c1", tags=('items',))

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
        if tags and tags[0] in self.modules:
            self._show_module(tags[0])

    def _show_module(self, module_name):
        """Switch content panel to the specified module using panel caching."""
        if module_name not in self.modules:
            return

        module = self.modules[module_name]

        # Hide current module
        if self._active_module and self._active_module is not module:
            self._active_module.on_hide()
            if self._active_module.panel:
                self._active_module.panel.pack_forget()

        # Build panel if first time
        if not module._built:
            self.status.config(text=u"\u6b63\u5728\u52a0\u5efa\u754c\u9762...")
            self.root.update_idletasks()
            module.build_panel(self.content_area)
            module._built = True

        # Show panel
        if module.panel:
            module.panel.pack(expand=1, fill='both')

        # Load data asynchronously if not loaded
        if not module._loaded:
            self.status.config(text=u"\u6b63\u5728\u52a0\u8f7d\u6570\u636e...")
            self.root.update_idletasks()
            self.root.after(10, lambda m=module: self._async_load_module(m))

        self._active_module = module
        module.on_show()

        # Update count label
        if module_name == 'troops':
            self._count_lbl.config(text=u"\u5171 %d \u4e2a\u5175\u79cd" % len(module.troops_entries))
        elif module_name == 'items':
            self._count_lbl.config(text=u"\u5171 %d \u4e2a\u7269\u54c1" % len(module.items_entries))

    def _async_load_module(self, module):
        """Load module data in after() callback (non-blocking)."""
        module.load()
        if self._active_module is module:
            module.on_show()
        self.root.update_idletasks()

    # ================================================================
    #  Global Wheel Handler
    # ================================================================

    def _on_global_wheel(self, event):
        """Root-level MouseWheel: dispatch to the region under the cursor."""
        px = self.root.winfo_pointerx()
        py = self.root.winfo_pointery()
        w = self.root.winfo_containing(px, py)
        if w is None:
            return
        if w.winfo_class() == 'Spinbox':
            return
        if self._active_module:
            result = self._active_module.handle_global_wheel(w, event)
            if result == 'break':
                return 'break'

    # ================================================================
    #  Config Persistence
    # ================================================================

    def _load_config(self):
        if os.path.isfile(self._config_path):
            try:
                with codecs.open(self._config_path, 'r', 'utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {}

    def _save_config(self):
        cfg = {
            'mod_path': self.mod_path,
            'source_path': self.source_path,
            'translation_path': self.translation_path,
            'module_info_path': self.module_info_path,
            'build_bat_path': self.build_bat_path,
            'font_size': self.font_size,
            'bg_color': self._config.get('bg_color', ''),
        }
        try:
            with codecs.open(self._config_path, 'w', 'utf-8') as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
        except:
            pass

    def _auto_load(self):
        """Auto-load on startup with saved config."""
        self._update_title()
        if self.mod_path and os.path.isdir(self.mod_path):
            self.status.config(text=u"\u6b63\u5728\u52a0\u8f7d...")
            self.root.update_idletasks()
            self._load_shared_resources()
            self._show_module('troops')

    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    app = TianyouEditor()
    app.run()
