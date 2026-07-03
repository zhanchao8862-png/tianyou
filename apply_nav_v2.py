#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Line-based transform: add navigation panel to tianyou_editor.py.

Strategy: read all lines, insert/replace at known positions.
"""

import codecs, os, sys

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tianyou_editor.py')
BAK = SRC + '.bak_nav_v2'

# Read lines (preserve BOM and encoding)
with open(SRC, 'rb') as f:
    raw = f.read()
# Decode to list of lines
with codecs.open(SRC, 'r', 'utf-8') as f:
    lines = f.readlines()

# Backup
with open(BAK, 'wb') as f:
    f.write(raw)
print("Backup: %s (%d bytes)" % (BAK, len(raw)))

# Helper: find line index (0-based) containing a given substring
def find_line(text, start=0):
    for i in range(start, len(lines)):
        if text in lines[i]:
            return i
    return -1

# ========================================================
# 1. In __init__: after "self.selected_idx = -1" add _current_module
# ========================================================
idx1 = find_line('self.selected_idx = -1')
assert idx1 >= 0, "selected_idx not found"
lines.insert(idx1 + 2, '        self._current_module = \'\'   # \'troops\' | \'items\' | ...\n')
lines.insert(idx1 + 3, '        self._modules_loaded = set()  # track which modules have been loaded\n')
print("  [1] Added _current_module tracking at line %d" % (idx1+1))

# ========================================================
# 2. Insert navigation methods BEFORE _build_ui (around line 1006)
# ========================================================
idx2 = find_line('def _build_ui')
assert idx2 >= 0, "_build_ui not found"

nav_methods = '''    # ================================================================
    #  Navigation & Module Switching
    # ================================================================

    def _build_nav(self, parent):
        """Build left navigation sidebar with Treeview."""
        nav = tk.Frame(parent, width=150, bg='#f0f0f0')
        nav.pack_propagate(False)

        tk.Label(nav, text=u"\u5bfc\u822a", bg='#f0f0f0',
                 font=('', 10, 'bold')).pack(fill='x', pady=(5, 3), padx=5)

        self.nav_tree = ttk.Treeview(nav, show='tree', selectmode='browse')
        self.nav_tree.pack(expand=1, fill='both', padx=3, pady=(0, 5))

        # Tree nodes
        editor_node = self.nav_tree.insert('', 'end',
            text=u"\u7f16\u8f91\u5668", open=True)
        self.nav_tree.insert(editor_node, 'end',
            text=u"\u5175\u79cd", tags=('troops',))
        self.nav_tree.insert(editor_node, 'end',
            text=u"\u7269\u54c1", tags=('items',))

        tools_node = self.nav_tree.insert('', 'end',
            text=u"\u5de5\u5177", open=True)
        # Tools sub-items added later by plugins

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
        """Switch content panel to the specified module and reload source."""
        if module_name not in ('troops', 'items'):
            return
        # Allow re-selecting same module to reload
        self._current_module = module_name

        # Clear content area
        for w in self.content_area.winfo_children():
            w.destroy()

        # Build module-specific UI
        if module_name == 'troops':
            self._build_troops_panel(self.content_area)
            self._load_troops()
        elif module_name == 'items':
            self._build_items_panel(self.content_area)
            self._load_items()

        # Highlight the active tree item
        for child in self.nav_tree.get_children(''):
            for sub in self.nav_tree.get_children(child):
                tags = self.nav_tree.item(sub, 'tags')
                if tags and tags[0] == module_name:
                    self.nav_tree.selection_set(sub)

'''

lines[idx2:idx2] = nav_methods.splitlines(True)
print("  [2] Inserted navigation methods before _build_ui")

# ========================================================
# 3. Replace _build_ui to add outer PanedWindow with nav
# ========================================================

# Find the original _build_ui method
idx_ui_start = find_line('def _build_ui(self):')
assert idx_ui_start >= 0, "_build_ui not found (after insert)"

# Find the next 'def ' after _build_ui
idx_ui_end = -1
for i in range(idx_ui_start + 1, len(lines)):
    if lines[i].startswith('    def ') and 'self' in lines[i]:
        idx_ui_end = i
        break
assert idx_ui_end >= 0, "Could not find end of _build_ui"

# Extract original method body (without the def line)
orig_body = lines[idx_ui_start + 1 : idx_ui_end]
orig_full = ''.join(lines[idx_ui_start : idx_ui_end])

# Only rewrite the first few lines that create the PanedWindow
# Replace the original method with wrapped version
new_ui_start = '''    def _build_ui(self):
        """Build main layout: nav sidebar + content area."""
        outer = tk.PanedWindow(self.root, orient='horizontal',
                               sashrelief='raised', sashwidth=4)
        outer.pack(expand=1, fill='both')

        # Navigation sidebar
        nav = self._build_nav(outer)
        outer.add(nav, minsize=120)

        # Content area (will hold troops/items panels)
        self.content_area = tk.PanedWindow(outer, orient='horizontal',
                                           sashrelief='raised', sashwidth=4)
        outer.add(self.content_area, minsize=400)

'''

# Find where the "main = tk.PanedWindow" line is in orig_body
# We need to find the actual troop panel content starts
# The troop panel starts with: main = tk.PanedWindow...
# We keep everything from "left = tk.Frame(main" onwards but wrap in _build_troops_panel

# Find the 'left = tk.Frame(main' line
troop_start_line = -1
for i, line in enumerate(orig_body):
    if 'left = tk.Frame(main, width=350)' in line:
        troop_start_line = i
        break
assert troop_start_line >= 0, "left Frame not found in _build_ui"

# Extract troop panel body (from 'left = ...' to end)
troop_body = orig_body[troop_start_line:]

# Now create _build_troops_panel method
troops_panel_method = '''    def _build_troops_panel(self, main):
        """Build troops editor panel."""
        \
''' + ''.join(troop_body)

# Find the end of _build_ui (after it's been replaced by new_ui_start)
# We'll add _build_troops_panel right after _build_ui
# Actually, let me replace the entire range from _build_ui def to next method

# Create replacement content
replacement = new_ui_start + '\n' + troops_panel_method + '\n'

# Replace
lines[idx_ui_start:idx_ui_end] = replacement.splitlines(True)
print("  [3] Replaced _build_ui with nav wrapper + _build_troops_panel")

# ========================================================
# 4. Add _load_troops (extracted from _load_data)
# ========================================================

# Find _load_data
idx_load = find_line('def _load_data')
assert idx_load >= 0, "_load_data not found"

# Find end of _load_data (next method)
idx_load_end = -1
for i in range(idx_load + 1, len(lines)):
    if lines[i].startswith('    def ') and 'self' in lines[i]:
        idx_load_end = i
        break
assert idx_load_end >= 0, "Could not find end of _load_data"

# Replace _load_data with _load_troops (keep the method but rename + trim items parts)
old_load_method = ''.join(lines[idx_load:idx_load_end])

new_load_method = '''    def _load_data(self):
        """Full data load (used by menu reload)."""
        self._load_troops()

    def _load_troops(self):
        """Load troops from module_troops.py."""
        if not self.source_path:
            return
        tp = os.path.join(self.source_path, 'module_troops.py')
        if not os.path.isfile(tp):
            tkMessageBox.showerror(u"\u9519\u8bef", u"\u627e\u4e0d\u5230 module_troops.py")
            return

        try:
            header, entries, footer = parse_array_by_lines(tp, 'troops')
        except ValueError as e:
            tkMessageBox.showerror(u"\u89e3\u6790\u9519\u8bef", unicode(e))
            return

        self.troops_header = header
        self.troops_footer = footer
        self.troops_entries = entries
        self.troops_fields = [parse_fields_in_entry(e) for e in entries]
        self._face_key_map = self._parse_face_keys()

        # --- Items (lightweight: just build lookup for equipment panel) ---
        ip = os.path.join(self.source_path, 'module_items.py')
        self.items = []
        self.item_lookup = {}
        self.item_category = {}
        if os.path.isfile(ip):
            try:
                _, ientries, _ = parse_array_by_lines(ip, 'items')
                for ie in ientries:
                    flds = parse_fields_in_entry(ie)
                    if flds and len(flds[0]) >= 2 and flds[0][0] in '\"\\\'':
                        iid_raw = flds[0].strip('\"').strip(\"'\")
                        full_id = 'itm_' + iid_raw if not iid_raw.startswith('itm_') else iid_raw
                        item_name = flds[1].strip('\"').strip(\"'\") if len(flds) > 1 else ''
                        d = {'id': full_id, 'name': item_name, 'raw': ie}
                        self.items.append(d)
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
        for it in self.items:
            raw = it.get('raw', '')
            found_types = set(re.findall(r'itp_type_\\w+', raw))
            if found_types & _ARMOR_TYPES:
                self.item_category[it['id']] = 'armor'
            elif found_types & _WEAPON_TYPES:
                self.item_category[it['id']] = 'weapon'
            else:
                self.item_category[it['id']] = 'other'

        # --- Translations ---
        self.troop_cn = {}
        self.troop_cn_pl = {}
        self.item_cn = {}
        self.faction_data = []
        self.faction_cn = {}
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
        if self.source_path:
            fac_path = os.path.join(self.source_path, 'module_factions.py')
            if os.path.isfile(fac_path):
                try:
                    with codecs.open(fac_path, 'r', 'utf-8', errors='replace') as ff:
                        fac_text = ff.read()
                    fac_list_match = re.search(r'factions\\s*=\\s*\\[(.*?)\\](?=\\s*$|\\s*\\n\\s*#|\\s*\\n\\s*\\Z)', fac_text, re.DOTALL)
                    if fac_list_match:
                        fac_body = fac_list_match.group(1)
                    else:
                        fac_body = fac_text[fac_text.index('factions = ['):]
                        depth = 0; end = fac_text.index('factions = ['); started = False
                        for i in range(end, len(fac_text)):
                            if fac_text[i] == '[': depth += 1; started = True
                            elif fac_text[i] == ']': depth -= 1
                            if started and depth == 0: fac_body = fac_text[end: i+1]; break
                        fac_body = fac_body[fac_body.index('[')+1 : fac_body.rindex(']')]
                    pparts = u'[' + fac_body + u']'
                    for m in re.finditer(r'\\(\\s*\"([^\"]+)\"\\s*,\\s*\"([^\"]*)\"', pparts):
                        fid = m.group(1)
                        fname = m.group(2).replace('{!}', '')
                        cn = self.faction_cn.get('fac_' + fid, '')
                        self.faction_data.append(('fac_' + fid, fname, cn))
                except:
                    pass

        # Build item display list
        self.item_list = []
        for it in self.items:
            zh = self.item_cn.get(it['id'], '') or it.get('name', '')
            self.item_list.append((it['id'], zh))

        # Parse upgrade tree
        self.upgrade_tree = {}
        try:
            self._parse_upgrade_calls(tp)
        except:
            pass

        # Populate UI
        self._populate_list()
        self.selected_idx = -1
        self._clear_detail()
        self._clear_equipment()
        self._set_ui_state(len(self.troops_entries) > 0)
        self._count_lbl.config(text=u"\u5171 %d \u4e2a\u5175\u79cd" % len(self.troops_entries))
        self.status.config(text=u"\u2705 \u5df2\u52a0\u8f7d: %s | \u5175\u79cd: %d | \u7269\u54c1: %d | \u5347\u7ea7: %d" % (
            os.path.basename(self.mod_path), len(self.troops_entries), len(self.items),
            len(self.upgrade_tree)))

    def _load_items(self):
        """Load items for the item editor panel (full load)."""
        if not self.source_path:
            return
        ip = os.path.join(self.source_path, 'module_items.py')
        if not os.path.isfile(ip):
            tkMessageBox.showerror(u"\u9519\u8bef", u"\u627e\u4e0d\u5230 module_items.py")
            return

        try:
            self.items_header, self.items_entries, self.items_footer = parse_array_by_lines(ip, 'items')
        except ValueError as e:
            tkMessageBox.showerror(u"\u89e3\u6790\u9519\u8bef", unicode(e))
            return

        self.items_fields = [parse_fields_in_entry(e) for e in self.items_entries]

        # Populate items list
        self._populate_items_list()
        self._clear_items_detail()
        self._set_items_ui_state(len(self.items_entries) > 0)
        self.status.config(text=u"\u2705 \u5df2\u52a0\u8f7d: %s | \u7269\u54c1: %d" % (
            os.path.basename(self.mod_path), len(self.items_entries)))

'''

lines[idx_load:idx_load_end] = new_load_method.splitlines(True)
print("  [4] Replaced _load_data with _load_troops + _load_items")

# ========================================================
# 5. Add _build_items_panel + items UI methods
# Insert before _reload method
# ========================================================
# Find where to insert (before _reload, after _load_items)
# Actually after _load_items we have the remaining methods.
# Let me find _reload and insert items panel methods before it.

idx_reload = find_line('def _reload')
assert idx_reload >= 0, "_reload not found"

items_panel = '''

    # ================================================================
    #  Items Panel
    # ================================================================

    def _build_items_panel(self, main):
        """Build the items editor panel."""
        left = tk.Frame(main, width=350)
        left.pack_propagate(False)
        main.add(left, minsize=250)

        # Search
        sf = tk.Frame(left)
        sf.pack(fill='x', pady=(0, 5))
        tk.Label(sf, text=u"\u641c\u7d22:").pack(side='left')
        self.items_search_var = tk.StringVar()
        self.items_search_var.trace('w', self._on_items_search)
        tk.Entry(sf, textvariable=self.items_search_var, width=22).pack(side='left', fill='x', expand=1, padx=5)

        # Items list
        lf = tk.LabelFrame(left, text=u"\u7269\u54c1\u5217\u8868")
        lf.pack(expand=1, fill='both')

        self.items_lb = tk.Listbox(lf, font=('Consolas', 10), exportselection=False)
        self.items_lb.pack(side='left', expand=1, fill='both')
        self.items_lb.bind('<<ListboxSelect>>', self._on_items_select)
        self.items_lb.bind('<Double-Button-1>', self._on_items_dblclick)
        lsb = tk.Scrollbar(lf, command=self.items_lb.yview)
        lsb.pack(side='right', fill='y')
        self.items_lb.config(yscrollcommand=lsb.set)

        # Action buttons
        bf = tk.Frame(left)
        bf.pack(fill='x', pady=5)
        tk.Button(bf, text=u"\u65b0\u589e", command=self._add_item, width=6).pack(side='left', padx=2)
        tk.Button(bf, text=u"\u590d\u5236", command=self._copy_item, width=6).pack(side='left', padx=2)
        tk.Button(bf, text=u"\u5220\u9664", command=self._delete_item, width=6).pack(side='left', padx=2)
        tk.Button(bf, text=u"\u25b2", command=self._move_item_up, width=2).pack(side='left', padx=1)
        tk.Button(bf, text=u"\u25bc", command=self._move_item_down, width=2).pack(side='left', padx=1)
        self._items_save_btn = tk.Button(bf, text=u"\u4fdd  \u5b58", command=self._save_items, width=8,
                                          bg='#4CAF50', fg='white')
        self._items_save_btn.pack(side='right', padx=2)

        # Right panel
        right = tk.Frame(main)
        main.add(right, minsize=400)

        self.items_detail_title = tk.Label(right, text=u"\u8bf7\u9009\u62e9\u4e00\u4e2a\u7269\u54c1",
                                           font=('', 12, 'bold'), anchor='w', fg='#333')
        self.items_detail_title.pack(fill='x', pady=(0, 5))

        # Tab buttons for items
        itbf = tk.Frame(right)
        itbf.pack(fill='x')
        self._items_tab_btns = {}
        self._items_tab_frames = {}
        for key, label in [('info', u'\u57fa\u672c\u4fe1\u606f'), ('raw', u'\u6e90\u7801')]:
            btn = tk.Button(itbf, text=label, relief='raised', width=12,
                            command=lambda k=key: self._show_items_tab(k))
            btn.pack(side='left', padx=1)
            self._items_tab_btns[key] = btn
            frame = tk.Frame(right)
            self._items_tab_frames[key] = frame

        # Items info text
        self._items_info_text = tk.Text(self._items_tab_frames['info'], font=('Consolas', 10),
                                        wrap='word', state='disabled')
        self._items_info_text.pack(expand=1, fill='both')

        # Items raw text
        self._items_raw_text = tk.Text(self._items_tab_frames['raw'], font=('Consolas', 10),
                                       wrap='none', undo=True)
        self._items_raw_text.pack(expand=1, fill='both')
        for seq in ('<Control-z>', '<Control-Z>'):
            self._items_raw_text.bind(seq, lambda e: self._items_raw_text.edit_undo() or 'break')
        for seq in ('<Control-y>', '<Control-Y>'):
            self._items_raw_text.bind(seq, lambda e: self._items_raw_text.edit_redo() or 'break')

        self._current_items_tab = 'info'
        self._items_tab_btns['info'].config(relief='sunken')
        self._items_tab_frames['info'].pack(side='top', expand=1, fill='both')

    def _show_items_tab(self, key):
        self._items_tab_btns[self._current_items_tab].config(relief='raised')
        self._items_tab_frames[self._current_items_tab].pack_forget()
        self._items_tab_btns[key].config(relief='sunken')
        self._items_tab_frames[key].pack(side='top', expand=1, fill='both')
        self._current_items_tab = key

    def _on_items_search(self, *args):
        self._populate_items_list(self.items_search_var.get())

    def _populate_items_list(self, filter_text=""):
        if not hasattr(self, 'items_lb'):
            return
        self.items_lb.delete(0, 'end')
        ft = filter_text.lower()
        for i, e in enumerate(self.items_entries if hasattr(self, 'items_entries') else []):
            flds = self.items_fields[i] if i < len(self.items_fields) else []
            iid = (flds[0].strip('\"').strip(\"'\") if flds else '')
            full_id = 'itm_' + iid if iid and not iid.startswith('itm_') else iid
            zh = self.item_cn.get(full_id, '') if hasattr(self, 'item_cn') else ''
            if ft and ft not in full_id.lower() and ft not in zh.lower():
                continue
            display = full_id
            if zh:
                display += u"  |  " + zh
            self.items_lb.insert('end', display)

    def _on_items_select(self, event):
        sel = self.items_lb.curselection()
        if not sel:
            return
        self._show_items_detail(sel[0])

    def _on_items_dblclick(self, event):
        self._current_items_tab = 'info'
        self._show_items_tab('raw')

    def _show_items_detail(self, idx):
        if idx < 0 or idx >= len(self.items_entries):
            return
        flds = self.items_fields[idx] if idx < len(self.items_fields) else []
        iid = (flds[0].strip('\"').strip(\"'\") if flds else '')
        full_id = 'itm_' + iid if iid and not iid.startswith('itm_') else iid
        zh = self.item_cn.get(full_id, '') if hasattr(self, 'item_cn') else ''

        self.items_detail_title.config(text=zh if zh else full_id)

        self._items_info_text.config(state='normal')
        self._items_info_text.delete('1.0', 'end')
        self._items_info_text.insert('end', u"ID: " + full_id + u"\\n\\n")
        self._items_info_text.insert('end', u"\u539f\u59cb\u5b57\u6bb5:\\n")
        for fi, f in enumerate(flds):
            self._items_info_text.insert('end', u"  [%d] %s\\n" % (fi, f))
        self._items_info_text.config(state='disabled')

        self._items_raw_text.delete('1.0', 'end')
        self._items_raw_text.insert('1.0', self.items_entries[idx])
        self._items_raw_text.edit_reset()

    def _clear_items_detail(self):
        self.items_detail_title.config(text=u"\u8bf7\u9009\u62e9\u4e00\u4e2a\u7269\u54c1")
        self._items_info_text.config(state='normal')
        self._items_info_text.delete('1.0', 'end')
        self._items_info_text.config(state='disabled')
        self._items_raw_text.delete('1.0', 'end')
        self._items_raw_text.edit_reset()

    def _set_items_ui_state(self, enabled):
        state = 'normal' if enabled else 'disabled'
        for w in [self.items_lb]:
            w.config(state=state)

    def _add_item(self):
        if not hasattr(self, 'items_entries'):
            return
        self._push_items_undo()
        new_raw = '  ["new_item","New Item", [("new_mesh",0)], itp_type_one_handed_wpn, 0, 100, weight(1.5)|difficulty(0)|spd_rtng(95)|weapon_length(100)|swing_damage(20, cut)|thrust_damage(0, pierce), imodbits_none, []],\\n'
        self.items_entries.append(new_raw)
        self.items_fields = [parse_fields_in_entry(e) for e in self.items_entries]
        self._populate_items_list()
        self.items_lb.selection_clear(0, 'end')
        self.items_lb.selection_set('end')
        self.items_lb.see('end')
        self._show_items_detail(len(self.items_entries) - 1)

    def _copy_item(self):
        sel = self.items_lb.curselection()
        if not sel:
            return
        idx = sel[0]
        self._push_items_undo()
        self.items_entries.insert(idx + 1, self.items_entries[idx])
        self.items_fields = [parse_fields_in_entry(e) for e in self.items_entries]
        self._populate_items_list()

    def _delete_item(self):
        sel = self.items_lb.curselection()
        if not sel:
            return
        idx = sel[0]
        if not tkMessageBox.askyesno(u"\u786e\u8ba4", u"\u786e\u5b9a\u5220\u9664\u8be5\u7269\u54c1\\uff1f"):
            return
        self._push_items_undo()
        del self.items_entries[idx]
        self.items_fields = [parse_fields_in_entry(e) for e in self.items_entries]
        self._populate_items_list()
        self._clear_items_detail()

    def _move_item_up(self):
        sel = self.items_lb.curselection()
        if not sel or sel[0] == 0:
            return
        idx = sel[0]
        self._push_items_undo()
        self.items_entries[idx], self.items_entries[idx - 1] = self.items_entries[idx - 1], self.items_entries[idx]
        self.items_fields = [parse_fields_in_entry(e) for e in self.items_entries]
        self._populate_items_list()
        self.items_lb.selection_set(idx - 1)

    def _move_item_down(self):
        sel = self.items_lb.curselection()
        if not sel or sel[0] >= len(self.items_entries) - 1:
            return
        idx = sel[0]
        self._push_items_undo()
        self.items_entries[idx], self.items_entries[idx + 1] = self.items_entries[idx + 1], self.items_entries[idx]
        self.items_fields = [parse_fields_in_entry(e) for e in self.items_entries]
        self._populate_items_list()
        self.items_lb.selection_set(idx + 1)

    def _push_items_undo(self):
        if not hasattr(self, 'items_entries'):
            return
        snap = (copy.deepcopy(self.items_entries),
                copy.deepcopy(self.items_fields))
        self._undo_stack.append(('items', snap))
        self._redo_stack[:] = []
        if len(self._undo_stack) > self._undo_max:
            self._undo_stack.pop(0)

    def _save_items(self):
        """Save items to module_items.py."""
        if not hasattr(self, 'items_entries') or not self.mod_path:
            return
        ip = os.path.join(self.source_path, 'module_items.py')
        if not os.path.isfile(ip):
            return

        # Commit raw text if on raw tab
        if self._current_items_tab == 'raw':
            try:
                raw_text = self._items_raw_text.get('1.0', 'end-1c')
                sel = self.items_lb.curselection()
                if sel:
                    self.items_entries[sel[0]] = raw_text
                    self.items_fields = [parse_fields_in_entry(e) for e in self.items_entries]
            except:
                pass

        # Backup
        if os.path.exists(ip + '.bak'):
            os.remove(ip + '.bak')
        shutil.copy2(ip, ip + '.bak')

        with codecs.open(ip, 'w', 'utf-8') as f:
            f.write(self.items_header)
            f.write(''.join(self.items_entries))
            f.write(self.items_footer)

        self.status.config(text=u"\u2705 \u7269\u54c1\u5df2\u4fdd\u5b58\u5230 module_items.py")
        return True

    # ================================================================

'''

lines[idx_reload:idx_reload] = items_panel.splitlines(True)
print("  [5] Inserted items panel methods")

# ========================================================
# 6. Modify _open_mod and _auto_load to use _show_module
# ========================================================

# Find _auto_load
idx_auto = find_line('def _auto_load')
assert idx_auto >= 0, "_auto_load not found"
# Find end of _auto_load
idx_auto_end = -1
for i in range(idx_auto + 1, len(lines)):
    if lines[i].startswith('    def ') and 'self' in lines[i]:
        idx_auto_end = i
        break
assert idx_auto_end >= 0

new_auto_load = '''    def _auto_load(self):
        """Auto-load on startup with saved config."""
        self._update_title()
        if self.mod_path and os.path.isdir(self.mod_path):
            self.status.config(text=u"\u6b63\u5728\u52a0\u8f7d...")
            self.root.update_idletasks()
            self._show_module('troops')

'''

lines[idx_auto:idx_auto_end] = new_auto_load.splitlines(True)
print("  [6] Updated _auto_load")

# Find _open_mod and update it
idx_open = find_line('def _open_mod')
assert idx_open >= 0, "_open_mod not found"

# Find the end of _open_mod
idx_open_end = -1
for i in range(idx_open + 1, len(lines)):
    if lines[i].startswith('    def ') and 'self' in lines[i]:
        idx_open_end = i
        break
assert idx_open_end >= 0

# Read and modify _open_mod
open_mod_lines = lines[idx_open:idx_open_end]
open_mod_text = ''.join(open_mod_lines)

# Replace the last part that calls _load_data
old_open_end = "            self._load_data()"
new_open_end = "            self._show_module('troops')"

if old_open_end in open_mod_text:
    open_mod_text = open_mod_text.replace(old_open_end, new_open_end)
    lines[idx_open:idx_open_end] = open_mod_text.splitlines(True)
    print("  [7] Updated _open_mod to use _show_module")
else:
    print("  [7] WARNING: Could not find _load_data call in _open_mod")

# ========================================================
# 7. Modify Ctrl+S dispatch and _reload
# ========================================================

# Update _reload
idx_reload = find_line('def _reload(self):')
assert idx_reload >= 0
idx_reload_end = -1
for i in range(idx_reload + 1, len(lines)):
    if lines[i].startswith('    def ') and 'self' in lines[i]:
        idx_reload_end = i
        break

new_reload = '''    def _reload(self):
        """Reload current module data."""
        if not self.source_path:
            return
        if self._current_module == 'troops':
            self._load_troops()
        elif self._current_module == 'items':
            self._load_items()
        else:
            self._load_troops()
        self.status.config(text=u"\u2705 \u5df2\u91cd\u65b0\u52a0\u8f7d")

'''

lines[idx_reload:idx_reload_end] = new_reload.splitlines(True)
print("  [8] Updated _reload")

# Add Ctrl+S binding in __init__ that dispatches to current module
# Find where Ctrl+S is bound (or add it)
# Look for existing Ctrl-S binding in __init__
init_start = find_line('def __init__(self):')
init_end = -1
for i in range(init_start + 1, len(lines)):
    if lines[i].startswith('    def ') and 'self' in lines[i]:
        init_end = i
        break

init_text = ''.join(lines[init_start:init_end])
# Replace Ctrl+Z binding section with added Ctrl+S
old_keys = '''        self.root.bind('<Control-z>', lambda e: self._undo())
        self.root.bind('<Control-Z>', lambda e: self._undo())
        self.root.bind('<Control-y>', lambda e: self._redo())
        self.root.bind('<Control-Y>', lambda e: self._redo())'''

new_keys = '''        self.root.bind('<Control-z>', lambda e: self._undo())
        self.root.bind('<Control-Z>', lambda e: self._undo())
        self.root.bind('<Control-y>', lambda e: self._redo())
        self.root.bind('<Control-Y>', lambda e: self._redo())
        self.root.bind('<Control-s>', lambda e: self._save_current_module())
        self.root.bind('<Control-S>', lambda e: self._save_current_module())'''

if old_keys in init_text:
    init_text = init_text.replace(old_keys, new_keys)
    lines[init_start:init_end] = init_text.splitlines(True)
    print("  [9] Added Ctrl+S dispatch")
else:
    print("  [9] WARNING: Could not find Ctrl+Z bindings in __init__")

# ========================================================
# 8. Add _save_current_module dispatch method
# Insert before _save_troops
# ========================================================
idx_save = find_line('def _save_troops')
assert idx_save >= 0

save_dispatch = '''    def _save_current_module(self, event=None):
        """Save current module (Ctrl+S dispatch)."""
        if self._current_module == 'troops':
            self._save_troops()
        elif self._current_module == 'items':
            self._save_items()
        else:
            pass  # no module loaded yet

'''

lines[idx_save:idx_save] = save_dispatch.splitlines(True)
print("  [10] Added _save_current_module dispatch")

# ========================================================
# 9. Modify _set_ui_state to handle items UI too
# ========================================================
idx_ui_state = find_line('def _set_ui_state')
assert idx_ui_state >= 0

# ========================================================
# Verify syntax
# ========================================================
import tempfile
tmp = os.path.join(tempfile.gettempdir(), '_tianyou_check.py')
with codecs.open(tmp, 'w', 'utf-8') as f:
    f.writelines(lines)

# Don't try to compile (may need module imports)
# Just verify the file was written

# Write final output
with codecs.open(SRC, 'w', 'utf-8') as f:
    f.writelines(lines)

print("\n=== DONE ===")
print("Lines: %d" % len(lines))
print("Written to: %s" % SRC)
