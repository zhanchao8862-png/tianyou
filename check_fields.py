# -*- coding: utf-8 -*-
import sys, io
_real = sys.stdout
sys.stdout = io.StringIO()
sys.path.insert(0, 'C:/Users/Administrator/.qclaw/workspace-tfxjjhfnjialcuju/tianyou_editor')
import tianyou_editor
sys.stdout = _real

src = 'G:/1_ruanjian/game/qikan/Mount&Blade Warband/Modules/Ahao/Module_system 1.171/module_troops.py'
header, entries, footer = tianyou_editor.parse_array_by_lines(src, 'troops')
fields_list = [tianyou_editor.parse_fields_in_entry(e) for e in entries[:10]]

for i, flds in enumerate(fields_list):
    tid = flds[0].strip(chr(34)+chr(39)) if flds else '?'
    print '--- Entry %d (%s) fields=%d ---' % (i, tid, len(flds))
    for j, f in enumerate(flds):
        print '  [%d] %s' % (j, f[:80])
    print
