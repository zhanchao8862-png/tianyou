#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
天佑战团源码编辑器
Mount & Blade Warband Module System Source Editor
Developer: 李天佑  电话: 15628308654
"""

VERSION = "2.3.0"

CHANGELOG = [
    {
        "version": "2.3.0",
        "date": "2026-06-21",
        "changes": [
            u"技能面板重构: 42技能两列Spinbox+Label,汉化名对齐,knows_xxx_N双向同步",
            u"升级树可视化: 可搜索下拉框,161条记录,最长5级深度,保存时自动同步",
            u"脸型码数字hex值解析: 86定义,传递引用,最多10次迭代",
            u"装备管理(F7)重构: 按部位分类双Listbox展示,双击跳转对应物品",
            u"拥有物品面板: 取消数量限制,滚动条Listbox,拖拽边框调整高度,鼠标悬停滚轮",
            u"详情面板按钮简化: 保存到左栏,详情仅留'应用修改'+'还原',新增Ctrl+S",
            u"SearchableCombobox自定义组件: Toplevel+Listbox,彻底修复滚轮问题",
            u"全局滚轮绑定: root级bind_all+鼠标坐标定位,三区域独立滚轮",
            u"修复: End/Home键列表消失, 背景色递归含交互控件, 解析器split/depth bug",
        ]
    },
    {
        "version": "2.2.0",
        "date": "2026-06-21",
        "changes": [
            u"新增「兵种详情面板」标签页 - 结构化字段编辑(基础信息/属性/技能/熟练度/升级树)",
            u"属性8值、技能28值、熟练度7值 可视化表格编辑,支持直接修改并保存",
            u"标记位分组优化:其他特征+武器特征(匹配header_troops.py tf_*常量)",
            u"装备槽位10格结构化显示与快速编辑入口",
        ]
    },
    {
        "version": "2.1.0",
        "date": "2026-06-21",
        "changes": [
            u"修复 raw 文本编辑与兵种级 undo 独立冲突 - 新增 _commit_raw_text() 自动提交机制",
            u"装备管理面板固定在上方,修复切标签页时位置跳动",
            u"文本 widget Ctrl+Z 优先走 edit_undo(文本级撤销),Ctrl+Y 走 edit_redo",
            u"撤销栈跨兵种不清空,仅文本 edit_reset 在 4 个出口清空",
            u"PyInstaller 构建单文件 EXE(7.8 MB)",
        ]
    },
    {
        "version": "2.0.0",
        "date": "2026-06-21",
        "changes": [
            u"全新 line-based 解析器 + 缩进感知,绕过括号陷阱,1079 兵种正确解析",
            u"撤销/重做快照系统(50 步),deepcopy 全量 snapshot",
            u"源码/基本信息双标签页,Text undo 独立",
            u"兵种增删复制、排序移动、搜索过滤",
            u"装备选择对话框(物品列表 + 当前装备面板 + 搜索 + 添删清空)",
            u"MOD 自动检测与配置持久化(tianyou_config.json)",
            u"汉化联动(Troops 中文名匹配显示)",
            u"编译菜单(build_module.bat / module_info 编辑)",
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
    import ttk  # Python 2.7 ttk (native combobox)
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

# Flags grouped by category (matching header_troops.py tf_* constants)
FLAG_OTHER = [
    # Basic type
    (0x00000001, u"男性"), (0x00000002, u"女性"), (0x00000004, u"不死"),
    # Hero / state
    (0x00000010, u"NPC英雄"), (0x00000020, u"无生命的"), (0x00000040, u"只能击晕"),
    (0x00000080, u"倒下必死"), (0x00000100, u"无法活捉"),
    # Behavior
    (0x00000400, u"骑马的"), (0x00001000, u"商队"), (0x00008000, u"随机面貌"),
    (0x10000000, u"不能作为驻兵"),
]

FLAG_WEAPON = [
    (0x00100000, u"保证有鞋子"), (0x00200000, u"保证穿盔甲"), (0x00400000, u"保证有头盔"),
    (0x00800000, u"保证有手套"), (0x01000000, u"保证有马"), (0x02000000, u"保证有盾"),
    (0x04000000, u"保证远程武器"), (0x08000000, u"保证长杆武器"),
]

ATTR_LABELS = [u"力量 (Str)", u"敏捷 (Agi)", u"智力 (Int)", u"魅力 (Cha)", u"等级 (Level)"]


# Reverse mapping: tf_name string -> bit value (e.g. "tf_hero" -> 0x10)
_tf_labels_bit = {
    u"男性": 0x00000001, u"女性": 0x00000002, u"不死": 0x00000004,
    u"NPC英雄": 0x00000010, u"无生命的": 0x00000020, u"只能击晕": 0x00000040,
    u"倒下必死": 0x00000080, u"无法活捉": 0x00000100,
    u"骑马的": 0x00000400, u"商队": 0x00001000, u"随机面貌": 0x00008000,
    u"不能作为驻兵": 0x10000000,
    u"保证有鞋子": 0x00100000, u"保证穿盔甲": 0x00200000, u"保证有头盔": 0x00400000,
    u"保证有手套": 0x00800000, u"保证有马": 0x01000000, u"保证有盾": 0x02000000,
    u"保证远程武器": 0x04000000, u"保证长杆武器": 0x08000000,
}
# Build TF_LOOKUP: tf_xxx -> bit value (from header_troops.py naming)
TF_LOOKUP = {
    'tf_male': 0x00000001, 'tf_female': 0x00000002, 'tf_undead': 0x00000004,
    'tf_hero': 0x00000010, 'tf_inactive': 0x00000020, 'tf_unkillable': 0x00000040,
    'tf_allways_fall_dead': 0x00000080, 'tf_no_capture_alive': 0x00000100,
    'tf_mounted': 0x00000400, 'tf_is_merchant': 0x00001000, 'tf_randomize_face': 0x00008000,
    'tf_unmoveable_in_party_window': 0x10000000,
    'tf_guarantee_boots': 0x00100000, 'tf_guarantee_armor': 0x00200000,
    'tf_guarantee_helmet': 0x00400000, 'tf_guarantee_gloves': 0x00800000,
    'tf_guarantee_horse': 0x01000000, 'tf_guarantee_shield': 0x02000000,
    'tf_guarantee_ranged': 0x04000000, 'tf_guarantee_polearm': 0x08000000,
}
# Compound constants (aggregate multiple bits)
TF_COMPOUND = {
    'tf_guarantee_all': 0x00100000|0x00200000|0x00400000|0x00800000|0x01000000|0x02000000|0x04000000,
    'tf_guarantee_all_wo_ranged': 0x00100000|0x00200000|0x00400000|0x00800000|0x01000000|0x02000000,
}
# Expand known compounds to their bit values
TF_LOOKUP['tf_guarantee_all'] = TF_COMPOUND['tf_guarantee_all']
TF_LOOKUP['tf_guarantee_all_wo_ranged'] = TF_COMPOUND['tf_guarantee_all_wo_ranged']

# Bit value -> tf_name (for building expression)
BIT_TO_TF = {v: k for k, v in TF_LOOKUP.items() if not k.startswith('tf_guarantee_all')}
# 42 skills based on header_skills.py (skl_xxx constants) with Chinese names
SKILL_LABELS = [
    u"交易", u"统御", u"俘虏管理", u"预留1", u"预留2", u"预留3", u"预留4",
    u"说服力", u"工程学", u"急救", u"手术", u"疗伤", u"物品管理", u"侦察",
    u"向导", u"战术", u"跟踪", u"教练", u"预留5", u"预留6", u"预留7", u"预留8",
    u"掠夺", u"骑射", u"骑术", u"跑动", u"盾防", u"武器掌握",
    u"预留9", u"预留10", u"预留11", u"预留12", u"预留13",
    u"强弓", u"强掷", u"强击", u"铁骨",
    u"预留14", u"预留15", u"预留16", u"预留17", u"预留18",
]

# Maps know_skill name like "riding" to slot index 24 (based on header_skills.py skl_xxx)
SKL_NAME_TO_INDEX = {
    "trade": 0, "leadership": 1, "prisoner_management": 2,
    "reserved_1": 3, "reserved_2": 4, "reserved_3": 5, "reserved_4": 6,
    "persuasion": 7, "engineer": 8, "first_aid": 9, "surgery": 10,
    "wound_treatment": 11, "inventory_management": 12, "spotting": 13,
    "pathfinding": 14, "tactics": 15, "tracking": 16, "trainer": 17,
    "reserved_5": 18, "reserved_6": 19, "reserved_7": 20, "reserved_8": 21,
    "looting": 22, "horse_archery": 23, "riding": 24, "athletics": 25,
    "shield": 26, "weapon_master": 27,
    "reserved_9": 28, "reserved_10": 29, "reserved_11": 30,
    "reserved_12": 31, "reserved_13": 32,
    "power_draw": 33, "power_throw": 34, "power_strike": 35, "ironflesh": 36,
    "reserved_14": 37, "reserved_15": 38, "reserved_16": 39,
    "reserved_17": 40, "reserved_18": 41,
}
SKL_INDEX_TO_NAME = {v: k for k, v in SKL_NAME_TO_INDEX.items()}

PROF_LABELS = [u"单手", u"双手", u"长杆", u"弓", u"弩", u"投掷", u"火器"]

SLOT_LABELS = [u"头部防具", u"身体防具", u"腿部防具", u"手部防具",
               u"主武器", u"副武器", u"武器3", u"武器4", u"马匹", u"马甲"]


def parse_flags(flag_raw):
    """Parse flag field to integer value.
    Handles: 0xHEX, decimal int, tf_hero|tf_male, or mixed tf_xxx|0xNN.
    """
    s = flag_raw.strip()
    if not s or s == '0':
        return 0
    # Plain hex
    if re.match(r'^0[xX][0-9a-fA-F]+$', s):
        return int(s, 16)
    # Plain integer
    if re.match(r'^\d+$', s):
        return int(s)
    # Symbolic expression: tf_hero|tf_male|0xNN|...
    val = 0
    for token in s.split('|'):
        token = token.strip()
        if not token:
            continue
        if token.startswith('0x') or token.startswith('0X'):
            try:
                val |= int(token, 16)
            except ValueError:
                pass
        elif token in TF_LOOKUP:
            val |= TF_LOOKUP[token]
        elif token.isdigit():
            val |= int(token)
        # Unknown tokens are silently ignored
    return val

def build_flags_expr(flag_val):
    """Build symbolic expression from an integer flag value.
    Returns tf_xxx|tf_yyy string, or '0' if empty.
    """
    if flag_val == 0:
        return '0'
    parts = []
    # Sort by bit value ascending for consistent output
    for bit_val, tf_name in sorted(BIT_TO_TF.items()):
        if (flag_val & bit_val) == bit_val:
            parts.append(tf_name)
            flag_val &= ~bit_val  # clear matched bits
    # Any remaining unmatched bits -> 0x...
    if flag_val:
        parts.append('0x%X' % flag_val)
    return '|'.join(parts)


def parse_int_list(raw, default=0):
    """Parse 'wp(N)' or comma-separated int list."""
    s = raw.strip()
    if not s:
        return []
    m = re.match(r'wp\((\d+)\)', s)
    if m:
        v = int(m.group(1))
        return [v] * 4  # wp(N) expands to 4 proficiencies
    # Try bracket list
    if s.startswith('['):
        inner = s.strip('[]')
        parts = [p.strip() for p in inner.split(',')]
        result = []
        for p in parts:
            try:
                result.append(int(p.strip()))
            except ValueError:
                result.append(default)
        return result
    # Single value
    try:
        return [int(s)]
    except ValueError:
        return []


def parse_attr_values(attr_raw):
    """Parse attribute field (8 values)."""
    vals = parse_int_list(attr_raw)
    while len(vals) < 8:
        vals.append(0)
    return vals[:8]

def parse_str_agi_int_cha(attr_raw):
    """Parse str_12|agi_10|int_8|cha_14|level(3) into (str, agi, int, cha, level).
    Handles: str_N, agi_N, int_N, cha_N, level(N), or hex packed value.
    """
    s = attr_raw.strip()
    if not s or s == '0':
        return (0, 0, 0, 0, 0)
    # Hex packed: parse as single int, unpack 5 values (8-bit each, level = higher)
    if s.startswith('0x') or s.startswith('0X'):
        try:
            v = int(s, 16)
            return (v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF, (v >> 24) & 0xFF, 0)
        except ValueError:
            return (0, 0, 0, 0, 0)
    # Symbolic: str_12|agi_10|int_8|cha_14|level(3)
    vals = {'str': 0, 'agi': 0, 'int': 0, 'cha': 0, 'level': 0}
    for token in s.split('|'):
        token = token.strip()
        if not token:
            continue
        m = re.match(r'(str|agi|int|cha)_(\d+)', token)
        if m:
            vals[m.group(1)] = int(m.group(2))
            continue
        m2 = re.match(r'level\((\d+)\)', token)
        if m2:
            vals['level'] = int(m2.group(1))
            continue
    return (vals['str'], vals['agi'], vals['int'], vals['cha'], vals['level'])

def build_attr_expr(str_v, agi_v, int_v, cha_v, level_v):
    """Build str_4|agi_4|int_4|cha_4|level(1) expression from values."""
    parts = []
    if str_v > 0:
        parts.append('str_%d' % str_v)
    if agi_v > 0:
        parts.append('agi_%d' % agi_v)
    if int_v > 0:
        parts.append('int_%d' % int_v)
    if cha_v > 0:
        parts.append('cha_%d' % cha_v)
    if level_v > 0:
        parts.append('level(%d)' % level_v)
    return '|'.join(parts) if parts else '0'

def parse_prof_values(prof_raw):
    """Parse proficiencies: wp_one_handed(100)|wp_two_handed(80)|... or plain int.
    Returns list of 7 values [one_handed, two_handed, polearm, bow, crossbow, throwing, firearm].
    """
    s = prof_raw.strip()
    if not s or s == '0':
        return [0] * 7
    # wp(N) - all same
    m = re.match(r'wp\((\d+)\)$', s)
    if m:
        return [int(m.group(1))] * 7
    # Numeric
    if re.match(r'^\d+$', s):
        v = int(s)
        return [(v >> (i * 10)) & 0x3FF for i in range(7)]
    # Symbolic: wp_one_handed(120)|wp_two_handed(80)|...
    vals = [0] * 7
    prof_map = {
        'wp_one_handed': 0, 'wp_two_handed': 1, 'wp_polearm': 2,
        'wp_archery': 3, 'wp_crossbow': 4, 'wp_throwing': 5, 'wp_firearm': 6,
    }
    for token in s.split('|'):
        token = token.strip()
        m = re.match(r'(wp_[a-z_]+)\((\d+)\)', token)
        if m:
            name, val = m.group(1), int(m.group(2))
            if name in prof_map:
                vals[prof_map[name]] = val
    return vals

def build_prof_expr(prof_vals):
    """Build wp_one_handed(100)|... expression from 7 values."""
    names = ['wp_one_handed', 'wp_two_handed', 'wp_polearm',
             'wp_archery', 'wp_crossbow', 'wp_throwing', 'wp_firearm']
    parts = []
    for name, val in zip(names, prof_vals):
        if val > 0:
            parts.append('%s(%d)' % (name, val))
    # If all same non-zero, use wp(N) shorthand
    if len(parts) == 7 and len(set(prof_vals)) == 1 and prof_vals[0] > 0:
        return 'wp(%d)' % prof_vals[0]
    return '|'.join(parts) if parts else '0'


def parse_skill_values(skill_raw):
    """Parse skill field to 42 values (0-10 each).
    Supports: knows_riding_3|knows_ironflesh_5, 0xHEX, or int list.
    """
    s = skill_raw.strip()
    if not s or s == '0':
        return [0] * 42
    # knows_xxx_N symbolic format
    if 'knows_' in s:
        result = [0] * 42
        for token in s.split('|'):
            token = token.strip()
            m = re.match(r'^knows_([a-z_]+[0-9]*)_([0-9]+)$', token)
            if m:
                skl_name = m.group(1)
                level = int(m.group(2))
                idx = SKL_NAME_TO_INDEX.get(skl_name)
                if idx is not None and 0 <= level <= 10:
                    result[idx] = level
        return result
    # hex format
    if s.startswith('0x') or s.startswith('0X'):
        try:
            v = int(s, 16)
            result = []
            for i in range(42):
                result.append((v >> (i * 4)) & 0xF)
            return result[:42]
        except ValueError:
            pass
    # int list format
    vals = parse_int_list(s)
    while len(vals) < 42:
        vals.append(0)
    return vals[:42]

def build_skill_expr(vals):
    """Build knows_xxx_N expression from 42 skill levels (0-10)."""
    parts = []
    for si in range(42):
        level = int(vals[si]) if isinstance(vals[si], (int, long)) else int(str(vals[si]))
        if level > 0:
            name = SKL_INDEX_TO_NAME.get(si)
            if name is not None:
                parts.append("knows_%s_%d" % (name, level))
    return '|'.join(parts) if parts else '0'


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

        # Entry start: line begins with [ + quote (even if commented with ##)
        is_commented_entry = (stripped.startswith('##') and
                              len(stripped) > 3 and
                              stripped[2:].lstrip().startswith('[') and
                              len(stripped[2:].lstrip()) > 2 and
                              stripped[2:].lstrip()[1] in '"\'')
        is_entry_start = (stripped.startswith('[') and
                          len(stripped) > 2 and
                          stripped[1] in '"\'')

        if is_entry_start or is_commented_entry:
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
    Handles nested brackets, strings, parens, and ##-commented entries."""
    s = entry.strip()
    # Strip ## comment prefix if present
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
            elif c == '\\' and j + 1 < len(s_body):
                j += 1
        j += 1

    if prev < len(s_body):
        fields.append(s_body[prev:].strip())

    return fields


# ============================================================
#  Searchable Combobox Widget
# ============================================================

class SearchableCombobox:
    """Custom combobox with a read-only Entry + overlaid Listbox dropdown.
    Full mouse-wheel control on both Entry and dropdown Listbox.
    Exposes same API as before: set_items, set_value, get_value."""

    def __init__(self, parent, width=40, height=15):
        self.parent = parent
        self.frame = tk.Frame(parent)
        self._id_to_display = {}
        self._display_to_id = {}
        self.on_select_callback = None
        self._items = []          # list of (id, display)
        self._drop_height = height
        self._popdown = None
        self._listbox = None

        # Entry (read-only, mimics a combobox)
        self.var = tk.StringVar()
        self.entry = tk.Entry(self.frame, textvariable=self.var,
                              width=width, state='readonly',
                              readonlybackground='white')
        self.entry.pack(side='left', fill='x', expand=1)

        # Arrow button
        self.arrow_btn = tk.Button(self.frame, text=u'\u25bc', width=2,
                                   command=self._toggle_dropdown)
        self.arrow_btn.pack(side='left')

        # Bindings
        self.entry.bind('<Button-1>', self._toggle_dropdown)
        self.entry.bind('<MouseWheel>', self._on_entry_wheel)
        self.arrow_btn.bind('<MouseWheel>', self._on_entry_wheel)

    # ── Public API ──

    def set_items(self, items):
        """Set all available items. items: list of (id, display_name)"""
        self._id_to_display = {}
        self._display_to_id = {}
        self._items = []
        for item_id, display in items:
            self._id_to_display[item_id] = display
            self._display_to_id[display] = item_id
            self._items.append((item_id, display))

    def set_value(self, value):
        """Set current value by raw troop ID."""
        value = value.strip('"\'')
        if value in self._id_to_display:
            self.var.set(self._id_to_display[value])
        else:
            self.var.set(value)

    def get_value(self):
        """Get current value as raw troop ID."""
        val = self.var.get().strip()
        if ' | ' in val:
            return val.rsplit(' | ', 1)[-1]
        if ' (' in val:
            return val.split(' (')[0]
        return val

    def set_on_select(self, callback):
        """Set callback when item selected. callback(item_id)"""
        self.on_select_callback = callback

    # ── Entry mouse-wheel ──

    def _on_entry_wheel(self, event):
        """Mouse-wheel on entry/arrow button - cycle items."""
        if not self._items:
            return 'break'
        cur_idx = self._current_index()
        new_idx = self._next_index(cur_idx, event.delta)
        self._select_index(new_idx)
        return 'break'  # stop propagation to global wheel handler

    # ── Dropdown show/hide ──

    def _toggle_dropdown(self, event=None):
        if self._popdown and self._popdown.winfo_exists():
            self._hide_dropdown()
        else:
            self._show_dropdown()

    def _show_dropdown(self):
        if not self._items:
            return

        self._hide_dropdown()

        self._popdown = tk.Toplevel(self.frame)
        self._popdown.overrideredirect(True)
        self._popdown.attributes('-topmost', True)

        # Geometry: same width as entry, positioned below it
        ew = self.entry.winfo_width()
        x = self.entry.winfo_rootx()
        y = self.entry.winfo_rooty() + self.entry.winfo_height()
        # Calculate height based on listbox height (approx 16px per row + scrollbar)
        row_height = 16
        max_height = 300  # cap at 300px
        calc_height = min(self._drop_height * row_height + 4, max_height)
        self._popdown.geometry('%dx%d+%d+%d' % (max(ew, 100), calc_height, x, y))
        self._popdown.update_idletasks()

        # Frame with border
        f = tk.Frame(self._popdown, borderwidth=1, relief='solid')
        f.pack(fill='both', expand=1)

        self._listbox = tk.Listbox(f, height=self._drop_height,
                                   exportselection=False)
        for _, display in self._items:
            self._listbox.insert('end', display)

        scrollbar = tk.Scrollbar(f, orient='vertical',
                                 command=self._listbox.yview)
        self._listbox.configure(yscrollcommand=scrollbar.set)
        self._listbox.pack(side='left', fill='both', expand=1)
        scrollbar.pack(side='right', fill='y')

        # Highlight current item
        cur_idx = self._current_index()
        if cur_idx >= 0:
            self._listbox.selection_set(cur_idx)
            self._listbox.see(cur_idx)
            self._listbox.activate(cur_idx)

        # Listbox bindings
        self._listbox.bind('<ButtonRelease-1>', self._on_listbox_click)
        self._listbox.bind('<Return>', self._on_listbox_click)
        self._listbox.bind('<Escape>', lambda e: self._hide_dropdown())
        self._listbox.bind('<MouseWheel>', self._on_listbox_wheel)

        # Click-outside-to-close
        self._popdown.bind('<FocusOut>', self._on_popdown_focusout)
        self._listbox.bind('<FocusOut>', self._on_popdown_focusout)

        self._listbox.focus_set()

    def _hide_dropdown(self):
        if self._popdown:
            try:
                self._popdown.destroy()
            except:
                pass
            self._popdown = None
            self._listbox = None

    def _on_popdown_focusout(self, event=None):
        """Close dropdown when focus leaves it."""
        # Use after to avoid races with listbox selection
        self.frame.after(100, self._check_popdown_focus)

    def _check_popdown_focus(self):
        if not self._popdown or not self._popdown.winfo_exists():
            return
        try:
            focused = self._popdown.focus_get()
            # If focus is inside popdown, keep it open
            if focused and str(focused).startswith(str(self._popdown)):
                return
        except:
            pass
        self._hide_dropdown()

    # ── Listbox interactions ──

    def _on_listbox_wheel(self, event):
        """Mouse-wheel on dropdown listbox - scroll + select."""
        if not self._listbox or not self._items:
            return 'break'
        try:
            sel = self._listbox.curselection()
            cur_idx = int(sel[0]) if sel else 0
        except:
            cur_idx = 0
        new_idx = self._next_index(cur_idx, event.delta)
        self._listbox.selection_clear(0, 'end')
        self._listbox.selection_set(new_idx)
        self._listbox.activate(new_idx)
        self._listbox.see(new_idx)
        # Update entry immediately
        item_id, display = self._items[new_idx]
        self.var.set(display)
        if self.on_select_callback:
            self.on_select_callback(item_id)
        return 'break'

    def _on_listbox_click(self, event=None):
        """Handle click/Enter on listbox item."""
        if not self._listbox:
            return
        try:
            sel = self._listbox.curselection()
            idx = int(sel[0])
        except:
            self._hide_dropdown()
            return
        self._select_index(idx)
        self._hide_dropdown()

    # ── Helpers ──

    def _current_index(self):
        """Return index of currently displayed item, or -1."""
        val = self.var.get()
        if val in self._display_to_id:
            for i, (_, display) in enumerate(self._items):
                if display == val:
                    return i
            return -1
        return -1

    def _next_index(self, cur, delta):
        """Cycle to next/prev index; wraps around."""
        n = len(self._items)
        if not n:
            return -1
        if delta > 0:  # scroll up
            return cur - 1 if cur > 0 else n - 1
        else:          # scroll down
            return cur + 1 if cur < n - 1 else 0

    def _select_index(self, idx):
        """Set combobox to item at index and fire callback."""
        if not self._items or idx < 0 or idx >= len(self._items):
            return
        item_id, display = self._items[idx]
        self.var.set(display)
        if self.on_select_callback:
            self.on_select_callback(item_id)


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
        self._dirty_upgrades = set()  # troop IDs whose upgrade fields changed
        self._face_key_map = {}       # face key name -> hex value lookup
        self.selected_idx = -1
        self._current_module = u''  # navigation state (set by _show_module)

        # ========== Items module state ==========
        self._item_selected_idx = -1
        self._item_undo_stack = []
        self._troops_loaded = False
        self._item_loaded = False
        self._item_redo_stack = []
        self.item_entries = []       # raw entry strings
        self.item_fields_list = []   # parsed field lists
        self.item_header = ""        # lines before 'items = ['
        self.item_footer = ""        # lines from ']' to EOF

        # Items
        self.items = []               # [{'id':'itm_xxx', 'name':'...', 'raw':'...'}]
        self.item_lookup = {}         # 'itm_xxx' -> item dict
        self.item_list = []           # [('itm_xxx', '中文名'), ...] for display

        # Translations
        self.troop_cn = {}            # 'trp_xxx' -> 中文名
        self.item_cn = {}             # 'itm_xxx' -> 中文名
        self.faction_data = []       # [(fac_id, en_name, cn_name), ...]
        self.faction_cn = {}         # 'fac_xxx' -> 中文名
        self.troop_cn_pl = {}        # 'trp_xxx_pl' -> 中文复数名

        # Undo/Redo
        self._undo_stack = []
        self._redo_stack = []
        self._undo_max = 50

        # ── Build UI ──
        self._build_menubar()
        self._build_ui()
        self._build_statusbar()
        # Root-level mousewheel dispatch: Windows sends MouseWheel to focused
        # widget, not the widget under cursor. We check cursor position instead.
        # Neutralize default class-level scroll bindings so bind_all has sole control.
        self.root.bind_class('Listbox', '<MouseWheel>', lambda e: None)
        self.root.bind_class('Canvas', '<MouseWheel>', lambda e: None)
        self.root.bind_all('<MouseWheel>', self._on_global_wheel)
        self._set_ui_state(False)

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Auto-load on startup if paths are valid
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

        # ── Load plugins ──
        self.plugins = []
        self._load_plugins()

    # ================================================================
    #  Undo / Redo
    # ================================================================

    def _push_undo(self):
        """Save current state before a modification."""
        if self._current_module == 'troops':
            snap = (copy.deepcopy(self.troops_entries),
                    copy.deepcopy(self.troops_fields),
                    self.selected_idx)
            self._undo_stack.append(snap)
            if len(self._undo_stack) > self._undo_max:
                self._undo_stack.pop(0)
            self._redo_stack = []
        elif self._current_module == 'items':
            snap = (copy.deepcopy(self.item_entries),
                    copy.deepcopy(self.item_fields_list),
                    self._item_selected_idx)
            self._item_undo_stack.append(snap)
            if len(self._item_undo_stack) > self._undo_max:
                self._item_undo_stack.pop(0)
            self._item_redo_stack = []

    def _undo(self):
        if self._current_module == 'troops':
            self._undo_troops()
        elif self._current_module == 'items':
            self._undo_items()

    def _undo_troops(self):
        if not self._undo_stack:
            self.status.config(text=u"没有可以撤销的操作")
            return
        cur = (copy.deepcopy(self.troops_entries),
               copy.deepcopy(self.troops_fields),
               self.selected_idx)
        self._redo_stack.append(cur)
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

    def _undo_items(self):
        if not self._item_undo_stack:
            self.status.config(text=u"没有可以撤销的操作")
            return
        cur = (copy.deepcopy(self.item_entries),
               copy.deepcopy(self.item_fields_list),
               self._item_selected_idx)
        self._item_redo_stack.append(cur)
        entries, fields, sel = self._item_undo_stack.pop()
        self.item_entries = entries
        self.item_fields_list = fields
        self._item_selected_idx = sel
        self._items_populate_list(self._item_search_var.get())
        if sel >= 0:
            self._show_item_detail()
        else:
            self._clear_item_detail()
        self._item_count_lbl.config(text=u"共 %d 个物品" % len(self.item_entries))
        self.status.config(text=u"↩ 已撤销 (剩余 %d 步)" % len(self._undo_stack))

    def _redo(self):
        if self._current_module == 'troops':
            self._redo_troops()
        elif self._current_module == 'items':
            self._redo_items()

    def _redo_troops(self):
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

    def _redo_items(self):
        if not self._item_redo_stack:
            self.status.config(text=u"没有可以重做的操作")
            return
        cur = (copy.deepcopy(self.item_entries),
               copy.deepcopy(self.item_fields_list),
               self._item_selected_idx)
        self._item_undo_stack.append(cur)
        entries, fields, sel = self._item_redo_stack.pop()
        self.item_entries = entries
        self.item_fields_list = fields
        self._item_selected_idx = sel
        self._items_populate_list(self._item_search_var.get())
        if sel >= 0:
            self._show_item_detail()
        else:
            self._clear_item_detail()
        self._item_count_lbl.config(text=u"共 %d 个物品" % len(self.item_entries))
        self.status.config(text=u"↪ 已重做 (剩余 %d 步)" % len(self._item_redo_stack))

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

        # ── Plugins menu (built from loaded plugins) ──
        self._plugin_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=u"插件", menu=self._plugin_menu)

        self.root.config(menu=menubar)
        self.root.bind('<Control-o>', lambda e: self._open_mod())
        self.root.bind('<Control-O>', lambda e: self._open_mod())
        self.root.bind('<Control-s>', lambda e: self._save_current_module())
        self.root.bind('<Control-S>', lambda e: self._save_current_module())
        self.root.bind('<F5>', lambda e: self._reload())

    # ================================================================
    #  Main UI
    # ================================================================

    def _build_ui(self):
        main = tk.PanedWindow(self.root, orient='horizontal', sashrelief='raised', sashwidth=4)
        main.pack(expand=1, fill='both')

        # ── Navigation panel ──
        nav = tk.Frame(main, width=145, bg='#e8e8e8')
        nav.pack_propagate(False)
        main.add(nav, minsize=110)

        # Nav button style
        self._nav_btn_style = {
            'active': {'bg': '#4a90d9', 'fg': 'white'},
            'normal': {'bg': '#e8e8e8', 'fg': '#333'},
        }

        # ── "编辑器" section (clickable header + foldable sub-items) ──
        self._editor_folded = tk.BooleanVar(value=False)
        editor_hdr = tk.Frame(nav, bg='#e0e0e0', cursor='hand2')
        editor_hdr.pack(fill='x', padx=4, pady=(12, 2))
        editor_hdr.bind('<Button-1>', self._toggle_editor_nav)
        self._editor_fold_icon = tk.Label(editor_hdr,
            text=u"▼ 编辑器",
            font=('Microsoft YaHei', 11, 'bold'), bg='#e0e0e0', fg='#333',
            anchor='w', cursor='hand2')
        self._editor_fold_icon.pack(fill='x', padx=8, pady=4)
        self._editor_fold_icon.bind('<Button-1>', self._toggle_editor_nav)

        # Sub-items container
        self._editor_subframe = tk.Frame(nav, bg='#e8e8e8')
        self._editor_subframe.pack(fill='x')

        self._btn_troops = tk.Button(self._editor_subframe, text=u"  ▸ 兵种", anchor='w',
                                      bg='#4a90d9', fg='white', relief='flat',
                                      font=('Microsoft YaHei', 10), padx=14, pady=6,
                                      activebackground='#3a7bc8', activeforeground='white',
                                      command=lambda: self._show_module('troops'))
        self._btn_troops.pack(fill='x', padx=6, pady=1)

        self._btn_items = tk.Button(self._editor_subframe, text=u"  ▸ 物品", anchor='w',
                                     bg='#e8e8e8', fg='#333', relief='flat',
                                     font=('Microsoft YaHei', 10), padx=14, pady=6,
                                     activebackground='#d0d0d0', activeforeground='#333',
                                     command=lambda: self._show_module('items'))
        self._btn_items.pack(fill='x', padx=6, pady=1)

        # Spacer
        tk.Frame(nav, height=8, bg='#e8e8e8').pack(fill='x')

        # ── "工具" section ──
        tools_hdr = tk.Frame(nav, bg='#e8e8e8')
        tools_hdr.pack(fill='x', padx=4, pady=(8, 2))
        tk.Label(tools_hdr, text=u"工具", font=('Microsoft YaHei', 11, 'bold'),
                 bg='#e8e8e8', fg='#333', anchor='w').pack(fill='x', padx=8, pady=4)

        self._nav_tools_frame = tk.Frame(nav, bg='#e8e8e8')
        self._nav_tools_frame.pack(fill='x')

        # Radar plugin button (placeholder)
        self._btn_radar = tk.Button(self._nav_tools_frame, text=u"  ▸ 雷达", anchor='w',
                                     bg='#e8e8e8', fg='#333', relief='flat',
                                     font=('Microsoft YaHei', 10), padx=14, pady=6,
                                     activebackground='#d0d0d0', activeforeground='#333',
                                     state='disabled')
        self._btn_radar.pack(fill='x', padx=6, pady=1)

        # Spacer
        tk.Frame(nav, height=20, bg='#e8e8e8').pack(fill='x')

        # ── Module container ──
        self._module_container = tk.Frame(main)
        main.add(self._module_container, minsize=500)

        # Build module-specific panels
        self._build_troops_panel(self._module_container)
        self._build_items_panel(self._module_container)

        # Show default module
        self._show_module('troops')

    def _toggle_editor_nav(self, event=None):
        """Toggle collapse/expand of editor sub-items."""
        if self._editor_folded.get():
            self._editor_folded.set(False)
            self._editor_fold_icon.config(text=u"▼ 编辑器")
            self._editor_subframe.pack(fill='x')
        else:
            self._editor_folded.set(True)
            self._editor_fold_icon.config(text=u"▶ 编辑器")
            self._editor_subframe.pack_forget()

    def _show_module(self, name):
        """Switch between troops / items modules."""
        if name == self._current_module:
            return

        # Hide all module frames
        for w in [self._troops_frame, self._items_frame]:
            if w is not None:
                w.pack_forget()

        # Show selected
        style = self._nav_btn_style
        if name == 'troops':
            self._troops_frame.pack(expand=1, fill='both')
            self._btn_troops.config(**style['active'])
            self._btn_items.config(**style['normal'])
            # Lazy load on first visit
            if not self._troops_loaded and self.mod_path:
                self._load_troops_data()
            self.status.config(text=u"兵种模块 — 共 %d 个兵种" % len(self.troops_entries))
        elif name == 'items':
            self._items_frame.pack(expand=1, fill='both')
            self._btn_items.config(**style['active'])
            self._btn_troops.config(**style['normal'])
            # Lazy load on first visit
            if not self._item_loaded and self.mod_path:
                self._load_items_data()
            else:
                self._items_populate_list(self._item_search_var.get())
            self.status.config(text=u"物品模块 — 共 %d 个物品" % len(self.item_entries))

        self._current_module = name

    def _build_troops_panel(self, parent):
        """Build troops module UI inside parent frame."""
        self._troops_frame = tk.Frame(parent)

        inner = tk.PanedWindow(self._troops_frame, orient='horizontal', sashrelief='raised', sashwidth=4)
        inner.pack(expand=1, fill='both')

        # ── Left panel ──
        left = tk.Frame(inner, width=350)
        left.pack_propagate(False)
        inner.add(left, minsize=250)

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
        self.troop_lb.bind('<End>', lambda e: self.troop_lb.after_idle(self._on_key_select))
        self.troop_lb.bind('<Home>', lambda e: self.troop_lb.after_idle(self._on_key_select))
        lsb = tk.Scrollbar(lf, command=self.troop_lb.yview)
        lsb.pack(side='right', fill='y')
        self.troop_lb.config(yscrollcommand=lsb.set)

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
        right = tk.Frame(inner)
        inner.add(right, minsize=400)

        # Title
        self.detail_title = tk.Label(right, text=u"请选择一个兵种", font=('', 12, 'bold'),
                                     anchor='w', fg='#333')
        self.detail_title.pack(fill='x', pady=(0, 5))

        # Tab buttons
        tbf = tk.Frame(right)
        tbf.pack(fill='x')
        self._tab_btns = {}
        self._tab_frames = {}
        for key, label in [('info', u'基本信息'), ('detail', u'兵种详情'), ('raw', u'源码')]:
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

        # Detail frame (structured troop editor)
        self._build_detail_panel(self._tab_frames['detail'])

        # Raw frame
        self._raw_text = tk.Text(self._tab_frames['raw'], font=('Consolas', 10), wrap='none', undo=True)
        self._raw_text.pack(expand=1, fill='both')
        for seq in ('<Control-z>', '<Control-Z>'):
            self._raw_text.bind(seq, lambda e: self._raw_text.edit_undo() or 'break')
        for seq in ('<Control-y>', '<Control-Y>'):
            self._raw_text.bind(seq, lambda e: self._raw_text.edit_redo() or 'break')

        self._current_tab = 'info'
        self._tab_btns['info'].config(relief='sunken')

        # Equipment panel - always at top
        eqf = tk.LabelFrame(right, text=u"拥有物品")
        eqf.pack(side='top', fill='x', pady=(5, 0))

        eqi = tk.Frame(eqf)
        eqi.pack(fill='both', expand=1, padx=5, pady=5)

        self._eq_height = tk.IntVar(value=8)
        self.eq_lb = tk.Listbox(eqi, font=('Consolas', 9), height=8, exportselection=False)
        self.eq_lb.pack(side='left', expand=1, fill='both')
        eq_sb = tk.Scrollbar(eqi, command=self.eq_lb.yview)
        eq_sb.pack(side='right', fill='y')
        self.eq_lb.config(yscrollcommand=eq_sb.set)

        # Buttons below list
        eqb = tk.Frame(eqf)
        eqb.pack(fill='x', padx=5, pady=(0, 5))
        self._btn_add_eq = tk.Button(eqb, text=u"添加", command=self._add_equipment, width=8)
        self._btn_add_eq.pack(side='left', padx=2)
        self._btn_rm_eq = tk.Button(eqb, text=u"移除", command=self._remove_equipment, width=8)
        self._btn_rm_eq.pack(side='left', padx=2)
        self._btn_clr_eq = tk.Button(eqb, text=u"清空", command=self._clear_equipment, width=8)
        self._btn_clr_eq.pack(side='left', padx=2)

        # Resize drag handle below equipment panel
        self._resize_handle = tk.Canvas(right, height=6, bg='#555', cursor='sb_v_double_arrow',
                                         highlightthickness=0, bd=0)
        self._resize_handle.pack(side='top', fill='x', pady=(2, 0))
        self._resize_handle.bind('<Button-1>', self._on_resize_start)
        self._resize_handle.bind('<B1-Motion>', self._on_resize_drag)
        self._resize_handle.bind('<ButtonRelease-1>', self._on_resize_end)
        self._resize_dragging = False
        self._resize_start_y = 0
        self._resize_start_h = 8

        # Tab frame - fills remaining space below equipment
        self._tab_frames['info'].pack(side='top', expand=1, fill='both')

    def _build_items_panel(self, parent):
        """Build items module UI inside parent frame."""
        self._items_frame = tk.Frame(parent)

        inner = tk.PanedWindow(self._items_frame, orient='horizontal', sashrelief='raised', sashwidth=4)
        inner.pack(expand=1, fill='both')

        # ── Left panel ──
        left = tk.Frame(inner, width=350)
        left.pack_propagate(False)
        inner.add(left, minsize=250)

        # Search
        sf = tk.Frame(left)
        sf.pack(fill='x', pady=(0, 5))
        tk.Label(sf, text=u"搜索:").pack(side='left')
        self._item_search_var = tk.StringVar()
        self._item_search_var.trace('w', self._items_on_search)
        tk.Entry(sf, textvariable=self._item_search_var, width=22).pack(side='left', fill='x', expand=1, padx=5)

        # Item list
        lf = tk.LabelFrame(left, text=u"物品列表")
        lf.pack(expand=1, fill='both')

        self._item_lb = tk.Listbox(lf, font=('Consolas', 10), exportselection=False)
        self._item_lb.pack(side='left', expand=1, fill='both')
        self._item_lb.bind('<<ListboxSelect>>', self._items_on_select)
        self._item_lb.bind('<Double-Button-1>', self._items_on_double_click)
        lsb = tk.Scrollbar(lf, command=self._item_lb.yview)
        lsb.pack(side='right', fill='y')
        self._item_lb.config(yscrollcommand=lsb.set)

        # Action buttons
        bf = tk.Frame(left)
        bf.pack(fill='x', pady=5)
        # Count label
        self._item_count_lbl = tk.Label(bf, text=u"共 0 个物品", fg='#666')
        self._item_count_lbl.pack(side='left', padx=2)
        tk.Button(bf, text=u"新增物品", command=self._add_item, width=8).pack(side='left', padx=2)
        tk.Button(bf, text=u"复制物品", command=self._copy_item, width=8).pack(side='left', padx=2)
        tk.Button(bf, text=u"删除物品", command=self._delete_item, width=8).pack(side='left', padx=2)
        self._item_btn_up = tk.Button(bf, text=u"▲", command=self._move_item_up, width=2)
        self._item_btn_up.pack(side='left', padx=1)
        self._item_btn_down = tk.Button(bf, text=u"▼", command=self._move_item_down, width=2)
        self._item_btn_down.pack(side='left', padx=1)
        self._item_save_btn = tk.Button(bf, text=u"保  存", command=self._save_items, width=8,
                                         bg='#4CAF50', fg='white')
        self._item_save_btn.pack(side='right', padx=2)

        # ── Right panel ──
        right = tk.Frame(inner)
        inner.add(right, minsize=400)

        # Title
        self._item_detail_title = tk.Label(right, text=u"请选择一个物品", font=('', 12, 'bold'),
                                           anchor='w', fg='#333')
        self._item_detail_title.pack(fill='x', pady=(0, 5))

        # Tab buttons
        tbf = tk.Frame(right)
        tbf.pack(fill='x')
        self._item_tab_btns = {}
        self._item_tab_frames = {}
        for key, label in [('form', u'编辑器'), ('raw', u'源码')]:
            btn = tk.Button(tbf, text=label, relief='raised', width=12,
                            command=lambda k=key: self._show_item_tab(k))
            btn.pack(side='left', padx=1)
            self._item_tab_btns[key] = btn
            frame = tk.Frame(right)
            self._item_tab_frames[key] = frame

        # Form frame (structured editor with scroll)
        form_outer = tk.Frame(self._item_tab_frames['form'])
        form_outer.pack(expand=1, fill='both')

        self._item_form_canvas = tk.Canvas(form_outer, highlightthickness=0, bg='#f5f5f5')
        self._item_form_scroll = tk.Scrollbar(form_outer, orient='vertical',
                                               command=self._item_form_canvas.yview)
        self._item_form_canvas.configure(yscrollcommand=self._item_form_scroll.set)
        self._item_form_scroll.pack(side='right', fill='y')
        self._item_form_canvas.pack(side='left', expand=1, fill='both')

        self._item_form_inner = tk.Frame(self._item_form_canvas, bg='#f5f5f5')
        self._item_form_canvas.create_window((0, 0), window=self._item_form_inner,
                                              anchor='nw', tags='form_inner')
        self._item_form_inner.bind('<Configure>',
            lambda e: self._item_form_canvas.configure(
                scrollregion=self._item_form_canvas.bbox('all')))
        self._item_form_canvas.bind('<Configure>',
            lambda e: self._item_form_canvas.itemconfig('form_inner',
                width=e.width))

        # Build form sections
        self._build_item_form(self._item_form_inner)

        # Raw frame
        self._item_raw_text = tk.Text(self._item_tab_frames['raw'], font=('Consolas', 10), wrap='none', undo=True)
        self._item_raw_text.pack(expand=1, fill='both')
        for seq in ('<Control-z>', '<Control-Z>'):
            self._item_raw_text.bind(seq, lambda e: self._item_raw_text.edit_undo() or 'break')
        for seq in ('<Control-y>', '<Control-Y>'):
            self._item_raw_text.bind(seq, lambda e: self._item_raw_text.edit_redo() or 'break')

        self._item_current_tab = 'form'
        self._item_tab_btns['form'].config(relief='sunken')

        self._item_tab_frames['form'].pack(side='top', expand=1, fill='both')

    def _show_item_tab(self, key):
        if key == self._item_current_tab:
            return
        # Un-sink old
        if self._item_current_tab in self._item_tab_btns:
            self._item_tab_btns[self._item_current_tab].config(relief='raised')
        # Hide old
        if self._item_current_tab in self._item_tab_frames:
            self._item_tab_frames[self._item_current_tab].pack_forget()
        # Show new
        self._item_tab_btns[key].config(relief='sunken')
        self._item_tab_frames[key].pack(side='top', expand=1, fill='both')
        self._item_current_tab = key
        # Refresh raw content if switching to raw
        if key == 'raw' and self._item_selected_idx >= 0:
            self._item_raw_text.delete('1.0', tk.END)
            self._item_raw_text.insert('1.0', self.item_entries[self._item_selected_idx])
            self._item_raw_text.edit_reset()


    # ================================================================
    #  Items Structured Form
    # ================================================================

    def _build_item_form(self, parent):
        """Build the structured item editor form."""
        p = parent

        # --- Section: Basic Info ---
        tk.Label(p, text=u"基本信息", font=('Microsoft YaHei', 10, 'bold'),
                 fg='#333', bg='#f5f5f5', anchor='w').pack(fill='x', padx=10, pady=(8, 2))

        # Name
        f1 = tk.Frame(p, bg='#f5f5f5')
        f1.pack(fill='x', padx=10, pady=1)
        tk.Label(f1, text=u"名称:", width=8, anchor='e', bg='#f5f5f5').pack(side='left')
        self._item_f_name = tk.StringVar()
        tk.Entry(f1, textvariable=self._item_f_name, width=40).pack(side='left', padx=5)

        # Plural name
        f1b = tk.Frame(p, bg='#f5f5f5')
        f1b.pack(fill='x', padx=10, pady=1)
        tk.Label(f1b, text=u"复数名:", width=8, anchor='e', bg='#f5f5f5').pack(side='left')
        self._item_f_plural = tk.StringVar()
        tk.Entry(f1b, textvariable=self._item_f_plural, width=40).pack(side='left', padx=5)

        # Price
        f2 = tk.Frame(p, bg='#f5f5f5')
        f2.pack(fill='x', padx=10, pady=1)
        tk.Label(f2, text=u"价格:", width=8, anchor='e', bg='#f5f5f5').pack(side='left')
        self._item_f_price = tk.IntVar(value=0)
        tk.Spinbox(f2, textvariable=self._item_f_price, from_=0, to=999999, width=10).pack(side='left', padx=5)

        # Weight
        f2b = tk.Frame(p, bg='#f5f5f5')
        f2b.pack(fill='x', padx=10, pady=1)
        tk.Label(f2b, text=u"重量:", width=8, anchor='e', bg='#f5f5f5').pack(side='left')
        self._item_f_weight = tk.DoubleVar(value=0.0)
        tk.Spinbox(f2b, textvariable=self._item_f_weight, from_=0.0, to=999.0, increment=0.5,
                   format='%.1f', width=10).pack(side='left', padx=5)

        # Abundance
        f2c = tk.Frame(p, bg='#f5f5f5')
        f2c.pack(fill='x', padx=10, pady=1)
        tk.Label(f2c, text=u"丰度:", width=8, anchor='e', bg='#f5f5f5').pack(side='left')
        self._item_f_abundance = tk.IntVar(value=100)
        tk.Spinbox(f2c, textvariable=self._item_f_abundance, from_=0, to=255, width=10).pack(side='left', padx=5)

        # --- Section: Armor Stats ---
        tk.Label(p, text=u"护甲属性", font=('Microsoft YaHei', 10, 'bold'),
                 fg='#333', bg='#f5f5f5', anchor='w').pack(fill='x', padx=10, pady=(10, 2))

        armor_vars = [
            (u"头部护甲:", '_item_f_head'),
            (u"身体护甲:", '_item_f_body'),
            (u"腿部护甲:", '_item_f_leg'),
        ]
        for label, attr in armor_vars:
            fa = tk.Frame(p, bg='#f5f5f5')
            fa.pack(fill='x', padx=10, pady=1)
            tk.Label(fa, text=label, width=8, anchor='e', bg='#f5f5f5').pack(side='left')
            var = tk.IntVar(value=0)
            setattr(self, attr, var)
            tk.Spinbox(fa, textvariable=var, from_=0, to=200, width=8).pack(side='left', padx=5)

        # --- Section: Weapon Stats ---
        tk.Label(p, text=u"武器属性", font=('Microsoft YaHei', 10, 'bold'),
                 fg='#333', bg='#f5f5f5', anchor='w').pack(fill='x', padx=10, pady=(10, 2))

        # Difficulty
        fda = tk.Frame(p, bg='#f5f5f5')
        fda.pack(fill='x', padx=10, pady=1)
        tk.Label(fda, text=u"需求力量:", width=10, anchor='e', bg='#f5f5f5').pack(side='left')
        self._item_f_difficulty = tk.IntVar(value=0)
        tk.Spinbox(fda, textvariable=self._item_f_difficulty, from_=0, to=63, width=8).pack(side='left', padx=5)

        # Speed rating
        fds = tk.Frame(p, bg='#f5f5f5')
        fds.pack(fill='x', padx=10, pady=1)
        tk.Label(fds, text=u"速度:", width=10, anchor='e', bg='#f5f5f5').pack(side='left')
        self._item_f_speed = tk.IntVar(value=0)
        tk.Spinbox(fds, textvariable=self._item_f_speed, from_=0, to=200, width=8).pack(side='left', padx=5)

        # Weapon length
        fdl = tk.Frame(p, bg='#f5f5f5')
        fdl.pack(fill='x', padx=10, pady=1)
        tk.Label(fdl, text=u"长度:", width=10, anchor='e', bg='#f5f5f5').pack(side='left')
        self._item_f_length = tk.IntVar(value=0)
        tk.Spinbox(fdl, textvariable=self._item_f_length, from_=0, to=999, width=8).pack(side='left', padx=5)

        # Swing damage
        fdsd = tk.Frame(p, bg='#f5f5f5')
        fdsd.pack(fill='x', padx=10, pady=1)
        tk.Label(fdsd, text=u"挥砍伤害:", width=10, anchor='e', bg='#f5f5f5').pack(side='left')
        self._item_f_swing_dmg = tk.IntVar(value=0)
        tk.Spinbox(fdsd, textvariable=self._item_f_swing_dmg, from_=0, to=999, width=8).pack(side='left', padx=5)

        # Swing type
        fdsdt = tk.Frame(p, bg='#f5f5f5')
        fdsdt.pack(fill='x', padx=10, pady=1)
        tk.Label(fdsdt, text=u"挥砍类型:", width=10, anchor='e', bg='#f5f5f5').pack(side='left')
        self._item_f_swing_type = ttk.Combobox(fdsdt, values=['cut', 'pierce', 'blunt'], width=10, state='readonly')
        self._item_f_swing_type.pack(side='left', padx=5)

        # Thrust damage
        fdtd = tk.Frame(p, bg='#f5f5f5')
        fdtd.pack(fill='x', padx=10, pady=1)
        tk.Label(fdtd, text=u"刺击伤害:", width=10, anchor='e', bg='#f5f5f5').pack(side='left')
        self._item_f_thrust_dmg = tk.IntVar(value=0)
        tk.Spinbox(fdtd, textvariable=self._item_f_thrust_dmg, from_=0, to=999, width=8).pack(side='left', padx=5)

        # Thrust type
        fdtt = tk.Frame(p, bg='#f5f5f5')
        fdtt.pack(fill='x', padx=10, pady=1)
        tk.Label(fdtt, text=u"刺击类型:", width=10, anchor='e', bg='#f5f5f5').pack(side='left')
        self._item_f_thrust_type = ttk.Combobox(fdtt, values=['cut', 'pierce', 'blunt'], width=10, state='readonly')
        self._item_f_thrust_type.pack(side='left', padx=5)

        # --- Section: Item Type Flags ---
        tk.Label(p, text=u"物品类型标志", font=('Microsoft YaHei', 10, 'bold'),
                 fg='#333', bg='#f5f5f5', anchor='w').pack(fill='x', padx=10, pady=(10, 2))

        self._item_type_vars = {}
        type_flags = [
            'itp_type_horse', 'itp_type_one_handed_wpn', 'itp_type_two_handed_wpn',
            'itp_type_polearm', 'itp_type_arrows', 'itp_type_bolts',
            'itp_type_shield', 'itp_type_bow', 'itp_type_crossbow',
            'itp_type_thrown', 'itp_type_goods', 'itp_type_head_armor',
            'itp_type_body_armor', 'itp_type_foot_armor', 'itp_type_hand_armor',
            'itp_type_pistol', 'itp_type_musket', 'itp_type_musket_ball',
            'itp_type_banner', 'itp_type_horse_harness',
        ]
        tf_frame = tk.Frame(p, bg='#f5f5f5')
        tf_frame.pack(fill='x', padx=10, pady=2)
        for i, flag in enumerate(type_flags):
            var = tk.BooleanVar(value=False)
            self._item_type_vars[flag] = var
            row = i // 3
            col = i % 3
            cb = tk.Checkbutton(tf_frame, text=flag.replace('itp_type_', ''),
                                variable=var, bg='#f5f5f5', anchor='w')
            cb.grid(row=row, column=col, sticky='w', padx=2, pady=1)

        # --- Section: Item Behavior Flags ---
        tk.Label(p, text=u"物品行为标志", font=('Microsoft YaHei', 10, 'bold'),
                 fg='#333', bg='#f5f5f5', anchor='w').pack(fill='x', padx=10, pady=(10, 2))

        self._item_flag_vars = {}
        behavior_flags = [
            'itp_merchandise', 'itp_wooden_attack', 'itp_wooden_parry',
            'itp_food', 'itp_cant_reload_on_horseback', 'itp_two_handed',
            'itp_primary', 'itp_secondary', 'itp_covers_legs',
            'itp_consumable', 'itp_bonus_against_shield', 'itp_penalty_with_shield',
            'itp_cant_use_on_horseback', 'itp_civilian', 'itp_next_item_as_melee',
            'itp_fit_to_head', 'itp_offset_lance', 'itp_covers_head',
            'itp_couchable', 'itp_crush_through', 'itp_remove_helmet',
            'itp_use_speed_as_damage_bonus',
        ]
        bf_frame = tk.Frame(p, bg='#f5f5f5')
        bf_frame.pack(fill='x', padx=10, pady=2)
        for i, flag in enumerate(behavior_flags):
            var = tk.BooleanVar(value=False)
            self._item_flag_vars[flag] = var
            row = i // 3
            col = i % 3
            cb = tk.Checkbutton(bf_frame, text=flag.replace('itp_', ''),
                                variable=var, bg='#f5f5f5', anchor='w')
            cb.grid(row=row, column=col, sticky='w', padx=2, pady=1)

        # --- Section: Extra Flags ---
        tk.Label(p, text=u"附加标志", font=('Microsoft YaHei', 10, 'bold'),
                 fg='#333', bg='#f5f5f5', anchor='w').pack(fill='x', padx=10, pady=(10, 2))

        extra_flag_frame = tk.Frame(p, bg='#f5f5f5')
        extra_flag_frame.pack(fill='x', padx=10, pady=2)
        self._item_f_unique = tk.BooleanVar(value=False)
        tk.Checkbutton(extra_flag_frame, text='itp_unique (unique)',
                       variable=self._item_f_unique, bg='#f5f5f5', anchor='w').pack(anchor='w')
        self._item_f_always_loot = tk.BooleanVar(value=False)
        tk.Checkbutton(extra_flag_frame, text='itp_always_loot',
                       variable=self._item_f_always_loot, bg='#f5f5f5', anchor='w').pack(anchor='w')
        self._item_f_no_parry = tk.BooleanVar(value=False)
        tk.Checkbutton(extra_flag_frame, text='itp_no_parry',
                       variable=self._item_f_no_parry, bg='#f5f5f5', anchor='w').pack(anchor='w')
        self._item_f_cant_reload = tk.BooleanVar(value=False)
        tk.Checkbutton(extra_flag_frame, text='itp_cant_reload_on_horseback',
                       variable=self._item_f_cant_reload, bg='#f5f5f5', anchor='w').pack(anchor='w')

        # --- Section: Mesh ---
        tk.Label(p, text=u"Mesh", font=('Microsoft YaHei', 10, 'bold'),
                 fg='#333', bg='#f5f5f5', anchor='w').pack(fill='x', padx=10, pady=(10, 2))

        mf1 = tk.Frame(p, bg='#f5f5f5')
        mf1.pack(fill='x', padx=10, pady=1)
        tk.Label(mf1, text=u"模型名:", width=10, anchor='e', bg='#f5f5f5').pack(side='left')
        self._item_f_mesh = tk.StringVar()
        tk.Entry(mf1, textvariable=self._item_f_mesh, width=30).pack(side='left', padx=5)

        # --- Section: Capabilities ---
        tk.Label(p, text=u"Capabilities (功能)", font=('Microsoft YaHei', 10, 'bold'),
                 fg='#333', bg='#f5f5f5', anchor='w').pack(fill='x', padx=10, pady=(10, 2))
        self._item_cap_vars = {}
        cap_flags = [
            'itcf_thrust_one_handed', 'itcf_overswing_one_handed',
            'itcf_slashright_one_handed', 'itcf_slashleft_one_handed',
            'itcf_thrust_two_handed', 'itcf_overswing_two_handed',
            'itcf_slashright_two_handed', 'itcf_slashleft_two_handed',
            'itcf_thrust_polearm', 'itcf_overswing_polearm',
            'itcf_slashright_polearm', 'itcf_slashleft_polearm',
            'itcf_shoot_bow', 'itcf_shoot_crossbow', 'itcf_shoot_pistol',
            'itcf_shoot_musket', 'itcf_throw_weapon',
            'itcf_carry_spear', 'itcf_carry_sword_left_hip',
            'itcf_carry_axe_left_hip', 'itcf_carry_dagger_front_left',
            'itcf_carry_mace_front_left', 'itcf_carry_quiver_front_right',
            'itcf_carry_quiver_back_right', 'itcf_carry_pistol_front_left',
            'itcf_carry_bow_back', 'itcf_carry_crossbow_back',
            'itcf_force_64_bits',
        ]
        cf_frame = tk.Frame(p, bg='#f5f5f5')
        cf_frame.pack(fill='x', padx=10, pady=2)
        for i, flag in enumerate(cap_flags):
            var = tk.BooleanVar(value=False)
            self._item_cap_vars[flag] = var
            row = i // 3
            col = i % 3
            cb = tk.Checkbutton(cf_frame, text=flag.replace('itcf_', ''),
                                variable=var, bg='#f5f5f5', anchor='w')
            cb.grid(row=row, column=col, sticky='w', padx=2, pady=1)

        # --- Apply button ---
        af = tk.Frame(p, bg='#f5f5f5')
        af.pack(fill='x', padx=10, pady=(10, 20))
        tk.Button(af, text=u"✉ 应用修改",
                  command=self._item_form_apply, bg='#4CAF50', fg='white',
                  font=('Microsoft YaHei', 10), padx=12, pady=4).pack(side='left')

        tk.Label(af, text=u"修改后请点击“应用”按钮保存到内存，然后按 Ctrl+S 保存文件",
                 fg='#888', bg='#f5f5f5', font=('', 8)).pack(side='left', padx=15)

    def _item_form_populate(self, flds):
        """Populate form fields from parsed item fields."""
        # Name (flds[1])
        name = flds[1].strip('"').strip("'") if len(flds) > 1 else ''
        self._item_f_name.set(name)

        # Plural name not directly stored; use name_pl if available or leave blank
        self._item_f_plural.set('')

        # Parse flags from flds[3]
        if len(flds) > 3:
            flags_str = flds[3]
            # Reset all vars
            for v in self._item_type_vars.values():
                v.set(False)
            for v in self._item_flag_vars.values():
                v.set(False)
            self._item_f_unique.set(False)
            self._item_f_always_loot.set(False)
            self._item_f_no_parry.set(False)
            # Also the behavior flags checkbox from flags_str
            flag_set = set(re.findall(r'itp_\w+', flags_str))
            for f in flag_set:
                if f in self._item_type_vars:
                    self._item_type_vars[f].set(True)
                elif f in self._item_flag_vars:
                    self._item_flag_vars[f].set(True)
                elif f == 'itp_unique':
                    self._item_f_unique.set(True)
                elif f == 'itp_always_loot':
                    self._item_f_always_loot.set(True)
                elif f == 'itp_no_parry':
                    self._item_f_no_parry.set(True)

        # Parse capabilities from flds[4]
        if len(flds) > 4:
            cap_str = flds[4]
            for v in self._item_cap_vars.values():
                v.set(False)
            cap_set = set(re.findall(r'itcf_\w+', cap_str))
            for f in cap_set:
                if f in self._item_cap_vars:
                    self._item_cap_vars[f].set(True)

        # Price (flds[5])
        if len(flds) > 5:
            try:
                self._item_f_price.set(int(flds[5]))
            except:
                self._item_f_price.set(0)

        # Stats (flds[6])
        if len(flds) > 6:
            stats_str = flds[6]
            stats = self._parse_item_stats(stats_str)
            self._item_f_weight.set(stats.get('weight', 0.0))
            self._item_f_head.set(stats.get('head_armor', 0))
            self._item_f_body.set(stats.get('body_armor', 0))
            self._item_f_leg.set(stats.get('leg_armor', 0))
            self._item_f_difficulty.set(stats.get('difficulty', 0))
            self._item_f_speed.set(stats.get('speed', 0))
            self._item_f_length.set(stats.get('length', 0))
            self._item_f_swing_dmg.set(stats.get('swing_damage', 0))
            self._item_f_swing_type.set(stats.get('swing_type', ''))
            self._item_f_thrust_dmg.set(stats.get('thrust_damage', 0))
            self._item_f_thrust_type.set(stats.get('thrust_type', ''))
            self._item_f_abundance.set(stats.get('abundance', 100))
        else:
            self._item_f_weight.set(0.0)
            self._item_f_head.set(0)
            self._item_f_body.set(0)
            self._item_f_leg.set(0)
            self._item_f_difficulty.set(0)
            self._item_f_speed.set(0)
            self._item_f_length.set(0)
            self._item_f_swing_dmg.set(0)
            self._item_f_swing_type.set('')
            self._item_f_thrust_dmg.set(0)
            self._item_f_thrust_type.set('')
            self._item_f_abundance.set(100)

        # Mesh (flds[2])
        if len(flds) > 2:
            mesh_str = flds[2]
            # Try to extract mesh name
            m = re.search(r'"(\w+)"', mesh_str)
            self._item_f_mesh.set(m.group(1) if m else '')
        else:
            self._item_f_mesh.set('')

        # Store current flds for apply
        self._item_form_flds = list(flds)

    def _parse_item_stats(self, stats_str):
        """Parse the stats tuple from flds[6]."""
        # Format: (weight, head_armor, body_armor, leg_armor, difficulty, ...)
        # Or more complex with damage types
        result = {}
        # Extract all numeric values and strings
        parts = []
        for m in re.finditer(r'\d+\.?\d*|[a-z_]+', stats_str):
            parts.append(m.group())
        nums = []
        words = []
        for p in parts:
            try:
                nums.append(float(p))
            except:
                words.append(p)

        idx = 0
        if len(nums) > idx: result['weight'] = float(nums[idx]); idx += 1
        if len(nums) > idx: result['head_armor'] = int(nums[idx]); idx += 1
        if len(nums) > idx: result['body_armor'] = int(nums[idx]); idx += 1
        if len(nums) > idx: result['leg_armor'] = int(nums[idx]); idx += 1
        if len(nums) > idx: result['difficulty'] = int(nums[idx]); idx += 1
        if len(nums) > idx: result['speed'] = int(nums[idx]); idx += 1
        if len(nums) > idx: result['length'] = int(nums[idx]); idx += 1
        if len(nums) > idx: result['swing_damage'] = int(nums[idx]); idx += 1
        # Find swing type
        wi = 0
        damage_types = ['cut', 'pierce', 'blunt']
        for w in words:
            if w in damage_types:
                if 'swing_type' not in result:
                    result['swing_type'] = w
                elif 'thrust_type' not in result:
                    result['thrust_type'] = w
        if len(nums) > idx: result['thrust_damage'] = int(nums[idx]); idx += 1
        if len(nums) > idx: result['abundance'] = int(nums[idx]); idx += 1

        return result

    def _item_form_clear(self):
        """Clear all form fields."""
        self._item_f_name.set('')
        self._item_f_plural.set('')
        self._item_f_price.set(0)
        self._item_f_weight.set(0.0)
        self._item_f_head.set(0)
        self._item_f_body.set(0)
        self._item_f_leg.set(0)
        self._item_f_difficulty.set(0)
        self._item_f_speed.set(0)
        self._item_f_length.set(0)
        self._item_f_swing_dmg.set(0)
        self._item_f_swing_type.set('')
        self._item_f_thrust_dmg.set(0)
        self._item_f_thrust_type.set('')
        self._item_f_abundance.set(100)
        self._item_f_mesh.set('')
        self._item_f_unique.set(False)
        self._item_f_always_loot.set(False)
        self._item_f_no_parry.set(False)
        for v in self._item_type_vars.values():
            v.set(False)
        for v in self._item_flag_vars.values():
            v.set(False)
        for v in self._item_cap_vars.values():
            v.set(False)
        self._item_form_flds = []

    def _item_form_apply(self):
        """Apply form changes back to the item entry."""
        idx = self._item_selected_idx
        if idx < 0 or not hasattr(self, '_item_form_flds'):
            return

        flds = self._item_form_flds

        # flds[1]: Name
        flds[1] = '"%s"' % self._item_f_name.get()

        # flds[3]: Flags (combine type + behavior + extra)
        flags = list(self._item_type_vars.keys())
        flags += [k for k in self._item_flag_vars if k not in self._item_type_vars]
        active_flags = []
        for f in flags:
            if f in self._item_type_vars and self._item_type_vars[f].get():
                active_flags.append(f)
            elif f in self._item_flag_vars and self._item_flag_vars[f].get():
                active_flags.append(f)
        if self._item_f_unique.get():
            active_flags.append('itp_unique')
        if self._item_f_always_loot.get():
            active_flags.append('itp_always_loot')
        if self._item_f_no_parry.get():
            active_flags.append('itp_no_parry')
        flds[3] = '|'.join(active_flags) if active_flags else '0'

        # flds[4]: Capabilities
        active_caps = [k for k, v in self._item_cap_vars.items() if v.get()]
        flds[4] = '|'.join(active_caps) if active_caps else '0'

        # flds[5]: Price
        flds[5] = str(self._item_f_price.get())

        # flds[6]: Stats
        weight = self._item_f_weight.get()
        head = self._item_f_head.get()
        body = self._item_f_body.get()
        leg = self._item_f_leg.get()
        diff = self._item_f_difficulty.get()
        spd = self._item_f_speed.get()
        length = self._item_f_length.get()
        swing_dmg = self._item_f_swing_dmg.get()
        swing_type = self._item_f_swing_type.get()
        thrust_dmg = self._item_f_thrust_dmg.get()
        thrust_type = self._item_f_thrust_type.get()
        abund = self._item_f_abundance.get()

        # Build stats string
        stats_parts = []
        stats_parts.append('%.1f' % weight)
        stats_parts.append(str(head))
        stats_parts.append(str(body))
        stats_parts.append(str(leg))
        stats_parts.append(str(diff))
        stats_parts.append(str(spd))
        stats_parts.append(str(length))
        stats_parts.append(str(swing_dmg))
        if swing_type:
            stats_parts.append(swing_type)
        stats_parts.append(str(thrust_dmg))
        if thrust_type:
            stats_parts.append(thrust_type)
        stats_parts.append(str(abund))
        flds[6] = ', '.join(stats_parts)

        # Rebuild entry string
        new_entry = '  [' + ', '.join(flds) + ']'

        # Push undo and save
        self._push_undo()
        self.item_entries[idx] = new_entry
        self.item_fields_list[idx] = parse_fields_in_entry(new_entry)

        # Update items/lookup
        full_id = 'itm_' + flds[0].strip('"').strip("'")
        if not flds[0].strip('"').strip("'").startswith('itm_'):
            full_id = 'itm_' + flds[0].strip('"').strip("'")
        for it in self.items:
            if it['id'] == full_id:
                it['raw'] = new_entry
                it['name'] = self._item_f_name.get()
                break

        self.status.config(text=u"✅ 已应用修改: %s" % full_id)

    # ================================================================
    #  Items List / Search / Select
    # ================================================================

    def _items_populate_list(self, filter_text=""):
        self._item_lb.delete(0, tk.END)
        ft = filter_text.lower()
        for idx, entry in enumerate(self.item_entries):
            flds = self.item_fields_list[idx] if idx < len(self.item_fields_list) else []
            iid = flds[0].strip('"').strip("'") if flds else '?'
            full_id = 'itm_' + iid if not iid.startswith('itm_') else iid
            zh = self.item_cn.get(full_id, '') or (flds[1].strip('"').strip("'") if len(flds) > 1 else '')
            disp = u'%s | %s' % (full_id, zh) if zh else full_id
            if ft and ft not in full_id.lower() and ft not in zh.lower():
                continue
            self._item_lb.insert(tk.END, disp)
        self._item_count_lbl.config(text=u"共 %d 个物品" % len(self.item_entries))

    def _items_on_search(self, *args):
        self._items_populate_list(self._item_search_var.get())

    def _items_on_select(self, event):
        sel = self._item_lb.curselection()
        if not sel:
            return
        # Map listbox index back to data index (accounting for search filter)
        disp = self._item_lb.get(sel[0])
        iid_part = disp.split(' | ')[0] if ' | ' in disp else disp
        # Find matching item
        for idx, entry in enumerate(self.item_entries):
            flds = self.item_fields_list[idx] if idx < len(self.item_fields_list) else []
            if not flds:
                continue
            iid = flds[0].strip('"').strip("'")
            full_id = 'itm_' + iid if not iid.startswith('itm_') else iid
            if full_id == iid_part:
                self._item_selected_idx = idx
                self._show_item_detail()
                return
        # If not found by ID match, try listbox position
        self._item_selected_idx = sel[0]
        self._show_item_detail()

    def _items_on_double_click(self, event):
        # Jump to source tab for quick edit
        self._show_item_tab('raw')


    # ================================================================
    #  Items Detail
    # ================================================================

    def _show_item_detail(self):
        idx = self._item_selected_idx
        if idx < 0 or idx >= len(self.item_entries):
            self._clear_item_detail()
            return

        flds = self.item_fields_list[idx]
        if not flds:
            self._clear_item_detail()
            return

        iid = flds[0].strip('"').strip("'") if flds else '?'
        full_id = 'itm_' + iid if not iid.startswith('itm_') else iid
        name = flds[1].strip('"').strip("'") if len(flds) > 1 else ''
        zh = self.item_cn.get(full_id, '')

        title = u'%s | %s' % (full_id, zh or name)
        self._item_detail_title.config(text=title)

        # Populate form fields
        self._item_form_populate(flds)

        # Raw tab
        if self._item_current_tab == 'raw':
            self._item_raw_text.delete('1.0', tk.END)
            self._item_raw_text.insert('1.0', self.item_entries[idx])
            self._item_raw_text.edit_reset()

    def _clear_item_detail(self):
        self._item_detail_title.config(text=u"请选择一个物品")
        self._item_form_clear()
        self._item_raw_text.delete('1.0', tk.END)
        self._item_raw_text.edit_reset()

    # ================================================================
    #  Items CRUD
    # ================================================================

    def _add_item(self):
        if not self.item_entries:
            return
        self._push_undo()
        # Clone last item as template
        template = self.item_entries[-1]
        tmpl_flds = parse_fields_in_entry(template)
        new_id = u'new_item_%d' % (len(self.item_entries) + 1)
        tmpl_flds[0] = '"%s"' % new_id
        tmpl_flds[1] = '"New Item"'
        new_entry = '  [' + ', '.join(tmpl_flds) + ']'
        self.item_entries.append(new_entry)
        self.item_fields_list.append(tmpl_flds)
        # Update lookup structures
        full_id = 'itm_' + new_id
        d = {'id': full_id, 'name': 'New Item', 'raw': new_entry}
        self.items.append(d)
        self.item_lookup[full_id] = d
        self.item_list.append((full_id, ''))
        self.item_category[full_id] = 'other'
        # Refresh
        self._items_populate_list(self._item_search_var.get())
        self._item_selected_idx = len(self.item_entries) - 1
        self._show_item_detail()
        self.status.config(text=u"★ 新增物品: %s" % full_id)

    def _copy_item(self):
        idx = self._item_selected_idx
        if idx < 0:
            tkMessageBox.showwarning(u"提示", u"请先选择一个物品")
            return
        self._push_undo()
        flds = copy.deepcopy(self.item_fields_list[idx])
        orig_id = flds[0].strip('"').strip("'")
        new_id = '%s_copy_%d' % (orig_id.replace('itm_', ''), len(self.item_entries) + 1)
        flds[0] = '"%s"' % new_id
        new_entry = '  [' + ', '.join(flds) + ']'
        self.item_entries.append(new_entry)
        self.item_fields_list.append(flds)
        full_id = 'itm_' + new_id if not new_id.startswith('itm_') else new_id
        d = {'id': full_id, 'name': flds[1].strip('"').strip("'") if len(flds) > 1 else '', 'raw': new_entry}
        self.items.append(d)
        self.item_lookup[full_id] = d
        self.item_list.append((full_id, self.item_cn.get(full_id, '')))
        self.item_category[full_id] = 'other'
        self._items_populate_list(self._item_search_var.get())
        self._item_selected_idx = len(self.item_entries) - 1
        self._show_item_detail()
        self.status.config(text=u"★ 复制物品: %s" % full_id)

    def _delete_item(self):
        idx = self._item_selected_idx
        if idx < 0:
            tkMessageBox.showwarning(u"提示", u"请先选择一个物品")
            return
        flds = self.item_fields_list[idx]
        iid = flds[0].strip('"').strip("'") if flds else '???'
        full_id = 'itm_' + iid if not iid.startswith('itm_') else iid
        if not tkMessageBox.askyesno(u"确认删除",
                                     u"确定删除物品 %s ?\n\n此操作可通过 Ctrl+Z 撤销。" % full_id):
            return
        self._push_undo()
        del self.item_entries[idx]
        del self.item_fields_list[idx]
        # Update lookup
        if full_id in self.item_lookup:
            del self.item_lookup[full_id]
        self.item_list = [(iid, zh) for iid, zh in self.item_list if iid != full_id]
        if full_id in self.item_category:
            del self.item_category[full_id]
        # Rebuild self.items to stay in sync
        self.items = [it for it in self.items if it['id'] != full_id]
        if self._item_selected_idx >= len(self.item_entries):
            self._item_selected_idx = len(self.item_entries) - 1
        self._items_populate_list(self._item_search_var.get())
        self._show_item_detail()
        self.status.config(text=u"★ 已删除: %s" % full_id)

    def _move_item_up(self):
        idx = self._item_selected_idx
        if idx <= 0:
            return
        self._reorder_items(idx, idx - 1)

    def _move_item_down(self):
        idx = self._item_selected_idx
        if idx < 0 or idx >= len(self.item_entries) - 1:
            return
        self._reorder_items(idx, idx + 1)

    def _reorder_items(self, from_idx, to_idx):
        self._push_undo()
        self.item_entries.insert(to_idx, self.item_entries.pop(from_idx))
        self.item_fields_list.insert(to_idx, self.item_fields_list.pop(from_idx))
        self._item_selected_idx = to_idx
        self._items_populate_list(self._item_search_var.get())
        self._select_item_after_move(to_idx)

    def _select_item_after_move(self, data_idx):
        ft = self._item_search_var.get().lower()
        visible_idx = 0
        for idx, entry in enumerate(self.item_entries):
            flds = self.item_fields_list[idx] if idx < len(self.item_fields_list) else []
            if not flds:
                continue
            iid = flds[0].strip('"').strip("'")
            full_id = 'itm_' + iid if not iid.startswith('itm_') else iid
            zh = self.item_cn.get(full_id, '') or (flds[1].strip('"').strip("'") if len(flds) > 1 else '')
            if ft and ft not in full_id.lower() and ft not in zh.lower():
                continue
            if idx == data_idx:
                self._item_lb.selection_clear(0, tk.END)
                self._item_lb.selection_set(visible_idx)
                self._item_lb.see(visible_idx)
                self._item_selected_idx = idx
                return
            visible_idx += 1

    # ================================================================
    #  Items Save
    # ================================================================

    def _save_items(self):
        if not self.mod_path:
            tkMessageBox.showwarning(u"提示", u"请先加载 MOD")
            return

        # Auto-apply raw tab edits
        if self._item_selected_idx >= 0 and self._item_current_tab == 'raw':
            raw = self._item_raw_text.get('1.0', 'end-1c').strip()
            if raw and raw != self.item_entries[self._item_selected_idx]:
                self._push_undo()
                self.item_entries[self._item_selected_idx] = raw
                self.item_fields_list[self._item_selected_idx] = parse_fields_in_entry(raw)

        if not tkMessageBox.askyesno(u"确认保存",
                                     u"确定保存物品数据到 module_items.py?\n\n"
                                     u"⚠ 此操作将覆盖源文件!\n"
                                     u"系统会自动创建 .bak 备份。\n\n"
                                     u"当前物品数: %d" % len(self.item_entries)):
            return

        filepath = os.path.join(self.source_path, 'module_items.py')

        # Backup
        bak = filepath + '.bak'
        try:
            shutil.copy2(filepath, bak)
        except Exception as e:
            tkMessageBox.showerror(u"错误", u"备份失败: %s" % e)
            return

        try:
            parts = []
            parts.append(self.item_header)
            for i, entry in enumerate(self.item_entries):
                if i < len(self.item_entries) - 1:
                    parts.append(entry + ',\n')
                else:
                    parts.append(entry + '\n')
            parts.append(self.item_footer)
            output = ''.join(parts)

            with open(filepath, 'wb') as f:
                f.write(output.encode('utf-8'))
        except Exception as e:
            tkMessageBox.showerror(u"错误", u"保存失败: %s" % e)
            return

        self.status.config(text=u"✅ 已保存到 module_items.py (备份: .bak) - %d 个物品" % len(self.item_entries))
        self._item_raw_text.edit_reset()    # ── Resize: equipment panel drag handle ──
    def _on_resize_start(self, event):
        self._resize_dragging = True
        self._resize_start_y = event.y_root
        self._resize_start_h = self._eq_height.get()
        self._resize_handle.config(bg='#888')

    def _on_resize_drag(self, event):
        if not self._resize_dragging:
            return
        dy = event.y_root - self._resize_start_y
        # Each unit ~= 18px line height, clamp to 2..40
        new_h = self._resize_start_h + int(round(dy / 18.0))
        if new_h < 2:
            new_h = 2
        if new_h > 40:
            new_h = 40
        self._eq_height.set(new_h)
        self.eq_lb.config(height=new_h)

    def _on_resize_end(self, event):
        self._resize_dragging = False
        self._resize_handle.config(bg='#555')

    def _commit_raw_text(self):
        """Save raw widget edits to troops_entries with undo snapshot."""
        if self._current_tab == 'raw' and self.selected_idx >= 0:
            raw = self._raw_text.get('1.0', 'end-1c').strip()
            if raw and raw != self.troops_entries[self.selected_idx]:
                self._push_undo()
                self.troops_entries[self.selected_idx] = raw
                self.troops_fields[self.selected_idx] = parse_fields_in_entry(raw)

    def _on_global_wheel(self, event):
        """Root-level MouseWheel: dispatch to the region under the cursor.
        On Windows, MouseWheel goes to the focused widget, not the widget
        under cursor. So we check cursor position instead of event.widget."""
        px = self.root.winfo_pointerx()
        py = self.root.winfo_pointery()
        w = self.root.winfo_containing(px, py)
        if w is None:
            return
        # Don't intercept Spinbox scroll (Spinbox uses wheel for value change)
        if w.winfo_class() == 'Spinbox':
            return
        # Walk up the widget tree to find which scroll region we're in
        widget = w
        while widget is not None:
            # Equipment listbox
            if hasattr(self, 'eq_lb') and widget is self.eq_lb:
                self.eq_lb.yview_scroll(int(-1 * (event.delta / 120)), 'units')
                return 'break'
            # Items list
            if hasattr(self, '_item_lb') and widget is self._item_lb:
                self._item_lb.yview_scroll(int(-1 * (event.delta / 120)), 'units')
                return 'break'
            # Items form canvas
            if hasattr(self, '_item_form_canvas') and widget is self._item_form_canvas:
                self._item_form_canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')
                return 'break'
            # Skill canvas region
            if hasattr(self, '_skill_canvas') and widget is self._skill_canvas:
                self._skill_canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')
                return 'break'
            # Detail canvas region
            if hasattr(self, '_detail_canvas') and widget is self._detail_canvas:
                self._detail_canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')
                return 'break'
            # Troop list region
            if widget is self.troop_lb:
                self.troop_lb.yview_scroll(int(-1 * (event.delta / 120)), 'units')
                return 'break'
            widget = widget.master
        return

    def _build_detail_panel(self, parent):
        """Build the structured troop detail panel based on ming MOD field layout:
        F0-F15: id|name|plural|flags|scene|reserved|faction|inventory|attributes|prof|skills|face1|face2|class|upgrade1|upgrade2"""
        # Scrollable container
        self._detail_canvas = canvas = tk.Canvas(parent)
        scrollbar = tk.Scrollbar(parent, orient='vertical', command=canvas.yview)
        self._detail_scroll_frame = tk.Frame(canvas)
        self._detail_scroll_frame.bind(
            '<Configure>',
            lambda e: canvas.configure(scrollregion=canvas.bbox('all'))
        )
        canvas.create_window((0, 0), window=self._detail_scroll_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side='left', expand=1, fill='both')
        scrollbar.pack(side='right', fill='y')
        f = self._detail_scroll_frame

        # ── Section 1: Basic Info (ID/Name/Plural + CN + Scene/Reserved/Faction) ──
        s1 = tk.LabelFrame(f, text=u"基础信息 (修改中文自动保存到汉化文件)", font=('', 10, 'bold'))
        s1.pack(fill='x', padx=5, pady=3)
        self._detail_vars = {}
        # Row helper: label + entry
        def _add_info_row(parent, key, label, width=36, readonly=False):
            row = tk.Frame(parent)
            row.pack(fill='x', padx=5, pady=1)
            tk.Label(row, text=label + ':', width=14, anchor='w').pack(side='left')
            self._detail_vars[key] = tk.StringVar()
            st = 'readonly' if readonly else 'normal'
            e = tk.Entry(row, textvariable=self._detail_vars[key], width=width, state=st)
            e.pack(side='left', fill='x', expand=1, padx=(5,0))
            return e

        _add_info_row(s1, 'tid', u'F0 兵种 ID', readonly=True)
        _add_info_row(s1, 'name', u'F1 英文名')
        _add_info_row(s1, 'plural', u'F2 英文复数名')
        _add_info_row(s1, 'name_cn', u'  中文名')
        _add_info_row(s1, 'plural_cn', u'  中文复数名')
        _add_info_row(s1, 'scene', u'F4 场景')
        _add_info_row(s1, 'reserved', u'F5 保留字段')
        # Faction: dropdown + CN label
        faction_row = tk.Frame(s1)
        faction_row.pack(fill='x', padx=5, pady=1)
        tk.Label(faction_row, text=u'F6 阵营:', width=14, anchor='w').pack(side='left')
        self._faction_var = tk.StringVar()
        self._faction_combo = None  # created in _populate_detail_panel
        self._faction_cn_lbl = tk.Label(faction_row, text='', fg='#666', width=16, anchor='w')
        self._faction_cn_lbl.pack(side='right', padx=(5,0))

        # ── Section 2: Flags F3 (two groups) ──
        s2 = tk.LabelFrame(f, text=u"F3 标记位 (Flags)", font=('', 10, 'bold'))
        s2.pack(fill='x', padx=5, pady=3)
        # Source expression row
        fr = tk.Frame(s2)
        fr.pack(fill='x', padx=5, pady=2)
        tk.Label(fr, text=u'源表达式:', width=10, anchor='w').pack(side='left')
        self._flag_raw_var = tk.StringVar(value='0')
        tk.Entry(fr, textvariable=self._flag_raw_var, width=50).pack(side='left', padx=(5,0), fill='x', expand=1)
        # Checkboxes: side-by-side groups
        self._flag_vars = {}  # bit -> IntVar
        flag_body = tk.Frame(s2)
        flag_body.pack(fill='x', padx=5, pady=2)
        # -- Group A: 其他特征 --
        fg_a = tk.LabelFrame(flag_body, text=u"其他特征", font=('', 9, 'bold'), fg='#336699')
        fg_a.pack(side='left', fill='both', expand=1, padx=(0,5))
        _fg_row_a = 0
        for bit_val, label in FLAG_OTHER:
            var = tk.IntVar(value=0)
            self._flag_vars[bit_val] = var
            cb = tk.Checkbutton(fg_a, text=label, variable=var,
                                 command=lambda bv=bit_val: self._on_flag_change(bv))
            cb.grid(row=_fg_row_a, column=0, sticky='w', padx=4, pady=1)
            _fg_row_a += 1
        # -- Group B: 武器特征 --
        fg_b = tk.LabelFrame(flag_body, text=u"武器特征", font=('', 9, 'bold'), fg='#996633')
        fg_b.pack(side='left', fill='both', expand=1, padx=(5,0))
        _fg_row_b = 0
        for bit_val, label in FLAG_WEAPON:
            var = tk.IntVar(value=0)
            self._flag_vars[bit_val] = var
            cb = tk.Checkbutton(fg_b, text=label, variable=var,
                                 command=lambda bv=bit_val: self._on_flag_change(bv))
            cb.grid(row=_fg_row_b, column=0, sticky='w', padx=4, pady=1)
            _fg_row_b += 1
        # Hex display
        fr2 = tk.Frame(s2)
        fr2.pack(fill='x', padx=5, pady=2)
        tk.Label(fr2, text=u'等效 Hex:', width=10, anchor='w').pack(side='left')
        self._flag_hex_var = tk.StringVar(value='0x00000000')
        tk.Entry(fr2, textvariable=self._flag_hex_var, width=14, state='readonly').pack(side='left', padx=5)

        # ── Section 3: Attributes F8 (str|agi|int|cha|level) ──
        s3 = tk.LabelFrame(f, text=u"F8 属性", font=('', 10, 'bold'))
        s3.pack(fill='x', padx=5, pady=3)
        # Raw expression
        ar = tk.Frame(s3)
        ar.pack(fill='x', padx=5, pady=2)
        tk.Label(ar, text=u'源表达式:', width=10, anchor='w').pack(side='left')
        self._attr_raw_var = tk.StringVar(value='0')
        self._attr_raw_var.trace('w', lambda *_: self._on_attr_expr_change())
        tk.Entry(ar, textvariable=self._attr_raw_var, width=50).pack(side='left', padx=(5,0), fill='x', expand=1)
        # Spinboxes
        attr_grid = tk.Frame(s3)
        attr_grid.pack(fill='x', padx=5, pady=2)
        self._attr_vars = []  # [str, agi, int, cha, level]
        self._attr_guard = False  # prevent recursive trace
        for ai, alabel in enumerate(ATTR_LABELS):
            c = ai % 5
            tk.Label(attr_grid, text=alabel, width=16, anchor='w').grid(row=0, column=c, sticky='w', padx=3)
            var = tk.StringVar(value='0')
            # Python 2.7 lambda compat: use default arg to capture ai
            var.trace('w', lambda n,i,m, a=ai: self._on_attr_spin_change(a))
            self._attr_vars.append(var)
            sp = tk.Spinbox(attr_grid, from_=0, to=63, width=5, textvariable=var)
            sp.grid(row=1, column=c, padx=3, pady=1)

        # ── Section 4: Proficiencies F9 (7 values, bit-packed wp) ──
        s5 = tk.LabelFrame(f, text=u"F9 熟练度 (wp_one_handed|wp_two_handed|...)", font=('', 10, 'bold'))
        s5.pack(fill='x', padx=5, pady=3)
        pr = tk.Frame(s5)
        pr.pack(fill='x', padx=5, pady=2)
        tk.Label(pr, text=u'源表达式:', width=10, anchor='w').pack(side='left')
        self._prof_raw_var = tk.StringVar(value='wp(0)')
        tk.Entry(pr, textvariable=self._prof_raw_var, width=50).pack(side='left', padx=(5,0), fill='x', expand=1)
        # Spinboxes for each weapon type
        prof_grid = tk.Frame(s5)
        prof_grid.pack(fill='x', padx=5, pady=2)
        self._prof_vars = []
        self._prof_guard = False
        for pi, plabel in enumerate(PROF_LABELS):
            c = pi % 7
            tk.Label(prof_grid, text=plabel, width=10, anchor='w').grid(row=0, column=c, sticky='w', padx=2)
            var = tk.StringVar(value='0')
            var.trace('w', lambda n,i,m, p=pi: self._on_prof_spin_change(p))
            self._prof_vars.append(var)
            sp = tk.Spinbox(prof_grid, from_=0, to=999, width=6, textvariable=var)
            sp.grid(row=1, column=c, padx=2, pady=1)

        # ── Section 5: Skills F10 (42 slots, knows_xxx_N expressions) ──
        s4 = tk.LabelFrame(f, text=u"F10 技能 (knows_xxx_N 源表达式 - 双向交互)", font=('', 10, 'bold'))
        s4.pack(fill='x', padx=5, pady=3)
        sr = tk.Frame(s4)
        sr.pack(fill='x', padx=5, pady=2)
        tk.Label(sr, text=u'源表达式:', width=10, anchor='w').pack(side='left')
        self._skill_raw_var = tk.StringVar(value='0')
        tk.Entry(sr, textvariable=self._skill_raw_var, width=50, font=('Consolas', 9)).pack(side='left', padx=(5,0), fill='x', expand=1)
        # Guard flags to prevent recursion between expr <-> spinboxes
        self._skill_expr_guard = False
        self._skill_spin_guard = False
        self._skill_raw_var.trace('w', lambda *_: self._on_skill_expr_change())
        # Scrollable 2-column skill list (points + skill name)
        lang_label = tk.Frame(s4)
        lang_label.pack(fill='x', padx=5, pady=(3,0))
        # Header
        tk.Label(lang_label, text=u'点数', width=5, font=('', 9, 'bold'), anchor='center', bg='#d0d0d0',
                 relief='groove').grid(row=0, column=0, sticky='ew', padx=1)
        tk.Label(lang_label, text=u'技能', width=14, font=('', 9, 'bold'), anchor='w', bg='#d0d0d0',
                 relief='groove').grid(row=0, column=1, sticky='ew', padx=(1,0))
        # Scrollable area
        self._skill_canvas = skill_canvas = tk.Canvas(s4, height=180)
        skill_sb = tk.Scrollbar(s4, orient='vertical', command=skill_canvas.yview)
        skill_inner = tk.Frame(skill_canvas)
        skill_inner.bind('<Configure>', lambda e: skill_canvas.configure(scrollregion=skill_canvas.bbox('all')))
        skill_canvas.create_window((0, 0), window=skill_inner, anchor='nw')
        skill_canvas.configure(yscrollcommand=skill_sb.set)
        skill_canvas.pack(side='left', fill='both', expand=1, padx=5, pady=2)
        skill_sb.pack(side='right', fill='y', padx=(0,5), pady=2)
        # Build 42 skill rows: Spinbox (points) + Label (name)
        self._skill_vars = []
        self._skill_labels = []
        for si in range(42):
            sklabel = SKILL_LABELS[si] if si < len(SKILL_LABELS) else u'预留(%d)' % si
            is_reserved = u'预留' in sklabel or u'Reserved' in sklabel
            # Points Spinbox
            var = tk.StringVar(value='0')
            self._skill_vars.append(var)
            sp = tk.Spinbox(skill_inner, from_=0, to=10, width=4, textvariable=var, font=('', 9))
            sp.grid(row=si, column=0, padx=3, pady=1)
            # Bind trace with closure to capture index (Python 2.7 compat)
            def _make_trace(idx):
                return lambda n,i,m, si=idx: self._on_skill_spin_change(si)
            var.trace('w', _make_trace(si))
            # Skill name Label
            lbl = tk.Label(skill_inner, text=sklabel, width=14, font=('', 9), anchor='w',
                          fg='#888' if is_reserved else '#000')
            lbl.grid(row=si, column=1, sticky='w', padx=5, pady=1)
            self._skill_labels.append(lbl)

        # ── Section 6: Face Codes F11/F12 ──
        s7 = tk.LabelFrame(f, text=u"F11/F12 脸型码", font=('', 10, 'bold'))
        s7.pack(fill='x', padx=5, pady=3)
        # 提示信息(放在输入框上方)
        hint_row = tk.Frame(s7)
        hint_row.pack(fill='x', padx=5, pady=(2,1))
        tk.Label(hint_row, text=u'*面部代码获取请在编辑模式下按Ctrl+E,代码位置如图所示', fg='#666', font=('', 8)).pack(anchor='w')
        # F11: face_code_1 (present in >=12 fields)
        row1 = tk.Frame(s7)
        row1.pack(fill='x', padx=5, pady=1)
        tk.Label(row1, text=u'F11 脸型码1:', width=14, anchor='w').pack(side='left')
        self._detail_vars['face1'] = tk.StringVar()
        tk.Entry(row1, textvariable=self._detail_vars['face1'], width=50).pack(side='left', fill='x', expand=1, padx=(5,0))
        # F12: face_code_2 (present in >=13 fields, for random face generation)
        row2 = tk.Frame(s7)
        row2.pack(fill='x', padx=5, pady=1)
        tk.Label(row2, text=u'F12 脸型码2:', width=14, anchor='w').pack(side='left')
        self._detail_vars['face2'] = tk.StringVar()
        tk.Entry(row2, textvariable=self._detail_vars['face2'], width=50).pack(side='left', fill='x', expand=1, padx=(5,0))
        # 示意图
        img_row = tk.Frame(s7)
        img_row.pack(fill='x', padx=5, pady=(2,4))
        try:
            import os, sys
            # 支持 PyInstaller 打包后的环境
            if hasattr(sys, '_MEIPASS'):
                # PyInstaller 临时目录
                base_dir = sys._MEIPASS
            else:
                base_dir = os.path.dirname(os.path.abspath(__file__))
            # 尝试多个可能的路径
            possible_paths = [
                os.path.join(base_dir, 'face_code_hint.png'),
                os.path.join(os.path.dirname(base_dir), 'face_code_hint.png'),  # EXE 同级目录
            ]
            img_path = None
            for p in possible_paths:
                if os.path.exists(p):
                    img_path = p
                    break
            if img_path:
                from PIL import Image, ImageTk
                img = Image.open(img_path)
                # 缩放图片到合适宽度(比如400px)
                max_width = 400
                w, h = img.size
                if w > max_width:
                    ratio = max_width / float(w)
                    h = int(h * ratio)
                    w = max_width
                    img = img.resize((w, h), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                img_lbl = tk.Label(img_row, image=photo)
                img_lbl.image = photo  # 保持引用防止GC
                img_lbl.pack(anchor='w')
        except Exception:
            pass  # 图片加载失败则跳过

        # ── Section 7: Equipment Slots F7 (10 slots, list) ──
        # ── Section 7: Equipment (F7 Inventory) - 分类展示 ──
        s6 = tk.LabelFrame(f, text=u"F7 装备槽位 (Inventory)", font=('', 10, 'bold'))
        s6.pack(fill='x', padx=5, pady=3)

        # Container for armor + weapon lists side by side
        eq_main = tk.Frame(s6)
        eq_main.pack(fill='x', padx=5, pady=2)

        # --- 安装物品 list ---
        armor_f = tk.LabelFrame(eq_main, text=u"🛡 安装物品", font=('', 9, 'bold'), fg='#8B4513')
        armor_f.pack(side='left', fill='both', expand=1, padx=(0, 3))
        self._armor_listbox = tk.Listbox(armor_f, font=('Consolas', 8), height=5,
                                          selectmode=tk.SINGLE, exportselection=False)
        self._armor_listbox.pack(side='left', fill='both', expand=1)
        asb = tk.Scrollbar(armor_f, command=self._armor_listbox.yview)
        asb.pack(side='right', fill='y')
        self._armor_listbox.config(yscrollcommand=asb.set)
        self._armor_listbox.bind('<Double-Button-1>', lambda e: self._on_equip_dblclick('armor'))
        self._armor_slot_vars = []  # flat list of StringVar per item, rebuilt on populate

        # --- 武器 list ---
        weapon_f = tk.LabelFrame(eq_main, text=u"⚔ 武器", font=('', 9, 'bold'), fg='#B22222')
        weapon_f.pack(side='right', fill='both', expand=1, padx=(3, 0))
        self._weapon_listbox = tk.Listbox(weapon_f, font=('Consolas', 8), height=5,
                                           selectmode=tk.SINGLE, exportselection=False)
        self._weapon_listbox.pack(side='left', fill='both', expand=1)
        wsb = tk.Scrollbar(weapon_f, command=self._weapon_listbox.yview)
        wsb.pack(side='right', fill='y')
        self._weapon_listbox.config(yscrollcommand=wsb.set)
        self._weapon_listbox.bind('<Double-Button-1>', lambda e: self._on_equip_dblclick('weapon'))
        self._weapon_slot_vars = []

        # Legacy compatibility: keep _slot_vars / _slot_labels for _apply_font_size etc.
        self._slot_vars = self._armor_slot_vars + self._weapon_slot_vars
        self._slot_labels = []

        # ── Section 8: Upgrade Tree (F14/F15) ──
        s8 = tk.LabelFrame(f, text=u"F14/F15 升级树 (Upgrade)", font=('', 10, 'bold'))
        s8.pack(fill='x', padx=5, pady=3)

        # Upgrade tree visualization
        self._upgrade_tree_frame = tk.Frame(s8)
        self._upgrade_tree_frame.pack(fill='x', padx=5, pady=2)

        # Parents (who upgrades to this troop)
        self._parents_lbl = tk.Label(self._upgrade_tree_frame, text=u'↑ 被升级: -',
                                     fg='#0066cc', font=('', 9), anchor='w')
        self._parents_lbl.pack(fill='x')

        # Children (who this troop upgrades to)
        self._children_lbl = tk.Label(self._upgrade_tree_frame, text=u'↓ 可升级: -',
                                      fg='#009900', font=('', 9), anchor='w',
                                      wraplength=380, justify='left')
        self._children_lbl.pack(fill='x')

        # Full upgrade chain
        self._chain_lbl = tk.Label(self._upgrade_tree_frame, text='',
                                   fg='#FF6600', font=('', 9), anchor='w',
                                   wraplength=380, justify='left')
        self._chain_lbl.pack(fill='x')

        # Separator
        tk.Frame(s8, height=1, bg='#ccc').pack(fill='x', padx=5, pady=3)

        # Upgrade selection with searchable combobox
        # Layout: "升级成:" label on left, two comboboxes stacked vertically on right
        self._upgrade_combos = {}

        upgrade_container = tk.Frame(s8)
        upgrade_container.pack(fill='x', padx=5, pady=2)

        # Left side: "升级成:" label
        tk.Label(upgrade_container, text=u'升级成:', fg='#0000FF', font=('', 9, 'bold'),
                 width=8, anchor='w').pack(side='left', padx=(0, 5))

        # Right side: two comboboxes stacked
        combo_frame = tk.Frame(upgrade_container)
        combo_frame.pack(side='left', fill='x', expand=1)

        for key, label in [('upgrade1', u''), ('upgrade2', u'')]:
            row = tk.Frame(combo_frame)
            row.pack(fill='x', pady=1)

            # Use searchable combobox
            combo = SearchableCombobox(row, width=40, height=12)
            combo.frame.pack(side='left', fill='x', expand=1)
            self._upgrade_combos[key] = combo

            # Clear button
            tk.Button(row, text=u'✕', width=3,
                     command=lambda k=key: self._clear_upgrade(k)).pack(side='left', padx=(3,0))

            # Jump button
            tk.Button(row, text=u'→', width=3,
                     command=lambda k=key: self._jump_to_upgrade(k)).pack(side='left', padx=(3,0))

        # ── Action buttons ──
        btn_f = tk.Frame(f)
        btn_f.pack(fill='x', padx=5, pady=5)
        tk.Button(btn_f, text=u"应用修改到当前",
                  command=self._apply_detail_changes, bg='#F44336', fg='white',
                  width=20, font=('', 9, 'bold')).pack(side='left', padx=5)
        tk.Button(btn_f, text=u"还原",
                  command=self._revert_from_source, width=12).pack(side='left', padx=5)

    def _on_flag_change(self, bit_val):
        """Recalculate and display flag hex value + source expression when a checkbox toggles."""
        val = 0
        for bv, var in self._flag_vars.items():
            if var.get():
                val |= bv
        self._flag_hex_var.set('0x%08X' % val)
        # Rebuild source expression to match checkboxes
        self._flag_raw_var.set(build_flags_expr(val))

    def _on_attr_spin_change(self, ai):
        """Spinbox value changed -> rebuild source expression."""
        if self._attr_guard:
            return
        self._attr_guard = True
        str_v = int(self._attr_vars[0].get() or '0') if len(self._attr_vars) > 0 else 0
        agi_v = int(self._attr_vars[1].get() or '0') if len(self._attr_vars) > 1 else 0
        int_v = int(self._attr_vars[2].get() or '0') if len(self._attr_vars) > 2 else 0
        cha_v = int(self._attr_vars[3].get() or '0') if len(self._attr_vars) > 3 else 0
        level_v = int(self._attr_vars[4].get() or '0') if len(self._attr_vars) > 4 else 0
        self._attr_raw_var.set(build_attr_expr(str_v, agi_v, int_v, cha_v, level_v))
        self._attr_guard = False

    def _on_attr_expr_change(self):
        """Source expression changed manually -> update spinboxes."""
        if self._attr_guard:
            return
        self._attr_guard = True
        expr = self._attr_raw_var.get()
        str_v, agi_v, int_v, cha_v, level_v = parse_str_agi_int_cha(expr)
        if len(self._attr_vars) >= 5:
            self._attr_vars[0].set(str(str_v))
            self._attr_vars[1].set(str(agi_v))
            self._attr_vars[2].set(str(int_v))
            self._attr_vars[3].set(str(cha_v))
            self._attr_vars[4].set(str(level_v))
        self._attr_guard = False

    def _on_prof_spin_change(self, pi):
        """Proficiency spinbox changed -> rebuild source expression."""
        if getattr(self, '_prof_guard', False):
            return
        self._prof_guard = True
        prof_vals = [int(v.get() or '0') for v in self._prof_vars]
        self._prof_raw_var.set(build_prof_expr(prof_vals))
        self._prof_guard = False

    def _on_equip_dblclick(self, cat='armor'):
        """Double-click on equipment listbox -> jump to item editor."""
        if self.selected_idx < 0:
            return
        if cat == 'armor':
            lb = self._armor_listbox
        else:
            lb = self._weapon_listbox
        sel = lb.curselection()
        if not sel:
            return
        text = lb.get(sel[0])
        # text format: u'中文名 | itm_xxx' or u'[?] 中文名 | itm_xxx'
        parts = text.split(' | ')
        if len(parts) >= 2:
            iid = parts[-1].strip()
            # Find and select the item in the equipment panel
            all_items = [i[0] for i in self.item_list]
            if iid in all_items:
                idx = all_items.index(iid)
                try:
                    self.eq_lb.selection_clear(0, tk.END)
                    self.eq_lb.selection_set(idx)
                    self.eq_lb.see(idx)
                except:
                    pass

    def _on_slot_double_click(self, slot_idx):
        """Open equipment selector (legacy)."""
        if self.selected_idx < 0:
            return
        self._add_equipment()

    def _populate_detail_panel(self, flds):
        """Fill all detail panel widgets from parsed fields.
        Field layout (ming MOD):
          F0=id F1=name F2=plural F3=flags F4=scene F5=reserved
          F6=faction F7=inventory F8=attributes(str|agi|int|cha|level)
          F9=prof(wp) F10=skills(knows/hex) F11=face1 F12=face2
          F13=class F14=upgrade2 F15=upgrade1
        """
        if not flds:
            return
        # F0-F2: strings
        self._detail_vars['tid'].set(flds[0].strip('"\'') if len(flds) > 0 else '')
        self._detail_vars['name'].set(flds[1].strip('"\'') if len(flds) > 1 else '')
        self._detail_vars['plural'].set(flds[2].strip('"\'') if len(flds) > 2 else '')
        # F3: flags
        flag_raw = flds[3] if len(flds) > 3 else '0'
        self._flag_raw_var.set(flag_raw)
        flag_val = parse_flags(flag_raw)
        for bv, var in self._flag_vars.items():
            var.set(1 if (flag_val & bv) else 0)
        self._flag_hex_var.set('0x%08X' % flag_val)
        # Chinese names from translation
        tid_key = 'trp_' + flds[0].strip('"\'')
        self._detail_vars['name_cn'].set(self.troop_cn.get(tid_key, ''))
        self._detail_vars['plural_cn'].set(self.troop_cn_pl.get(tid_key + '_pl', ''))
        # F4: scene & F5: reserved
        self._detail_vars['scene'].set(flds[4] if len(flds) > 4 else '0')
        self._detail_vars['reserved'].set(flds[5] if len(flds) > 5 else 'reserved')
        # F6: faction - rebuild dropdown + select current
        faction_val = flds[6].strip() if len(flds) > 6 else ''
        # Rebuild faction dropdown choices
        if self._faction_combo:
            self._faction_combo.destroy()
        fac_choices = [fid for fid, en, cn in self.faction_data]
        fac_display = []
        for fid, en, cn in self.faction_data:
            d = fid
            if en:
                d += u'  %s' % en
            if cn:
                d += u'  %s' % cn
            fac_display.append(d)
        self._faction_var.set('')
        self._faction_combo = ttk.Combobox(
            self._faction_cn_lbl.master,
            textvariable=self._faction_var,
            values=fac_display,
            state='readonly',
            width=40)
        self._faction_combo.pack(side='left', fill='x', expand=1, padx=(5,0))
        # Bind selection change to update CN label
        def _on_faction_select(evt):
            sel = self._faction_var.get()
            fid = sel.split()[0] if sel.split() else ''
            cn = self.faction_cn.get(fid, '')
            self._faction_cn_lbl.config(text=cn if cn else u'(无汉化)')
        self._faction_combo.bind('<<ComboboxSelected>>', _on_faction_select)
        # Select current faction
        if faction_val:
            for choice in fac_display:
                if choice.startswith(faction_val):
                    self._faction_var.set(choice)
                    break
            else:
                self._faction_var.set(faction_val)
        else:
            self._faction_var.set('')
        # Show CN label
        cur_fid = faction_val.split()[0] if faction_val else faction_val
        cn = self.faction_cn.get(cur_fid, '')
        self._faction_cn_lbl.config(text=cn if cn else u'(无汉化)')
        # F7: inventory -> categorized listboxes
        inv_raw = flds[7] if len(flds) > 7 else '[]'
        inv_ids = parse_inventory(inv_raw)
        self._armor_listbox.delete(0, tk.END)
        self._weapon_listbox.delete(0, tk.END)
        self._armor_slot_vars = []
        self._weapon_slot_vars = []
        if hasattr(self, 'item_category'):
            for iid in inv_ids:
                cat = self.item_category.get(iid, 'other')
                zh = self.item_cn.get(iid, '') or (self.item_lookup.get(iid, {}) or {}).get('name', '')
                display = u'%s | %s' % (zh if zh else iid, iid)
                if cat == 'armor':
                    self._armor_listbox.insert(tk.END, display)
                    self._armor_slot_vars.append(tk.StringVar(value=display))
                elif cat == 'weapon':
                    self._weapon_listbox.insert(tk.END, display)
                    self._weapon_slot_vars.append(tk.StringVar(value=display))
                else:
                    # Unknown type: put in armor list with tag
                    self._armor_listbox.insert(tk.END, u'[?] ' + display)
                    self._armor_slot_vars.append(tk.StringVar(value=display))
        # Show placeholder if list is empty
        if self._armor_listbox.size() == 0:
            self._armor_listbox.insert(tk.END, u'  (空)')
            self._armor_listbox.itemconfig(0, fg='#999')
        if self._weapon_listbox.size() == 0:
            self._weapon_listbox.insert(tk.END, u'  (空)')
            self._weapon_listbox.itemconfig(0, fg='#999')
        # Legacy compatibility
        self._slot_vars = self._armor_slot_vars + self._weapon_slot_vars
        self._slot_labels = [self._armor_listbox, self._weapon_listbox]
        # F8: attributes
        attr_raw = flds[8] if len(flds) > 8 else '0'
        self._attr_raw_var.set(attr_raw)
        str_v, agi_v, int_v, cha_v, level_v = parse_str_agi_int_cha(attr_raw)
        if len(self._attr_vars) >= 5:
            self._attr_vars[0].set(str(str_v))
            self._attr_vars[1].set(str(agi_v))
            self._attr_vars[2].set(str(int_v))
            self._attr_vars[3].set(str(cha_v))
            self._attr_vars[4].set(str(level_v))
        # level is shown in attr section spinbox, no separate basic-info field
        # F9: proficiencies
        prof_raw = flds[9] if len(flds) > 9 else '0'
        self._prof_raw_var.set(prof_raw)
        prof_vals = parse_prof_values(prof_raw)
        for pi in range(min(len(prof_vals), len(self._prof_vars))):
            self._prof_vars[pi].set(str(prof_vals[pi]))
        # F10: skills (bidirectional: expr <-> spinboxes)
        skill_raw = flds[10] if len(flds) > 10 else '0'
        skill_vals = parse_skill_values(skill_raw)
        for si in range(min(len(skill_vals), len(self._skill_vars))):
            self._skill_vars[si].set(str(skill_vals[si]))
        self._skill_raw_var.set(skill_raw)
        # F11: face_code_1 (present in >=12 fields)
        f11 = flds[11] if len(flds) > 11 else '0'
        self._detail_vars['face1'].set(self._resolve_face_code(f11))
        # F12: face_code_2 (present in >=13 fields, for regular troops)
        f12 = flds[12] if len(flds) > 12 else ''
        self._detail_vars['face2'].set(self._resolve_face_code(f12))
        # F14-F15: upgrades - build items once (combobox fill deferred to _on_troop_select)
        self._upgrade_items_cache = self._build_upgrade_items()

    def _apply_detail_changes(self):
        """Apply all detail panel edits back to troops_fields/troops_entries.
        Rebuilds the source expression from individual Spinbox values."""
        idx = self.selected_idx
        if idx < 0 or idx >= len(self.troops_fields):
            tkMessageBox.showwarning(u"提示", u"请先选择一个兵种")
            return
        self._push_undo()
        flds = self.troops_fields[idx]
        tid = flds[0].strip('"\'')  # troop ID for dirty tracking
        # Extend to 16 fields if needed
        while len(flds) < 16:
            flds.append('0')

        # F0-F2: strings
        flds[0] = '"' + self._detail_vars['tid'].get().strip() + '"'
        flds[1] = '"' + self._detail_vars['name'].get().strip() + '"'
        flds[2] = '"' + self._detail_vars['plural'].get().strip() + '"'
        # F3: flags - use raw expression or rebuild from checkboxes
        flag_val = 0
        for bv, var in self._flag_vars.items():
            if var.get():
                flag_val |= bv
        if flag_val == 0:
            flds[3] = '0'
        else:
            # Rebuild as hex for simplicity
            flds[3] = '0x%08X' % flag_val
        # F4: scene (keep original if unchanged)
        flds[4] = self._detail_vars['scene'].get().strip() or '0'
        # F5: reserved
        flds[5] = self._detail_vars['reserved'].get().strip() or 'reserved'
        # F6: faction - extract ID from dropdown selection
        fac_sel = self._faction_var.get().strip()
        flds[6] = fac_sel.split()[0] if fac_sel else 'fac_commoners'
        # Save Chinese names to troops.csv
        self._save_troop_translation(flds)
        # F7: inventory (preserved from original, managed via equipment panel)
        # flds[7] unchanged
        # F8: attributes - rebuild expression
        if len(self._attr_vars) >= 5:
            str_v = int(self._attr_vars[0].get() or '0')
            agi_v = int(self._attr_vars[1].get() or '0')
            int_v = int(self._attr_vars[2].get() or '0')
            cha_v = int(self._attr_vars[3].get() or '0')
            level_v = int(self._attr_vars[4].get() or '0')
            flds[8] = build_attr_expr(str_v, agi_v, int_v, cha_v, level_v)
        # F9: proficiencies - rebuild expression
        prof_vals = [int(v.get() or '0') for v in self._prof_vars]
        flds[9] = build_prof_expr(prof_vals)
        # F10: skills - rebuild from spinboxes
        if hasattr(self, '_skill_vars') and self._skill_vars:
            svals = [int(v.get() or '0') for v in self._skill_vars]
            flds[10] = build_skill_expr(svals)
        # F11-F12: face codes
        flds[11] = self._detail_vars['face1'].get().strip() or '0'
        flds[12] = self._detail_vars['face2'].get().strip() or '0'
        # F14-F15: upgrades (after removing F13: F14->flds[13], F15->flds[14])
        up1 = self._upgrade_combos['upgrade1'].get_value() if 'upgrade1' in self._upgrade_combos else '0'
        up2 = self._upgrade_combos['upgrade2'].get_value() if 'upgrade2' in self._upgrade_combos else '0'
        # Track dirty: mark troop if upgrade values actually changed
        old_up1 = flds[13].strip('"\'') if len(flds) > 13 else '0'
        old_up2 = flds[14].strip('"\'') if len(flds) > 14 else '0'
        new_up1 = up1 if up1 else '0'
        new_up2 = up2 if up2 else '0'
        if new_up1 != old_up1 or new_up2 != old_up2:
            self._dirty_upgrades.add(tid)
        flds[13] = new_up1
        flds[14] = new_up2

        # Trim trailing zeros
        while len(flds) > 11 and flds[-1] == '0' and flds[-2] == '0':
            flds.pop()

        # Rebuild entry string
        self.troops_entries[idx] = '  [' + ', '.join(flds) + ']'
        self.troops_fields[idx] = flds
        # Sync upgrade_tree with current flds data (tid defined earlier)
        if tid in self.upgrade_tree:
            # Update existing entry
            self.upgrade_tree[tid]['upgrade1'] = up1 if up1 else '0'
            self.upgrade_tree[tid]['upgrade2'] = up2 if up2 else '0'
        elif up1 != '0' or up2 != '0':
            # New upgrade entry
            self.upgrade_tree[tid] = {'upgrade1': up1 if up1 else '0', 'upgrade2': up2 if up2 else '0'}
        # Refresh views
        self._show_detail()
        self._fill_equipment()
        self.status.config(text=u"详情面板修改已应用 (未保存到文件)")

    def _on_skill_expr_change(self):
        """Source expression changed -> update all 42 spinboxes."""
        if self._skill_spin_guard:
            return
        if not hasattr(self, '_skill_vars') or not self._skill_vars:
            return
        expr = self._skill_raw_var.get().strip()
        skill_vals = parse_skill_values(expr)
        self._skill_expr_guard = True
        for si in range(min(len(skill_vals), len(self._skill_vars))):
            self._skill_vars[si].set(str(skill_vals[si]))
        self._skill_expr_guard = False

    def _on_skill_spin_change(self, idx):
        """Spinbox value changed -> rebuild source expression."""
        if self._skill_expr_guard:
            return
        if not hasattr(self, '_skill_vars') or not self._skill_vars:
            return
        self._skill_spin_guard = True
        vals = [int(v.get() or '0') for v in self._skill_vars]
        self._skill_raw_var.set(build_skill_expr(vals))
        self._skill_spin_guard = False

    def _revert_from_source(self):
        """Re-parse module_troops.py from disk and refresh all views.
        This discards all unsaved edits and reloads from the source file."""
        if not self.mod_path:
            tkMessageBox.showwarning(u"提示", u"请先加载 MOD")
            return

        if not tkMessageBox.askyesno(
            u"确认还原",
            u"将从 module_troops.py 重新读取,所有未保存的修改将丢失。\n\n确定还原?"
        ):
            return

        tp = os.path.join(self.source_path, 'module_troops.py')
        if not os.path.isfile(tp):
            tkMessageBox.showerror(u"错误", u"找不到 module_troops.py")
            return

        try:
            header, entries, footer = parse_array_by_lines(tp, 'troops')
        except ValueError as e:
            tkMessageBox.showerror(u"解析错误", unicode(e))
            return

        # Remember old selection
        old_troop_id = None
        if self.selected_idx >= 0 and self.selected_idx < len(self.troops_fields):
            flds = self.troops_fields[self.selected_idx]
            if flds:
                old_troop_id = flds[0].strip('"\'')

        # Replace data
        self.troops_header = header
        self.troops_footer = footer
        self.troops_entries = entries
        self.troops_fields = [parse_fields_in_entry(e) for e in entries]
        self._face_key_map = self._parse_face_keys()
        self.upgrade_tree = {}
        try:
            self._parse_upgrade_calls(tp)
        except Exception:
            pass  # upgrade tree is non-critical

        # Clear undo
        self.undo_stack = []
        self.redo_stack = []

        # Restore selection
        new_idx = -1
        if old_troop_id:
            for i, flds in enumerate(self.troops_fields):
                if flds and flds[0].strip('"\'') == old_troop_id:
                    new_idx = i
                    break
        if new_idx < 0:
            new_idx = 0

        # Refresh views
        self._fill_list()
        self.selected_idx = new_idx
        if new_idx >= 0 and new_idx < len(self.troops_fields):
            self._select_troop(new_idx)

        self.status.config(text=u"已从源文件还原 (%d 兵种)" % len(self.troops_fields))

    def _refresh_detail_from_source(self):
        """Re-populate detail panel from current source data."""
        if self.selected_idx >= 0 and self.selected_idx < len(self.troops_fields):
            self._populate_detail_panel(self.troops_fields[self.selected_idx])
            self.status.config(text=u"详情面板已从源码刷新")

    def _build_upgrade_items(self):
        """Build list of (troop_id, display_name) for upgrade comboboxes.
        Format: (1)中文名 | trp_xxx (matches reference UI)"""
        items = [('0', '(无)')]
        for i, flds in enumerate(self.troops_fields):
            if len(flds) > 0:
                tid = flds[0].strip('"\'')
                name = flds[1].strip('"\'') if len(flds) > 1 else ''
                trp_key = 'trp_' + tid
                cn = self.troop_cn.get(trp_key, '')
                # Format: (1)中文名 | trp_xxx
                if cn:
                    display = '(%d)%s | %s' % (i+1, cn, tid)
                else:
                    display = '(%d)%s | %s' % (i+1, name, tid)
                items.append((tid, display))
        return items

    def _update_upgrade_tree(self, idx):
        """Update upgrade tree visualization for troop at idx.
        Uses self.upgrade_tree (built from upgrade()/upgrade2() calls + inline fields).
        Shows full upgrade chain path with Chinese names where available."""
        if idx < 0 or idx >= len(self.troops_fields):
            if hasattr(self, '_parents_lbl'):
                self._parents_lbl.config(text=u'↑ 被升级: -')
                self._children_lbl.config(text=u'↓ 可升级: -')
            if hasattr(self, '_chain_lbl'):
                self._chain_lbl.config(text='')
            return

        flds = self.troops_fields[idx]
        if len(flds) < 1:
            return
        current_tid = flds[0].strip('"\'')

        def _get_troop_display(tid):
            """Return display string: tid (cn_name) or tid (en_name)"""
            # Try translation first
            trp_key = 'trp_' + tid
            cn = self.troop_cn.get(trp_key, '')
            if cn:
                return u'%s (%s)' % (tid, cn)
            # Try to find English name from any entry
            for f in self.troops_fields:
                if len(f) > 0 and f[0].strip('"\'') == tid:
                    en = f[1].strip('"\'') if len(f) > 1 else ''
                    if en and en != '0':
                        return u'%s (%s)' % (tid, en)
            return tid

        def _format_chain(tid_list, arrow=u' → '):
            """Format a chain of troop IDs as display text."""
            if not tid_list:
                return ''
            return arrow.join(_get_troop_display(t) for t in tid_list)

        # ---- Find parents (who upgrades to this troop) ----
        parents = []
        for other_tid, info in self.upgrade_tree.items():
            if info.get('upgrade1') == current_tid or info.get('upgrade2') == current_tid:
                parents.append(other_tid)
        # Also check inline fields (for troops that might have upgrades not in upgrade_tree)
        for other_flds in self.troops_fields:
            if len(other_flds) < 14:
                continue
            other_tid = other_flds[0].strip('"\'')
            if other_tid in self.upgrade_tree:
                continue  # Already checked above
            up1 = other_flds[13].strip('"\'') if len(other_flds) > 13 else '0'
            up2 = other_flds[14].strip('"\'') if len(other_flds) > 14 else '0'
            if up1 == current_tid or up2 == current_tid:
                parents.append(other_tid)

        # ---- Find children (who this troop upgrades to) ----
        children = []
        if current_tid in self.upgrade_tree:
            info = self.upgrade_tree[current_tid]
            if info.get('upgrade1', '0') != '0':
                children.append(info['upgrade1'])
            if info.get('upgrade2', '0') != '0':
                children.append(info['upgrade2'])
        # Also check inline fields
        for f in self.troops_fields:
            if len(f) > 0 and f[0].strip('"\'') == current_tid and len(f) > 13:
                up1 = f[13].strip('"\'') if len(f) > 13 else '0'
                up2 = f[14].strip('"\'') if len(f) > 14 else '0'
                if up1 != '0' and up1 not in children:
                    children.append(up1)
                if up2 != '0' and up2 not in children:
                    children.append(up2)

        # ---- Build full forward chain (deepest path from current) ----
        def _trace_forward(tid, visited=None):
            """Trace forward from tid to the deepest leaf."""
            if visited is None:
                visited = set()
            if not tid or tid == '0' or tid in visited:
                return []
            visited.add(tid)
            info = self.upgrade_tree.get(tid, {})
            up1 = info.get('upgrade1', '0')
            up2 = info.get('upgrade2', '0')
            # Prefer upgrade2 path first (usually the direct upgrade)
            chain1 = _trace_forward(up2, visited) if up2 != '0' else []
            chain2 = _trace_forward(up1, visited) if up1 != '0' else []
            if not chain1 and not chain2:
                return [tid]
            # Return longer chain
            if len(chain1) >= len(chain2):
                return [tid] + chain1
            else:
                return [tid] + chain2

        # ---- Build backward chain (from root to current) ----
        def _trace_backward(tid, visited=None):
            """Trace backward from tid to the root."""
            if visited is None:
                visited = set()
            if not tid or tid == '0' or tid in visited:
                return []
            visited.add(tid)
            # Find all parents
            p = []
            for ot, info in self.upgrade_tree.items():
                if info.get('upgrade1') == tid or info.get('upgrade2') == tid:
                    p.append(ot)
            if not p:
                return [tid]
            # Use first parent
            parent_chain = _trace_backward(p[0], visited)
            return parent_chain + [tid]

        forward = _trace_forward(current_tid)
        backward = _trace_backward(current_tid)

        # ---- Update labels ----
        # Parents line: show immediate parents
        if not hasattr(self, '_parents_lbl'):
            return
        if parents:
            display_parents = [_get_troop_display(p) for p in parents[:4]]
            parent_text = u'↑ 被升级: ' + u', '.join(display_parents)
            if len(parents) > 4:
                parent_text += u' (共%d个)' % len(parents)
            self._parents_lbl.config(text=parent_text)
        else:
            self._parents_lbl.config(text=u'↑ 被升级: (无)')

        # Children line: show immediate children
        if children:
            display_children = [_get_troop_display(c) for c in children]
            child_text = u'↓ 可升级: ' + u', '.join(display_children)
            self._children_lbl.config(text=child_text)
        else:
            self._children_lbl.config(text=u'↓ 可升级: (无)')

        # Full chain line: forward from current
        if len(forward) > 1:
            self._chain_lbl.config(text=u'  升级链: ' + _format_chain(forward))
        else:
            self._chain_lbl.config(text='')

    def _clear_upgrade(self, key):
        """Clear upgrade field."""
        if key in self._upgrade_combos:
            self._upgrade_combos[key].set_value('0')

    def _jump_to_upgrade(self, key):
        """Jump to the selected upgrade troop."""
        if key not in self._upgrade_combos:
            return
        tid = self._upgrade_combos[key].get_value()
        if not tid or tid == '0':
            return
        # Find troop index
        for i, flds in enumerate(self.troops_fields):
            if len(flds) > 0 and flds[0].strip('"\'') == tid:
                self.troop_lb.selection_clear(0, 'end')
                self.troop_lb.selection_set(i)
                self.troop_lb.see(i)
                self._on_troop_select(None)
                return
        tkMessageBox.showinfo(u'提示', u'未找到兵种: %s' % tid)

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
        elif key == 'detail' and 0 <= self.selected_idx < len(self.troops_fields):
            self._populate_detail_panel(self.troops_fields[self.selected_idx])

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
        self._load_shared_data()
        # Reset load flags — each module loads on demand
        self._troops_loaded = False
        self._item_loaded = False
        # Auto-load current module if visible
        if self._current_module == 'troops':
            self._load_troops_data()
        elif self._current_module == 'items':
            self._load_items_data()
        self.root.update()

        # Plugin hook
        for p in self.plugins:
            try:
                p.on_mod_open(self, self.mod_path)
            except Exception:
                pass

    def _reload(self):
        if not self.mod_path:
            tkMessageBox.showwarning(u"提示", u"请先打开MOD")
            return
        # Reload shared data (translations, factions)
        self._load_shared_data()
        # Reload current module
        self._reload_module(self._current_module)

    # ================================================================
    # ================================================================
    #  Data Loading (lazy: each module loads on demand)
    # ================================================================

    def _load_shared_data(self):
        """Load translations, factions, and other shared data."""
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
            # Load faction translations
            fcp = os.path.join(self.translation_path, 'factions.csv')
            if os.path.isfile(fcp):
                self.faction_cn = load_translations(fcp)
        # Parse module_factions.py for faction en names
        if self.source_path:
            fac_path = os.path.join(self.source_path, 'module_factions.py')
            if os.path.isfile(fac_path):
                try:
                    with codecs.open(fac_path, 'r', 'utf-8', errors='replace') as ff:
                        fac_text = ff.read()
                    # Find the factions list
                    fac_list_match = re.search(r'factions\s*=\s*\[(.*?)\](?=\s*$|\s*\n\s*#|\s*\n\s*\Z)', fac_text, re.DOTALL)
                    if fac_list_match:
                        fac_body = fac_list_match.group(1)
                    else:
                        fac_body = fac_text[fac_text.index('factions = ['):]
                        # Find closing bracket
                        depth = 0; end = fac_text.index('factions = ['); started = False
                        for i in range(end, len(fac_text)):
                            if fac_text[i] == '[': depth += 1; started = True
                            elif fac_text[i] == ']': depth -= 1
                            if started and depth == 0: fac_body = fac_text[end: i+1]; break
                        fac_body = fac_body[fac_body.index('[')+1 : fac_body.rindex(']')]
                    fids = []
                    pparts = u'[' + fac_body + u']'
                    for m in re.finditer(r'\(\s*"([^"]+)"\s*,\s*"([^"]*)"', pparts):
                        fid = m.group(1)
                        fname = m.group(2).replace('{!}', '')
                        cn = self.faction_cn.get('fac_' + fid, '')
                        self.faction_data.append(('fac_' + fid, fname, cn))
                        fids.append('fac_' + fid)
                except Exception as e:
                    print 'Faction parse warning:', str(e)

    def _load_troops_data(self):
        """Load troops from module_troops.py."""
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

        # --- Parse upgrade tree from upgrade()/upgrade2() calls ---
        self.upgrade_tree = {}  # troop_id -> {'upgrade1': 'x', 'upgrade2': 'y'}
        try:
            self._parse_upgrade_calls(tp)
        except Exception as e:
            print "WARNING: upgrade tree parse failed:", str(e)

        # --- Populate UI ---
        self._populate_list()
        self.selected_idx = -1
        self._clear_detail()
        self._clear_equipment()
        self._set_ui_state(len(self.troops_entries) > 0)
        self._count_lbl.config(text=u"\u5171 %d \u4e2a\u5175\u79cd" % len(self.troops_entries))
        self._undo_stack = []
        self._redo_stack = []
        self._troops_loaded = True
        self.status.config(text=u"\u2705 \u5df2\u52a0\u8f7d\u5175\u79cd: %d | \u5347\u7ea7\u6811: %d" % (
            len(self.troops_entries), len(self.upgrade_tree)))

    def _load_items_data(self):
        """Load items from module_items.py."""
        ip = os.path.join(self.source_path, 'module_items.py')
        self.items = []
        self.item_lookup = {}
        self.item_entries = []
        self.item_fields_list = []
        if os.path.isfile(ip):
            try:
                item_header, ientries, item_footer = parse_array_by_lines(ip, 'items')
                self.item_header = item_header
                self.item_footer = item_footer
                self.item_entries = ientries
                self.item_fields_list = [parse_fields_in_entry(e) for e in ientries]
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

        # --- Build item type categories ---
        self.item_category = {}  # 'itm_xxx' -> 'armor' | 'weapon' | 'other'
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
            found_types = set(re.findall(r'itp_type_\w+', raw))
            if found_types & _ARMOR_TYPES:
                self.item_category[it['id']] = 'armor'
            elif found_types & _WEAPON_TYPES:
                self.item_category[it['id']] = 'weapon'
            else:
                self.item_category[it['id']] = 'other'

        # --- Build item display list ---
        self.item_list = []
        for it in self.items:
            zh = self.item_cn.get(it['id'], '') or it.get('name', '')
            self.item_list.append((it['id'], zh))

        # --- Don't populate UI until user visits items tab ---
        self._clear_item_detail()
        self._item_undo_stack = []
        self._item_redo_stack = []
        self._item_loaded = True
        self.status.config(text=u"\u2705 \u5df2\u52a0\u8f7d\u7269\u54c1: %d" % len(self.item_entries))

    def _reload_module(self, name):
        """Reload a specific module's data."""
        if name == 'troops':
            self._troops_loaded = False
            self._load_troops_data()
            if self._current_module == 'troops':
                self._show_module('troops')
        elif name == 'items':
            self._item_loaded = False
            self._load_items_data()
            if self._current_module == 'items':
                self._show_module('items')

    def _parse_upgrade_calls(self, troops_path):
        """Parse upgrade()/upgrade2() function calls from the full
        module_troops.py file to build a complete upgrade tree.

        Stores into self.upgrade_tree:
            troop_id -> {'upgrade1': str, 'upgrade2': str}

        Handles both:
          upgrade(troops, "from", "to")        -> sets upgrade1 or upgrade2 (first empty slot)
          upgrade2(troops, "from", "to1", "to2") -> sets both upgrade1 and upgrade2
        """
        import re as _re
        with codecs.open(troops_path, 'r', 'utf-8', errors='replace') as f:
            content = f.read()

        # Pattern for active upgrade calls (not commented)
        # upgrade(troops, "a", "b")  or  upgrade2(troops, "a", "b", "c")
        active_re = _re.compile(
            r'^\s*upgrade(2)?\s*\(\s*troops\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"(?:\s*,\s*"([^"]+)")?\s*\)',
            _re.MULTILINE)

        for m in active_re.finditer(content):
            is_upgrade2 = (m.group(1) == '2')
            from_id = m.group(2)
            to1 = m.group(3)
            to2 = m.group(4) if is_upgrade2 else None

            if from_id not in self.upgrade_tree:
                self.upgrade_tree[from_id] = {'upgrade1': '0', 'upgrade2': '0'}
            info = self.upgrade_tree[from_id]

            if is_upgrade2:
                info['upgrade1'] = to1
                info['upgrade2'] = to2
            else:
                # upgrade() fills first available slot
                if info['upgrade1'] == '0':
                    info['upgrade1'] = to1
                elif info['upgrade2'] == '0':
                    info['upgrade2'] = to1

        # Also parse inline upgrade fields from troops array entries
        for flds in self.troops_fields:
            if len(flds) < 14:
                continue
            tid = flds[0].strip('"\'')
            up1 = flds[13].strip('"\'') if len(flds) > 13 else '0'
            up2 = flds[14].strip('"\'') if len(flds) > 14 else '0'
            if up1 != '0' or up2 != '0':
                if tid in self.upgrade_tree:
                    # Inline fields supplement, don't override function calls
                    info = self.upgrade_tree[tid]
                    if info['upgrade1'] == '0':
                        info['upgrade1'] = up1
                    if info['upgrade2'] == '0':
                        info['upgrade2'] = up2
                else:
                    self.upgrade_tree[tid] = {'upgrade1': up1, 'upgrade2': up2}

    def _parse_face_keys(self):
        """Parse face key definitions from troops_header.
        Returns dict: key_name -> resolved hex value (0x...).
        Supports transitive references like: merchant_face_1 = man_face_young_1."""
        raw_map = {}
        # Scan header lines for: identifier = value
        for line in self.troops_header.split('\n'):
            m = re.match(r'^(\w+)\s*=\s*(.+?)\s*(?:#.*)?$', line.strip())
            if not m:
                continue
            key = m.group(1)
            val = m.group(2).strip().rstrip(',')
            # Skip Python keywords, imports, etc.
            if key in ('import', 'from', 'def', 'class', 'if', 'else', 'elif',
                       'for', 'while', 'return', 'True', 'False', 'None', 'and',
                       'or', 'not', 'in', 'is', 'as', 'with', 'try', 'except',
                       'raise', 'pass', 'break', 'continue', 'yield', 'lambda',
                       'global', 'exec', 'print', 'del', 'assert'):
                continue
            # Standard module-system keys (attributes, skills, etc. have pipes)
            if '|' in key or '(' in key:
                continue
            raw_map[key] = val
        # Resolve transitive references (max 10 passes to break cycles)
        for _ in range(10):
            changed = False
            for key, val in raw_map.items():
                if val.startswith('0x') or val.startswith('0X'):
                    continue  # already hex
                if val in raw_map:
                    target = raw_map[val]
                    if target.startswith('0x') or target.startswith('0X'):
                        raw_map[key] = target
                        changed = True
            if not changed:
                break
        return {k: v for k, v in raw_map.items() if v.startswith('0x') or v.startswith('0X')}

    def _resolve_face_code(self, val):
        """Resolve a face code value: key name -> hex, or pass-through."""
        val = val.strip()
        if not val or val == '0':
            return '0'
        if val.startswith('0x') or val.startswith('0X'):
            return val  # already hex
        if val in self._face_key_map:
            return self._face_key_map[val]
        return val  # unresolved, keep as-is

    # ================================================================
    #  List Population
    # ================================================================


    def _save_troop_translation(self, flds):
        """Save Chinese name/plural to troops.csv localization file."""
        if not self.translation_path:
            return
        tcp = os.path.join(self.translation_path, 'troops.csv')
        if not os.path.isfile(tcp):
            return
        tid = 'trp_' + flds[0].strip("\"'")
        cn_sing = self._detail_vars['name_cn'].get().strip()
        cn_pl = self._detail_vars['plural_cn'].get().strip()
        # Read existing lines
        with codecs.open(tcp, 'r', 'utf-8-sig', errors='replace') as f:
            lines = f.readlines()
        # Update or append
        sing_found = False
        pl_found = False
        new_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(tid + '_pl|') or stripped == tid + '_pl':
                pl_found = True
                if cn_pl:
                    new_lines.append(tid + '_pl|' + cn_pl + '\n')
                else:
                    continue  # skip empty
            elif stripped.startswith(tid + '|') or stripped == tid:
                sing_found = True
                if cn_sing:
                    new_lines.append(tid + '|' + cn_sing + '\n')
                else:
                    continue
            else:
                new_lines.append(line)
        if not sing_found and cn_sing:
            new_lines.append(tid + '|' + cn_sing + '\n')
        if not pl_found and cn_pl:
            new_lines.append(tid + '_pl|' + cn_pl + '\n')
        # Write back
        with codecs.open(tcp, 'w', 'utf-8-sig') as f:
            f.write(''.join(new_lines))
        # Update memory caches
        if cn_sing:
            self.troop_cn[tid] = cn_sing
        else:
            self.troop_cn.pop(tid, None)
        if cn_pl:
            self.troop_cn_pl[tid + '_pl'] = cn_pl
        else:
            self.troop_cn_pl.pop(tid + '_pl', None)
        # Refresh list display
        self._populate_list(self._search_var.get() if hasattr(self, '_search_var') else '')
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
            # Plugin hook
            try:
                troop = (self.troops_fields[self.selected_idx]
                         if 0 <= self.selected_idx < len(self.troops_fields) else None)
                for p in self.plugins:
                    p.on_troop_select(self, troop, self.selected_idx)
            except Exception:
                pass

    def _on_key_select(self):
        """Handle selection after End/Home keys have scrolled the list."""
        self._on_select(None)

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

        self.detail_title.config(text=u'#%d  %s - %s' % (idx, full_id, zh))

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

        # Detail tab
        if self._current_tab == 'detail':
            self._populate_detail_panel(flds)

        # Always update upgrade tree visualization (visible on all tabs)
        # Update combobox items from cache or rebuild
        if hasattr(self, '_upgrade_combos'):
            upgrade_items = getattr(self, '_upgrade_items_cache', None) or self._build_upgrade_items()
            self._upgrade_items_cache = upgrade_items
            # Get current troop ID
            current_tid = flds[0].strip('"\'') if len(flds) > 0 else ''
            # Get upgrade info from tree (merge of function calls + embedded fields)
            up_info = self.upgrade_tree.get(current_tid, {})
            for key in ['upgrade1', 'upgrade2']:
                if key in self._upgrade_combos:
                    self._upgrade_combos[key].set_items(upgrade_items)
                    # Priority: upgrade_tree (function calls) > embedded fields (flds)
                    tree_val = up_info.get(key, '0')
                    if tree_val != '0':
                        val = tree_val
                    else:
                        # Fallback to embedded fields (F14/F15 indices after removing F13)
                        if key == 'upgrade1':
                            val = flds[13] if len(flds) > 13 else '0'
                        else:
                            val = flds[14] if len(flds) > 14 else '0'
                    self._upgrade_combos[key].set_value(val.strip('"\''))
        self._update_upgrade_tree(idx)

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
        # Clear equipment listboxes
        try:
            self._armor_listbox.delete(0, tk.END)
            self._weapon_listbox.delete(0, tk.END)
        except:
            pass

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
            self.eq_lb.insert(tk.END, u'Slot %-2d  %s | %s' % (i, iid, zh))

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
        dlg.title(u"选择装备 - %s" % tid)
        dlg.geometry("720x560")
        dlg.transient(self.root)

        # Search
        sf = tk.Frame(dlg)
        sf.pack(fill='x', padx=5, pady=5)
        tk.Label(sf, text=u"搜索物品:").pack(side='left')
        sv = tk.StringVar()
        tk.Entry(sf, textvariable=sv, width=30).pack(side='left', padx=5)
        tk.Label(sf, text=u"共 %d 件物品" % len(self.item_list), fg='#666').pack(side='right')

        # Current equipment - with scrollbar, no limit
        cef = tk.LabelFrame(dlg, text=u"当前拥有物品 (双击移除)")
        cef.pack(fill='both', expand=1, padx=5, pady=5)
        ce_frame = tk.Frame(cef)
        ce_frame.pack(fill='both', expand=1, padx=5, pady=5)
        ce_lb = tk.Listbox(ce_frame, font=('Consolas', 9), height=8, selectmode=tk.MULTIPLE)
        ce_lb.pack(side='left', fill='both', expand=1)
        ce_sb = tk.Scrollbar(ce_frame, command=ce_lb.yview)
        ce_sb.pack(side='right', fill='y')
        ce_lb.config(yscrollcommand=ce_sb.set)
        ce_lb.bind('<Double-Button-1>', lambda e: _del_selected(ce_lb))

        def _refresh_ce():
            ce_lb.delete(0, tk.END)
            for si, iid in enumerate(current_ids):
                zh = self.item_cn.get(iid, '') or (self.item_lookup.get(iid, {}) or {}).get('name', '')
                ce_lb.insert(tk.END, u'Slot %-2d  %s | %s' % (si, iid, zh))
        _refresh_ce()

        # All items
        itf = tk.LabelFrame(dlg, text=u"物品列表 (双击或多选后点添加)")
        itf.pack(fill='x', padx=5, pady=5)

        it_frame = tk.Frame(itf)
        it_frame.pack(fill='x', padx=5, pady=5)
        ilb = tk.Listbox(it_frame, font=('Consolas', 9), selectmode=tk.MULTIPLE, height=6)
        ilb.pack(side='left', fill='both', expand=1)
        isb = tk.Scrollbar(it_frame, command=ilb.yview)
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
                # Allow duplicates - just append
                current_ids.append(iid)
                zh = self.item_cn.get(iid, '') or (self.item_lookup.get(iid, {}) or {}).get('name', '')
                dst_lb.insert(tk.END, u'Slot %-2d  %s | %s' % (len(current_ids)-1, iid, zh))

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
            self.status.config(text=u"物品已修改 (未保存到文件,请点击保存按钮)")
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
        if not tkMessageBox.askyesno(u"确认", u"确定清空 %s 的全部装备?" % tid):
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
        if not tkMessageBox.askyesno(u"确认", u"确定新增一个空兵种模板?\n将添加到列表末尾。"):
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
        if not tkMessageBox.askyesno(u"确认", u"确定复制兵种 %s?" % tid):
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
                                     u"确定永久删除兵种 %s?\n\n"
                                     u"⚠ 此操作不可撤销!\n"
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

    def _rebuild_footer_upgrades(self, footer):
        """Update upgrade()/upgrade2() calls IN-PLACE in footer.
        Only touches troops in self._dirty_upgrades (modified since last save).
        Retains all other upgrade calls and their original positions."""
        import re as _re
        _valid_id = _re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')
        # Pattern for active upgrade lines: indent + upgrade[2](troops,"from","to1"[,"to2"])
        _call_pat = _re.compile(
            r'^([ \t]*)(#*\s*)(upgrade)(2?)\s*\(\s*troops\s*,'
            r'\s*"([^"]+)"\s*,\s*"([^"]+)"(?:\s*,\s*"([^"]+)")?\s*\)')

        # Build desired calls ONLY from dirty troops
        desired = {}
        to_remove = set()  # dirty troops that no longer have upgrades
        for flds in self.troops_fields:
            if len(flds) <= 13:
                continue
            tid = flds[0].strip('"\'')
            if not _valid_id.match(tid):
                continue
            if tid not in self._dirty_upgrades:
                continue  # untouched → keep existing footer calls
            up1 = flds[13].strip('"\'') if len(flds) > 13 else '0'
            up2 = flds[14].strip('"\'') if len(flds) > 14 else '0'
            up1_valid = up1 and up1 != '0' and _valid_id.match(up1)
            up2_valid = up2 and up2 != '0' and _valid_id.match(up2)
            if up2_valid:
                desired[tid] = 'upgrade2(troops,"%s","%s","%s")' % (tid, up1, up2)
            elif up1_valid:
                desired[tid] = 'upgrade(troops,"%s","%s")' % (tid, up1)
            else:
                # Dirty troop now has no upgrades - remove its calls
                to_remove.add(tid)

        if not desired and not to_remove:
            return footer  # nothing to do

        # Process footer lines: replace dirty calls, remove stale, keep rest
        lines = footer.split('\n')
        last_upgrade_line = -1
        result = []
        for i, line in enumerate(lines):
            m = _call_pat.match(line)
            if m:
                prefix = m.group(2).strip()
                if prefix.startswith('#'):
                    result.append(line)  # keep commented calls as-is
                    continue
                from_id = m.group(5)
                if from_id in desired:
                    indent = m.group(1)
                    result.append(indent + desired.pop(from_id))
                    last_upgrade_line = len(result) - 1
                elif from_id in to_remove:
                    result.append('')  # remove old call → blank line, collapsed later
                else:
                    result.append(line)  # keep untouched call as-is
            else:
                result.append(line)

        # Collapse consecutive blank lines (max 2)
        collapsed = []
        blank_count = 0
        for line in result:
            if line.strip() == '':
                blank_count += 1
                if blank_count <= 2:
                    collapsed.append(line)
            else:
                blank_count = 0
                collapsed.append(line)

        # Append remaining new calls
        if desired:
            new_block = '\n'.join(desired.values())
            if last_upgrade_line >= 0:
                collapsed.insert(last_upgrade_line + 1, new_block)
            else:
                collapsed.append('')
                collapsed.append(new_block)

        result_text = '\n'.join(collapsed)
        result_text = result_text.rstrip('\n')
        return result_text + '\n'

        # Collapse consecutive blank lines (max 2)
        collapsed = []
        blank_count = 0
        for line in result:
            if line.strip() == '':
                blank_count += 1
                if blank_count <= 2:
                    collapsed.append(line)
            else:
                blank_count = 0
                collapsed.append(line)

        # Append new calls after the last upgrade line position
        if desired:
            tail = '\n' + '\n'.join(desired.values())
            if last_upgrade_line >= 0:
                # Insert right after the last replaced upgrade line
                collapsed.insert(last_upgrade_line + 1, tail)
            else:
                # No existing upgrade lines found: append at end
                collapsed.extend(tail.split('\n'))

        result_text = '\n'.join(collapsed)
        result_text = result_text.rstrip('\n')
        return result_text + '\n'

    def _save_current_module(self):
        """Smart save: delegates to current module."""
        if self._current_module == 'troops':
            self._save_troops()
        elif self._current_module == 'items':
            self._save_items()

    def _save_troops(self):
        if not self.mod_path:
            tkMessageBox.showwarning(u"提示", u"请先加载 MOD")
            return

        # Auto-apply detail panel edits before saving (one-step save)
        # Skip if user is on raw tab (raw edits bypass detail vars)
        if self.selected_idx >= 0 and self._current_tab != 'raw':
            try:
                self._apply_detail_changes()
            except Exception:
                pass  # non-fatal: if apply fails, still try to save what we have

        if not tkMessageBox.askyesno(u"确认保存",
                                     u"确定保存兵种数据到 module_troops.py?\n\n"
                                     u"⚠ 此操作将覆盖源文件!\n"
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
            # Rebuild upgrade()/upgrade2() calls to sync with current data
            footer = self._rebuild_footer_upgrades(self.troops_footer)
            parts.append(footer)

            output = ''.join(parts)

            with open(filepath, 'wb') as f:
                f.write(output.encode('utf-8'))

        except Exception as e:
            tkMessageBox.showerror(u"错误", u"保存失败: %s" % e)
            return

        self.status.config(text=u"✅ 已保存到 module_troops.py (备份: .bak) - %d 个兵种" % len(
            self.troops_entries))
        self._dirty_upgrades.clear()  # reset dirty tracking after save
        self._raw_text.edit_reset()
        # Plugin hook
        for p in self.plugins:
            try:
                p.on_save(self)
            except Exception:
                pass

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
                                     u"确定运行编译脚本?\n\n"
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
            self.status.config(text=u"编译已启动 - 请查看控制台窗口")
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
        """Apply background color to containers, preserving button/entry native colors.
        Strategy: save all interactive widget colors first, apply bg to containers,
        then restore saved colors to prevent any interference."""
        # 1. Collect all interactive widgets and save their current colors
        saved = []
        self._collect_saved_bg(widget, saved)
        # 2. Apply bg to containers only
        self._apply_bg_to_containers(widget, clr)
        # 3. Restore all saved colors (guarantees no interference)
        for w, orig_bg in saved:
            try:
                w.config(bg=orig_bg)
            except:
                pass

    def _collect_saved_bg(self, widget, saved):
        """Recursively collect (widget, current_bg) for interactive widgets."""
        try:
            wclass = widget.winfo_class()
            if wclass in {'Button', 'Checkbutton', 'Radiobutton', 'Entry',
                          'Spinbox', 'Scrollbar', 'Listbox', 'Text', 'Scale'}:
                try:
                    saved.append((widget, widget.cget('bg')))
                except:
                    saved.append((widget, 'SystemButtonFace'))
                return  # don't recurse into interactive widgets
        except:
            pass
        try:
            for child in widget.winfo_children():
                self._collect_saved_bg(child, saved)
        except:
            pass

    def _apply_bg_to_containers(self, widget, clr):
        """Recursively set bg on container widgets, skip interactive."""
        try:
            wclass = widget.winfo_class()
            # Don't recolor the resize drag handle
            if hasattr(self, '_resize_handle') and widget is self._resize_handle:
                return
            if wclass in {'Frame', 'LabelFrame', 'Canvas', 'Tk', 'Toplevel',
                          'Label', 'PanedWindow'}:
                widget.config(bg=clr)
            else:
                return  # don't touch or recurse into non-containers
        except:
            pass
        try:
            for child in widget.winfo_children():
                self._apply_bg_to_containers(child, clr)
        except:
            pass

    def _change_font_size(self):
        """Popup dialog to change global font size."""
        dlg = tk.Toplevel(self.root)
        dlg.title(u"字体大小")
        dlg.geometry("320x200")
        dlg.transient(self.root)
        dlg.resizable(False, False)

        tk.Label(dlg, text=u"调整字体大小 (8-20)", font=('', 10)).pack(pady=10)

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
        # Also update detail panel widgets if they exist
        try:
            for v in list(self._detail_vars.values()) + self._attr_vars + \
                    self._skill_vars + self._prof_vars:
                try:
                    widgets.append(v)
                except:
                    pass
        except AttributeError:
            pass
        # Add categorized equipment listboxes
        for attr in ['_armor_listbox', '_weapon_listbox']:
            try:
                lb = getattr(self, attr, None)
                if lb is not None:
                    widgets.append(lb)
            except:
                pass
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
            self.root.title(u"天佑战团 v%s - %s" % (VERSION, self.mod_path))
        else:
            self.root.title(u"天佑战团源码编辑器 v%s" % VERSION)

    def _about(self):
        tkMessageBox.showinfo(u"关于",
                              u"天佑战团源码编辑器 v%s\n\n"
                              u"Mount & Blade Warband\n"
                              u"Module System Source Editor\n\n"
                              u"开发者:李天佑\n"
                              u"电话:15628308654\n\n"
                              u"功能:\n"
                              u"\u2022 兵种编辑器 - 查看/新增/复制/删除/排序\n"
                              u"\u2022 兵种编辑器 - 查看/新增/复制/删除/排序\n"
                              u"\u2022 技能面板 - 42技能可视化编辑 (knows_xxx_N)\n"
                              u"\u2022 升级树 - 可搜索下拉框,161条记录\n"
                              u"\u2022 装备管理 - 分类展示+拥有物品面板\n"
                              u"\u2022 源码三标签页(基本信息 + 详情 + 源码)\n"
                              u"\u2022 撤销/重做(50步快照) + Ctrl+S快捷保存\n"
                              u"\u2022 编译集成 + 汉化联动 + 模块化插件\n\n"
                              u"技术栈:Python 2.7 + Tkinter" % VERSION)

    def _show_changelog(self):
        """Show version history in a scrollable dialog."""
        dlg = tk.Toplevel(self.root)
        dlg.title(u"更新日志 - 天佑战团源码编辑器")
        dlg.geometry("600x500")
        dlg.transient(self.root)
        dlg.grab_set()

        tk.Label(dlg, text=u"天佑战团源码编辑器 - 更新日志",
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
                    u'  MAJOR - 架构级重写\n'
                    u'  MINOR - 功能新增 / 较大改动\n'
                    u'  PATCH - Bug 修复 / 文案调整\n')
        text.config(state='disabled')
        tk.Button(dlg, text=u"关闭", command=dlg.destroy, width=12).pack(pady=10)

    def _show_tutorial(self):
        """Show editor tutorial in a scrollable dialog."""
        dlg = tk.Toplevel(self.root)
        dlg.title(u"教程 - 天佑战团源码编辑器")
        dlg.geometry("650x520")
        dlg.transient(self.root)
        dlg.grab_set()

        tk.Label(dlg, text=u"天佑战团源码编辑器 - 使用教程",
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

2. 左侧兵种列表:
   • 双击 → 打开装备选择器
   • 搜索框 → 按 ID 或中文名过滤
   • 新增/复制/删除 → 对应按钮
   • ▲▼ → 上下移动兵种位置

3. 右侧详情面板(两个标签页):
   • 基本信息 - 兵种全字段解析展示
   • 源码 - 原始 module_troops.py 片段可直接编辑
     → Ctrl+Z/Y 在此标签页内撤回源码修改

4. 顶栏「装备管理」:
   • 双击装备列表项 → 快速打开装备选择器
   • 添加装备 → 打开物品选择对话框(支持搜索)
   • 移除选中 → 删除当前装备
   • 清空装备 → 移除该兵种全部装备

5. 右上角「应用修改到当前」→ 暂存到内存(可 Ctrl+Z 撤销)
   左下角「保存」或 Ctrl+S → 自动应用修改 + 写入文件
   (自动创建 .bak 备份)

══════════════════════════════════════════════
  编译与发布
══════════════════════════════════════════════

6. 编译 → 设置 module_info 路径
   指向游戏的 .exe 目录后,点击「运行 build_module.bat」
   自动编译所有 .py 源文件到 Mod

7. 汉化联动:
   编辑器读取 cns/csv 中的 troop 汉化字段
   自动匹配显示中文名

══════════════════════════════════════════════
  撤销/重做
══════════════════════════════════════════════

8. Ctrl+Z / Ctrl+Y:
   • 焦点在源码框 → 文本级撤销(只撤销文本改动)
   • 焦点在列表/按钮 → 兵种级撤销(增删复制移动装备)
   • 菜单「编辑→撤销」始终走兵种级撤销
   • 快照 50 步,跨兵种不清空

══════════════════════════════════════════════
  快捷键速查
══════════════════════════════════════════════

  Ctrl+O    - 打开 MOD
  F5        - 重新加载
  Ctrl+Z    - 撤销(文本级/兵种级)
  Ctrl+Y    - 重做
  Ctrl+S    - 保存(自动应用修改 + 写入文件)
"""

        text.insert('1.0', tutorial)
        text.config(state='disabled')
        tk.Button(dlg, text=u"关闭", command=dlg.destroy, width=12).pack(pady=10)

    # ================================================================
    #  Lifecycle
    # ================================================================

    def _load_plugins(self):
        """Discover and load all plugins from plugins/ directory."""
        try:
            from plugins import discover_plugins
            self.plugins = discover_plugins()
            for p in self.plugins:
                try:
                    p.on_load(self)
                except Exception as e:
                    print("[plugin] {} on_load error: {}".format(p.name, e))
            # Populate plugins menu
            self._plugin_menu.delete(0, 'end')
            has_items = False
            for p in self.plugins:
                for label, cb in (p.get_menu_items() or []):
                    self._plugin_menu.add_command(label=label, command=cb)
                    has_items = True
            if not has_items:
                self._plugin_menu.add_command(label=u"(无插件)", state='disabled')
            if self.plugins:
                self.status.config(text=u"已加载 {} 个插件".format(len(self.plugins)))
        except ImportError:
            pass  # plugins/ not available

    def _on_close(self):
        has_unsaved = self.troops_entries or self.item_entries
        if self.mod_path and has_unsaved:
            if tkMessageBox.askyesno(u"退出", u"退出前是否保存修改?"):
                self._save_troops()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    app = TianyouEditor()
    app.run()
