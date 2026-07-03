# -*- coding: utf-8 -*-
import os
import sys

here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)

lines = open(os.path.join(here, 'tianyou_editor.py'), 'r').readlines()
for i, l in enumerate(lines):
    if '_on_select' in l or '_on_troop_select' in l or '_selection_guard' in l:
        print('%d: %s' % (i+1, l.rstrip()))
