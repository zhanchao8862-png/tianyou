# -*- coding: utf-8 -*-
"""Patch 3-6: move buttons + reorder methods. Patches 1-2 already applied."""
import os

fpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tianyou_editor.py')

with open(fpath, 'rb') as f:
    c = f.read()

print "Size:", len(c)

# Patch 3: add move buttons. Old: line with save_btn after delete button
# Correct byte sequence for "删除兵种" in UTF-8
p3_marker = b'\xe5\x88\xa0\xe9\x99\xa4\xe5\x85\xb5\xe7\xa7\x8d'  # 删除兵种
i = c.find(p3_marker)
assert i >= 0, "P3 marker not found at all"
# Find the end of this line
i_nl = c.find(b'\n', i)
assert i_nl >= 0
line_end = i_nl

# Find the save_btn line start
save_marker = b'\xe4\xbf\x9d  \xe5\xad\x98'  # 保  存
i_save = c.find(save_marker, line_end)
assert i_save >= 0
# Find the line before save_btn
save_line_start = c.rfind(b'\n', line_end, i_save) + 1

insert = b'''        self._btn_move_up = tk.Button(bf, text=u"\\u25b2", command=self._move_troop_up, width=2)
        self._btn_move_up.pack(side='left', padx=1)
        self._btn_move_down = tk.Button(bf, text=u"\\u25bc", command=self._move_troop_down, width=2)
        self._btn_move_down.pack(side='left', padx=1)
'''
c = c[:save_line_start] + insert + c[save_line_start:]
print "P3 OK"

# Patch 4: _set_ui_state add move buttons
p4_old = b'\n        for w in [self.troop_lb, self._btn_add_eq, self._btn_rm_eq, self._btn_clr_eq]:'
assert p4_old in c, "P4 old not found"
p4_new = b'\n        for w in [self.troop_lb, self._btn_add_eq, self._btn_rm_eq, self._btn_clr_eq,\n                  self._btn_move_up, self._btn_move_down]:'
c = c.replace(p4_old, p4_new, 1)
print "P4 OK"

# Patch 5: keyboard shortcuts
p5_old = b"\n        self.root.bind('<F5>', lambda e: self._reload())"
assert p5_old in c, "P5 old not found"
p5_new = p5_old + b"\n        self.root.bind('<Control-Up>', lambda e: self._move_troop_up())\n        self.root.bind('<Control-Down>', lambda e: self._move_troop_down())"
c = c.replace(p5_old, p5_new, 1)
print "P5 OK"

# Patch 6: new methods before _save_troops
p6_marker = b'\n    def _save_troops(self):'
assert p6_marker in c, "P6 marker not found"
new_code = b'''
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
