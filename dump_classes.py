#!/usr/bin/env python
# -*- coding: utf-8 -*-
import codecs, re
c = codecs.open(r'C:\Users\Administrator\.qclaw\workspace-tfxjjhfnjialcuju\tianyounew\tianyou_editor\tianyou_editor.py', 'r', 'utf-8').read()

# Find both TroopModule and ItemModule
for cls_name in ['TroopModule', 'ItemModule']:
    m = re.search(r'class ' + cls_name + r'\(EditorModule\)(.*?)(?=\nclass )', c, re.S)
    if m:
        with codecs.open(r'C:\Users\Administrator\.qclaw\workspace-tfxjjhfnjialcuju\tianyounew\tianyou_editor\%s.txt' % cls_name, 'w', 'utf-8') as f:
            for i, l in enumerate(m.group(0).split(u'\n')):
                f.write(u'%d: %s\n' % (i+1, l))
        print(cls_name, 'dumped')
