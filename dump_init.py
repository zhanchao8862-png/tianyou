#!/usr/bin/env python
# -*- coding: utf-8 -*-
import codecs
c = codecs.open(r'C:\Users\Administrator\.qclaw\workspace-tfxjjhfnjialcuju\tianyounew\tianyou_editor\tianyou_editor.py', 'r', 'utf-8').read()
lines = c.split(u'\n')
with codecs.open(r'C:\Users\Administrator\.qclaw\workspace-tfxjjhfnjialcuju\tianyounew\tianyou_editor\init_dump.txt', 'w', 'utf-8') as f:
    for i in range(924, 1080):
        f.write(u'%d: %s\n' % (i+1, lines[i]))
print("done")
