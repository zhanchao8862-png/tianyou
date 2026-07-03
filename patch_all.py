# -*- coding: utf-8 -*-
"""Apply 6 patches to tianyou_editor.py"""
import os
import shutil

fpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tianyou_editor.py')
shutil.copy2(fpath, fpath + '.bak')

with open(fpath, 'rb') as f:
    c = f.read()

print "Original size:", len(c)

# Patch 1: drag-drop state vars in __init__
# Match: "self.item_cn = {}             # 'itm_xxx' -> 中文名"
p1 = "\n        self.item_cn = {}             # 'itm_xxx' -> 中文名"
assert p1 in c, "P1 marker not found"
c = c.replace(p1, p1 + "\n\n        # Drag-drop state\n        self._drag_start_y = -1\n        self._drag_start_idx = -1\n        self._drag_threshold_passed = False", 1)
print "P1 OK"

# Patch 2: drag-drop bindings on troop_lb
p2 = "\n        self.troop_lb.config(yscrollcommand=lsb.set)"
assert p2 in c, "P2 marker not found"
c = c.replace(p2, p2 + "\n        self.troop_lb.bind('<ButtonPress-1>', self._on_drag_press)\n        self.troop_lb.bind('<B1-Motion>', self._on_drag_motion)\n        self.troop_lb.bind('<ButtonRelease-1>', self._on_drag_release)", 1)
print "P2 OK"

# Patch 3: move up/down buttons
# Old: delete button line then save_btn line
p3_old = '\n        tk.Button(bf, text=u"\\u5220\\u9664\\u5175\\u79cd", command=self._delete_troop, width=8).pack(side=\'left\', padx=2)'
assert p3_old in c, "P3 old not found"
p3_new = p3_old + '\n        self._btn_move_up = tk.Button(bf, text=u"\\u25b2", command=self._move_troop_up, width=2)\n        self._btn_move_up.pack(side=\'left\', padx=1)\n        self._btn_move_down = tk.Button(bf, text=u"\\u25bc", command=self._move_troop_down, width=2)\n        self._btn_move_down.pack(side=\'left\', padx=1)'
c = c.replace(p3_old, p3_new, 1)
print "P3 OK"

# Patch 4: _set_ui_state add move buttons
p4_old = '\n        for w in [self.troop_lb, self._btn_add_eq, self._btn_rm_eq, self._btn_clr_eq]:'
assert p4_old in c, "P4 old not found"
p4_new = p4_old.replace('self._btn_clr_eq]', 'self._btn_clr_eq,\n                  self._btn_move_up, self._btn_move_down]')
c = c.replace(p4_old, p4_new, 1)
print "P4 OK"

# Patch 5: keyboard shortcuts Ctrl+Up/Down
p5_old = "\n        self.root.bind('<F5>', lambda e: self._reload())"
assert p5_old in c, "P5 old not found"
p5_new = p5_old + "\n        self.root.bind('<Control-Up>', lambda e: self._move_troop_up())\n        self.root.bind('<Control-Down>', lambda e: self._move_troop_down())"
c = c.replace(p5_old, p5_new, 1)
print "P5 OK"

# Patch 6: new methods before _save_troops
p6_marker = '\n    def _save_troops(self):'
assert p6_marker in c, "P6 marker not found"
new_code = '''

    # ================================================================
    #  Troop Reordering
    # ================================================================

    def _reorder_troops(self, from_idx, to_idx):
        if from_idx == to_idx or min(from_idx, to_idx) < 0:
            return
        if max(from_idx, to_idx) >= len(self.troops_entries):
            return
        entry = self.troops_entries.pop(from_idx)
        field = self.troops_fields.pop(from_idx)
        self.troops_entries.insert(to_idx, entry)
        self.troops_fields.insert(to_idx, field)
        self._populate_list(self.search_var.get())
        self.selected_idx = to_idx
        self._show_detail()
        self._fill_equipment()
        self.status.config(text=u"\\u5175\\u79cd\\u5df2\\u79fb\\u52a8 (\\u672a\\u4fdd\\u5b58\\u5230\\u6587\\u4ef6)")

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
    #  Drag-and-Drop on Troop List
    # ================================================================

    def _on_drag_press(self, event):
        self._drag_start_y = event.y
        self._drag_start_idx = self.troop_lb.nearest(event.y)
        self._drag_threshold_passed = False

    def _on_drag_motion(self, event):
        if self._drag_start_idx < 0:
            return
        if abs(event.y - self._drag_start_y) < 10:
            return
        self._drag_threshold_passed = True
        cur = self.troop_lb.cget('cursor')
        if cur != 'hand2':
            self.troop_lb.config(cursor='hand2')

    def _on_drag_release(self, event):
        start = self._drag_start_idx
        start_y = self._drag_start_y
        self.troop_lb.config(cursor='')
        self._drag_start_idx = -1
        self._drag_start_y = -1
        if start < 0 or not self._drag_threshold_passed:
            self._drag_threshold_passed = False
            return
        self._drag_threshold_passed = False
        if abs(event.y - start_y) < 10:
            return
        target = self.troop_lb.nearest(event.y)
        if target < 0 or target == start or target >= len(self._list_index_map):
            return
        from_data = self._list_index_map[start]
        to_data = self._list_index_map[target]
        self._reorder_troops(from_data, to_data)
'''
c = c.replace(p6_marker, new_code + p6_marker, 1)
print "P6 OK"

with open(fpath, 'wb') as f:
    f.write(c)
print "DONE. New size:", len(c)
