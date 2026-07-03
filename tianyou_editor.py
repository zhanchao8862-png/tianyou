#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
天佑战团源码编辑器
Mount & Blade Warband Module System Source Editor
Developer: 李天佑  电话: 15628308654
"""

VERSION = "2.3.1"

CHANGELOG = [
    {
        "version": "2.3.1",
        "date": "2026-06-26",
        "changes": [
            u"Bug修复: 物品详情面板空白 — _populate_item_detail中self.editor误引用→self导致AttributeError",
            u"物品详情表单数据全部正确填充: 基本属性/模型/类型标记/属性值/修饰符/阵营",
            u"汉化名称字段接入item_kinds.csv, cn_name显示+编辑+回写完整闭环",
            u"Mesh三行(名称/标志/动作)正则解析修复, shield_kite_a等模型正确解析",
            u"Stats正则支持hit_points等字段, 盾牌hit_points(480)正确渲染",
            u"构建脚本build_exe.py路径修正 — 旧源文件→新源文件(物品详情代码之前缺失)",
        ]
    },
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

import os, sys, re, codecs, shutil, subprocess, copy, json, time, traceback, logging
reload(sys)
sys.setdefaultencoding('utf-8')

# Import flag dictionary (bit-grouped labels parsed from header_items.py)
try:
    from flag_dict import ITP_TYPE_FLAGS, ITP_OTHER_FLAGS, ITC_TEMPLATES, ITC_TEMPLATE_LABELS, ITCF_FLAGS
except Exception:
    # Fallback if flag_dict.py is missing
    ITP_TYPE_FLAGS = []
    ITP_OTHER_FLAGS = []
    ITC_TEMPLATES = []
    ITC_TEMPLATE_LABELS = {}
    ITCF_FLAGS = []

# Import MVC section controllers for item detail form
try:
    from item_sections import build_all_sections
except Exception:
    build_all_sections = None

# Import capability category structure (derived from module_items.py F4 data)
try:
    from cap_dict import ITCF_CATEGORIES
except Exception:
    ITCF_CATEGORIES = []

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
    encodings = ('utf-8-sig', 'utf-8', 'gbk', 'gb18030')
    raw = None
    for enc in encodings:
        try:
            with codecs.open(csv_path, 'r', enc, errors='replace') as f:
                raw = f.read()
            break
        except Exception:
            raw = None
    if raw is None:
        return trans
    if not isinstance(raw, unicode):
        try:
            raw = unicode(raw, 'utf-8', 'replace')
        except Exception:
            raw = unicode(raw, 'replace')
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split('|', 1)
        if len(parts) >= 2:
            key = parts[0].strip()
            val = parts[1].strip()
            if key:
                trans[key] = val
                # Normalize item / faction keys so lookups work whether the CSV
                # stores `itm_xxx` or bare `xxx`, and whether callers pass the
                # normalized or raw identifier.
                if key.startswith('itm_'):
                    trans.setdefault(key[4:], val)
                else:
                    trans.setdefault('itm_' + key, val)
    return trans


def _normalize_item_id(item_id):
    item_id = (item_id or '').strip()
    if not item_id:
        return ''
    if item_id.startswith('itm_'):
        return item_id
    return 'itm_' + item_id


def _item_cn_lookup(item_cn, item_id, default=''):
    item_id = (item_id or '').strip()
    if not item_cn or not item_id:
        return default
    # Accept both raw item ids and `itm_`-prefixed ids.
    item_id = item_id.strip('"').strip("'")
    val = item_cn.get(item_id, '')
    if val:
        return val
    if item_id.startswith('itm_'):
        val = item_cn.get(item_id[4:], '')
    else:
        val = item_cn.get('itm_' + item_id, '')
    if val:
        return val
    # Some callers may pass identifiers with stray whitespace or quoting.
    item_id = item_id.strip()
    return item_cn.get(item_id, default)


def _item_display_name(item_cn, item_lookup, full_id, fallback_name=''):
    zh = _item_cn_lookup(item_cn, full_id, '')
    if zh:
        return zh
    if full_id and full_id in item_lookup:
        return (item_lookup.get(full_id, {}) or {}).get('name', '') or fallback_name
    return fallback_name


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

    def _copy_title_id(self, event=None):
        """Double-click title -> copy troop/item ID to clipboard."""
        import re
        # Parse ID from label text: "#N  trp_xxx - 中文名" or "#N  itm_xxx - 中文名"
        label = event.widget
        text = label.cget('text')
        tid = ''
        if text:
            m = re.search(r'\b(trp_\w+|itm_\w+)\b', text)
            if m:
                tid = m.group(1)
        if tid:
            self.editor.root.clipboard_clear()
            self.editor.root.clipboard_append(tid)
            if hasattr(self.editor, '_set_status'):
                self.editor._set_status(u'\u2713 \u5df2\u590d\u5236 ID: ' + tid)

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


class TianyouEditor(object):
    def __init__(self):
        self.root = tk.Tk()
        self._setup_debug_runtime()
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

        # ── Module instances ──
        self._troop_module = TroopModule(self)
        self._item_module = ItemModule(self)
        self._modules = {u'troops': self._troop_module, u'items': self._item_module}
        self._active_module = None

        self.translation_path = self._config.get('translation_path', '')
        self.module_info_path = self._config.get('module_info_path', '')
        self.build_bat_path = self._config.get('build_bat_path', '')
        self.font_size = self._config.get('font_size', 10)

        # Source data
        self.selected_idx = -1

        self._current_module = ''   # 'troops' | 'items' | ...
        self._modules_loaded = set()  # track which modules have been loaded
        self._ui_drag_freeze_until = 0.0
        self._ui_drag_freeze_after = None
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

        # ── Build UI ──
        self._build_menubar()
        self._build_ui()
        self._build_statusbar()
        self.root.bind_class('Listbox', '<MouseWheel>', lambda e: None)
        self.root.bind_class('Canvas', '<MouseWheel>', lambda e: None)
        self.root.bind_all('<MouseWheel>', self._on_global_wheel)
        self._set_ui_state(False)
        self.root.bind('<Configure>', self._on_root_configure)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        if hasattr(self, 'status') and self.status is not None:
            self.status.config(text=u"就绪 - [文件] → [打开MOD] 加载项目")
        self._update_title()
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
        self.plugins = []
        self._load_plugins()
        # Root-level mousewheel dispatch: Windows sends MouseWheel to focused
        # widget, not the widget under cursor. We check cursor position instead.
        # Neutralize default class-level scroll bindings so bind_all has sole control.

    def _setup_debug_runtime(self):
        """Write exceptions to console and a local log file for dev runs."""
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        except Exception:
            base_dir = os.getcwd()
        self._debug_log_path = os.path.join(base_dir, 'tianyou_editor_debug.log')
        try:
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s %(levelname)s %(message)s',
                filename=self._debug_log_path,
                filemode='a'
            )
        except Exception:
            pass
        def _hook(exc_type, exc, tb):
            msg = ''.join(traceback.format_exception(exc_type, exc, tb))
            try:
                logging.error(msg)
            except Exception:
                pass
            try:
                head = msg.splitlines()[-1] if msg.splitlines() else u'运行错误'
                self._set_status(head[:120])
            except Exception:
                pass
            try:
                tkMessageBox.showerror(u'运行错误', msg.decode('utf-8', 'ignore') if isinstance(msg, str) else msg)
            except Exception:
                pass
        sys.excepthook = _hook
        try:
            self.root.report_callback_exception = lambda et, ev, tb: _hook(et, ev, tb)
        except Exception:
            pass

    # ================================================================
    #  Undo / Redo
    # ================================================================


    # ── Module Attribute Routing ──
    _ROUTED_ATTRS = frozenset([
        '_attr_vars',
        '_btn_add_eq',
        '_btn_clr_eq',
        '_btn_move_down',
        '_btn_move_up',
        '_btn_rm_eq',
        '_current_items_tab',
        '_current_tab',
        '_detail_vars',
        '_dirty_upgrades',
        '_eq_height',
        '_face_key_map',
        '_guard',
        '_info_text',
        '_item_detail_canvas',
        'item_sections',
        '_items_loaded',
        '_items_panel',
        '_items_redo_stack',
        '_items_undo_stack',
        '_prof_vars',
        '_raw_text',
        '_redo_stack',
        '_resize_dragging',
        '_resize_handle',
        '_resize_start_h',
        '_resize_start_y',
        '_copy_title_id',
        '_save_btn',
        '_skill_vars',
        '_tab_btns',
        '_tab_frames',
        '_troops_loaded',
        '_troops_panel',
        '_undo_max',
        '_undo_stack',
        'detail_title',
        'eq_lb',
        'items_detail_title',
        'items_entries',
        'items_fields',
        'items_footer',
        'items_header',
        'items_info_text',
        'items_lb',
        'items_raw_text',
        'items_search_var',
        'items_selected_idx',
        'items_tab_btns',
        'items_tab_frames',
        '_items_list_index_map',
        'search_var',
        'selected_idx',
        'troop_lb',
        'troops_entries',
        'troops_fields',
        'troops_footer',
        'troops_header',
        'upgrade_tree',

    ])

    def __getattribute__(self, name):
        if name in TianyouEditor._ROUTED_ATTRS:
            # Try active module first
            try:
                mod = object.__getattribute__(self, '_active_module')
                if mod is not None and hasattr(mod, name):
                    return getattr(mod, name)
            except AttributeError:
                pass
            # Fall back: find any module that owns this attr
            try:
                mods = object.__getattribute__(self, '_modules')
                for m in mods.values():
                    if hasattr(m, name):
                        return getattr(m, name)
            except AttributeError:
                pass
        return object.__getattribute__(self, name)

    def __setattr__(self, name, value):
        if name in TianyouEditor._ROUTED_ATTRS:
            # Try active module first
            try:
                mod = object.__getattribute__(self, '_active_module')
                if mod is not None and hasattr(mod, name):
                    setattr(mod, name, value)
                    return
            except AttributeError:
                pass
            # Fall back: find any module that owns this attr
            try:
                mods = object.__getattribute__(self, '_modules')
                for m in mods.values():
                    if hasattr(m, name):
                        setattr(m, name, value)
                        return
            except AttributeError:
                pass
        object.__setattr__(self, name, value)


    def _push_undo(self):
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
            self.status.config(text=u"\u6ca1\u6709\u53ef\u4ee5\u64a4\u9500\u7684\u64cd\u4f5c")
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
        self._count_lbl.config(text=u"\u5171 %d \u4e2a\u5175\u79cd" % len(mod.troops_entries))
        self.status.config(text=u"\u21a9 \u5df2\u64a4\u9500 (\u5269\u4f59 %d \u6b65)" % len(mod._undo_stack))

    def _undo_items(self):
        mod = self._active_module
        if not mod._undo_stack:
            self.status.config(text=u"\u6ca1\u6709\u53ef\u4ee5\u64a4\u9500\u7684\u64cd\u4f5c")
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
        self.status.config(text=u"\u21a9 \u5df2\u64a4\u9500 (\u5269\u4f59 %d \u6b65)" % len(mod._undo_stack))

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
            self.status.config(text=u"\u6ca1\u6709\u53ef\u4ee5\u91cd\u505a\u7684\u64cd\u4f5c")
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
        self._count_lbl.config(text=u"\u5171 %d \u4e2a\u5175\u79cd" % len(mod.troops_entries))
        self.status.config(text=u"\u21aa \u5df2\u91cd\u505a (\u5269\u4f59 %d \u6b65)" % len(mod._redo_stack))

    def _redo_items(self):
        mod = self._active_module
        if not mod._redo_stack:
            self.status.config(text=u"\u6ca1\u6709\u53ef\u4ee5\u91cd\u505a\u7684\u64cd\u4f5c")
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
        self.status.config(text=u"\u21aa \u5df2\u91cd\u505a (\u5269\u4f59 %d \u6b65)" % len(mod._redo_stack))

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
        dm.add_command(label=u"调试日志", command=self._show_debug_console)
        dm.add_separator()
        dm.add_command(label=u"关于", command=self._about)
        menubar.add_cascade(label=u"开发者", menu=dm)

        # ── Plugins menu (built from loaded plugins) ──
        self._plugin_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=u"插件", menu=self._plugin_menu)

        self.root.config(menu=menubar)
        self.root.bind('<Control-o>', lambda e: self._open_mod())
        self.root.bind('<Control-O>', lambda e: self._open_mod())
        self.root.bind('<Control-s>', lambda e: self._save_troops())
        self.root.bind('<Control-S>', lambda e: self._save_troops())
        self.root.bind('<F5>', lambda e: self._reload())

    # ================================================================
    #  Main UI
    # ================================================================

    # ================================================================
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
            elif module_name == u'items':
                self._build_items_panel(self.content_area)
            self._active_module._built = True

        # Show
        if self._active_module.panel:
            self._active_module.panel.pack(expand=1, fill=u'both')

        self._active_module.on_show()

        # Async load
        if not self._active_module._loaded:
            if module_name == u'troops':
                self.status.config(text=u"\u52a0\u8f7d\u5175\u79cd\u6570\u636e\u4e2d...")
                self.root.after(50, self._load_troops_async)
            elif module_name == u'items':
                self.status.config(text=u"\u52a0\u8f7d\u7269\u54c1\u6570\u636e\u4e2d...")
                self.root.after(50, self._load_items_async)

        # Highlight tree
        for child in self.nav_tree.get_children(''):
            for sub in self.nav_tree.get_children(child):
                tags = self.nav_tree.item(sub, u'tags')
                if tags and tags[0] == module_name:
                    self.nav_tree.selection_set(sub)

    def _load_troops_async(self):
        if self._is_ui_frozen():
            self.root.after(50, self._load_troops_async)
            return
        try:
            self._load_troops()
            self._active_module._loaded = True
        except Exception as e:
            self.status.config(text=u"\u52a0\u8f7d\u5931\u8d25: " + unicode(e))

    def _load_items_async(self):
        if self._is_ui_frozen():
            self.root.after(50, self._load_items_async)
            return
        try:
            self._load_items()
            self._active_module._loaded = True
        except Exception as e:
            self.status.config(text=u"\u52a0\u8f7d\u5931\u8d25: " + unicode(e))

    def _build_ui(self):
        """Build main layout: nav sidebar + content area."""
        outer = tk.PanedWindow(self.root, orient='horizontal',
                               sashrelief='raised', sashwidth=4)
        outer.pack(expand=1, fill='both')

        # Navigation sidebar
        nav = self._build_nav(outer)
        outer.add(nav, minsize=120)

        # Content area (will hold troops/items panels)
        # Use Frame for easy show/hide caching; each module creates its own PanedWindow
        self.content_area = tk.Frame(outer)
        outer.add(self.content_area, minsize=400)


    def _build_troops_panel(self, parent):
        """Build troops editor panel."""
        # Wrap panel in root Frame for easy show/hide caching
        root_frame = tk.Frame(parent)
        self._active_module.panel = root_frame
        # Internal PanedWindow for left/right split
        main = tk.PanedWindow(root_frame, orient='horizontal',
                               sashrelief='raised', sashwidth=4)
        main.pack(expand=1, fill='both')
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
        # End/Home keys: defer selection handling to after default scroll
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
        right = tk.Frame(main)
        main.add(right, minsize=320)

        def _fit_troop_panes(_event=None):
            try:
                if self._is_ui_frozen():
                    return
                total = main.winfo_width()
                if total <= 1:
                    return
                left_pref = 320
                left_min = 220
                right_min = 420
                target = total - right_min
                if target < left_min:
                    target = left_min
                if target > left_pref:
                    target = left_pref
                if total - target < left_min:
                    target = max(left_min, total - left_min)
                main.sash_place(0, target, 1)
            except Exception:
                pass

        main.bind('<ButtonRelease-1>', _fit_troop_panes)
        root_frame.after_idle(_fit_troop_panes)

        # Title
        self.detail_title = tk.Label(right, text=u"请选择一个兵种", font=('', 12, 'bold'),
                                     anchor='w', fg='#333', cursor='hand2')
        self.detail_title.pack(fill='x', pady=(0, 5))
        self.detail_title.bind('<Double-Button-1>', self._copy_title_id)

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
        # Text-level undo/redo (takes priority over troop-level when focused)
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

        # Equipment listbox with scrollbar (no limit on items)
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

    # ── Resize: equipment panel drag handle ──

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
            if hasattr(self, '_faction_combo') and widget is self._faction_combo:
                try:
                    return self.item_sections.get('triggers')._on_faction_wheel(event)
                except Exception:
                    return 'break'
            # Equipment listbox
            if hasattr(self, 'eq_lb') and widget is self.eq_lb:
                self.eq_lb.yview_scroll(int(-1 * (event.delta / 120)), 'units')
                return 'break'
            if widget.winfo_class() == 'Listbox' and hasattr(widget, 'yview_scroll'):
                try:
                    widget.yview_scroll(int(-1 * (event.delta / 120)), 'units')
                    return 'break'
                except Exception:
                    pass
            # Skill canvas region
            if hasattr(self, '_skill_canvas') and widget is self._skill_canvas:
                self._skill_canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')
                return 'break'
            # Detail canvas region
            if hasattr(self, '_detail_canvas') and widget is self._detail_canvas:
                self._detail_canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')
                return 'break'
            # Item detail canvas region
            if hasattr(self, '_item_detail_canvas') and widget is self._item_detail_canvas:
                self._item_detail_canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')
                return 'break'
            if hasattr(self, '_item_detail_canvas') and self._is_descendant(widget, self._item_detail_canvas):
                self._item_detail_canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')
                return 'break'
            # Troop list region
            if widget is self.troop_lb:
                self.troop_lb.yview_scroll(int(-1 * (event.delta / 120)), 'units')
                return 'break'
            widget = widget.master
        return

    def _is_descendant(self, widget, ancestor):
        while widget is not None:
            if widget is ancestor:
                return True
            widget = getattr(widget, 'master', None)
        return False

    def _build_detail_panel(self, parent):
        """Build the structured troop detail panel based on ming MOD field layout:
        F0-F15: id|name|plural|flags|scene|reserved|faction|inventory|attributes|prof|skills|face1|face2|class|upgrade1|upgrade2"""
        # Wrap in a Frame so scrollbar has right padding
        wrap = tk.Frame(parent)
        wrap.pack(fill='both', expand=1)
        # Scrollable container (inside wrap)
        self._detail_canvas = canvas = tk.Canvas(wrap, highlightthickness=0)
        scrollbar = tk.Scrollbar(wrap, orient='vertical', command=canvas.yview, width=18)
        self._detail_scroll_frame = tk.Frame(canvas)
        def _detail_on_config(event):
            if self._is_ui_frozen():
                return
            w = event.width
            h = event.height
            if getattr(canvas, '_last_detail_size', None) == (w, h):
                return
            canvas._last_detail_size = (w, h)
            if getattr(canvas, '_scroll_after_id', None):
                try:
                    canvas.after_cancel(canvas._scroll_after_id)
                except Exception:
                    pass
            canvas._scroll_after_id = canvas.after_idle(lambda c=canvas: (
                setattr(c, '_scroll_after_id', None),
                c.configure(scrollregion=c.bbox('all'))
            ))

        self._detail_scroll_frame.bind('<Configure>', _detail_on_config)
        canvas.create_window((0, 0), window=self._detail_scroll_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side='left', expand=1, fill='both')
        scrollbar.pack(side='right', fill='y', padx=(2, 4))
        f = self._detail_scroll_frame

        # ── Section 1: Basic Info (ID/Name/Plural + CN + Scene/Reserved/Faction) ──
        s1 = tk.LabelFrame(f, text=u"基础信息 (修改中文自动保存到汉化文件)", font=('', 10, 'bold'))
        s1.pack(fill='x', padx=5, pady=3)
        self._detail_vars = {}
        # Row helper: label + entry
        def _add_info_row(parent, key, label, width=36, readonly=False):
            row = tk.Frame(parent)
            row.pack(fill='x', padx=5, pady=1)
            tk.Label(row, text=label + ':', width=13, anchor='w').pack(side='left')
            self._detail_vars[key] = tk.StringVar()
            st = 'readonly' if readonly else 'normal'
            e = tk.Entry(row, textvariable=self._detail_vars[key], width=width, state=st)
            e.pack(side='left', fill='x', expand=1, padx=(5,0))
            return e

        basic_body = tk.Frame(s1)
        basic_body.pack(fill='x', padx=5, pady=2)
        left = tk.Frame(basic_body)
        left.pack(side='left', fill='both', expand=1)
        right = tk.Frame(basic_body)
        right.pack(side='left', fill='both', expand=1, padx=(10, 0))

        _add_info_row(left, 'tid', u'F0 兵种 ID', readonly=True)
        _add_info_row(left, 'name', u'F1 英文名')
        _add_info_row(left, 'plural', u'F2 英文复数名')
        _add_info_row(left, 'name_cn', u'  中文名')
        _add_info_row(left, 'plural_cn', u'  中文复数名')
        _add_info_row(right, 'scene', u'F4 场景')
        _add_info_row(right, 'reserved', u'F5 保留字段')
        # Faction: dropdown + CN label
        faction_row = tk.Frame(s1)
        faction_row.pack(fill='x', padx=5, pady=1)
        tk.Label(faction_row, text=u'F6 阵营:', width=13, anchor='w').pack(side='left')
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
        self._attr_raw_var.trace('w', lambda *a: self._on_attr_expr_change())
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
        self._skill_raw_var.trace('w', lambda *a: self._on_skill_expr_change())
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
        skill_win = skill_canvas.create_window((0, 0), window=skill_inner, anchor='nw')
        skill_canvas.configure(yscrollcommand=skill_sb.set)
        skill_canvas.pack(side='left', fill='both', expand=1, padx=5, pady=2)
        skill_sb.pack(side='right', fill='y', padx=(0,5), pady=2)
        def _skill_update_scroll(event=None):
            try:
                skill_canvas.configure(scrollregion=skill_canvas.bbox('all'))
            except Exception:
                pass
        def _skill_on_canvas_config(event):
            try:
                skill_canvas.itemconfig(skill_win, width=event.width)
            except Exception:
                pass
        skill_inner.bind('<Configure>', _skill_update_scroll)
        skill_canvas.bind('<Configure>', _skill_on_canvas_config)
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
        _skill_update_scroll()

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
                zh = _item_cn_lookup(self.item_cn, iid, '') or (self.item_lookup.get(iid, {}) or {}).get('name', '')
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

        # Update scrollregion after content rebuild
        if hasattr(self, '_detail_canvas') and self._detail_canvas:
            self._detail_canvas.after_idle(lambda c=self._detail_canvas: c.configure(scrollregion=c.bbox('all')))

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
        self.status_var = tk.StringVar(value='')
        self.status = tk.Label(sf, textvariable=self.status_var, anchor='w')
        self.status.pack(side='left', fill='x', expand=1, padx=5)
        self._count_lbl = tk.Label(sf, text="", anchor='e')
        self._count_lbl.pack(side='right', padx=5)

    def _set_status(self, text):
        try:
            if hasattr(self, 'status_var') and self.status_var is not None:
                self.status_var.set(text)
                return
        except Exception:
            pass
        try:
            if hasattr(self, 'status') and self.status is not None:
                self.status.config(text=text)
        except Exception:
            pass

    def _set_ui_state(self, enabled):
        state = 'normal' if enabled else 'disabled'
        troop_widgets = ['troop_lb', '_btn_add_eq', '_btn_rm_eq', '_btn_clr_eq',
                         '_btn_move_up', '_btn_move_down']
        for name in troop_widgets:
            w = getattr(self, name, None)
            if w is not None:
                w.config(state=state)
        if hasattr(self, '_tab_btns'):
            for btn in self._tab_btns.values():
                btn.config(state=state)

    def _freeze_ui_during_window_move(self, grace_ms=180):
        try:
            until = time.time() + (grace_ms / 1000.0)
            if until > self._ui_drag_freeze_until:
                self._ui_drag_freeze_until = until
            pending = self._ui_drag_freeze_after
            if pending is not None:
                try:
                    self.root.after_cancel(pending)
                except Exception:
                    pass
            self._ui_drag_freeze_after = self.root.after(
                grace_ms + 40, self._thaw_ui_after_window_move
            )
        except Exception:
            pass

    def _thaw_ui_after_window_move(self):
        self._ui_drag_freeze_after = None
        self._ui_drag_freeze_until = 0.0

    def _is_ui_frozen(self):
        try:
            return time.time() < self._ui_drag_freeze_until
        except Exception:
            return False

    def _on_root_configure(self, event=None):
        # WM move/resize produces a burst of configure events. Freeze heavy UI work briefly.
        self._freeze_ui_during_window_move()

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
            self._show_module('troops')

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
        self._show_module('troops')
        self.root.update()

        # Plugin hook
        for p in self.plugins:
            try:
                p.on_mod_open(self, self.mod_path)
            except Exception:
                pass



    # ================================================================
    #  Items Panel
    # ================================================================

    def _build_items_panel(self, parent):
        """Build the items editor panel."""
        root_frame = tk.Frame(parent)
        self._active_module.panel = root_frame
        main = tk.PanedWindow(root_frame, orient='horizontal',
                               sashrelief='raised', sashwidth=4)
        main.pack(expand=1, fill='both')
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
        self._items_apply_btn = tk.Button(bf, text=u"\u5e94\u7528\u4fee\u6539", command=self._apply_items_detail,
                                            width=10, bg='#FF9800', fg='white')
        self._items_apply_btn.pack(side='right', padx=2)
        self._items_save_btn = tk.Button(bf, text=u"\u4fdd  \u5b58", command=self._save_items, width=8,
                                          bg='#4CAF50', fg='white')
        self._items_save_btn.pack(side='right', padx=2)

        # Right panel
        right = tk.Frame(main)
        main.add(right, minsize=320)

        def _fit_item_panes(_event=None):
            try:
                if self._is_ui_frozen():
                    return
                total = main.winfo_width()
                if total <= 1:
                    return
                left_pref = 300
                left_min = 220
                right_min = 460
                target = total - right_min
                if target < left_min:
                    target = left_min
                if target > left_pref:
                    target = left_pref
                if total - target < left_min:
                    target = max(left_min, total - left_min)
                main.sash_place(0, target, 1)
            except Exception:
                pass

        main.bind('<ButtonRelease-1>', _fit_item_panes)
        root_frame.after_idle(_fit_item_panes)

        self.items_detail_title = tk.Label(right, text=u"\u8bf7\u9009\u62e9\u4e00\u4e2a\u7269\u54c1",
                                           font=('', 12, 'bold'), anchor='w', fg='#333', cursor='hand2')
        self.items_detail_title.pack(fill='x', pady=(0, 5))
        self.items_detail_title.bind('<Double-Button-1>', self._copy_title_id)

        # Tab buttons for items
        itbf = tk.Frame(right)
        itbf.pack(fill='x')
        self._items_tab_btns = {}
        self._items_tab_frames = {}
        for key, label in [('info', u'\u57fa\u672c\u4fe1\u606f'), ('detail', u'\u7269\u54c1\u8be6\u60c5'), ('raw', u'\u6e90\u7801')]:
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

        # Items detail canvas (scrollable form)
        self._build_item_detail_panel(self._items_tab_frames['detail'])

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

    def _build_item_detail_panel(self, parent):
        """Build scrollable item detail form using MVC Section Controllers."""
        # Put the title outside the scroller for a stable header like troop detail.
        title_bar = tk.Frame(parent)
        title_bar.pack(fill='x', padx=3, pady=(0, 4))
        tk.Label(title_bar, text=u'物品详情', font=('', 10, 'bold')).pack(side='left')

        # Wrap canvas + scrollbar in a frame so the scrollbar has right padding
        wrap = tk.Frame(parent)
        wrap.pack(fill='both', expand=1)
        canvas = tk.Canvas(wrap, highlightthickness=0)
        vsb = tk.Scrollbar(wrap, orient='vertical', command=canvas.yview, width=18)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side='right', fill='y', padx=(2, 4))
        canvas.pack(side='left', expand=1, fill='both')
        self._item_detail_canvas = canvas

        f = tk.Frame(canvas)
        canvas.create_window((0, 0), window=f, anchor='nw', tags='inner')
        canvas.bind('<MouseWheel>', lambda e: self._on_global_wheel(e))
        f.bind('<MouseWheel>', lambda e: self._on_global_wheel(e))
        # Debounced scrollregion update (only when content actually changes, not every pixel)
        def _items_detail_on_config(event):
            if self._is_ui_frozen():
                return
            w = event.width
            h = event.height
            if getattr(canvas, '_last_items_detail_size', None) == (w, h):
                return
            canvas._last_items_detail_size = (w, h)
            if getattr(canvas, '_scroll_after_id', None):
                try:
                    canvas.after_cancel(canvas._scroll_after_id)
                except Exception:
                    pass
            canvas._scroll_after_id = canvas.after_idle(lambda c=canvas: (
                setattr(c, '_scroll_after_id', None),
                c.configure(scrollregion=c.bbox('all'))
            ))

        f.bind('<Configure>', _items_detail_on_config)

        # Build MVC sections (item_sections.py)
        if build_all_sections is not None:
            self.item_sections = build_all_sections(self, f)
        else:
            self.item_sections = {}

        # cn_name trace → write back to item_cn
        basic = self.item_sections.get('basic')
        if basic and 'cn_name' in basic.fields:
            basic.fields['cn_name'].trace('w', self._on_cn_name_changed)

        # Initialize master scrollregion after all sections packed.
        # Without this, canvas.bbox('all') is (0,0,0,0) until something triggers it,
        # leaving huge empty gaps and a stuck scrollbar.
        def _init_scroll():
            try:
                canvas.configure(scrollregion=canvas.bbox('all'))
            except Exception:
                pass
        self._item_detail_canvas = canvas
        canvas.after_idle(_init_scroll)
        # Re-init after idle settles, when all geometry is final
        canvas.after(50, _init_scroll)
        canvas.after(250, _init_scroll)


    def _show_items_tab(self, key):
        self._items_tab_btns[self._current_items_tab].config(relief='raised')
        self._items_tab_frames[self._current_items_tab].pack_forget()
        self._items_tab_btns[key].config(relief='sunken')
        self._items_tab_frames[key].pack(side='top', expand=1, fill='both')
        self._current_items_tab = key
        if key == 'info' and hasattr(self, '_cached_items_info') and hasattr(self, '_items_info_text') and self._items_info_text:
            self._items_info_text.config(state='normal')
            self._items_info_text.delete('1.0', 'end')
            self._items_info_text.insert('1.0', self._cached_items_info)
            self._items_info_text.config(state='disabled')
        elif key == 'detail' and hasattr(self, '_cached_items_detail_fields'):
            try:
                self._populate_item_detail(list(self._cached_items_detail_fields))
            except Exception:
                pass
        elif key == 'raw' and hasattr(self, '_cached_items_raw'):
            self._items_raw_text.delete('1.0', 'end')
            self._items_raw_text.insert('1.0', self._cached_items_raw)
            self._items_raw_text.edit_reset()

    def _on_items_search(self, *args):
        self._populate_items_list(self.items_search_var.get())

    def _populate_items_list(self, filter_text=""):
        if not hasattr(self, 'items_lb'):
            return
        self._ensure_item_display_cache()
        self.items_lb.delete(0, 'end')
        self._items_list_index_map = []
        ft = filter_text.lower()
        batch = []
        batch_map = []
        for i, full_id, zh, display in getattr(self, '_item_display_cache', []):
            if ft and ft not in full_id.lower() and ft not in zh.lower():
                continue
            batch.append(display)
            batch_map.append(i)
            if len(batch) >= 200:
                self.items_lb.insert('end', *batch)
                self._items_list_index_map.extend(batch_map)
                batch = []
                batch_map = []
        if batch:
            self.items_lb.insert('end', *batch)
            self._items_list_index_map.extend(batch_map)

    def _on_items_select(self, event):
        sel = self.items_lb.curselection()
        if not sel:
            return
        vis_idx = sel[0]
        if hasattr(self, '_items_list_index_map') and vis_idx < len(self._items_list_index_map):
            self._show_items_detail(self._items_list_index_map[vis_idx])
        else:
            self._show_items_detail(vis_idx)

    def _on_items_dblclick(self, event):
        self._current_items_tab = 'info'
        self._show_items_tab('raw')

    def _show_items_detail(self, idx):
        if idx < 0 or idx >= len(self.items_entries):
            return
        flds = self.items_fields[idx] if idx < len(self.items_fields) else []
        iid = (flds[0].strip('"').strip("'") if flds else '')
        full_id = 'itm_' + iid if iid and not iid.startswith('itm_') else iid
        zh = _item_cn_lookup(self.item_cn, full_id, u'(\u65e0\u6c49\u5316)') if hasattr(self, 'item_cn') else u'(\u65e0\u6c49\u5316)'
        if not zh:
            zh = u'(\u65e0\u6c49\u5316)'

        self._current_item_idx = idx
        self._current_item_title_id = full_id
        self._cached_items_detail_fields = list(flds)
        self._cached_items_raw = self.items_entries[idx]
        self.items_detail_title.config(text=u'#%d  %s - %s' % (idx, full_id, zh))

        # Info tab: styled like troop info
        info = []
        info.append(u'\u2550' * 60)
        info.append(u'  Slot: %d    ID: %s    \u4e2d\u6587\u540d: %s' % (idx, full_id, zh))
        info.append(u'\u2500' * 60)
        field_names = [
            u'ID(0)', u'\u540d\u79f0(1)', u'\u6a21\u578b(2)',
            u'\u7c7b\u578b\u6807\u8bb0(3)', u'\u80fd\u529b(4)', u'\u4ef7\u503c(5)',
            u'\u5c5e\u6027(6)', u'\u4fee\u9970\u7b26(7)', u'\u89e6\u53d1\u5668(8)',
            u'\u9635\u8425(9)'
        ]
        for fi, fv in enumerate(flds):
            label = field_names[fi] if fi < len(field_names) else u'\u5b57\u6bb5%d' % (fi + 1)
            info.append(u'  %s: %s' % (label, fv))
        info.append(u'\u2550' * 60)

        # Only build info text when viewing info tab; cache for later
        self._cached_items_info = '\n'.join(info)
        if getattr(self, '_current_items_tab', 'detail') == 'info':
            self._items_info_text.config(state='normal')
            self._items_info_text.delete('1.0', 'end')
            self._items_info_text.insert('1.0', self._cached_items_info)
            self._items_info_text.config(state='disabled')

        # Detail tab: populate form fields only when visible
        if getattr(self, '_current_items_tab', 'detail') == 'detail' and hasattr(self, 'item_sections') and self.item_sections:
            self._populate_item_detail(flds)

        if getattr(self, '_current_items_tab', 'detail') == 'raw':
            self._items_raw_text.delete('1.0', 'end')
            self._items_raw_text.insert('1.0', self.items_entries[idx])
            self._items_raw_text.edit_reset()

    # ═══════════════════════════════════════════════
    # Item Detail — MVC Section Controllers
    # All bidirectional sync is handled by item_sections.py
    # The old raw_var/guard/on_*_toggle methods are replaced.
    # ═══════════════════════════════════════════════

    def _populate_item_detail(self, flds):
        """Populate item detail form from parsed fields via MVC sections."""
        if not hasattr(self, 'item_sections') or not self.item_sections:
            return
        while len(flds) < 10:
            flds.append('')

        # S0: Basic (F0, F1, F5)
        basic = self.item_sections.get('basic')
        if basic:
            f0_raw = flds[0].strip('"\u2019\u2018').strip() if flds[0] else ''
            f1_raw = flds[1].strip('"\u2019\u2018').strip() if flds[1] else ''
            f5_raw = flds[5].strip() if len(flds) > 5 and flds[5] else '0'
            basic.populate(u'id="%s"  name="%s"  value=%s' % (f0_raw, f1_raw, f5_raw))
            # Chinese name
            iid = flds[0].strip('"').strip("'") if flds[0] else ''
            full_id = 'itm_' + iid if iid and not iid.startswith('itm_') else iid
            basic.populate_chinese(full_id)

        # S2: Mesh (F2)
        mesh = self.item_sections.get('mesh')
        if mesh:
            mesh.populate(flds[2] if len(flds) > 2 else '[]')

        # S3: Type Flags (F3)
        tf = self.item_sections.get('type_flags')
        if tf:
            tf.populate(flds[3] if len(flds) > 3 else '0')

        # S4: Capabilities (F4)
        cap = self.item_sections.get('capabilities')
        if cap:
            cap.populate(flds[4] if len(flds) > 4 else '0')

        # S5: Other Flags (F3 same field)
        of = self.item_sections.get('other_flags')
        if of:
            of.populate(flds[3] if len(flds) > 3 else '0')

        # S6: Stats (F6)
        stats = self.item_sections.get('stats')
        if stats:
            stats.populate(flds[6] if len(flds) > 6 else '0')

        # S7: Modifier (F7)
        mod = self.item_sections.get('modifier')
        if mod:
            mod.populate(flds[7] if len(flds) > 7 else 'imodbits_none')

        # S8: Triggers (F8) / Factions (F9)
        trig = self.item_sections.get('triggers')
        if trig:
            f8 = flds[8] if len(flds) > 8 else '[]'
            f9 = flds[9] if len(flds) > 9 else '[]'
            trig.populate_triggers(f8, f9)
            self._item_faction_combo = getattr(trig, '_faction_combo', None)





        # Update scrollregion after content rebuild
        if hasattr(self, '_items_detail_canvas') and self._items_detail_canvas:
            self._items_detail_canvas.after_idle(lambda c=self._items_detail_canvas: c.configure(scrollregion=c.bbox('all')))

    def _on_cn_name_changed(self, *args):
        """When user edits cn_name field, write back to item_cn."""
        basic = self.item_sections.get('basic') if hasattr(self, 'item_sections') else None
        if not basic:
            return
        new_cn = basic.fields.get('cn_name')
        if new_cn is None:
            return
        new_val = new_cn.get().strip()
        id_var = basic.fields.get('id')
        if id_var:
            raw_id = id_var.get().strip()
            full_id = 'itm_' + raw_id if raw_id and not raw_id.startswith('itm_') else raw_id
            if full_id and hasattr(self, 'item_cn'):
                if new_val:
                    self.item_cn[full_id] = new_val
                elif full_id in self.item_cn:
                    del self.item_cn[full_id]
                self._set_status(u'\u2713 \u6c49\u5316\u5df2\u66f4\u65b0: ' + (new_val or u'(\u5df2\u6e05\u9664)'))
                # Refresh cached display and visible list inline instead of full rebuild
                if hasattr(self, '_item_display_cache'):
                    for ci, (real_idx, cached_id, cached_zh, cached_display) in enumerate(self._item_display_cache):
                        if cached_id == full_id:
                            display = u"Slot %-3d %s" % (real_idx, cached_id)
                            if new_val:
                                display += u"  |  " + new_val
                            self._item_display_cache[ci] = (real_idx, cached_id, new_val, display)
                            break
                if hasattr(self, '_populate_items_list') and hasattr(self, '_items_list_index_map') and hasattr(self, 'items_lb'):
                    # Update the line for this item
                    new_zh = new_val or ''
                    for vi, real_idx in enumerate(self._items_list_index_map):
                        pflds = self.items_fields[real_idx] if real_idx < len(self.items_fields) else []
                        piid = pflds[0].strip('"').strip("'") if pflds else ''
                        pfid = 'itm_' + piid if piid and not piid.startswith('itm_') else piid
                        if pfid == full_id:
                            display = u"Slot %-3d %s" % (real_idx, pfid)
                            if new_zh:
                                display += u"  |  " + new_zh
                            self.items_lb.delete(vi)
                            self.items_lb.insert(vi, display)
                            break
                # Refresh title
                if hasattr(self, 'items_detail_title') and self._current_item_idx >= 0:
                    zh = _item_cn_lookup(self.item_cn, full_id, u'(\u65e0\u6c49\u5316)')
                    if not zh:
                        zh = u'(\u65e0\u6c49\u5316)'
                    self.items_detail_title.config(text=u'#%d  %s - %s' % (self._current_item_idx, full_id, zh))

    def _clear_items_detail(self):
        self._current_item_title_id = ''
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
        new_raw = '  ["new_item","New Item", [("new_mesh",0)], itp_type_one_handed_wpn, 0, 100, weight(1.5)|difficulty(0)|spd_rtng(95)|weapon_length(100)|swing_damage(20, cut)|thrust_damage(0, pierce), imodbits_none, []],\n'
        self.items_entries.append(new_raw)
        self.items_fields.append(parse_fields_in_entry(new_raw))
        self._rebuild_item_display_cache()
        self._populate_items_list()
        self.items_lb.selection_clear(0, 'end')
        self.items_lb.selection_set('end')
        self.items_lb.see('end')
        self._show_items_detail(len(self.items_entries) - 1)

    def _copy_item(self):
        sel = self.items_lb.curselection()
        if not sel:
            return
        idx = self._items_list_index_map[sel[0]] if hasattr(self, '_items_list_index_map') and sel[0] < len(self._items_list_index_map) else sel[0]
        self._push_items_undo()
        new_entry = self.items_entries[idx]
        self.items_entries.insert(idx + 1, new_entry)
        self.items_fields.insert(idx + 1, parse_fields_in_entry(new_entry))
        self._rebuild_item_display_cache()
        self._populate_items_list()

    def _delete_item(self):
        sel = self.items_lb.curselection()
        if not sel:
            return
        idx = self._items_list_index_map[sel[0]] if hasattr(self, '_items_list_index_map') and sel[0] < len(self._items_list_index_map) else sel[0]
        if not tkMessageBox.askyesno(u"\u786e\u8ba4", u"\u786e\u5b9a\u5220\u9664\u8be5\u7269\u54c1\uff1f"):
            return
        self._push_items_undo()
        del self.items_entries[idx]
        del self.items_fields[idx]
        self._rebuild_item_display_cache()
        self._populate_items_list()
        self._clear_items_detail()

    def _move_item_up(self):
        sel = self.items_lb.curselection()
        if not sel:
            return
        idx = self._items_list_index_map[sel[0]] if hasattr(self, '_items_list_index_map') and sel[0] < len(self._items_list_index_map) else sel[0]
        if idx == 0:
            return
        self._push_items_undo()
        self.items_entries[idx], self.items_entries[idx - 1] = self.items_entries[idx - 1], self.items_entries[idx]
        self.items_fields[idx], self.items_fields[idx - 1] = self.items_fields[idx - 1], self.items_fields[idx]
        self._rebuild_item_display_cache()
        self._populate_items_list()

    def _move_item_down(self):
        sel = self.items_lb.curselection()
        if not sel:
            return
        idx = self._items_list_index_map[sel[0]] if hasattr(self, '_items_list_index_map') and sel[0] < len(self._items_list_index_map) else sel[0]
        if idx >= len(self.items_entries) - 1:
            return
        self._push_items_undo()
        self.items_entries[idx], self.items_entries[idx + 1] = self.items_entries[idx + 1], self.items_entries[idx]
        self.items_fields[idx], self.items_fields[idx + 1] = self.items_fields[idx + 1], self.items_fields[idx]
        self._rebuild_item_display_cache()
        self._populate_items_list()

    def _push_items_undo(self):
        if not hasattr(self, 'items_entries'):
            return
        # shallow copy: strings are immutable, list copy is enough
        snap = (list(self.items_entries), list(self.items_fields))
        self._undo_stack.append(('items', snap))
        self._redo_stack[:] = []
        if len(self._undo_stack) > self._undo_max:
            self._undo_stack.pop(0)

    def _apply_items_detail(self):
        """Apply structured detail panel edits back to items_entries[idx] via MVC sections."""
        sel = self.items_lb.curselection()
        if not sel:
            tkMessageBox.showwarning(u"\u63d0\u793a", u"\u8bf7\u5148\u9009\u62e9\u4e00\u4e2a\u7269\u54c1")
            return
        idx = self._items_list_index_map[sel[0]] if hasattr(self, '_items_list_index_map') and sel[0] < len(self._items_list_index_map) else sel[0]
        if idx < 0 or idx >= len(self.items_entries):
            tkMessageBox.showwarning(u"\u63d0\u793a", u"\u7d22\u5f15\u65e0\u6548")
            return
        self._push_items_undo()

        # Get current fields
        flds = self.items_fields[idx] if hasattr(self, 'items_fields') and idx < len(self.items_fields) else parse_fields_in_entry(self.items_entries[idx])
        while len(flds) < 10:
            flds.append('')

        sections = getattr(self, 'item_sections', {})

        # F0: id (from BasicSection)
        basic = sections.get('basic')
        if basic and 'id' in basic.fields:
            raw_id = basic.fields['id'].get().strip()
            if raw_id and not raw_id.startswith('itm_'):
                raw_id = 'itm_' + raw_id
            flds[0] = raw_id if raw_id else flds[0]

        # F1: name
        if basic and 'name' in basic.fields:
            flds[1] = basic.fields['name'].get().strip() or flds[1]

        # F2: mesh (read-only, keep original)

        # F3: type flags — merge type_flags + other_flags sections
        parts_f3 = []
        tf = sections.get('type_flags')
        if tf:
            parts_f3.extend(n for n, var in tf.fields.items() if var.get())
        of = sections.get('other_flags')
        if of:
            parts_f3.extend(n for n, var in of.fields.items() if var.get())
        flds[3] = ' | '.join(parts_f3) if parts_f3 else '0'

        # F4: capabilities
        cap = sections.get('capabilities')
        if cap:
            flds[4] = cap.get_raw() or '0'

        # F5: value
        if basic and 'value' in basic.fields:
            flds[5] = basic.fields['value'].get().strip() or '0'

        # F6: stats
        stats = sections.get('stats')
        if stats:
            flds[6] = stats.get_raw() or '0'

        # F7: modifier
        mod = sections.get('modifier')
        if mod and 'modifier' in mod.fields:
            flds[7] = mod.fields['modifier'].get().strip() or 'imodbits_none'

        # F8 triggers / F9 factions
        trig = sections.get('triggers')
        if trig and 'triggers' in trig.fields:
            t = trig.fields['triggers'].get().strip()
            flds[8] = t if t else '[]'
        if trig and 'factions' in trig.fields:
            f = trig._get_faction_raw().strip() if hasattr(trig, '_get_faction_raw') else trig.fields['factions'].get().strip()
            flds[9] = f if f else '[]'

        # Store cn_name
        if basic and 'cn_name' in basic.fields:
            cn = basic.fields['cn_name'].get().strip()
            iid = flds[0].strip('"').strip("'")
            full_id = 'itm_' + iid if iid and not iid.startswith('itm_') else iid
            if hasattr(self, 'item_cn') and full_id:
                if cn:
                    self.item_cn[full_id] = cn
                elif full_id in self.item_cn:
                    del self.item_cn[full_id]

        # Rebuild raw entry
        self.items_entries[idx] = '  [' + ', '.join(flds) + '],\n'
        self.items_fields[idx] = flds
        self._rebuild_item_display_cache()
        self._populate_items_list()
        self.status.config(text=u"\u7269\u54c1\u8be6\u60c5\u5df2\u5e94\u7528 (\u672a\u4fdd\u5b58\u5230\u6587\u4ef6)")

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

    def _reload(self):
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

    def _load_data(self):
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
                    if flds and len(flds[0]) >= 2 and flds[0][0] in '"\'':
                        iid_raw = flds[0].strip('"').strip("'")
                        full_id = 'itm_' + iid_raw if not iid_raw.startswith('itm_') else iid_raw
                        item_name = flds[1].strip('"').strip("'") if len(flds) > 1 else ''
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
            # Quick scan: find the first itp_type_ mention instead of full regex
            a = raw.find('itp_type_')
            if a < 0:
                self.item_category[it['id']] = 'other'
            else:
                end = raw.find(',', a)
                if end < 0:
                    end = raw.find('|', a)
                if end < 0:
                    end = raw.find(' ', a)
                seg = raw[a:end] if end > a else raw[a:a+30]
                if any(t in seg for t in _ARMOR_TYPES):
                    self.item_category[it['id']] = 'armor'
                elif any(t in seg for t in _WEAPON_TYPES):
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
                    fac_list_match = re.search(r'factions\s*=\s*\[(.*?)\](?=\s*$|\s*\n\s*#|\s*\n\s*\Z)', fac_text, re.DOTALL)
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
                    for m in re.finditer(r'\(\s*"([^"]+)"\s*,\s*"([^"]*)"', pparts):
                        fid = m.group(1)
                        fname = m.group(2).replace('{!}', '')
                        cn = self.faction_cn.get('fac_' + fid, '')
                        self.faction_data.append(('fac_' + fid, fname, cn))
                except:
                    pass

        # Build item display list
        self.item_list = []
        for it in self.items:
            zh = _item_display_name(self.item_cn, self.item_lookup, it['id'], it.get('name', ''))
            self.item_list.append((it['id'], zh))
        self._rebuild_item_display_cache()

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
        # Parse modifier bit definitions from header_item_modifiers.py
        # and imodbits preset constants from module_items.py header.
        self._parse_modifiers_header(ip)

        # Populate items list
        self._populate_items_list()
        self._clear_items_detail()
        self._set_items_ui_state(len(self.items_entries) > 0)
        self.status.config(text=u"\u2705 \u5df2\u52a0\u8f7d: %s | \u7269\u54c1: %d" % (
            os.path.basename(self.mod_path), len(self.items_entries)))

    def _rebuild_item_display_cache(self):
        """Build lightweight cached display/search strings for item list rendering."""
        self._item_display_cache = []
        self._item_search_cache = []
        item_cn = getattr(self, 'item_cn', {})
        item_lookup = getattr(self, 'item_lookup', {})
        for i, flds in enumerate(self.items_fields if hasattr(self, 'items_fields') else []):
            iid = (flds[0].strip('"').strip("'") if flds else '')
            full_id = 'itm_' + iid if iid and not iid.startswith('itm_') else iid
            zh = _item_display_name(item_cn, item_lookup, full_id, '')
            display = u"Slot %-3d %s" % (i, full_id)
            if zh:
                display += u"  |  " + zh
            self._item_display_cache.append((i, full_id, zh, display))
            self._item_search_cache.append((full_id.lower(), zh.lower(), display))

    def _ensure_item_display_cache(self):
        if not hasattr(self, '_item_display_cache') or len(getattr(self, '_item_display_cache', [])) != len(getattr(self, 'items_entries', [])):
            self._rebuild_item_display_cache()

    def _parse_modifiers_header(self, items_path):
        """Parse imodbit_xxx definitions from header_item_modifiers.py and
        imodbits_xxx preset constants from module_items.py header.

        Stores:
            self.imodbit_defs: ordered list of {'name', 'value', 'label'}
            self.imodbit_constants: {imodbit_name: int}
            self.imodbits_constants: {imodbits_name: resolved_int_value}
        """
        import re as _re
        self.imodbit_defs = []
        self.imodbit_constants = {}
        self.imodbits_constants = {}
        self.imodbits_expansions = {}
        mod_dir = os.path.dirname(items_path)
        header_files = [
            os.path.join(mod_dir, 'header_item_modifiers.py'),
            os.path.join(mod_dir, 'header files', 'header_item_modifiers.py'),
        ]
        try:
            with codecs.open(items_path, 'r', 'utf-8', errors='replace') as f:
                header_text = f.read()
        except Exception:
            return
        # Parse modifier bit file first if present.
        mod_bits_path = None
        for candidate in header_files:
            if os.path.isfile(candidate):
                mod_bits_path = candidate
                break
        if mod_bits_path:
            try:
                with codecs.open(mod_bits_path, 'r', 'utf-8', errors='replace') as f:
                    mod_text = f.read()
                for m in _re.finditer(r'^(imodbit_\w+)\s*=\s*(0x[0-9a-fA-F]+|\d+)', mod_text, _re.MULTILINE):
                    name = m.group(1)
                    raw_val = m.group(2)
                    val = int(raw_val, 16) if raw_val.lower().startswith('0x') else int(raw_val)
                    self.imodbit_constants[name] = val
                    self.imodbit_defs.append({'name': name, 'value': val, 'label': name})
            except Exception:
                pass
        # Parse imodbits_xxx = expr from module_items.py header.
        raw_bits = dict(self.imodbit_constants)
        imodbits_raw = {}
        for m in _re.finditer(r'^(imodbits_\w+)\s*=\s*(.+?)(?:\s*#.*)?$', header_text, _re.MULTILINE):
            imodbits_raw[m.group(1)] = m.group(2).strip()
        # Resolve with iterative expansion (max 10 passes for nested refs)
        for _ in range(10):
            changed = False
            for name, expr in imodbits_raw.items():
                if name in self.imodbits_constants:
                    continue
                resolved = expr
                unresolved = False
                for dep_name in _re.findall(r'\b(imod(?:bit|bits)_\w+)\b', expr):
                    if dep_name in self.imodbits_constants:
                        resolved = resolved.replace(dep_name, str(self.imodbits_constants[dep_name]))
                    elif dep_name in raw_bits:
                        resolved = resolved.replace(dep_name, str(raw_bits[dep_name]))
                    elif dep_name == name:
                        continue  # self-ref=0
                    else:
                        unresolved = True
                        break
                if not unresolved:
                    try:
                        val = eval(resolved, {'__builtins__': {}}, {})
                        self.imodbits_constants[name] = int(val)
                        self.imodbits_expansions[name] = sorted(set(_re.findall(r'\bimodbit_\w+\b', expr)))
                        changed = True
                    except Exception:
                        pass
            if not changed:
                break
        # Also resolve imodbits_none = 0 (explicit)
        self.imodbits_constants['imodbits_none'] = 0
        # Build a readable alias map for the preset groups.
        self.imodbits_labels = {}
        for name in sorted(self.imodbits_constants.keys()):
            if name == 'imodbits_none':
                continue
            pretty = self._pretty_imodbits_label(name)
            self.imodbits_labels[name] = pretty

    def _pretty_imodbits_label(self, name):
        mapping = {
            'imodbits_horse_basic': u'\u9a6c\u5339\u57fa\u7840',
            'imodbits_cloth': u'\u8863\u670d',
            'imodbits_armor': u'\u7532\u80f6',
            'imodbits_plate': u'\u677f\u7532',
            'imodbits_polearm': u'\u957f\u6746',
            'imodbits_shield': u'\u76fe',
            'imodbits_sword': u'\u5251',
            'imodbits_sword_high': u'\u9ad8\u7ea7\u5251',
            'imodbits_axe': u'\u65a7',
            'imodbits_mace': u'\u9524',
            'imodbits_pick': u'\u9504\u5934',
            'imodbits_bow': u'\u5f13',
            'imodbits_crossbow': u'\u5f31\u5f13',
            'imodbits_missile': u'\u6295\u63b7\u88c5\u5907',
            'imodbits_thrown': u'\u6295\u63b7',
            'imodbits_thrown_minus_heavy': u'\u8f7b\u578b\u6295\u63b7',
            'imodbits_horse_good': u'\u826f\u9a6c',
            'imodbits_good': u'\u7cbe\u826f',
            'imodbits_bad': u'\u4f4e\u8d28',
        }
        return mapping.get(name, name.replace('imodbits_', '').replace('_', ' '))

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
            display = u"Slot %-3d %s" % (i, full_id)
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
            if self._current_tab != 'detail':
                self._show_tab('detail')
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

        self._current_troop_title_id = full_id
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
        self._current_troop_title_id = ''
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
            zh = _item_cn_lookup(self.item_cn, iid, '') or (self.item_lookup.get(iid, {}) or {}).get('name', '')
            self.eq_lb.insert(tk.END, u'Slot %-2d  %s | %s' % (i, iid, zh))

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
                zh = _item_cn_lookup(self.item_cn, iid, '') or (self.item_lookup.get(iid, {}) or {}).get('name', '')
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
                zh = _item_cn_lookup(self.item_cn, iid, '') or (self.item_lookup.get(iid, {}) or {}).get('name', '')
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

    def _save_current_module(self, event=None):
        """Save current module (Ctrl+S dispatch)."""
        if self._current_module == 'troops':
            self._save_troops()
        elif self._current_module == 'items':
            self._save_items()
        else:
            pass  # no module loaded yet

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
        widget_names = ['troop_lb', 'eq_lb', '_info_text', '_raw_text',
                        'status', '_count_lbl', 'detail_title']
        widgets = []
        for name in widget_names:
            w = getattr(self, name, None)
            if w is not None:
                widgets.append(w)
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

    def _show_debug_console(self):
        """Show runtime log content inside the app."""
        dlg = tk.Toplevel(self.root)
        dlg.title(u"调试日志")
        dlg.geometry("900x520")
        dlg.transient(self.root)

        top = tk.Frame(dlg)
        top.pack(fill='x', padx=6, pady=4)
        tk.Label(top, text=u"日志文件:").pack(side='left')
        path_var = tk.StringVar(value=getattr(self, '_debug_log_path', ''))
        tk.Entry(top, textvariable=path_var, state='readonly').pack(side='left', fill='x', expand=1, padx=6)

        body = tk.Frame(dlg)
        body.pack(fill='both', expand=1, padx=6, pady=6)
        sb = tk.Scrollbar(body)
        sb.pack(side='right', fill='y')
        text = tk.Text(body, font=('Consolas', 10), wrap='none', yscrollcommand=sb.set)
        text.pack(side='left', fill='both', expand=1)
        sb.config(command=text.yview)

        def refresh():
            text.config(state='normal')
            text.delete('1.0', 'end')
            p = getattr(self, '_debug_log_path', '')
            if p and os.path.isfile(p):
                try:
                    with codecs.open(p, 'r', 'utf-8', errors='replace') as f:
                        text.insert('1.0', f.read())
                except Exception as e:
                    text.insert('1.0', unicode(e))
            else:
                text.insert('1.0', u'暂无日志。请先触发一次报错或运行输出。')
            text.config(state='disabled')

        tk.Button(top, text=u"刷新", width=10, command=refresh).pack(side='right')
        refresh()
        dlg.after(1500, refresh)

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
        if self.mod_path and self.troops_entries:
            if tkMessageBox.askyesno(u"退出", u"退出前是否保存修改?"):
                self._save_troops()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    app = TianyouEditor()
    app.run()
