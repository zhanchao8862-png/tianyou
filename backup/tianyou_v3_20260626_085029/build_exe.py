# -*- coding: utf-8 -*-
"""Build tianyou_editor.py into a standalone EXE using PyInstaller 3.6 for Python 2.7"""

import os, sys, subprocess

SCRIPT = r'C:\Users\Administrator\.qclaw\workspace-tfxjjhfnjialcuju\tianyounew\tianyou_editor\tianyou_editor.py'
OUTDIR = r'C:\Users\Administrator\.qclaw\workspace-tfxjjhfnjialcuju\tianyounew\tianyou_editor\dist'
NAME = 'tianyou_editor'
ICON = None  # Optional: r'path\to\icon.ico'

cmd = [
    sys.executable.replace('python.exe', 'Scripts\\pyinstaller.exe'),
    '--onefile',
    '--windowed',
    '--name', NAME,
    '--distpath', OUTDIR,
    '--clean',
    '--noconfirm',
    SCRIPT,
]

print 'Running:', ' '.join(cmd)
print

ret = subprocess.call(cmd)
if ret == 0:
    exe = os.path.join(OUTDIR, NAME + '.exe')
    if os.path.isfile(exe):
        sz = os.path.getsize(exe)
        print '\nBuild SUCCESS!'
        print 'Output:', exe
        print 'Size:', sz, 'bytes (%.1f MB)' % (sz / 1048576.0)
    else:
        print '\nBuild completed but EXE not found at', exe
else:
    print '\nBuild FAILED with code', ret
