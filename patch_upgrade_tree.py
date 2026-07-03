# -*- coding: utf-8 -*-
"""
Patch for upgrade tree optimization
- Add searchable combobox for upgrade selection
- Add upgrade tree visualization (parents and children)
"""

# New code to insert after the imports section (around line 50)

SEARCHABLE_COMBOBOX_CODE = '''
class SearchableCombobox:
    """A searchable combobox widget with dropdown list."""
    
    def __init__(self, parent, width=40, height=10):
        self.parent = parent
        self.width = width
        self.height = height
        self.all_items = []  # (id, display_name)
        self.filtered_items = []
        self.on_select_callback = None
        
        # Create frame
        self.frame = tk.Frame(parent)
        
        # Entry for search
        self.var = tk.StringVar()
        self.entry = tk.Entry(self.frame, textvariable=self.var, width=width)
        self.entry.pack(fill='x')
        
        # Dropdown button
        self.btn = tk.Button(self.frame, text='▼', width=2, command=self._toggle_dropdown)
        self.btn.pack(side='right')
        
        # Dropdown window (Toplevel)
        self.dropdown = None
        self.listbox = None
        
        # Bind events
        self.var.trace('w', self._on_search)
        self.entry.bind('<FocusIn>', self._on_focus_in)
        self.entry.bind('<Key-Return>', self._on_enter)
        self.entry.bind('<Key-Down>', self._on_key_down)
        
    def set_items(self, items):
        """Set all available items. items: list of (id, display_name)"""
        self.all_items = items
        self.filtered_items = list(items)
        
    def set_value(self, value):
        """Set current value (id)"""
        self.var.set(value)
        
    def get_value(self):
        """Get current value (id)"""
        val = self.var.get().strip()
        # Extract ID from "id (name)" format
        if ' (' in val:
            return val.split(' (')[0]
        return val
        
    def set_on_select(self, callback):
        """Set callback when item selected. callback(item_id)"""
        self.on_select_callback = callback
        
    def _on_search(self, *args):
        """Filter items based on search text"""
        search = self.var.get().lower()
        if not search:
            self.filtered_items = list(self.all_items)
        else:
            self.filtered_items = [
                item for item in self.all_items
                if search in item[0].lower() or search in item[1].lower()
            ]
        if self.listbox:
            self._update_listbox()
            
    def _update_listbox(self):
        """Update listbox with filtered items"""
        if not self.listbox:
            return
        self.listbox.delete(0, 'end')
        for item_id, display in self.filtered_items:
            self.listbox.insert('end', display)
            
    def _toggle_dropdown(self):
        """Show/hide dropdown"""
        if self.dropdown and self.dropdown.winfo_exists():
            self._hide_dropdown()
        else:
            self._show_dropdown()
            
    def _show_dropdown(self):
        """Show dropdown window"""
        if not self.dropdown or not self.dropdown.winfo_exists():
            self.dropdown = tk.Toplevel(self.parent)
            self.dropdown.overrideredirect(True)
            self.dropdown.transient(self.parent)
            
            # Position below entry
            x = self.entry.winfo_rootx()
            y = self.entry.winfo_rooty() + self.entry.winfo_height()
            self.dropdown.geometry('%dx%d+%d+%d' % (self.width * 8, self.height * 20, x, y))
            
            # Listbox with scrollbar
            frame = tk.Frame(self.dropdown)
            frame.pack(fill='both', expand=1)
            
            scrollbar = tk.Scrollbar(frame)
            scrollbar.pack(side='right', fill='y')
            
            self.listbox = tk.Listbox(frame, width=self.width, height=self.height,
                                      yscrollcommand=scrollbar.set)
            self.listbox.pack(side='left', fill='both', expand=1)
            scrollbar.config(command=self.listbox.yview)
            
            self._update_listbox()
            
            # Bind selection
            self.listbox.bind('<ButtonRelease-1>', self._on_select)
            self.listbox.bind('<Key-Return>', self._on_select)
            self.listbox.bind('<Key-Escape>', lambda e: self._hide_dropdown())
            
            # Focus
            self.listbox.focus_set()
            
            # Click outside to close
            self.dropdown.bind('<FocusOut>', lambda e: self._hide_dropdown())
            
    def _hide_dropdown(self):
        """Hide dropdown window"""
        if self.dropdown and self.dropdown.winfo_exists():
            self.dropdown.destroy()
            self.dropdown = None
            self.listbox = None
            
    def _on_select(self, event=None):
        """Handle item selection"""
        if not self.listbox:
            return
        selection = self.listbox.curselection()
        if selection:
            idx = selection[0]
            if idx < len(self.filtered_items):
                item_id, display = self.filtered_items[idx]
                self.var.set(item_id)
                if self.on_select_callback:
                    self.on_select_callback(item_id)
        self._hide_dropdown()
        
    def _on_focus_in(self, event):
        """Select all text on focus"""
        self.entry.select_range(0, 'end')
        
    def _on_enter(self, event):
        """Handle Enter key - select first match"""
        if self.filtered_items:
            item_id, display = self.filtered_items[0]
            self.var.set(item_id)
            if self.on_select_callback:
                self.on_select_callback(item_id)
        self._hide_dropdown()
        
    def _on_key_down(self, event):
        """Handle Down key - open dropdown"""
        self._show_dropdown()
        if self.listbox and self.filtered_items:
            self.listbox.selection_set(0)
            self.listbox.activate(0)


'''

# Code to replace Section 8 (around line 1165)
# Original:
'''
        # ── Section 8: Upgrade Tree (F14/F15) ──
        s8 = tk.LabelFrame(f, text=u"F14/F15 升级树 (Upgrade)", font=('', 10, 'bold'))
        s8.pack(fill='x', padx=5, pady=3)
        for key, label in [('upgrade1', u'F14 升级到1'), ('upgrade2', u'F15 升级到2')]:
            row = tk.Frame(s8)
            row.pack(fill='x', padx=5, pady=1)
            tk.Label(row, text=label + ':', width=14, anchor='w').pack(side='left')
            self._detail_vars[key] = tk.StringVar()
            tk.Entry(row, textvariable=self._detail_vars[key], width=40).pack(side='left', fill='x', expand=1, padx=(5,0))
'''

# New Section 8 code:
NEW_SECTION_8 = '''
        # ── Section 8: Upgrade Tree (F14/F15) ──
        s8 = tk.LabelFrame(f, text=u"F14/F15 升级树 (Upgrade)", font=('', 10, 'bold'))
        s8.pack(fill='x', padx=5, pady=3)
        
        # Upgrade tree visualization
        self._upgrade_tree_frame = tk.Frame(s8)
        self._upgrade_tree_frame.pack(fill='x', padx=5, pady=2)
        
        # Parents (who upgrades to this troop)
        self._parents_lbl = tk.Label(self._upgrade_tree_frame, text=u'被升级: -', 
                                     fg='#0066cc', font=('', 9), anchor='w')
        self._parents_lbl.pack(fill='x')
        
        # Children (who this troop upgrades to)
        self._children_lbl = tk.Label(self._upgrade_tree_frame, text=u'可升级: -',
                                      fg='#009900', font=('', 9), anchor='w')
        self._children_lbl.pack(fill='x')
        
        # Separator
        tk.Frame(s8, height=1, bg='#ccc').pack(fill='x', padx=5, pady=3)
        
        # Upgrade selection with searchable combobox
        self._upgrade_combos = {}
        for key, label in [('upgrade1', u'F14 升级到1'), ('upgrade2', u'F15 升级到2')]:
            row = tk.Frame(s8)
            row.pack(fill='x', padx=5, pady=1)
            tk.Label(row, text=label + ':', width=14, anchor='w').pack(side='left')
            
            # Use searchable combobox
            combo = SearchableCombobox(row, width=35, height=8)
            combo.frame.pack(side='left', fill='x', expand=1, padx=(5,0))
            self._upgrade_combos[key] = combo
            
            # Clear button
            tk.Button(row, text='✕', width=2, 
                     command=lambda k=key: self._clear_upgrade(k)).pack(side='left', padx=(2,0))
            
            # Jump button
            tk.Button(row, text='→', width=2,
                     command=lambda k=key: self._jump_to_upgrade(k)).pack(side='left', padx=(2,0))
'''

# Methods to add to TianyouEditor class

BUILD_UPGRADE_ITEMS_METHOD = '''
    def _build_upgrade_items(self):
        """Build list of (troop_id, display_name) for upgrade comboboxes."""
        items = [('0', '0 (无)')]
        for i, flds in enumerate(self.troops_fields):
            if len(flds) > 0:
                tid = flds[0].strip('"\'')
                name = flds[1].strip('"\'') if len(flds) > 1 else ''
                cn = self.troop_cn.get(tid, '')
                if cn:
                    display = '%s (%s / %s)' % (tid, name, cn)
                else:
                    display = '%s (%s)' % (tid, name)
                items.append((tid, display))
        return items
'''

UPDATE_UPGRADE_TREE_METHOD = '''
    def _update_upgrade_tree(self, idx):
        """Update upgrade tree visualization for troop at idx."""
        if idx < 0 or idx >= len(self.troops_fields):
            self._parents_lbl.config(text=u'被升级: -')
            self._children_lbl.config(text=u'可升级: -')
            return
            
        flds = self.troops_fields[idx]
        if len(flds) < 1:
            return
        current_tid = flds[0].strip('"\'')
        
        # Find parents (troops that upgrade to current)
        parents = []
        for i, other_flds in enumerate(self.troops_fields):
            if len(other_flds) < 16:
                continue
            other_tid = other_flds[0].strip('"\'')
            up1 = other_flds[14].strip('"\'') if len(other_flds) > 14 else '0'
            up2 = other_flds[15].strip('"\'') if len(other_flds) > 15 else '0'
            if up1 == current_tid or up2 == current_tid:
                parents.append(other_tid)
                
        # Find children (troops that current upgrades to)
        children = []
        up1 = flds[14].strip('"\'') if len(flds) > 14 else '0'
        up2 = flds[15].strip('"\'') if len(flds) > 15 else '0'
        if up1 and up1 != '0':
            children.append(up1)
        if up2 and up2 != '0':
            children.append(up2)
            
        # Update labels
        if parents:
            parent_text = u'被升级: ' + ', '.join(parents[:5])
            if len(parents) > 5:
                parent_text += '...'
            self._parents_lbl.config(text=parent_text)
        else:
            self._parents_lbl.config(text=u'被升级: (无)')
            
        if children:
            child_text = u'可升级: ' + ', '.join(children)
            self._children_lbl.config(text=child_text)
        else:
            self._children_lbl.config(text=u'可升级: (无)')
'''

CLEAR_UPGRADE_METHOD = '''
    def _clear_upgrade(self, key):
        """Clear upgrade field."""
        if key in self._upgrade_combos:
            self._upgrade_combos[key].set_value('0')
'''

JUMP_TO_UPGRADE_METHOD = '''
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
'''

# Code to modify _show_detail method (around line 1330)
# Add after loading upgrades:
'''
        # F14-F15: upgrades
        self._detail_vars['upgrade2'].set(flds[14] if len(flds) > 14 else '0')
        self._detail_vars['upgrade1'].set(flds[15] if len(flds) > 15 else '0')
'''
# Replace with:
'''
        # F14-F15: upgrades - update combobox items and values
        upgrade_items = self._build_upgrade_items()
        for key in ['upgrade1', 'upgrade2']:
            if key in self._upgrade_combos:
                self._upgrade_combos[key].set_items(upgrade_items)
                val = flds[15] if key == 'upgrade1' and len(flds) > 15 else (flds[14] if len(flds) > 14 else '0')
                self._upgrade_combos[key].set_value(val.strip('"\''))
        
        # Update upgrade tree visualization
        self._update_upgrade_tree(idx)
'''

# Code to modify _apply_detail_changes method (around line 1410)
# Replace:
'''
        # F14-F15: upgrades
        flds[14] = self._detail_vars['upgrade2'].get().strip() or '0'
        flds[15] = self._detail_vars['upgrade1'].get().strip() or '0'
'''
# With:
'''
        # F14-F15: upgrades
        up1 = self._upgrade_combos['upgrade1'].get_value() if 'upgrade1' in self._upgrade_combos else '0'
        up2 = self._upgrade_combos['upgrade2'].get_value() if 'upgrade2' in self._upgrade_combos else '0'
        flds[15] = up1 if up1 else '0'
        flds[14] = up2 if up2 else '0'
'''

print("Patch definitions loaded successfully.")
print("\nTo apply patch manually:")
print("1. Insert SearchableCombobox class after imports")
print("2. Replace Section 8 with NEW_SECTION_8")
print("3. Add _build_upgrade_items, _update_upgrade_tree, _clear_upgrade, _jump_to_upgrade methods")
print("4. Modify _show_detail to use comboboxes")
print("5. Modify _apply_detail_changes to read from comboboxes")
