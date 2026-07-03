# -*- coding: utf-8 -*-
"""
item_sections.py — MVC Section Controllers for Item Detail Form

Architecture:
  - SectionController (base) → build / populate / guard / bidirectional sync
  - Each F0-F9 section is a subclass with its own parse/rebuild logic
  - Two-way sync: raw_var ← trace → parse → fields; field changes → rebuild → raw_var
  - Guard flag prevents recursion

Shared conventions:
  - _guard: bool, set True during programmatic changes to skip trace callbacks
  - raw_var: tk.StringVar, source expression (source of truth)
  - fields: dict str→tk.StringVar/IntVar, derived UI widgets
  - populate(raw_expr): external entry point, sets raw_var + syncs fields
  - on_raw_change(): raw Entry edited → parse, sync fields
  - on_field_change(field_name=None): field edited → rebuild raw → set raw_var (guard on)
"""

import re as _re
import os as _os
try:
    import Tkinter as tk
    import ttk
except ImportError:
    import tkinter as tk
    from tkinter import ttk

try:
    from flag_dict import (ITP_TYPE_FLAGS, ITP_OTHER_FLAGS, ITC_TEMPLATES,
                           ITC_TEMPLATE_LABELS, ITC_TEMPLATE_EXPANSIONS,
                           ITCF_FLAGS)
except Exception:
    ITP_TYPE_FLAGS = []
    ITP_OTHER_FLAGS = []
    ITC_TEMPLATES = []
    ITC_TEMPLATE_LABELS = {}
    ITC_TEMPLATE_EXPANSIONS = {}
    ITCF_FLAGS = []


# ============================================================
#  Base Section Controller
# ============================================================

class SectionController(object):
    """Base class for item detail sections with bidirectional sync."""

    def __init__(self, owner):
        """
        Args:
            owner: ItemModule instance (for accessing item_cn, imodbits_constants, etc.)
        """
        self.owner = owner
        self.raw_var = tk.StringVar(value='')
        self.fields = {}          # str -> StringVar | IntVar
        self._guard = False       # recursion guard for trace callbacks
        self._widget = None       # root LabelFrame after build()

    # ---------- override points ----------

    def parse_raw(self, raw):
        """Parse raw expression → dict of field values. Must be overridden."""
        raise NotImplementedError

    def rebuild_raw(self):
        """Rebuild raw expression from current field values. Must be overridden."""
        raise NotImplementedError

    def build_ui(self, parent):
        """Build UI widgets inside a LabelFrame, return the LabelFrame.
        Must be overridden. Call _make_raw_row() for source expression."""
        raise NotImplementedError

    def populate_fields(self, parsed):
        """Write parsed dict into self.fields widgets. Override for complex types."""
        for key, var in self.fields.items():
            if isinstance(var, tk.IntVar):
                var.set(1 if parsed.get(key) else 0)
            else:
                var.set(str(parsed.get(key, '')))

    def rebuild_from_fields(self):
        """Called by on_field_change. Default: rebuild + set raw_var.
        Override if multiple fields contribute to one raw expression."""
        self.raw_var.set(self.rebuild_raw())

    # ---------- built-in helpers ----------

    def _make_raw_row(self, parent, label=u'\u6e90\u8868\u8fbe\u5f0f:', readonly=False):
        """Create source expression Entry row. Called by build_ui()."""
        fr = tk.Frame(parent)
        fr.pack(fill='x', padx=5, pady=2)
        tk.Label(fr, text=label, width=10, anchor='w').pack(side='left')
        state = 'readonly' if readonly else 'normal'
        self.raw_var.trace('w', lambda *a: self.on_raw_change())
        tk.Entry(fr, textvariable=self.raw_var,
                 font=('Consolas', 9), width=80, state=state).pack(
                     side='left', padx=(5, 0), fill='x', expand=1)
        return fr

    def _make_label_frame(self, parent, title):
        lf = tk.LabelFrame(parent, text=title, font=('', 10, 'bold'))
        lf.pack(fill='x', padx=5, pady=3)
        return lf

    def _add_entry_row(self, parent, label_text, var_name, row, col=0, width=45):
        """Add label + Entry, store var in self.fields[var_name]."""
        tk.Label(parent, text=label_text + ':', anchor='e', width=16).grid(
            row=row, column=col, sticky='e', padx=(5, 2), pady=2)
        var = tk.StringVar()
        tk.Entry(parent, textvariable=var, width=width).grid(
            row=row, column=col + 1, sticky='w', padx=2, pady=2)
        self.fields[var_name] = var
        return var

    def _add_intvar_row(self, parent, label_text, var_name, row, col=0):
        """Add label + disabled Entry (for display), store IntVar in self.fields."""
        tk.Label(parent, text=label_text + ':', anchor='e', width=16).grid(
            row=row, column=col, sticky='e', padx=(5, 2), pady=2)
        var = tk.IntVar()
        ent = tk.Entry(parent, textvariable=var, width=20, state='readonly')
        ent.grid(row=row, column=col + 1, sticky='w', padx=2, pady=2)
        self.fields[var_name] = var
        return var

    def _make_checkbuttons_grid(self, parent, items, columns=6):
        """
        Items: list of (bit_hex, label_text, primary_flag_name)
        Returns dict: flag_name → IntVar
        """
        cb_vars = {}
        frm = tk.Frame(parent)
        frm.pack(fill='x', padx=5, pady=2)
        for i, (bit_hex, lbl, pname) in enumerate(items):
            var = tk.IntVar()
            # Closure-safe: capture pname by default arg
            cb = tk.Checkbutton(frm, text=lbl, variable=var,
                                command=lambda n=pname: self.on_field_change(n))
            cb.grid(row=i // columns, column=i % columns, sticky='w', padx=3, pady=1)
            cb_vars[pname] = var
        return cb_vars

    # ---------- sync methods ----------

    def on_raw_change(self):
        """Called when raw_var is edited. Parse → populate fields."""
        if self._guard:
            return
        raw = self.raw_var.get().strip()
        if not raw:
            raw = '0'
        self._guard = True
        try:
            self.populate_fields(self.parse_raw(raw))
        finally:
            self._guard = False

    def on_field_change(self, trigger_name=None):
        """Called when any field/checkbox changes. Rebuild → set raw_var."""
        if self._guard:
            return
        self._guard = True
        try:
            self.rebuild_from_fields()
        finally:
            self._guard = False

    # ---------- public API ----------

    def populate(self, raw_expr):
        """External entry point: set raw expression + sync all fields."""
        raw = raw_expr.strip() if raw_expr else '0'
        self._guard = True
        try:
            self.raw_var.set(raw)
        finally:
            self._guard = False
        self.on_raw_change()

    def build(self, parent):
        """Build UI, return root LabelFrame."""
        self.build_ui(parent)
        return self._widget

    def get_raw(self):
        """Return current raw expression string."""
        return self.raw_var.get().strip()

    def clean_up(self):
        """Remove all traces to prevent memory leaks."""
        pass  # No explicit cleanup needed—garbage collected when owner dies


# ============================================================
#  S0: Basic Info  (F0 ID, F1 Name, Chinese Name, F5 Value)
# ============================================================

class BasicSection(SectionController):
    """id="xxx"  name="xxx"  value=xxx"""

    def parse_raw(self, raw):
        out = {'id': '', 'name': '', 'value': '0'}
        m = _re.search(r'''id\s*=\s*["']([^"']*)["']''', raw)
        if m: out['id'] = m.group(1)
        m = _re.search(r'''name\s*=\s*["']([^"']*)["']''', raw)
        if m: out['name'] = m.group(1)
        m = _re.search(r'value\s*=\s*(\S+)', raw)
        if m: out['value'] = m.group(1)
        return out

    def rebuild_raw(self):
        fid = self.fields['id'].get().strip()
        fname = self.fields['name'].get().strip()
        fval = self.fields['value'].get().strip() or '0'
        return u'id="%s"  name="%s"  value=%s' % (fid, fname, fval)

    def build_ui(self, parent):
        lf = self._make_label_frame(parent, u'F0 \u57fa\u672c\u5c5e\u6027 (Basic)')
        self._make_raw_row(lf)
        self._widget = lf
        # Use pure pack layout: rows stacked vertically, label + entry in one row
        for (lbl, name) in [
            (u'F0 ID', 'id'),
            (u'F1 \u540d\u79f0', 'name'),
            (u'     \u6c49\u5316\u540d\u79f0', 'cn_name'),
            (u'F5 \u4ef7\u503c (Value)', 'value'),
        ]:
            row = tk.Frame(lf)
            row.pack(fill='x', padx=5, pady=1)
            tk.Label(row, text=lbl + ':', anchor='e', width=18).pack(side='left')
            var = tk.StringVar()
            tk.Entry(row, textvariable=var, width=50).pack(side='left', fill='x', expand=1, padx=(2, 0))
            self.fields[name] = var
        # Trace field changes → on_field_change
        self.fields['id'].trace('w', lambda *a: self.on_field_change('id'))
        self.fields['name'].trace('w', lambda *a: self.on_field_change('name'))
        self.fields['value'].trace('w', lambda *a: self.on_field_change('value'))
        # cn_name trace goes to owner._on_cn_name_changed
        return lf

    def populate_chinese(self, full_id):
        """Set cn_name from item_cn dict."""
        cn = ''
        if hasattr(self.owner, 'item_cn'):
            lookup = getattr(self.owner, '_item_cn_lookup', None)
            if callable(lookup):
                cn = lookup(self.owner.item_cn, full_id, '')
            else:
                cn = self.owner.item_cn.get(full_id, '')
                if not cn and full_id:
                    fallback_id = full_id[4:] if full_id.startswith('itm_') else full_id
                    cn = self.owner.item_cn.get(fallback_id, '')
        self._guard = True
        try:
            self.fields['cn_name'].set(cn)
        finally:
            self._guard = False


# ============================================================
#  S2: Mesh  (F2: [("mesh_name", flag, "ixmesh_carry"), ...])
# ============================================================

class MeshSection(SectionController):
    """Source expression + N-row editable mesh list. Each mesh tuple:
        ("mesh_id", flag [, "ixmesh_carry"])
    Common forms:
        0 flag                  \u2014 main mesh (e.g. ("sword", 0))
        ixmesh_flying_ammo      \u2014 projectile flying mesh (arrows/bolts)
        ixmesh_carry            \u2014 carried/holstered mesh (quiver/sheath)
    """

    def parse_raw(self, raw):
        out = {'meshes': []}  # list of {id, flag, action}
        if not raw or raw == '[]' or not raw.startswith('['):
            return out
        inner = raw[1:-1].strip()
        idx = 0
        while idx < len(inner):
            # Per user spec: ("model_id", flag [, "ixmesh_*"])
            # flag is a word token (0, ixmesh_flying_ammo, ixmesh_carry, #x, etc.)
            # Optional 3rd token is action / ixmesh_carry
            m = _re.match(r'\s*\(\s*"([^"]*)"\s*,\s*([\w#]+)\s*(?:,\s*"([^"]*)")?\s*\)\s*', inner[idx:])
            if m:
                out['meshes'].append({
                    'id': m.group(1),
                    'flag': m.group(2),
                    'action': m.group(3) or '',
                })
                idx += m.end()
                if idx < len(inner) and inner[idx] == ',':
                    idx += 1
            else:
                break
        return out

    def rebuild_raw(self):
        # Rebuild from current mesh list vars (rebuild from fields)
        parts = []
        for row in self._mesh_rows:
            mid = row['id'].get().strip()
            if not mid:
                continue
            flag = row['flag'].get().strip() or '0'
            action = row['action'].get().strip()
            if action:
                parts.append('("%s", %s, "%s")' % (mid, flag, action))
            else:
                parts.append('("%s", %s)' % (mid, flag))
        raw = '[' + ','.join(parts) + ']'
        return raw

    def _rebuild_from_fields(self):
        if not hasattr(self, '_mesh_raw_var') or not hasattr(self, '_mesh_guard'):
            return
        self._mesh_guard = True
        try:
            self._mesh_raw_var.set(self.rebuild_raw())
        finally:
            self._mesh_guard = False

    def _on_mesh_row_change(self, *args):
        if getattr(self, '_mesh_guard', False):
            return
        self._rebuild_from_fields()

    def _add_mesh_row(self, mid='', flag='0', action=''):
        row_frame = tk.Frame(self._mesh_rows_frame)
        row_frame.pack(fill='x', padx=5, pady=1)
        idx = len(self._mesh_rows) + 1
        tk.Label(row_frame, text='#%d' % idx, width=4, anchor='e', fg='gray50').pack(side='left')
        # model id
        id_var = tk.StringVar(value=mid)
        id_var.trace('w', self._on_mesh_row_change)
        tk.Entry(row_frame, textvariable=id_var, width=28).pack(side='left', padx=2)
        # flag / ixmesh_*
        flag_var = tk.StringVar(value=flag)
        flag_var.trace('w', self._on_mesh_row_change)
        tk.Entry(row_frame, textvariable=flag_var, width=18).pack(side='left', padx=2)
        # action (optional)
        action_var = tk.StringVar(value=action)
        action_var.trace('w', self._on_mesh_row_change)
        tk.Entry(row_frame, textvariable=action_var, width=14).pack(side='left', padx=2)
        # delete button
        tk.Button(row_frame, text=u'\u5220', width=3,
                  command=lambda: self._del_mesh_row(row_frame)).pack(side='left', padx=2)
        self._mesh_rows.append({'id': id_var, 'flag': flag_var, 'action': action_var, 'frame': row_frame})

    def _del_mesh_row(self, row_frame):
        for i, r in enumerate(self._mesh_rows):
            if r['frame'] is row_frame:
                row_frame.destroy()
                self._mesh_rows.pop(i)
                # relabel remaining rows
                for j, r2 in enumerate(self._mesh_rows):
                    for child in r2['frame'].winfo_children():
                        if isinstance(child, tk.Label) and child.cget('text').startswith('#'):
                            child.config(text='#%d' % (j + 1))
                            break
                self._rebuild_from_fields()
                return

    def build_ui(self, parent):
        lf = self._make_label_frame(parent, u'F2 \u6a21\u578b (Meshes)')
        self._widget = lf
        # Source expression (editable, syncs with row edits)
        raw_row = tk.Frame(lf)
        raw_row.pack(fill='x', padx=5, pady=2)
        tk.Label(raw_row, text=u'\u6e90\u8868\u8fbe\u5f0f:', width=10, anchor='w').pack(side='left')
        self._mesh_raw_var = tk.StringVar(value='[]')
        self._mesh_guard = False
        self._mesh_raw_var.trace('w', lambda *_: self._on_raw_change())
        tk.Entry(raw_row, textvariable=self._mesh_raw_var,
                 font=('Consolas', 9)).pack(side='left', fill='x', expand=1, padx=(5, 0))
        # Column header
        hdr = tk.Frame(lf)
        hdr.pack(fill='x', padx=5, pady=(4, 0))
        tk.Label(hdr, text='No.', width=4, anchor='e', fg='gray50').pack(side='left')
        tk.Label(hdr, text=u'\u6a21\u578bID (model_id)', width=28, anchor='w').pack(side='left', padx=2)
        tk.Label(hdr, text=u'\u6a21\u578b\u4f4d (ixmesh_*)', width=18, anchor='w').pack(side='left', padx=2)
        tk.Label(hdr, text=u'\u52a8\u4f5c (\u9009)', width=14, anchor='w').pack(side='left', padx=2)
        tk.Label(hdr, text=u'\u52a0\u62b9', width=4, anchor='w').pack(side='left', padx=2)
        # Rows container
        self._mesh_rows_frame = tk.Frame(lf)
        self._mesh_rows_frame.pack(fill='x', padx=0, pady=0)
        self._mesh_rows = []  # list of dicts
        # Add button
        btn_row = tk.Frame(lf)
        btn_row.pack(fill='x', padx=5, pady=2)
        tk.Button(btn_row, text=u'+ \u6dfb\u52a0\u6a21\u578b',
                  command=lambda: self._add_mesh_row()).pack(side='left')
        return lf

    def _on_raw_change(self):
        if self._mesh_guard:
            return
        # Re-parse raw expression into rows
        meshes = self.parse_raw(self._mesh_raw_var.get()).get('meshes', [])
        # Clear existing rows
        for r in self._mesh_rows:
            r['frame'].destroy()
        self._mesh_rows = []
        for m in meshes:
            self._add_mesh_row(m['id'], m['flag'], m['action'])

    def populate(self, raw_expr):
        """Owner calls this with the F2 raw string, e.g. '[("arrow",0),("flying_missile",ixmesh_flying_ammo)]'."""
        if not hasattr(self, '_mesh_raw_var'):
            return
        raw = raw_expr or '[]'
        self._mesh_guard = True
        try:
            self._mesh_raw_var.set(raw)
        finally:
            self._mesh_guard = False
        # Build rows from raw
        self._on_raw_change()



# ============================================================
#  S3: Type Flags  (F3: itp_type_* bits < 0x1000)
# ============================================================

class TypeFlagsSection(SectionController):
    """Checkbuttons for 20 type flags, bidirectional with source expression."""

    def parse_raw(self, raw):
        return {flag: 1 for flag in raw.replace('|', ' ').split() if flag and flag != '0'}

    def rebuild_raw(self):
        parts = [n for n, var in self.fields.items() if var.get()]
        return ' | '.join(parts) if parts else '0'

    def build_ui(self, parent):
        lf = self._make_label_frame(parent, u'F3 \u7c7b\u578b\u6807\u8bb0 (Type Flags)')
        self._make_raw_row(lf)
        self._widget = lf
        self.fields = self._make_checkbuttons_grid(lf, ITP_TYPE_FLAGS, columns=6)
        return lf


# ============================================================
#  S4: Capabilities  (F4: itc_xxx | itcf_xxx | ...)
# ============================================================

class CapabilitiesSection(SectionController):
    """itc_ template checkbuttons + itcf_ flag checkbuttons, bidirectional."""

    def __init__(self, owner):
        SectionController.__init__(self, owner)
        self._template_implied_flags = set()

    def parse_raw(self, raw):
        return {t: 1 for t in raw.replace('|', ' ').split() if t and t != '0'}

    def rebuild_raw(self):
        parts = []
        for n in ITC_TEMPLATES:
            var = self.fields.get(n)
            if var is not None and var.get():
                parts.append(n)
        for _bit, _label, n in ITCF_FLAGS:
            var = self.fields.get(n)
            if var is not None and var.get() and n not in self._template_implied_flags:
                parts.append(n)
        return ' | '.join(parts) if parts else '0'

    def populate_fields(self, parsed):
        SectionController.populate_fields(self, parsed)
        self._sync_template_implied_flags()
        self._update_template_expansion()

    def on_field_change(self, trigger_name=None):
        if trigger_name in ITC_TEMPLATES:
            self._sync_template_implied_flags()
        elif trigger_name in self._template_implied_flags:
            self._sync_templates_from_flags()
        SectionController.on_field_change(self, trigger_name)
        self._update_template_expansion()

    def _selected_templates(self):
        return [n for n in ITC_TEMPLATES
                if self.fields.get(n) is not None and self.fields[n].get()]

    def _sync_template_implied_flags(self):
        implied = set()
        for tcn in self._selected_templates():
            implied.update(ITC_TEMPLATE_EXPANSIONS.get(tcn, []))
        self._template_implied_flags = implied
        old_guard = self._guard
        self._guard = True
        try:
            for name in implied:
                var = self.fields.get(name)
                if var is not None:
                    var.set(1)
        finally:
            self._guard = old_guard

    def _sync_templates_from_flags(self):
        """Drop a template when the user unchecks one of its implied flags."""
        old_guard = self._guard
        self._guard = True
        try:
            changed = False
            for tcn in ITC_TEMPLATES:
                tvar = self.fields.get(tcn)
                if tvar is None or not tvar.get():
                    continue
                for name in ITC_TEMPLATE_EXPANSIONS.get(tcn, []):
                    var = self.fields.get(name)
                    if var is not None and not var.get():
                        tvar.set(0)
                        changed = True
                        break
            if changed:
                self._sync_template_implied_flags()
        finally:
            self._guard = old_guard

    def _label_for_itcf(self, flag_name):
        for _bit, label, name in ITCF_FLAGS:
            if name == flag_name:
                return label
        return flag_name

    def _group_itcf_flags(self):
        """Group itcf_ flags by function. Order: horseback > carry > parry > shoot/throw/reload > melee-by-type > masks/other."""
        # Categories in display order
        c_melee_1h   = (u'\u5355\u624b\u51b2\u523a/\u65a9\u51fb (One-handed)', [])
        c_melee_2h   = (u'\u53cc\u624b\u51b2\u523a/\u65a9\u51fb (Two-handed)', [])
        c_polearm    = (u'\u957f\u67aa/\u957f\u6746 (Polearm/Spear/Pike)', [])
        c_shoot      = (u'\u5c04\u51fb (Shoot) \u4e0e \u88c5\u586b (Reload)', [])
        c_throw      = (u'\u6295\u63b7 (Throw)', [])
        c_horse      = (u'\u9a6c\u4e0a\u52a8\u4f5c (Horseback)', [])
        c_carry      = (u'\u643a\u5e26\u4f4d\u7f6e (Carry/Holster)', [])
        c_parry      = (u'\u683c\u6321 (Parry)', [])
        c_other      = (u'\u5176\u4ed6 (Masks / Special)', [])
        groups = [c_melee_1h, c_melee_2h, c_polearm, c_shoot, c_throw, c_horse, c_carry, c_parry, c_other]
        by_idx = {g[0]: g[1] for g in groups}

        for bit_hex, label, name in ITCF_FLAGS:
            # Skip mask constants (they're never toggled individually)
            if name in ('itcf_carry_mask', 'itcf_reload_mask', 'itcf_shoot_mask', 'itcf_force_64_bits'):
                by_idx[c_other[0]].append((name, label))
                continue
            item = (name, label)
            n = name
            # 1. Horseback: highest priority
            if n.startswith('itcf_horseback_'):
                by_idx[c_horse[0]].append(item)
            # 2. Carry
            elif n.startswith('itcf_carry_'):
                by_idx[c_carry[0]].append(item)
            # 3. Parry
            elif n.startswith('itcf_parry_'):
                by_idx[c_parry[0]].append(item)
            # 4. Throw
            elif n.startswith('itcf_throw_'):
                by_idx[c_throw[0]].append(item)
            # 5. Shoot / reload
            elif n.startswith('itcf_shoot_') or n.startswith('itcf_reload_'):
                by_idx[c_shoot[0]].append(item)
            # 6. Polearm-class (overswing_spear, thrust_polearm, etc.)
            elif ('polearm' in n) or ('spear' in n) or ('lance' in n) or n == 'itcf_horseback_slash_polearm' or 'musket' in n:
                by_idx[c_polearm[0]].append(item)
            # 7. Two-handed melee
            elif 'twohanded' in n:
                by_idx[c_melee_2h[0]].append(item)
            # 8. One-handed melee
            elif 'onehanded' in n:
                by_idx[c_melee_1h[0]].append(item)
            # 9. show_holster (cosmetic)
            elif 'show_holster' in n:
                by_idx[c_carry[0]].append(item)
            # 10. Fallback
            else:
                by_idx[c_other[0]].append(item)
        return [(title, items) for title, items in groups if items]

    def _update_template_expansion(self):
        text = getattr(self, '_template_expansion_text', None)
        if text is None:
            return
        lines = []
        for tcn in ITC_TEMPLATES:
            var = self.fields.get(tcn)
            if not var or not var.get():
                continue
            label = ITC_TEMPLATE_LABELS.get(tcn, tcn)
            flags = ITC_TEMPLATE_EXPANSIONS.get(tcn, [])
            if flags:
                pretty = [u'%s (%s)' % (self._label_for_itcf(n), n) for n in flags]
                lines.append(u'%s (%s): %s' % (label, tcn, u', '.join(pretty)))
            else:
                lines.append(u'%s (%s): %s' % (label, tcn, u'\u672a\u6536\u5f55\u5c55\u5f00\u9879'))
        text.config(state='normal')
        text.delete('1.0', 'end')
        text.insert('end', u'\n'.join(lines) if lines else u'\u672a\u9009\u62e9 itc_ \u6a21\u677f')
        text.config(state='disabled')

    def _make_scrolled_frame(self, parent, height=260):
        outer = tk.Frame(parent)
        outer.pack(fill='both', expand=1, padx=5, pady=2)
        canvas = tk.Canvas(outer, height=height, highlightthickness=0)
        vbar = tk.Scrollbar(outer, orient='vertical', command=canvas.yview, width=18)
        inner = tk.Frame(canvas)
        win = canvas.create_window((0, 0), window=inner, anchor='nw')
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side='left', fill='both', expand=1)
        vbar.pack(side='right', fill='y', padx=(2, 0))

        def update_scrollregion():
            """Call after content changes. Never called during resize."""
            canvas.configure(scrollregion=canvas.bbox('all'))

        def on_canvas_config(event):
            # lightweight: only set inner window width for text reflow
            editor = getattr(getattr(self, 'owner', None), 'editor', None)
            if editor is not None and getattr(editor, '_is_ui_frozen', lambda: False)():
                return
            w = event.width
            if not hasattr(canvas, '_last_width') or abs(canvas._last_width - w) > 12:
                canvas._last_width = w
                canvas.itemconfig(win, width=w)
                updater = getattr(inner, '_update_wraplength', None)
                if updater:
                    try:
                        pending = getattr(canvas, '_wrap_after_id', None)
                        if pending:
                            try:
                                canvas.after_cancel(pending)
                            except Exception:
                                pass
                        canvas._wrap_after_id = inner.after(120, lambda cw=w: (
                            setattr(canvas, '_wrap_after_id', None),
                            updater(cw)
                        ))
                    except Exception:
                        pass

        def on_wheel(event):
            canvas.yview_scroll(-1 * int(event.delta / 120), 'units')
            return 'break'

        def bind_wheel_recursive(widget):
            try:
                widget.bind('<MouseWheel>', on_wheel)
                widget.bind('<Button-4>', lambda e: on_wheel(type('E', (), {'delta': 120})()))
                widget.bind('<Button-5>', lambda e: on_wheel(type('E', (), {'delta': -120})()))
            except Exception:
                pass
            for child in widget.winfo_children():
                bind_wheel_recursive(child)

        # Apply bindings: canvas + vbar + inner + recursive on children
        canvas.bind('<Configure>', on_canvas_config)
        canvas.bind('<MouseWheel>', on_wheel)
        inner.bind('<MouseWheel>', on_wheel)
        outer.bind('<MouseWheel>', on_wheel)
        vbar.bind('<MouseWheel>', on_wheel)
        vbar.bind('<Button-4>', lambda e: on_wheel(type('E', (), {'delta': 120})()))
        vbar.bind('<Button-5>', lambda e: on_wheel(type('E', (), {'delta': -120})()))
        # Store on inner frame so each scrolled frame keeps its own closure
        inner._bind_wheel = bind_wheel_recursive
        inner._canvas = canvas
        inner._update_scroll = update_scrollregion
        return inner

    def _wheel_bind_scrolled_tree(self, inner_frame):
        """Ensure all descendants of a scrolled frame consume mousewheel."""
        bind_wheel = getattr(inner_frame, '_bind_wheel', None)
        if bind_wheel:
            try:
                bind_wheel(inner_frame)
            except Exception:
                pass
        canvas = getattr(inner_frame, '_canvas', None)
        if canvas is not None:
            try:
                canvas.bind('<MouseWheel>', lambda e, c=canvas: c.yview_scroll(-1 * int(e.delta / 120), 'units') or 'break')
                canvas.bind('<Button-4>', lambda e, c=canvas: c.yview_scroll(-1, 'units') or 'break')
                canvas.bind('<Button-5>', lambda e, c=canvas: c.yview_scroll(1, 'units') or 'break')
            except Exception:
                pass

    def _ensure_wheel_on_scrolled(self, inner_frame):
        """(Re)bind wheel recursively on a scrolled inner frame, using its own canvas closure."""
        bind_wheel = getattr(inner_frame, '_bind_wheel', None)
        if bind_wheel:
            try:
                bind_wheel(inner_frame)
            except Exception:
                pass

    def build_ui(self, parent):
        lf = self._make_label_frame(parent, u'F4 \u52a8\u4f5c (Capabilities)')
        self._make_raw_row(lf, readonly=False)
        self._widget = lf

        # Sub-frame: itc_ templates (21 items)
        tc_frame = tk.LabelFrame(lf, text=u'itc_ \u6a21\u677f')
        tc_frame.pack(fill='x', padx=5, pady=2)
        tc_inner = tk.Frame(tc_frame)
        tc_inner.pack(fill='x', padx=3, pady=2)
        for ti, tcn in enumerate(ITC_TEMPLATES):
            tcl = ITC_TEMPLATE_LABELS.get(tcn, tcn)
            var = tk.IntVar()
            cb = tk.Checkbutton(tc_inner, text=tcl, variable=var,
                                command=lambda n=tcn: self.on_field_change(n))
            cb.grid(row=ti // 7, column=ti % 7, sticky='w', padx=3, pady=1)
            self.fields[tcn] = var

        ex_frame = tk.LabelFrame(lf, text=u'itc_ \u6a21\u677f\u62c6\u89e3')
        ex_frame.pack(fill='x', padx=5, pady=2)
        ex_body = tk.Frame(ex_frame)
        ex_body.pack(fill='both', expand=1, padx=3, pady=2)
        self._template_expansion_text = tk.Text(ex_body, height=5, wrap='none',
                                                font=('Consolas', 9))
        ex_y = tk.Scrollbar(ex_body, orient='vertical',
                            command=self._template_expansion_text.yview)
        ex_x = tk.Scrollbar(ex_body, orient='horizontal',
                            command=self._template_expansion_text.xview)
        self._template_expansion_text.configure(yscrollcommand=ex_y.set,
                                                xscrollcommand=ex_x.set)
        self._template_expansion_text.grid(row=0, column=0, sticky='nsew')
        ex_y.grid(row=0, column=1, sticky='ns')
        ex_x.grid(row=1, column=0, sticky='ew')
        ex_body.grid_rowconfigure(0, weight=1)
        ex_body.grid_columnconfigure(0, weight=1)
        self._template_expansion_text.config(state='disabled')

        # Sub-frame: itcf_ flags by category
        cf_frame = tk.LabelFrame(lf, text=u'itcf_ \u529f\u80fd\u65d7\u6807 (header_items.py)')
        cf_frame.pack(fill='both', expand=1, padx=5, pady=2)
        cf_outer = self._make_scrolled_frame(cf_frame, height=360)
        itcf_categories = self._group_itcf_flags()
        self._itcf_checkbuttons = []

        def _update_itcf_wraplength(canvas_width):
            # Keep labels readable while avoiding a hard-coded width that breaks on resize.
            usable = max(220, int(canvas_width) - 70)
            for cb in self._itcf_checkbuttons:
                try:
                    cb.configure(wraplength=usable)
                except Exception:
                    pass
            if getattr(cf_outer, '_update_scroll', None):
                cf_outer.after_idle(cf_outer._update_scroll)

        cf_outer._update_wraplength = _update_itcf_wraplength

        for gi, (gname, gitems) in enumerate(itcf_categories):
            gf = tk.LabelFrame(cf_outer, text=gname, font=('', 8))
            gf.pack(fill='x', expand=1, padx=2, pady=2)
            # 2-column grid: each item fills one cell
            n_items = len(gitems)
            n_cols = 2 if n_items >= 4 else 1
            for ii, (cfn, cfl) in enumerate(gitems):
                var = tk.IntVar()
                cb = tk.Checkbutton(gf, text=u'%s (%s)' % (cfl, cfn), variable=var,
                                    anchor='w', justify='left', wraplength=260,
                                    command=lambda n=cfn: self.on_field_change(n))
                cb.grid(row=ii // n_cols, column=ii % n_cols, sticky='w', padx=4, pady=1)
                self.fields[cfn] = var
                self._itcf_checkbuttons.append(cb)
        # Wheel bindings: each scrolled frame uses its own closure via inner._bind_wheel
        self._ensure_wheel_on_scrolled(cf_outer)
        # Update scrollregion after all checkboxes are created
        if getattr(cf_outer, '_update_scroll', None):
            cf_outer.after_idle(cf_outer._update_scroll)
        if getattr(cf_outer, '_update_wraplength', None):
            cf_outer.after_idle(lambda: cf_outer._update_wraplength(cf_outer._canvas.winfo_width() if getattr(cf_outer, '_canvas', None) else 0))

        return lf


# ============================================================
#  S5: Other Flags  (F3: itp_* non-type, bit-grouped)
# ============================================================

class OtherFlagsSection(SectionController):
    """Same F3 field as TypeFlags, but shows non-type flags with bit-grouped labels."""

    def parse_raw(self, raw):
        return {flag: 1 for flag in raw.replace('|', ' ').split() if flag and flag != '0'}

    def rebuild_raw(self):
        parts = [n for n, var in self.fields.items() if var.get()]
        return ' | '.join(parts) if parts else '0'

    def build_ui(self, parent):
        lf = self._make_label_frame(parent, u'\u5176\u4ed6\u6807\u8bb0 (Other Flags, bit-grouped)')
        self._make_raw_row(lf)
        self._widget = lf
        self.fields = self._make_checkbuttons_grid(lf, ITP_OTHER_FLAGS, columns=6)
        return lf


# ============================================================
#  S6: Stats  (F6: weight|difficulty|spd_rtng|...|swing_damage(20,cut)|...)
# ============================================================

class StatsSection(SectionController):
    """18 numeric fields + 3 damage type Comboboxes, bidirectional with pipe-separated raw."""

    STAT_KEYS = [
        'weight', 'difficulty', 'spd_rtng', 'weapon_length', 'max_ammo',
        'shoot_speed', 'accuracy', 'head_armor', 'body_armor', 'leg_armor',
        'speed_rating', 'horse_speed', 'horse_maneuver', 'horse_charge',
        'horse_scale', 'abundance', 'armor', 'hit_points',
    ]
    STAT_LABELS = [
        u'\u91cd\u91cf', u'\u96be\u5ea6', u'\u901f\u5ea6', u'\u957f\u5ea6',
        u'\u5f39\u91cf', u'\u5c04\u901f', u'\u7cbe\u5ea6', u'\u5934\u9632',
        u'\u8eab\u9632', u'\u817f\u9632', u'\u901f\u5ea6\u8bc4\u7ea7',
        u'\u9a6c\u901f', u'\u9a6c\u64cd\u63a7', u'\u9a6c\u51b2\u51fb',
        u'\u9a6c\u5c3a\u5bf8', u'\u5145\u88d5\u5ea6', u'\u62a4\u7532',
        u'\u751f\u547d\u503c',
    ]
    DMG_LABELS = [u'\u6325\u780d\u4f24\u5bb3', u'\u523a\u51fb\u4f24\u5bb3', u'\u51b2\u950b\u4f24\u5bb3']
    DMG_KEYS  = ['swing_damage', 'thrust_damage', 'horse_charge_damage']

    def parse_raw(self, raw):
        """Parse pipe-separated stats: weight(1.5)|difficulty(0)|swing_damage(20,cut)|...
        Returns dict with key→value_string. Damage types stored as key_type."""
        out = {}
        # Also init damage type defaults
        for dk in self.DMG_KEYS:
            out[dk + '_type'] = 'cut'

        if not raw or raw == '0':
            return out

        # Tokenize by | but respect parentheses nesting
        tokens = []
        depth = 0
        current = ''
        for ch in raw:
            if ch == '(':
                depth += 1
                current += ch
            elif ch == ')':
                depth -= 1
                current += ch
            elif ch == '|' and depth == 0:
                token = current.strip()
                if token:
                    tokens.append(token)
                current = ''
            else:
                current += ch
        if current.strip():
            tokens.append(current.strip())

        for tok in tokens:
            # Try key(value) or key(val, type)
            m = _re.match(r'(\w+)\(([^)]*)\)', tok)
            if m:
                key = m.group(1)
                val = m.group(2)
                if key in self.DMG_KEYS:
                    # ex: "20, cut" or "20"
                    parts = [p.strip() for p in val.split(',')]
                    out[key] = parts[0] if parts else val
                    out[key + '_type'] = parts[1] if len(parts) > 1 else 'cut'
                else:
                    out[key] = val
        return out

    def rebuild_raw(self):
        parts = []
        # Regular stats: key(value)
        for sk in self.STAT_KEYS:
            if sk in self.fields:
                val = self.fields[sk].get().strip()
                if val:
                    parts.append('%s(%s)' % (sk, val))
        # Damage: key(val, type)
        for dk in self.DMG_KEYS:
            if dk in self.fields:
                val = self.fields[dk].get().strip()
                dtype = self.fields.get(dk + '_type', tk.StringVar(value='cut')).get()
                if val:
                    parts.append('%s(%s, %s)' % (dk, val, dtype))
        return '|'.join(parts) if parts else '0'

    def populate_fields(self, parsed):
        for sk in self.STAT_KEYS:
            if sk in self.fields:
                self.fields[sk].set(str(parsed.get(sk, '')))
        for dk in self.DMG_KEYS:
            if dk in self.fields:
                self.fields[dk].set(str(parsed.get(dk, '')))
            dt_key = dk + '_type'
            if dt_key in self.fields:
                self.fields[dt_key].set(str(parsed.get(dt_key, 'cut')))

    def build_ui(self, parent):
        lf = self._make_label_frame(parent, u'F6 \u5c5e\u6027 (Stats)')
        self._make_raw_row(lf)
        self._widget = lf
        # Pure pack layout, fields in two columns
        cols_frame = tk.Frame(lf)
        cols_frame.pack(fill='x', padx=5, pady=2)
        left_col = tk.Frame(cols_frame)
        left_col.pack(side='left', fill='both', expand=1)
        right_col = tk.Frame(cols_frame)
        right_col.pack(side='left', fill='both', expand=1, padx=(10, 0))

        # 18 stat fields split across left/right columns
        for si, (sk, sl) in enumerate(zip(self.STAT_KEYS, self.STAT_LABELS)):
            parent_col = left_col if si < 9 else right_col
            local_idx = si if si < 9 else si - 9
            row = tk.Frame(parent_col)
            row.pack(fill='x', pady=1)
            tk.Label(row, text=sl + ':', anchor='e', width=8).pack(side='left')
            var = tk.StringVar()
            var.trace('w', lambda n=sk, *a: self.on_field_change(n))
            tk.Entry(row, textvariable=var, width=12).pack(side='left', padx=(2, 0))
            self.fields[sk] = var

        # Damage rows (full width below stats)
        for di, (dl, dk) in enumerate(zip(self.DMG_LABELS, self.DMG_KEYS)):
            row = tk.Frame(lf)
            row.pack(fill='x', padx=5, pady=1)
            tk.Label(row, text=dl + ':', anchor='e', width=10).pack(side='left')
            var = tk.StringVar()
            var.trace('w', lambda n=dk, *a: self.on_field_change(n))
            tk.Entry(row, textvariable=var, width=8).pack(side='left', padx=(2, 0))
            self.fields[dk] = var
            dt_key = dk + '_type'
            dt_var = tk.StringVar(value='cut')
            dt_var.trace('w', lambda n=dt_key, *a: self.on_field_change(n))
            cb = ttk.Combobox(row, textvariable=dt_var, width=8,
                              values=['cut', 'pierce', 'blunt'], state='readonly')
            cb.pack(side='left', padx=(4, 0))
            self.fields[dt_key] = dt_var
        return lf


# ============================================================
#  S7: Modifier  (F7: imodbits_xxx)
# ============================================================

class ModifierSection(SectionController):
    """F7 modifier bits: selectable imodbit flags with breakdown."""

    PREFIX_LABELS = {
        'imodbit_plain': u'\u666e\u901a\u7684',
        'imodbit_cracked': u'\u88c2\u5f00\u7684',
        'imodbit_rusty': u'\u751f\u9519\u7684',
        'imodbit_bent': u'\u5f2f\u66f2\u7684',
        'imodbit_chipped': u'\u7f3a\u53e3\u7684',
        'imodbit_battered': u'\u7834\u635f\u7684',
        'imodbit_poor': u'\u7cca\u7cd5\u7684',
        'imodbit_crude': u'\u7b80\u9648\u7684',
        'imodbit_old': u'\u7ea0\u65e7\u7684',
        'imodbit_cheap': u'\u4fbf\u5b9c\u7684',
        'imodbit_fine': u'\u7cbe\u826f\u7684',
        'imodbit_well_made': u'\u7cbe\u5de5\u7684',
        'imodbit_sharp': u'\u9510\u5229\u7684',
        'imodbit_balanced': u'\u5e73\u8861\u7684',
        'imodbit_tempered': u'\u56de\u706b\u7684',
        'imodbit_deadly': u'\u81f4\u547d\u7684',
        'imodbit_exquisite': u'\u7cbe\u81f4\u7684',
        'imodbit_masterwork': u'\u4e3b\u4f5c\u7684',
        'imodbit_heavy': u'\u91cd\u7684',
        'imodbit_strong': u'\u5f3a\u6709\u529b\u7684',
        'imodbit_powerful': u'\u5f3a\u5927\u7684',
        'imodbit_tattered': u'\u7834\u65e7\u7684',
        'imodbit_ragged': u'\u7834\u7cd5\u7684',
        'imodbit_rough': u'\u7c97\u7cd9\u7684',
        'imodbit_sturdy': u'\u7ed3\u5b9e\u7684',
        'imodbit_thick': u'\u539a\u91cd\u7684',
        'imodbit_hardened': u'\u786c\u5316\u7684',
        'imodbit_reinforced': u'\u52a0\u56fa\u7684',
        'imodbit_superb': u'\u4f18\u79c0\u7684',
        'imodbit_lordly': u'\u8d35\u65cf\u7684',
        'imodbit_lame': u'\u762b\u75a5\u7684',
        'imodbit_swaybacked': u'\u9a70\u80cc\u7684',
        'imodbit_stubborn': u'\u56fa\u6267\u7684',
        'imodbit_timid': u'\u6de1\u7684',
        'imodbit_meek': u'\u8f6f\u5f31\u7684',
        'imodbit_spirited': u'\u7cbe\u795e\u7684',
        'imodbit_champion': u'\u51a0\u519b\u7684',
        'imodbit_fresh': u'\u65b0\u9c9c\u7684',
        'imodbit_day_old': u'\u5927\u6628\u7684',
        'imodbit_two_day_old': u'\u4e24\u5929\u524d\u7684',
        'imodbit_smelling': u'\u53d1\u81ed\u7684',
        'imodbit_rotten': u'\u8150\u70c2\u7684',
        'imodbit_large_bag': u'\u5927\u888b\u88c5\u7684',
    }

    def __init__(self, owner):
        SectionController.__init__(self, owner)
        self._mod_vars = {}
        self._mod_options = []
        self._mod_display = {}
        self._mod_breakdown = None
        self._mod_box_inner = None
        self._mod_widgets_built = False
        self._preset_vars = {}
        self._preset_options = []
        self._preset_box_inner = None
        self._preset_map = {}
        self._preset_manual_off = set()

    def parse_raw(self, raw):
        return {'modifier': raw}

    def rebuild_raw(self):
        preset = self._selected_preset()
        if preset:
            return preset
        parts = []
        for name in self._mod_options:
            var = self._mod_vars.get(name)
            if var is not None and var.get():
                parts.append(name)
        return ' | '.join(parts) if parts else 'imodbits_none'

    def populate_fields(self, parsed):
        raw = parsed.get('modifier', 'imodbits_none') or 'imodbits_none'
        self._set_modifiers_from_raw(raw)
        self._ensure_mod_options()
        self._build_mod_option_widgets()
        self._build_preset_widgets()
        self._update_breakdown()

    def on_field_change(self, trigger_name=None):
        if trigger_name in self._preset_options:
            if self._preset_vars.get(trigger_name) and self._preset_vars[trigger_name].get():
                self._preset_manual_off.discard(trigger_name)
                self._apply_preset(trigger_name)
            else:
                self._preset_manual_off.add(trigger_name)
                self._clear_preset(trigger_name)
        SectionController.on_field_change(self, trigger_name)
        self._sync_presets_from_modifiers()
        self._update_breakdown()

    def _u(self, value):
        if value is None:
            return u''
        try:
            if isinstance(value, unicode):
                return value
        except NameError:
            pass
        try:
            return value.decode('utf-8')
        except Exception:
            try:
                return value.decode('gbk')
            except Exception:
                return unicode(value)

    def _ensure_mod_options(self):
        if self._mod_options:
            return
        names = []
        defs = getattr(self.owner, 'imodbit_defs', [])
        if defs:
            for item in defs:
                name = item.get('name')
                if name and name != 'imodbit_none':
                    names.append(name)
                    self._mod_display[name] = self.PREFIX_LABELS.get(name, item.get('label', name))
        if not names:
            for name in sorted(getattr(self.owner, 'imodbit_constants', {}).keys()):
                if name == 'imodbit_none':
                    continue
                names.append(name)
                self._mod_display[name] = self.PREFIX_LABELS.get(name, name)
        self._mod_options = names
        self._preset_map = getattr(self.owner, 'imodbits_expansions', {}) or {}

    def _set_modifiers_from_raw(self, raw):
        raw = (raw or '').strip()
        if raw.startswith('0'):
            raw = 'imodbits_none'
        preset = raw if raw.startswith('imodbits_') else ''
        tokens = [tok.strip() for tok in raw.split('|') if tok.strip()]
        self._guard = True
        try:
            self._ensure_mod_options()
            expanded = []
            if preset and preset in self._preset_map:
                expanded = list(self._preset_map.get(preset, []))
            elif preset:
                expanded = [preset]
            elif tokens:
                expanded = tokens
            for name in self._mod_options:
                if name not in self._mod_vars:
                    continue
                self._mod_vars[name].set(1 if name in expanded or name in tokens else 0)
            self._ensure_preset_options()
            for name in self._preset_options:
                if name not in self._preset_vars:
                    continue
                self._preset_vars[name].set(1 if name == preset else 0)
        finally:
            self._guard = False

    def _get_selected_modifiers(self):
        return [name for name in self._mod_options
                if self._mod_vars.get(name) is not None and self._mod_vars[name].get()]

    def _selected_preset(self):
        for name in self._preset_options:
            var = self._preset_vars.get(name)
            if var is not None and var.get():
                return name
        exact = sorted(self._get_selected_modifiers())
        for name in self._preset_options:
            expanded = sorted(self._preset_map.get(name, []))
            if expanded and expanded == exact and name not in self._preset_manual_off:
                return name
        return ''

    def _update_breakdown(self):
        if self._mod_breakdown is None:
            return
        selected = self._get_selected_modifiers()
        txt = u', '.join([self._u(self._mod_display.get(n, n)) for n in selected]) if selected else u'imodbits_none'
        self._mod_breakdown.config(state='normal')
        self._mod_breakdown.delete('1.0', 'end')
        self._mod_breakdown.insert('end', txt)
        self._mod_breakdown.config(state='disabled')

    def _wheel_bind_scrolled_tree(self, inner_frame):
        """Ensure all descendants of a scrolled frame consume mousewheel."""
        bind_wheel = getattr(inner_frame, '_bind_wheel', None)
        if bind_wheel:
            try:
                bind_wheel(inner_frame)
            except Exception:
                pass
        canvas = getattr(inner_frame, '_canvas', None)
        if canvas is not None:
            try:
                canvas.bind('<MouseWheel>', lambda e, c=canvas: c.yview_scroll(-1 * int(e.delta / 120), 'units') or 'break')
                canvas.bind('<Button-4>', lambda e, c=canvas: c.yview_scroll(-1, 'units') or 'break')
                canvas.bind('<Button-5>', lambda e, c=canvas: c.yview_scroll(1, 'units') or 'break')
            except Exception:
                pass

    def _make_scrolled_frame(self, parent, height=190):
        outer = tk.Frame(parent)
        outer.pack(fill='both', expand=1, padx=5, pady=2)
        canvas = tk.Canvas(outer, height=height, highlightthickness=0)
        vbar = tk.Scrollbar(outer, orient='vertical', command=canvas.yview, width=18)
        inner = tk.Frame(canvas)
        win = canvas.create_window((0, 0), window=inner, anchor='nw')
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side='left', fill='both', expand=1)
        vbar.pack(side='right', fill='y', padx=(2, 0))

        def update_scrollregion():
            """Call after content changes. Never called during resize."""
            canvas.configure(scrollregion=canvas.bbox('all'))

        def on_canvas_config(event):
            # lightweight: only set inner window width for text reflow
            editor = getattr(getattr(self, 'owner', None), 'editor', None)
            if editor is not None and getattr(editor, '_is_ui_frozen', lambda: False)():
                return
            w = event.width
            if not hasattr(canvas, '_last_width') or abs(canvas._last_width - w) > 3:
                canvas._last_width = w
                canvas.itemconfig(win, width=w)

        def on_wheel(event):
            canvas.yview_scroll(-1 * int(event.delta / 120), 'units')
            return 'break'

        def bind_wheel_recursive(widget):
            try:
                widget.bind('<MouseWheel>', on_wheel)
                widget.bind('<Button-4>', lambda e: on_wheel(type('E', (), {'delta': 120})()))
                widget.bind('<Button-5>', lambda e: on_wheel(type('E', (), {'delta': -120})()))
            except Exception:
                pass
            for child in widget.winfo_children():
                bind_wheel_recursive(child)

        canvas.bind('<Configure>', on_canvas_config)
        canvas.bind('<MouseWheel>', on_wheel)
        inner.bind('<MouseWheel>', on_wheel)
        outer.bind('<MouseWheel>', on_wheel)
        vbar.bind('<MouseWheel>', on_wheel)
        vbar.bind('<Button-4>', lambda e: on_wheel(type('E', (), {'delta': 120})()))
        vbar.bind('<Button-5>', lambda e: on_wheel(type('E', (), {'delta': -120})()))
        inner._bind_wheel = bind_wheel_recursive
        inner._canvas = canvas
        inner._update_scroll = update_scrollregion
        return inner

    def _build_mod_option_widgets(self):
        if self._mod_box_inner is None:
            return
        for child in self._mod_box_inner.winfo_children():
            try:
                child.destroy()
            except Exception:
                pass
        cols = 3
        for i, name in enumerate(self._mod_options):
            if name not in self._mod_vars:
                self._mod_vars[name] = tk.IntVar(value=0)
            label = self._mod_display.get(name, name)
            cb = tk.Checkbutton(self._mod_box_inner, text=label, variable=self._mod_vars[name],
                                anchor='w', command=lambda n=name: self.on_field_change(n))
            cb.grid(row=i // cols, column=i % cols, sticky='w', padx=4, pady=1)
        self._mod_widgets_built = True
        # Update scrollregion after widgets rebuilt
        if getattr(self._mod_box_inner, '_update_scroll', None):
            self._mod_box_inner.after_idle(self._mod_box_inner._update_scroll)
        self._wheel_bind_scrolled_tree(self._mod_box_inner)

    def _ensure_preset_options(self):
        if self._preset_options:
            return
        self._preset_options = [name for name in sorted(getattr(self.owner, 'imodbits_constants', {}).keys())
                                if name != 'imodbits_none']

    def _build_preset_widgets(self):
        if self._preset_box_inner is None:
            return
        for child in self._preset_box_inner.winfo_children():
            try:
                child.destroy()
            except Exception:
                pass
        self._ensure_preset_options()
        cols = 3
        labels = getattr(self.owner, 'imodbits_labels', {})
        for i, name in enumerate(self._preset_options):
            if name not in self._preset_vars:
                self._preset_vars[name] = tk.IntVar(value=0)
            label = self._u(labels.get(name, name))
            cb = tk.Checkbutton(self._preset_box_inner, text=label, variable=self._preset_vars[name],
                                anchor='w', command=lambda n=name: self.on_field_change(n))
            cb.grid(row=i // cols, column=i % cols, sticky='w', padx=4, pady=1)
        # Update scrollregion after widgets rebuilt
        if getattr(self._preset_box_inner, '_update_scroll', None):
            self._preset_box_inner.after_idle(self._preset_box_inner._update_scroll)
        self._wheel_bind_scrolled_tree(self._preset_box_inner)

    def _apply_preset(self, preset_name):
        expanded = set(self._preset_map.get(preset_name, []))
        old_guard = self._guard
        self._guard = True
        try:
            for name in self._mod_options:
                var = self._mod_vars.get(name)
                if var is not None:
                    var.set(1 if name in expanded else 0)
            for name, var in self._preset_vars.items():
                var.set(1 if name == preset_name else 0)
        finally:
            self._guard = old_guard

    def _clear_preset(self, preset_name):
        expanded = set(self._preset_map.get(preset_name, []))
        old_guard = self._guard
        self._guard = True
        try:
            for name in expanded:
                var = self._mod_vars.get(name)
                if var is not None:
                    var.set(0)
            self._preset_vars[preset_name].set(0)
        finally:
            self._guard = old_guard

    def _sync_presets_from_modifiers(self):
        if self._guard:
            return
        selected = sorted(self._get_selected_modifiers())
        match = ''
        for name in self._preset_options:
            expanded = sorted(self._preset_map.get(name, []))
            if expanded and expanded == selected and name not in self._preset_manual_off:
                match = name
                break
        old_guard = self._guard
        self._guard = True
        try:
            for name, var in self._preset_vars.items():
                var.set(1 if name == match else 0)
        finally:
            self._guard = old_guard

    def build_ui(self, parent):
        lf = self._make_label_frame(parent, u'F7 \u4fee\u9970\u7b26 (Modifier Bits)')
        self._make_raw_row(lf, readonly=True)
        self._widget = lf
        inner = tk.Frame(lf)
        inner.pack(fill='x', padx=5, pady=2)
        self._ensure_mod_options()
        self.fields['modifier'] = tk.StringVar()
        self.fields['modifier'].trace('w', lambda *a: self.on_raw_change())
        tk.Label(inner, text=u'原始表达式:', anchor='e', width=10).pack(side='left', padx=(5, 0))
        tk.Entry(inner, textvariable=self.fields['modifier']).pack(side='left', fill='x', expand=1, padx=2)

        brf = tk.LabelFrame(lf, text=u'F7 拆解')
        brf.pack(fill='x', padx=5, pady=2)
        self._mod_breakdown = tk.Text(brf, height=2, wrap='word', font=('Consolas', 9))
        self._mod_breakdown.pack(fill='x', padx=3, pady=2)
        self._mod_breakdown.config(state='disabled')

        box = tk.LabelFrame(lf, text=u'\u524d\u7f00')
        box.pack(fill='both', expand=1, padx=5, pady=2)
        self._mod_box_inner = self._make_scrolled_frame(box, height=240)
        self._build_mod_option_widgets()
        preset_box = tk.LabelFrame(lf, text=u'\u9884\u8bbe\u524d\u7f00\u7ec4')
        preset_box.pack(fill='both', expand=1, padx=5, pady=2)
        self._preset_box_inner = self._make_scrolled_frame(preset_box, height=140)
        self._build_preset_widgets()
        return lf


# ============================================================
#  S8: Triggers (F8) / Factions (F9)
# ============================================================

class TriggersSection(SectionController):
    """F8 triggers editor + F9 faction selector."""

    def __init__(self, owner):
        SectionController.__init__(self, owner)
        self._faction_combo = None
        self._faction_options = []
        self._faction_by_display = {}
        self._faction_raw = '[]'

    def parse_raw(self, raw):
        return {'triggers': raw, 'factions': ''}

    def rebuild_raw(self):
        return self.fields.get('triggers').get().strip() if 'triggers' in self.fields else '[]'

    def populate_triggers(self, f8_raw, f9_raw):
        """Override: populate F8 triggers and F9 factions separately."""
        self._guard = True
        try:
            self.raw_var.set(f8_raw if f8_raw else '[]')
            self.fields['triggers'].set(f8_raw if f8_raw and f8_raw != '[]' else '')
            self._ensure_faction_options()
            self._set_faction_value(f9_raw if f9_raw and f9_raw != '[]' else '')
        finally:
            self._guard = False

    def _ensure_faction_options(self):
        if self._faction_options:
            return
        data = getattr(self.owner, 'faction_data', None) or []
        if not data and getattr(self.owner, 'source_path', ''):
            self._load_faction_data_from_source()
            data = getattr(self.owner, 'faction_data', None) or []
        options = []
        by_display = {}
        for fid, en, cn in data:
            label = self._u(fid)
            if en:
                label += u'  %s' % self._u(en)
            if cn:
                label += u'  %s' % self._u(cn)
            options.append(label)
            by_display[label] = fid
        self._faction_options = options
        self._faction_by_display = by_display

    def _u(self, value):
        if value is None:
            return u''
        try:
            if isinstance(value, unicode):
                return value
        except NameError:
            pass
        try:
            return value.decode('utf-8')
        except Exception:
            try:
                return value.decode('gbk')
            except Exception:
                return unicode(value)

    def _load_faction_data_from_source(self):
        path = _os.path.join(getattr(self.owner, 'source_path', ''), 'module_factions.py')
        if not _os.path.isfile(path):
            return
        try:
            import codecs
            with codecs.open(path, 'r', 'utf-8', errors='replace') as f:
                text = f.read()
            data = []
            started = False
            for line in text.splitlines():
                stripped = line.strip()
                if not started:
                    if stripped.startswith('factions') and '[' in stripped:
                        started = True
                    continue
                if stripped.startswith(']'):
                    break
                fm = _re.match(r'^\(\s*["\']([^"\']+)["\']\s*,\s*["\']([^"\']*)["\']', stripped)
                if not fm:
                    continue
                fid = 'fac_' + fm.group(1).strip()
                en = fm.group(2).replace('{!}', '').strip()
                cn = ''
                if hasattr(self.owner, 'faction_cn'):
                    cn = self.owner.faction_cn.get(fid, '')
                data.append((fid, en, cn))
            if data:
                self.owner.faction_data = data
        except Exception:
            pass

    def _set_faction_value(self, raw_value):
        raw_value = (raw_value or '').strip()
        raw_value = raw_value.strip('[]').strip()
        raw_value = raw_value.strip('"\'')
        fid = raw_value if raw_value.startswith('fac_') else ('fac_' + raw_value if raw_value else '')
        display = fid
        if fid:
            for d in self._faction_options:
                if self._faction_by_display.get(d, '') == fid:
                    display = d
                    break
        self._faction_raw = '[%s]' % fid if fid else '[]'
        self.fields['factions'].set(display)
        if self._faction_combo:
            self._faction_combo.set(display)

    def _get_faction_raw(self):
        return self._faction_raw or '[]'

    def _sync_faction_from_combo(self, event=None):
        if self._guard:
            return
        self._guard = True
        try:
            if self._faction_combo:
                val = self._faction_combo.get().strip()
                self.fields['factions'].set(val)
                fid = self._faction_by_display.get(val, '')
                if fid:
                    self._faction_raw = '[%s]' % fid
        finally:
            self._guard = False
        self.on_field_change('factions')

    def _on_faction_wheel(self, event):
        if not self._faction_combo or not self._faction_options:
            return 'break'
        cur = self._faction_combo.get().strip()
        try:
            idx = self._faction_options.index(cur)
        except ValueError:
            idx = 0
        step = -1 if getattr(event, 'delta', 0) > 0 else 1
        idx = max(0, min(len(self._faction_options) - 1, idx + step))
        self._faction_combo.set(self._faction_options[idx])
        self.fields['factions'].set(self._faction_options[idx])
        self._faction_raw = '[%s]' % self._faction_by_display.get(self._faction_options[idx], self._faction_options[idx].split()[0])
        self._sync_faction_from_combo()
        return 'break'

    def _bind_faction_popdown_wheel(self):
        """Bind mousewheel to the combobox popdown list when it exists."""
        combo = self._faction_combo
        if not combo:
            return
        try:
            popdown = combo.tk.call('ttk::combobox::PopdownWindow', str(combo))
            listbox = combo.nametowidget(popdown + '.f.l')
        except Exception:
            return

        def _popdown_wheel(event):
            try:
                step = -1 * int(getattr(event, 'delta', 0) / 120)
                if step == 0:
                    step = 1 if getattr(event, 'delta', 0) < 0 else -1
                listbox.yview_scroll(step, 'units')
            except Exception:
                pass
            return 'break'

        try:
            listbox.bind('<MouseWheel>', _popdown_wheel)
            listbox.bind('<Button-4>', lambda e: _popdown_wheel(type('E', (), {'delta': 120})()))
            listbox.bind('<Button-5>', lambda e: _popdown_wheel(type('E', (), {'delta': -120})()))
        except Exception:
            pass

    def build_ui(self, parent):
        lf = self._make_label_frame(parent, u'F8 \u89e6\u53d1 & F9 \u9635\u8425 (Triggers & Factions)')
        self._make_raw_row(lf, readonly=True)
        self._widget = lf
        # F8 Triggers — full width Entry
        row1 = tk.Frame(lf)
        row1.pack(fill='x', padx=5, pady=1)
        tk.Label(row1, text=u'F8 Triggers:', anchor='e', width=12).pack(side='left')
        self.fields['triggers'] = tk.StringVar()
        tk.Entry(row1, textvariable=self.fields['triggers']).pack(side='left', fill='x', expand=1, padx=(2, 0))
        # F9 Factions — combobox
        row2 = tk.Frame(lf)
        row2.pack(fill='x', padx=5, pady=1)
        tk.Label(row2, text=u'F9 Factions:', anchor='e', width=12).pack(side='left')
        self._ensure_faction_options()
        self.fields['factions'] = tk.StringVar()
        self._faction_combo = ttk.Combobox(row2, textvariable=self.fields['factions'],
                                           values=self._faction_options,
                                           state='readonly', width=30)
        self._faction_combo.pack(side='left', padx=2, fill='x', expand=1)
        self._faction_combo.configure(postcommand=self._bind_faction_popdown_wheel)
        self._faction_combo.bind('<<ComboboxSelected>>', self._sync_faction_from_combo)
        self._faction_combo.bind('<MouseWheel>', self._on_faction_wheel)
        self._faction_combo.bind('<Button-4>', lambda e: self._on_faction_wheel(type('E', (), {'delta': 120})()))
        self._faction_combo.bind('<Button-5>', lambda e: self._on_faction_wheel(type('E', (), {'delta': -120})()))
        return lf


# ============================================================
#  Factory: build all sections
# ============================================================

def build_all_sections(owner, parent):
    """Create all 8 section controllers, build UI, return list.
    
    Args:
        owner: ItemModule instance
        parent: tk Frame to pack sections into
    
    Returns:
        dict: {section_key: SectionController}
    """
    sections = {}

    # S0: Basic
    sections['basic'] = BasicSection(owner)
    sections['basic'].build(parent)

    # S2: Mesh
    sections['mesh'] = MeshSection(owner)
    sections['mesh'].build(parent)

    # S3: Type Flags
    sections['type_flags'] = TypeFlagsSection(owner)
    sections['type_flags'].build(parent)

    # S4: Capabilities
    sections['capabilities'] = CapabilitiesSection(owner)
    sections['capabilities'].build(parent)

    # S5: Other Flags
    sections['other_flags'] = OtherFlagsSection(owner)
    sections['other_flags'].build(parent)

    # S6: Stats
    sections['stats'] = StatsSection(owner)
    sections['stats'].build(parent)

    # S7: Modifier
    sections['modifier'] = ModifierSection(owner)
    sections['modifier'].build(parent)

    # S8: Triggers & Factions
    sections['triggers'] = TriggersSection(owner)
    sections['triggers'].build(parent)

    return sections
