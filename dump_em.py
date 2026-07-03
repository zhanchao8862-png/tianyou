#!/usr/bin/env python
# -*- coding: utf-8 -*-
import codecs, re
c = codecs.open(r'C:\Users\Administrator\.qclaw\workspace-tfxjjhfnjialcuju\tianyounew\tianyou_editor\tianyou_editor.py', 'r', 'utf-8').read()
m = re.search(r'class EditorModule.*?(?=\nclass )', c, re.S)
if m:
    with codecs.open(r'C:\Users\Administrator\.qclaw\workspace-tfxjjhfnjialcuju\tianyounew\tianyou_editor\em_dump.txt', 'w', 'utf-8') as f:
        for i, l in enumerate(m.group(0).split(u'\n')):
            f.write(u'%d: %s\n' % (i+1, l))
    print('done')
