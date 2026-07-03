#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Compatibility wrapper for applying the v2 patch script."""

from __future__ import print_function

import os
import runpy


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    target = os.path.join(here, 'patch_all.py')
    if not os.path.exists(target):
        raise SystemExit('patch_all.py not found: %s' % target)
    runpy.run_path(target, run_name='__main__')


if __name__ == '__main__':
    main()
