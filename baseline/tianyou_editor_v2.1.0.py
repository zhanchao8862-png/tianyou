#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
天佑战团源码编辑器
Mount & Blade Warband Module System Source Editor
Developer: 李天佑  电话: 15628308654
"""

VERSION = "2.1.0"

CHANGELOG = [
    {
        "version": "2.1.0",
        "date": "2026-06-21",
        "changes": [
            u"修复 raw 文本编辑与兵种级 undo 独立冲突 — 新增 _commit_raw_text() 自动提交机制",
            u"装备管理面板固定在上方，修复切标签页时位置跳动",
            u"文本 widget Ctrl+Z 优先走 edit_undo（文本级撤销），Ctrl+Y 走 edit_redo",
            u"撤销栈跨兵种不清空，仅文本 edit_reset 在 4 个出口清空",
            u"PyInstaller 构建单文件 EXE（7.8 MB）",
        ]
    },
    {
        "version": "2.0.0",
        "date": "2026-06-21",
        "changes": [
            u"全新 line-based 解析器 + 缩进感知，绕过括号陷阱，1079 兵种正确解析",
            u"撤销/重做快照系统（50 步），deepcopy 全量 snapshot",
            u"源码/基本信息双标签页，Text undo 独立",
            u"兵种增删复制、排序移动、搜索过滤",
            u"装备选择对话框（物品列表 + 当前装备面板 + 搜索 + 添删清空）",
            u"MOD 自动检测与配置持久化（tianyou_config.json）",
            u"汉化联动（Troops 中文名匹配显示）",
            u"编译菜单（build_module.bat / module_info 编辑）",
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
except ImportError:
    import tkinter as tk
    from tkinter import filedialog as tkFileDialog
    from tkinter import messagebox as tkMessageBox


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
#  Line-based Entry Parser (handles anomalous ],] in source)
# ============================================================

def parse_array_by_lines(filepath, array_name):
    """Parse a module_*.py file using line-based entry detection.
    Returns (header, entries, footer) where:
      header:  text from file start through 'array_name = [\n'
      entries: list of raw multi-line entry strings (normalized)
      footer:  text from array close ']' to file end
    """
    with codecs.open(filepath, 'r', 'utf-8', errors='replace') as f:
        lines = f.readlines()

    # 1. Find 'array_name = [' line
    arr_start = -1
    for i, line in enumerate(lines):
        if re.match(r'^\s*' + re.escape(array_name) + r'\s*=\s*\[', line):
            arr_start = i
            break
    if arr_start < 0:
        raise ValueError("'%s = [' not found in %s" % (array_name, filepath))

    # Base indent of the array declaration
    base_indent = len(lines[arr_start]) - len(lines[arr_start].lstrip())

    # 2. Find matching ']' at same indent
    arr_close = -1
    for i in range(arr_start + 1, len(lines)):
        stripped = lines[i].rstrip('\r\n')
        line_indent = len(lines[i]) - len(lines[i].lstrip())
        if stripped == ']' and line_indent == base_indent:
            arr_close = i
            break
    if arr_close < 0:
        raise ValueError("Array close ']' not found for '%s = ['" % array_name)

    # 3. Parse entries between arr_start+1 and arr_close
    entries_raw = []
    current_lines = []
    in_entry = False

    for i in range(arr_start + 1, arr_close):
        line = lines[i]
        stripped = line.lstrip()
        if not stripped:
            continue

        # Skip pure comment lines (not commented-out entries)
        if stripped.startswith('#') and not (
            stripped.startswith('##') and 
            len(stripped) > 3 and 
            stripped[2:].lstrip().startswith('[') and
            len(stripped[2:].lstrip()) > 2 and
            stripped[2:].lstrip()[1] in '"\''):
            continue

        # Entry start: line begins with [ + quote
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

    # 4. Build header and footer
    header = ''.join(lines[:arr_start + 1])
    footer = ''.join(lines[arr_close:])

    # 5. Normalize entries: strip trailing comma, fix anomalous '],]' -> ']'
    entries = []
    for e in entries_raw:
        e = e.rstrip('\r\n ')
        e = e.rstrip(',')
        e = e.rstrip()
        # Fix anomalous double bracket (e.g. line ends with '...0000],]')
        if e.endswith(']]'):
            e = e[:-1]
        entries.append(e)

    return header, entries, footer


def parse_fields_in_entry(entry):
    """Parse a single entry's [...] content into a list of field strings.
    Handles nested brackets, strings, and parens."""
    s = entry.strip()
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
            elif c == '\\' and j + 1 < len(s_body):
                j += 1
        j += 1

    if prev < len(s_body):
        fields.append(s_body[prev:].strip())

    return fields


# ============================================================
#  Main Editor Application
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

        # ── Project State ──
        self.mod_path = self._config.get('mod_path', '')
        self.source_path = self._config.get('source_path', '')
        self.translation_path = self._config.get('translation_path', '')
        self.module_info_path = self._config.get('module_info_path', '')
        self.build_bat_path = self._config.get('build_bat_path', '')
        self.font_size = self._config.get('font_size', 10)

        # Source data
        self.troops_header = ""       # lines including 'troops = [\n'
        self.troops_footer = ""       # lines from ']\n' to file end
        self.troops_entries = []      # list of normalized entry strings
        self.troops_fields = []       # parallel list of parsed field lists
        self.selected_idx = -1

        # Items
        self.items = []               # [{'id':'itm_xxx', 'name':'...', 'raw':'...'}]
        self.item_lookup = {}         # 'itm_xxx' -> item dict
        self.item_list = []           # [('itm_xxx', '中文名'), ...] for display

        # Translations
        self.troop_cn = {}            # 'trp_xxx' -> 中文名
        self.item_cn = {}             # 'itm_xxx' -> 中文名

        # Undo/Redo
        self._undo_stack = []
        self._redo_stack = []
        self._undo_max = 50

        # ── Build UI ──
        self._build_menubar()
        self._build_ui()
        self._build_statusbar()
        self._set_ui_state(False)

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Auto-load on startup if paths are valid
        self.status.config(text=u"就绪 — [文件] → [打开MOD] 加载项目")
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

    # ================================================================
    #  Undo / Redo
    # ================================================================

    def _push_undo(self):
        """Save current state before a modification."""
        snap = (copy.deepcopy(self.troops_entries),
                copy.deepcopy(self.troops_fields),
                self.selected_idx)
        self._undo_stack.append(snap)
        if len(self._undo_stack) > self._undo_max:
            self._undo_stack.pop(0)
        self._redo_stack = []  # new action clears redo history

    def _undo(self):
        if not self._undo_stack:
            self.status.config(text=u"没有可以撤销的操作")
            return
        # Push current to redo
        cur = (copy.deepcopy(self.troops_entries),
               copy.deepcopy(self.troops_fields),
               self.selected_idx)
        self._redo_stack.append(cur)
        # Restore from undo
        entries, fields, sel = self._undo_stack.pop()
        self.troops_entries = entries
        self.troops_fields = fields
        self.selected_idx = sel
        self._populate_list(self.search_var.get())
        if sel >= 0:
            self._show_detail()
            self._fill_equipment()
        else:
            self._clear_detail()
            self._clear_equipment()
        self._count_lbl.config(text=u"共 %d 个兵种" % len(self.troops_entries))
        self.status.config(text=u"↩ 已撤销 (剩余 %d 步)" % len(self._undo_stack))

    def _redo(self):
        if not self._redo_stack:
            self.status.config(text=u"没有可以重做的操作")
            return
        # Push current to undo
        cur = (copy.deepcopy(self.troops_entries),
               copy.deepcopy(self.troops_fields),
               self.selected_idx)
        self._undo_stack.append(cur)
        # Restore from redo
        entries, fields, sel = self._redo_stack.pop()
        self.troops_entries = entries
        self.troops_fields = fields
        self.selected_idx = sel
        self._populate_list(self.search_var.get())
        if sel >= 0:
            self._show_detail()
            self._fill_equipment()
        else:
            self._clear_detail()
            self._clear_equipment()
        self._count_lbl.config(text=u"共 %d 个兵种" % len(self.troops_entries))
        self.status.config(text=u"↪ 已重做 (剩余 %d 步)" % len(self._redo_stack))

    # ================================================================
    #  Menu Bar
    # ================================================================

    def _build_menubar(self):
        menubar = tk.Menu(self.root)

        fm = tk.Menu(menubar, tearoff=0)
        fm.add_command(label=u"打开MOD...", command=self._open_mod, accelerator="Ctrl+O")
        fm.add_command(label=u"重新加载", command=self._reload, accelerator="F5")
        fm.add_separator()
        fm.add_command(label=u"退出", command=self._on_close, accelerator="Alt+F4")
        menubar.add_cascade(label=u"文件", menu=fm)

        em = tk.Menu(menubar, tearoff=0)
        em.add_command(label=u"撤销", command=self._undo, accelerator="Ctrl+Z")
        em.add_command(label=u"重做", command=self._redo, accelerator="Ctrl+Y")
        menubar.add_cascade(label=u"编辑", menu=em)

        bm = tk.Menu(menubar, tearoff=0)
        bm.add_command(label=u"设置 module_info 路径...", command=self._set_module_info)
        bm.add_command(label=u"编辑 module_info.py", command=self._edit_module_info)
        bm.add_separator()
        bm.add_command(label=u"运行 build_module.bat", command=self._compile_module)
        menubar.add_cascade(label=u"编译", menu=bm)

        sm = tk.Menu(menubar, tearoff=0)
        self._autostart_var = tk.BooleanVar(value=False)
        sm.add_checkbutton(label=u"开机启动", variable=self._autostart_var,
                           command=self._toggle_autostart)
        sm.add_command(label=u"页面颜色...", command=self._change_color)
        sm.add_command(label=u"字体大小...", command=self._change_font_size)
        menubar.add_cascade(label=u"设置", menu=sm)

        dm = tk.Menu(menubar, tearoff=0)
        dm.add_command(label=u"更新日志", command=self._show_changelog)
        dm.add_command(label=u"教程", command=self._show_tutorial)
        dm.add_separator()
        dm.add_command(label=u"关于", command=self._about)
        menubar.add_cascade(label=u"开发者", menu=dm)

        self.root.config(menu=menubar)
        self.root.bind('<Control-o>', lambda e: self._open_mod())
        self.root.bind('<Control-O>', lambda e: self._open_mod())
        self.root.bind('<F5>', lambda e: self._reload())

    # ================================================================
    #  Main UI
    # ================================================================

    def _build_ui(self):
        main = tk.PanedWindow(self.root, orient='horizontal', sashrelief='raised', sashwidth=4)
        main.pack(expand=1, fill='both')

        # ── Left panel ──
        left = tk.Frame(main, width=350)
        left.pack_propagate(False)
        main.add(left, minsize=250)

        # Search
        sf = tk.Frame(left)
        sf.pack(fill='x', pady=(0, 5))
        tk.Label(sf, text=u"搜索:").pack(side='left')
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self._on_search)
        tk.Entry(sf, textvariable=self.search_var, width=22).pack(side='left', fill='x', expand=1, padx=5)

        # Troop list
        lf = tk.LabelFrame(left, text=u"兵种列表")
        lf.pack(expand=1, fill='both')

        self.troop_lb = tk.Listbox(lf, font=('Consolas', 10), exportselection=False)
        self.troop_lb.pack(side='left', expand=1, fill='both')
        self.troop_lb.bind('<<ListboxSelect>>', self._on_select)
        self.troop_lb.bind('<Double-Button-1>', self._on_double_click)
        lsb = tk.Scrollbar(lf, command=self.troop_lb.yview)
        lsb.pack(side='right', fill='y')
        self.troop_lb.config(yscrollcommand=lsb.set)

        # Mouse wheel scroll for troop listbox (Windows uses <MouseWheel>)
        def _on_mousewheel(event):
            self.troop_lb.yview_scroll(int(-1 * (event.delta / 120)), 'units')
        self.troop_lb.bind('<MouseWheel>', _on_mousewheel)

        # Action buttons
        bf = tk.Frame(left)
        bf.pack(fill='x', pady=5)
        tk.Button(bf, text=u"新增兵种", command=self._add_troop, width=8).pack(side='left', padx=2)
        tk.Button(bf, text=u"复制兵种", command=self._copy_troop, width=8).pack(side='left', padx=2)
        tk.Button(bf, text=u"删除兵种", command=self._delete_troop, width=8).pack(side='left', padx=2)
        self._btn_move_up = tk.Button(bf, text=u"▲", command=self._move_troop_up, width=2)
        self._btn_move_up.pack(side='left', padx=1)
        self._btn_move_down = tk.Button(bf, text=u"▼", command=self._move_troop_down, width=2)
        self._btn_move_down.pack(side='left', padx=1)
        self._save_btn = tk.Button(bf, text=u"保  存", command=self._save_troops, width=8,
                                    bg='#4CAF50', fg='white')
        self._save_btn.pack(side='right', padx=2)

        # ── Right panel ──
        right = tk.Frame(main)
        main.add(right, minsize=400)

        # Title
        self.detail_title = tk.Label(right, text=u"请选择一个兵种", font=('', 12, 'bold'),
                                     anchor='w', fg='#333')
        self.detail_title.pack(fill='x', pady=(0, 5))

        # Tab buttons
        tbf = tk.Frame(right)
        tbf.pack(fill='x')
        self._tab_btns = {}
        self._tab_frames = {}
        for key, label in [('info', u'基本信息'), ('raw', u'源码')]:
            btn = tk.Button(tbf, text=label, relief='raised', width=12,
                            command=lambda k=key: self._show_tab(k))
            btn.pack(side='left', padx=1)
            self._tab_btns[key] = btn
            frame = tk.Frame(right)
            self._tab_frames[key] = frame

        # Info frame
        self._info_text = tk.Text(self._tab_frames['info'], font=('Consolas', 10),
                                  wrap='word', state='disabled')
        self._info_text.pack(expand=1, fill='both')

        # Raw frame
        self._raw_text = tk.Text(self._tab_frames['raw'], font=('Consolas', 10), wrap='none', undo=True)
        self._raw_text.pack(expand=1, fill='both')
        # Text-level undo/redo (takes priority over troop-level when focused)
        for seq in ('<Control-z>', '<Control-Z>'):
            self._raw_text.bind(seq, lambda e: self._raw_text.edit_undo() or 'break')
        for seq in ('<Control-y>', '<Control-Y>'):
            self._raw_text.bind(seq, lambda e: self._raw_text.edit_redo() or 'break')

        self._current_tab = 'info'
        self._tab_btns['info'].config(relief='sunken')

        # Equipment panel - always at top
        eqf = tk.LabelFrame(right, text=u"装备管理")
        eqf.pack(side='top', fill='x', pady=(5, 0))

        # Tab frame - fills remaining space below equipment
        self._tab_frames['info'].pack(side='top', expand=1, fill='both')

        eqi = tk.Frame(eqf)
        eqi.pack(fill='x', padx=5, pady=5)

        self.eq_lb = tk.Listbox(eqi, font=('Consolas', 9), height=5, exportselection=False)
        self.eq_lb.pack(side='left', expand=1, fill='x')

        eqb = tk.Frame(eqi)
        eqb.pack(side='right', fill='y', padx=(5, 0))
        self._btn_add_eq = tk.Button(eqb, text=u"添加装备", command=self._add_equipment, width=10)
        self._btn_add_eq.pack(pady=2)
        self._btn_rm_eq = tk.Button(eqb, text=u"移除选中", command=self._remove_equipment, width=10)
        self._btn_rm_eq.pack(pady=2)
        self._btn_clr_eq = tk.Button(eqb, text=u"清空装备", command=self._clear_equipment, width=10)
        self._btn_clr_eq.pack(pady=2)

    def _commit_raw_text(self):
        """Save raw widget edits to troops_entries with undo snapshot."""
        if self._current_tab == 'raw' and self.selected_idx >= 0:
            raw = self._raw_text.get('1.0', 'end-1c').strip()
            if raw and raw != self.troops_entries[self.selected_idx]:
                self._push_undo()
                self.troops_entries[self.selected_idx] = raw
                self.troops_fields[self.selected_idx] = parse_fields_in_entry(raw)

    def _show_tab(self, key):
        if self._current_tab == 'raw':
            self._commit_raw_text()
        self._tab_frames[self._current_tab].pack_forget()
        self._tab_btns[self._current_tab].config(relief='raised')
        self._tab_frames[key].pack(side='top', expand=1, fill='both')
        self._tab_btns[key].config(relief='sunken')
        self._current_tab = key
        if key == 'raw' and 0 <= self.selected_idx < len(self.troops_entries):
            self._raw_text.delete('1.0', tk.END)
            self._raw_text.insert('1.0', self.troops_entries[self.selected_idx])
            self._raw_text.edit_reset()

    def _build_statusbar(self):
        sf = tk.Frame(self.root, bd=1, relief='sunken')
        sf.pack(side='bottom', fill='x')
        self.status = tk.Label(sf, text="", anchor='w')
        self.status.pack(side='left', fill='x', expand=1, padx=5)
        self._count_lbl = tk.Label(sf, text="", anchor='e')
        self._count_lbl.pack(side='right', padx=5)

    def _set_ui_state(self, enabled):
        state = 'normal' if enabled else 'disabled'
        for w in [self.troop_lb, self._btn_add_eq, self._btn_rm_eq, self._btn_clr_eq,
                  self._btn_move_up, self._btn_move_down]:
            w.config(state=state)
        for btn in self._tab_btns.values():
            btn.config(state=state)

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
        """Auto-load MOD on startup from saved config."""
        self._load_data()

    # ================================================================
    #  File Operations
    # ================================================================

    def _open_mod(self):
        path = tkFileDialog.askdirectory(
            title=u"选择 MOD 根目录",
            initialdir=self.mod_path or
            r"G:\1_ruanjian\game\qikan\Mount&Blade Warband\Modules")
        if not path:
            return
        self.mod_path = path

        # Auto-detect source directory
        for cand in ('source', 'src', '1175source', 'source 1.171', 'Module_system 1.171'):
            sp = os.path.join(path, cand)
            if os.path.isdir(sp) and any(f.startswith('module_') and f.endswith('.py')
                                          for f in os.listdir(sp)):
                self.source_path = sp
                break
        else:
            sp = tkFileDialog.askdirectory(title=u"选择源码目录", initialdir=path)
            if not sp:
                return
            self.source_path = sp

        # Auto-detect translations
        for cand in (u'languages/cns', u'languages/zh', u'languages/chs'):
            tp = os.path.join(path, cand)
            if os.path.isdir(tp):
                self.translation_path = tp
                break

        # Auto-detect module_info
        mi = os.path.join(self.source_path, 'module_info.py')
        if os.path.isfile(mi):
            self.module_info_path = mi

        # Auto-detect build script (check source dir first, then mod root)
        self.build_bat_path = ''
        for search_dir in (self.source_path, path):
            if not search_dir or not os.path.isdir(search_dir):
                continue
            for bat in ('build_module.bat', 'build.bat', 'compile.bat'):
                bp = os.path.join(search_dir, bat)
                if os.path.isfile(bp):
                    self.build_bat_path = bp
                    break
            if self.build_bat_path:
                break

        self._save_config()
        self._update_title()
        self._load_data()
        self.root.update()

    def _reload(self):
        if not self.mod_path:
            tkMessageBox.showwarning(u"提示", u"请先打开MOD")
            return
        self._load_data()

    # ================================================================
    #  Data Loading
    # ================================================================

    def _load_data(self):
        """Load troops, items, and translations."""
        # --- Troops ---
        tp = os.path.join(self.source_path, 'module_troops.py')
        if not os.path.isfile(tp):
            tkMessageBox.showerror(u"错误", u"找不到 module_troops.py")
            return

        try:
            header, entries, footer = parse_array_by_lines(tp, 'troops')
        except ValueError as e:
            tkMessageBox.showerror(u"解析错误", unicode(e))
            return

        self.troops_header = header
        self.troops_footer = footer
        self.troops_entries = entries
        self.troops_fields = [parse_fields_in_entry(e) for e in entries]

        # --- Items ---
        ip = os.path.join(self.source_path, 'module_items.py')
        self.items = []
        self.item_lookup = {}
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
                        self.items.append(d)
                        self.item_lookup[full_id] = d
            except:
                pass

        # --- Translations ---
        self.troop_cn = {}
        self.item_cn = {}
        if self.translation_path:
            tcp = os.path.join(self.translation_path, 'troops.csv')
            if os.path.isfile(tcp):
                self.troop_cn = load_translations(tcp)
            icp = os.path.join(self.translation_path, 'item_kinds.csv')
            if os.path.isfile(icp):
                self.item_cn = load_translations(icp)

        # --- Build item display list ---
        self.item_list = []
        for it in self.items:
            zh = self.item_cn.get(it['id'], '') or it.get('name', '')
            self.item_list.append((it['id'], zh))

        # --- Populate UI ---
        self._populate_list()
        self.selected_idx = -1
        self._clear_detail()
        self._clear_equipment()
        self._set_ui_state(len(self.troops_entries) > 0)
        self._count_lbl.config(text=u"共 %d 个兵种" % len(self.troops_entries))
        self.status.config(text=u"✅ 已加载: %s | 兵种: %d | 物品: %d" % (
            os.path.basename(self.mod_path), len(self.troops_entries), len(self.items)))

    # ================================================================
    #  List Population
    # ================================================================

    def _populate_list(self, filter_text=""):
        self.troop_lb.delete(0, tk.END)
        self._list_index_map = []
        ft = filter_text.lower().strip()
        for i, flds in enumerate(self.troops_fields):
            tid = flds[0].strip('"').strip("'") if flds else '???'
            full_id = 'trp_' + tid if not tid.startswith('trp_') else tid
            zh = self.troop_cn.get(full_id, '')
            display = u'%-4d %s' % (i, full_id)
            if zh:
                display += u'  %s' % zh
            if not ft or ft in full_id.lower() or ft in zh.lower():
                self.troop_lb.insert(tk.END, display)
                self._list_index_map.append(i)

    def _on_search(self, *args):
        self._populate_list(self.search_var.get())

    # ================================================================
    #  Selection & Detail
    # ================================================================

    def _on_select(self, event):
        sel = self.troop_lb.curselection()
        if not sel:
            return
        vis_idx = sel[0]
        if vis_idx < len(self._list_index_map):
            self._commit_raw_text()  # save current troop's text before switching
            self.selected_idx = self._list_index_map[vis_idx]
            self._show_detail()
            self._fill_equipment()

    def _on_double_click(self, event):
        """Double-click on troop list -> focus equipment."""
        self._on_select(event)
        if self.selected_idx >= 0:
            self._add_equipment()

    def _show_detail(self):
        idx = self.selected_idx
        if idx < 0 or idx >= len(self.troops_fields):
            self._clear_detail()
            return

        flds = self.troops_fields[idx]
        tid = flds[0].strip('"').strip("'") if flds else '???'
        full_id = 'trp_' + tid if not tid.startswith('trp_') else tid
        zh = self.troop_cn.get(full_id, u'(无汉化)')

        self.detail_title.config(text=u'#%d  %s — %s' % (idx, full_id, zh))

        # Info tab
        info = []
        info.append(u'═' * 60)
        info.append(u'  索引: %d    兵种 ID: %s    中文名: %s' % (idx, full_id, zh))
        info.append(u'─' * 60)

        field_names = [
            u'ID(1)', u'名称(2)', u'复数名(3)',
            u'Flags(4)', u'Scene(5)', u'Reserved(6)',
            u'Faction(7)', u'装备(8)', u'属性(9)',
            u'熟练度(10)', u'技能(11)', u'Face码(12)'
        ]
        for fi, fv in enumerate(flds):
            label = field_names[fi] if fi < len(field_names) else u'字段%d' % (fi + 1)
            info.append(u'  %s: %s' % (label, fv))
        info.append(u'═' * 60)

        self._info_text.config(state='normal')
        self._info_text.delete('1.0', tk.END)
        self._info_text.insert('1.0', '\n'.join(info))
        self._info_text.config(state='disabled')

        # Raw tab
        if self._current_tab == 'raw':
            self._raw_text.delete('1.0', tk.END)
            self._raw_text.insert('1.0', self.troops_entries[idx])
            self._raw_text.edit_reset()  # clear undo stack for new troop content

    def _clear_detail(self):
        self.detail_title.config(text=u"请选择一个兵种")
        self._info_text.config(state='normal')
        self._info_text.delete('1.0', tk.END)
        self._info_text.config(state='disabled')
        self._raw_text.delete('1.0', tk.END)
        self._raw_text.edit_reset()

    # ================================================================
    #  Equipment Display & Editing
    # ================================================================

    def _fill_equipment(self):
        idx = self.selected_idx
        if idx < 0 or idx >= len(self.troops_fields):
            self._clear_equipment()
            return

        self.eq_lb.delete(0, tk.END)
        flds = self.troops_fields[idx]
        inv_raw = flds[7] if len(flds) > 7 else '[]'
        ids = parse_inventory(inv_raw)

        for i, iid in enumerate(ids):
            zh = self.item_cn.get(iid, '') or (self.item_lookup.get(iid, {}) or {}).get('name', '')
            self.eq_lb.insert(tk.END, u'Slot%-2d  %s  %s' % (i, iid, zh))

    def _clear_equipment(self):
        self.eq_lb.delete(0, tk.END)

    def _update_inventory(self, idx, new_inv):
        """Replace inventory field (index 7) and rebuild entry."""
        flds = self.troops_fields[idx]
        while len(flds) <= 7:
            flds.append('0')
        flds[7] = new_inv
        # Rebuild entry from fields
        self.troops_entries[idx] = '  [' + ', '.join(flds) + ']'
        self.troops_fields[idx] = flds

    def _add_equipment(self):
        idx = self.selected_idx
        if idx < 0:
            tkMessageBox.showwarning(u"提示", u"请先选择一个兵种")
            return

        flds = self.troops_fields[idx]
        inv_raw = flds[7] if len(flds) > 7 else '[]'
        current_ids = parse_inventory(inv_raw)
        tid = flds[0].strip('"').strip("'") if flds else '???'

        dlg = tk.Toplevel(self.root)
        dlg.title(u"选择装备 — %s" % tid)
        dlg.geometry("720x560")
        dlg.transient(self.root)

        # Search
        sf = tk.Frame(dlg)
        sf.pack(fill='x', padx=5, pady=5)
        tk.Label(sf, text=u"搜索物品:").pack(side='left')
        sv = tk.StringVar()
        tk.Entry(sf, textvariable=sv, width=30).pack(side='left', padx=5)
        tk.Label(sf, text=u"共 %d 件物品" % len(self.item_list), fg='#666').pack(side='right')

        # Current equipment
        cef = tk.LabelFrame(dlg, text=u"当前装备 (双击移除)")
        cef.pack(fill='x', padx=5, pady=5)
        ce_lb = tk.Listbox(cef, font=('Consolas', 9), height=4)
        ce_lb.pack(fill='x', padx=5, pady=5)
        ce_lb.bind('<Double-Button-1>', lambda e: _del_selected(ce_lb))

        for iid in current_ids:
            zh = self.item_cn.get(iid, '') or (self.item_lookup.get(iid, {}) or {}).get('name', '')
            ce_lb.insert(tk.END, u'%s | %s' % (iid, zh))

        # All items
        itf = tk.LabelFrame(dlg, text=u"物品列表 (双击或多选后点添加)")
        itf.pack(expand=1, fill='both', padx=5, pady=5)

        ilb = tk.Listbox(itf, font=('Consolas', 9), selectmode=tk.MULTIPLE)
        ilb.pack(side='left', expand=1, fill='both')
        isb = tk.Scrollbar(itf, command=ilb.yview)
        isb.pack(side='right', fill='y')
        ilb.config(yscrollcommand=isb.set)
        ilb.bind('<Double-Button-1>', lambda e: _add_selected(ilb, ce_lb))

        def do_filter(*args):
            ilb.delete(0, tk.END)
            kw = sv.get().lower()
            for iid, zh in self.item_list:
                if not kw or kw in iid.lower() or kw in zh.lower():
                    ilb.insert(tk.END, u'%s | %s' % (iid, zh))

        def _add_selected(src_lb, dst_lb):
            sel = src_lb.curselection()
            for si in sel:
                text = src_lb.get(si)
                iid = text.split(' | ')[0].strip()
                if iid not in current_ids:
                    current_ids.append(iid)
                    zh = self.item_cn.get(iid, '') or (self.item_lookup.get(iid, {}) or {}).get('name', '')
                    dst_lb.insert(tk.END, u'%s | %s' % (iid, zh))

        def _del_selected(dst_lb):
            sel = dst_lb.curselection()
            for si in reversed(sel):
                if si < len(current_ids):
                    del current_ids[si]
                dst_lb.delete(si)

        do_filter()
        sv.trace('w', do_filter)

        # Buttons
        bf = tk.Frame(dlg)
        bf.pack(fill='x', padx=5, pady=5)
        tk.Button(bf, text=u"添加 >>",
                  command=lambda: _add_selected(ilb, ce_lb)).pack(side='left', padx=5)
        tk.Button(bf, text=u"<< 移除",
                  command=lambda: _del_selected(ce_lb)).pack(side='left', padx=5)
        tk.Button(bf, text=u"全部清空",
                  command=lambda: (ce_lb.delete(0, tk.END), current_ids.__delslice__(0, len(current_ids)))
                  ).pack(side='left', padx=5)

        def on_confirm():
            self._push_undo()
            new_inv = '[' + ', '.join(current_ids) + ']' if current_ids else '[]'
            self._update_inventory(idx, new_inv)
            self._fill_equipment()
            self._show_detail()
            self.status.config(text=u"装备已修改 (未保存到文件，请点击保存按钮)")
            dlg.destroy()

        tk.Button(bf, text=u"确认", command=on_confirm, width=10,
                  bg='#4CAF50', fg='white').pack(side='right', padx=5)
        tk.Button(bf, text=u"取消", command=dlg.destroy, width=8).pack(side='right', padx=5)

    def _remove_equipment(self):
        idx = self.selected_idx
        if idx < 0:
            return
        sel = self.eq_lb.curselection()
        if not sel:
            tkMessageBox.showwarning(u"提示", u"请先在装备列表中选择要移除的装备")
            return

        self._push_undo()
        flds = self.troops_fields[idx]
        inv_raw = flds[7] if len(flds) > 7 else '[]'
        ids = parse_inventory(inv_raw)

        for si in reversed(sel):
            if si < len(ids):
                del ids[si]

        new_inv = '[' + ', '.join(ids) + ']' if ids else '[]'
        self._update_inventory(idx, new_inv)
        self._fill_equipment()
        self._show_detail()
        self.status.config(text=u"装备已移除 (未保存到文件)")

    def _clear_equipment(self):
        idx = self.selected_idx
        if idx < 0:
            return
        flds = self.troops_fields[idx]
        tid = flds[0].strip('"').strip("'") if flds else '???'
        if not tkMessageBox.askyesno(u"确认", u"确定清空 %s 的全部装备？" % tid):
            return
        self._push_undo()
        self._update_inventory(idx, '[]')
        self._fill_equipment()
        self._show_detail()
        self.status.config(text=u"装备已清空 (未保存到文件)")

    # ================================================================
    #  Troop CRUD
    # ================================================================

    def _add_troop(self):
        if not tkMessageBox.askyesno(u"确认", u"确定新增一个空兵种模板？\n将添加到列表末尾。"):
            return

        self._push_undo()
        template = '  ["new_troop","New Troop","New Troops",tf_hero,no_scene,reserved,fac_commoners,[],def_attrib,wp(60),knows_common,0x0000000000000000000000000000000000000000000000000000000000000000]'
        fields = parse_fields_in_entry(template)

        self.troops_entries.append(template)
        self.troops_fields.append(fields)

        self._populate_list(self.search_var.get())
        self.selected_idx = len(self.troops_entries) - 1
        self._show_detail()
        self._fill_equipment()
        self._count_lbl.config(text=u"共 %d 个兵种" % len(self.troops_entries))
        self.status.config(text=u"已新增兵种 (未保存到文件)")

    def _copy_troop(self):
        idx = self.selected_idx
        if idx < 0:
            tkMessageBox.showwarning(u"提示", u"请先选择一个兵种")
            return

        flds = self.troops_fields[idx]
        tid = flds[0].strip('"').strip("'") if flds else '???'
        if not tkMessageBox.askyesno(u"确认", u"确定复制兵种 %s？" % tid):
            return

        self._push_undo()
        new_flds = copy.deepcopy(flds)
        new_tid = '"' + tid + '_copy"'
        new_flds[0] = new_tid
        new_entry = '  [' + ', '.join(new_flds) + ']'

        self.troops_entries.append(new_entry)
        self.troops_fields.append(new_flds)

        self._populate_list(self.search_var.get())
        self.selected_idx = len(self.troops_entries) - 1
        self._show_detail()
        self._fill_equipment()
        self._count_lbl.config(text=u"共 %d 个兵种" % len(self.troops_entries))
        self.status.config(text=u"已复制兵种 (未保存到文件)")

    def _delete_troop(self):
        idx = self.selected_idx
        if idx < 0:
            tkMessageBox.showwarning(u"提示", u"请先选择一个兵种")
            return

        flds = self.troops_fields[idx]
        tid = flds[0].strip('"').strip("'") if flds else '???'
        if not tkMessageBox.askyesno(u"确认删除",
                                     u"确定永久删除兵种 %s？\n\n"
                                     u"⚠ 此操作不可撤销！\n"
                                     u"删除后请点击保存按钮写入文件。" % tid):
            return

        self._push_undo()
        del self.troops_entries[idx]
        del self.troops_fields[idx]

        self.selected_idx = -1
        self._populate_list(self.search_var.get())
        self._clear_detail()
        self._clear_equipment()
        self._count_lbl.config(text=u"共 %d 个兵种" % len(self.troops_entries))
        self.status.config(text=u"已删除兵种 (未保存到文件)")

    # ================================================================
    #  Troop Reordering
    # ================================================================

    def _reorder_troops(self, from_idx, to_idx):
        if from_idx == to_idx or min(from_idx, to_idx) < 0:
            return
        if max(from_idx, to_idx) >= len(self.troops_entries):
            return
        self._push_undo()
        entry = self.troops_entries.pop(from_idx)
        field = self.troops_fields.pop(from_idx)
        self.troops_entries.insert(to_idx, entry)
        self.troops_fields.insert(to_idx, field)
        self._populate_list(self.search_var.get())
        self.selected_idx = to_idx
        self._show_detail()
        self._fill_equipment()
        self.status.config(text=u"兵种已移动 (未保存到文件)")

    def _move_troop_up(self):
        idx = self.selected_idx
        if idx > 0:
            self._reorder_troops(idx, idx - 1)
            self._select_after_move(idx - 1)

    def _move_troop_down(self):
        idx = self.selected_idx
        if idx < len(self.troops_entries) - 1:
            self._reorder_troops(idx, idx + 1)
            self._select_after_move(idx + 1)

    def _select_after_move(self, data_idx):
        try:
            vis_pos = self._list_index_map.index(data_idx)
            self.troop_lb.selection_clear(0, 'end')
            self.troop_lb.selection_set(vis_pos)
            self.troop_lb.see(vis_pos)
        except ValueError:
            pass

    # ================================================================
    #  Save
    # ================================================================

    def _save_troops(self):
        if not self.mod_path:
            tkMessageBox.showwarning(u"提示", u"请先加载 MOD")
            return

        # Save raw tab edits if visible
        if self._current_tab == 'raw' and self.selected_idx >= 0:
            raw = self._raw_text.get('1.0', 'end-1c').strip()
            if raw and raw != self.troops_entries[self.selected_idx]:
                self._push_undo()
                self.troops_entries[self.selected_idx] = raw
                self.troops_fields[self.selected_idx] = parse_fields_in_entry(raw)
            elif raw:
                self.troops_entries[self.selected_idx] = raw
                self.troops_fields[self.selected_idx] = parse_fields_in_entry(raw)

        if not tkMessageBox.askyesno(u"确认保存",
                                     u"确定保存兵种数据到 module_troops.py？\n\n"
                                     u"⚠ 此操作将覆盖源文件！\n"
                                     u"系统会自动创建 .bak 备份。\n\n"
                                     u"当前兵种数: %d" % len(self.troops_entries)):
            return

        # Save raw tab edits (after user confirms)
        if self._current_tab == 'raw' and self.selected_idx >= 0:
            raw = self._raw_text.get('1.0', 'end-1c').strip()
            if raw and raw != self.troops_entries[self.selected_idx]:
                self._push_undo()
                self.troops_entries[self.selected_idx] = raw
                self.troops_fields[self.selected_idx] = parse_fields_in_entry(raw)
            elif raw:
                self.troops_entries[self.selected_idx] = raw
                self.troops_fields[self.selected_idx] = parse_fields_in_entry(raw)

        filepath = os.path.join(self.source_path, 'module_troops.py')

        # Backup
        bak = filepath + '.bak'
        try:
            shutil.copy2(filepath, bak)
        except Exception as e:
            tkMessageBox.showerror(u"错误", u"备份失败: %s" % e)
            return

        # Reconstruct
        try:
            parts = []
            # Header (includes 'troops = [\n')
            parts.append(self.troops_header)

            # Entries
            for i, entry in enumerate(self.troops_entries):
                if i < len(self.troops_entries) - 1:
                    parts.append(entry + ',\n')
                else:
                    parts.append(entry + '\n')

            # Footer (includes ']\n' + everything after)
            parts.append(self.troops_footer)

            output = ''.join(parts)

            with open(filepath, 'wb') as f:
                f.write(output.encode('utf-8'))

        except Exception as e:
            tkMessageBox.showerror(u"错误", u"保存失败: %s" % e)
            return

        self.status.config(text=u"✅ 已保存到 module_troops.py (备份: .bak) — %d 个兵种" % len(
            self.troops_entries))
        self._raw_text.edit_reset()

    # ================================================================
    #  Compile
    # ================================================================

    def _set_module_info(self):
        path = tkFileDialog.askopenfilename(
            title=u"选择 module_info.py",
            filetypes=[("Python files", "module_info.py"), ("All files", "*.*")],
            initialdir=self.source_path)
        if path:
            self.module_info_path = path
            self.status.config(text=u"module_info 路径已设置: %s" % os.path.basename(path))

    def _edit_module_info(self):
        if not self.module_info_path or not os.path.isfile(self.module_info_path):
            tkMessageBox.showwarning(u"提示", u"请先设置 module_info 路径")
            return
        os.startfile(self.module_info_path)

    def _compile_module(self):
        if not self.build_bat_path or not os.path.isfile(self.build_bat_path):
            path = tkFileDialog.askopenfilename(
                title=u"选择编译脚本 (.bat)",
                filetypes=[("Batch files", "*.bat"), ("All files", "*.*")],
                initialdir=self.mod_path if self.mod_path else '/')
            if path:
                self.build_bat_path = path
                self._save_config()
            else:
                return

        if not os.path.isfile(self.build_bat_path):
            tkMessageBox.showerror(u"错误", u"编译脚本不存在:\n%s" % self.build_bat_path)
            self.build_bat_path = ''
            return

        if not tkMessageBox.askyesno(u"确认编译",
                                     u"确定运行编译脚本？\n\n"
                                     u"%s\n\n"
                                     u"编译可能需要较长时间。\n"
                                     u"请在弹出的控制台窗口中查看进度。" % self.build_bat_path):
            return

        try:
            workdir = os.path.dirname(self.build_bat_path)
            bat = os.path.basename(self.build_bat_path)
            # start /D opens a new visible console; more reliable than
            # CREATE_NEW_CONSOLE when called from a noconsole PyInstaller exe
            cmd = 'start "Compile" /D "%s" cmd /k ""%s""' % (
                workdir, bat)
            subprocess.Popen(cmd, cwd=workdir, shell=True)
            self.status.config(text=u"编译已启动 — 请查看控制台窗口")
        except Exception as e:
            tkMessageBox.showerror(u"错误", u"编译启动失败:\n%s" % e)

    # ================================================================
    #  Settings
    # ================================================================

    def _toggle_autostart(self):
        import _winreg as winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "TianyouEditor"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0,
                                 winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE)
            if self._autostart_var.get():
                import sys
                exe_path = sys.argv[0] if hasattr(sys, 'frozen') else sys.executable
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, '"%s"' % exe_path)
                self.status.config(text=u"已设置开机启动")
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                except:
                    pass
                self.status.config(text=u"已取消开机启动")
            winreg.CloseKey(key)
        except Exception as e:
            tkMessageBox.showerror(u"错误", u"设置开机启动失败: %s" % e)

    def _change_color(self):
        colors = ['#F5F5F5', '#E8F5E9', '#E3F2FD', '#FFF3E0',
                  '#FCE4EC', '#FFFFFF', '#F0F4C3', '#E0F7FA']
        dlg = tk.Toplevel(self.root)
        dlg.title(u"选择页面颜色")
        dlg.geometry("400x300")
        dlg.transient(self.root)

        tk.Label(dlg, text=u"选择背景颜色:", font=('', 10)).pack(pady=10)
        cf = tk.Frame(dlg)
        cf.pack(expand=1, fill='both', padx=20)

        def set_bg(clr, win):
            self._apply_bg_color(self.root, clr)
            self._config['bg_color'] = clr
            self._save_config()
            win.destroy()

        r, c = 0, 0
        for color in colors:
            tk.Button(cf, bg=color, width=10, height=3, relief='ridge',
                      command=lambda clr=color, w=dlg: set_bg(clr, w)).grid(row=r, column=c, padx=5, pady=5)
            c += 1
            if c >= 4:
                c = 0
                r += 1

    def _apply_bg_color(self, widget, clr):
        """Recursively apply background color to widget and all children."""
        try:
            widget.config(bg=clr)
        except:
            pass
        try:
            for child in widget.winfo_children():
                self._apply_bg_color(child, clr)
        except:
            pass

    def _change_font_size(self):
        """Popup dialog to change global font size."""
        dlg = tk.Toplevel(self.root)
        dlg.title(u"字体大小")
        dlg.geometry("320x200")
        dlg.transient(self.root)
        dlg.resizable(False, False)

        tk.Label(dlg, text=u"调整字体大小 (8–20)", font=('', 10)).pack(pady=10)

        sv = tk.IntVar(value=self.font_size)
        tk.Scale(dlg, from_=8, to=20, orient='horizontal', variable=sv,
                 length=250, showvalue=True).pack(pady=10)

        def _apply():
            self.font_size = sv.get()
            self._apply_font_size(self.font_size)
            self._config['font_size'] = self.font_size
            self._save_config()
            dlg.destroy()

        bf = tk.Frame(dlg)
        bf.pack(pady=10)
        tk.Button(bf, text=u"确定", command=_apply, width=10,
                  bg='#4CAF50', fg='white').pack(side='left', padx=5)
        tk.Button(bf, text=u"取消", command=dlg.destroy, width=10).pack(side='left', padx=5)

    def _apply_font_size(self, size):
        """Apply font size to all text widgets, listboxes, etc."""
        widgets = [self.troop_lb, self.eq_lb, self._info_text, self._raw_text,
                   self.status, self._count_lbl, self.detail_title]
        for w in widgets:
            try:
                current_font = w.cget('font')
                if isinstance(current_font, tuple):
                    w.config(font=(current_font[0], size) + current_font[2:])
                elif isinstance(current_font, str):
                    w.config(font=(current_font, size))
                else:
                    w.config(font=('', size))
            except:
                pass

    def _update_title(self):
        """Update window title: show MOD path if loaded."""
        if self.mod_path:
            self.root.title(u"天佑战团 v%s — %s" % (VERSION, self.mod_path))
        else:
            self.root.title(u"天佑战团源码编辑器 v%s" % VERSION)

    def _about(self):
        tkMessageBox.showinfo(u"关于",
                              u"天佑战团源码编辑器 v%s\n\n"
                              u"Mount & Blade Warband\n"
                              u"Module System Source Editor\n\n"
                              u"开发者：李天佑\n"
                              u"电话：15628308654\n\n"
                              u"功能：\n"
                              u"\u2022 兵种编辑器 — 查看/新增/复制/删除/排序\n"
                              u"\u2022 装备管理 — 双击兵种快捷选装\n"
                              u"\u2022 源码双标签页（基本信息 + 源码）\n"
                              u"\u2022 撤销/重做（50步快照）\n"
                              u"\u2022 编译集成 + 汉化联动\n\n"
                              u"技术栈：Python 2.7 + Tkinter" % VERSION)

    def _show_changelog(self):
        """Show version history in a scrollable dialog."""
        dlg = tk.Toplevel(self.root)
        dlg.title(u"更新日志 — 天佑战团源码编辑器")
        dlg.geometry("600x500")
        dlg.transient(self.root)
        dlg.grab_set()

        tk.Label(dlg, text=u"天佑战团源码编辑器 — 更新日志",
                 font=('', 13, 'bold'), pady=10).pack()
        tk.Label(dlg, text=u"当前版本: v%s" % VERSION, fg='#666').pack()

        frame = tk.Frame(dlg)
        frame.pack(expand=1, fill='both', padx=15, pady=10)

        sb = tk.Scrollbar(frame)
        sb.pack(side='right', fill='y')
        text = tk.Text(frame, font=('Consolas', 10), wrap='word',
                       yscrollcommand=sb.set)
        text.pack(expand=1, fill='both')
        sb.config(command=text.yview)

        for entry in CHANGELOG:
            text.insert(tk.END, u'\u2501' * 50 + '\n')
            text.insert(tk.END, u'  v%-8s  %s\n' % (entry['version'], entry['date']))
            text.insert(tk.END, u'\u2501' * 50 + '\n')
            for ci, change in enumerate(entry['changes']):
                text.insert(tk.END, u'  %d. %s\n' % (ci + 1, change))
            text.insert(tk.END, '\n')

        text.insert(tk.END,
                    u'─' * 50 + '\n'
                    u'  版本号规则: MAJOR.MINOR.PATCH\n'
                    u'  MAJOR — 架构级重写\n'
                    u'  MINOR — 功能新增 / 较大改动\n'
                    u'  PATCH — Bug 修复 / 文案调整\n')
        text.config(state='disabled')
        tk.Button(dlg, text=u"关闭", command=dlg.destroy, width=12).pack(pady=10)

    def _show_tutorial(self):
        """Show editor tutorial in a scrollable dialog."""
        dlg = tk.Toplevel(self.root)
        dlg.title(u"教程 — 天佑战团源码编辑器")
        dlg.geometry("650x520")
        dlg.transient(self.root)
        dlg.grab_set()

        tk.Label(dlg, text=u"天佑战团源码编辑器 — 使用教程",
                 font=('', 13, 'bold'), pady=10).pack()

        frame = tk.Frame(dlg)
        frame.pack(expand=1, fill='both', padx=15, pady=10)

        sb = tk.Scrollbar(frame)
        sb.pack(side='right', fill='y')
        text = tk.Text(frame, font=('Microsoft YaHei', 10), wrap='word',
                       yscrollcommand=sb.set)
        text.pack(expand=1, fill='both')
        sb.config(command=text.yview)

        tutorial = u"""
══════════════════════════════════════════════
  快速上手
══════════════════════════════════════════════

1. 文件 → 打开MOD 或 Ctrl+O 选择 Mod 主目录
   编辑器会自动检测源码/汉化目录并加载 troops

2. 左侧兵种列表：
   • 双击 → 打开装备选择器
   • 搜索框 → 按 ID 或中文名过滤
   • 新增/复制/删除 → 对应按钮
   • ▲▼ → 上下移动兵种位置

3. 右侧详情面板（两个标签页）：
   • 基本信息 — 兵种全字段解析展示
   • 源码 — 原始 module_troops.py 片段可直接编辑
     → Ctrl+Z/Y 在此标签页内撤回源码修改

4. 顶栏「装备管理」：
   • 双击装备列表项 → 快速打开装备选择器
   • 添加装备 → 打开物品选择对话框（支持搜索）
   • 移除选中 → 删除当前装备
   • 清空装备 → 移除该兵种全部装备

5. 右上角「保存」→ 写入 module_troops.py
   （自动创建 .bak 备份）

══════════════════════════════════════════════
  编译与发布
══════════════════════════════════════════════

6. 编译 → 设置 module_info 路径
   指向游戏的 .exe 目录后，点击「运行 build_module.bat」
   自动编译所有 .py 源文件到 Mod

7. 汉化联动：
   编辑器读取 cns/csv 中的 troop 汉化字段
   自动匹配显示中文名

══════════════════════════════════════════════
  撤销/重做
══════════════════════════════════════════════

8. Ctrl+Z / Ctrl+Y：
   • 焦点在源码框 → 文本级撤销（只撤销文本改动）
   • 焦点在列表/按钮 → 兵种级撤销（增删复制移动装备）
   • 菜单「编辑→撤销」始终走兵种级撤销
   • 快照 50 步，跨兵种不清空

══════════════════════════════════════════════
  快捷键速查
══════════════════════════════════════════════

  Ctrl+O    — 打开 MOD
  F5        — 重新加载
  Ctrl+Z    — 撤销（文本级/兵种级）
  Ctrl+Y    — 重做
  Ctrl+S    — 保存（菜单）
"""

        text.insert('1.0', tutorial)
        text.config(state='disabled')
        tk.Button(dlg, text=u"关闭", command=dlg.destroy, width=12).pack(pady=10)

    # ================================================================
    #  Lifecycle
    # ================================================================

    def _on_close(self):
        if self.mod_path and self.troops_entries:
            if tkMessageBox.askyesno(u"退出", u"退出前是否保存修改？"):
                self._save_troops()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    app = TianyouEditor()
    app.run()
