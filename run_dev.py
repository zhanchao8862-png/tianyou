# -*- coding: utf-8 -*-
"""Development launcher with console output and traceback logging."""

import os
import sys
import traceback

os.environ['TIANYOU_DEBUG'] = '1'

from tianyou_editor import TianyouEditor


def main():
    app = TianyouEditor()
    app.run()


if __name__ == '__main__':
    try:
        main()
    except Exception:
        with open('run_dev_error.log', 'a') as f:
            f.write(traceback.format_exc())
        raise
