# -*- coding: utf-8 -*-
"""Plugin auto-discovery and loader for Tianyou Editor."""

import os
import sys

from ._base import BasePlugin


def discover_plugins():
    """Scan plugins/ directory for Python files (not starting with _) that
    define a class inheriting BasePlugin. Return a list of plugin instances."""
    plugins = []
    plugin_dir = os.path.dirname(os.path.abspath(__file__))

    # Guard: directory must exist (may be missing in PyInstaller bundle)
    if not os.path.isdir(plugin_dir):
        return plugins

    try:
        fnames = sorted(os.listdir(plugin_dir))
    except OSError:
        return plugins

    for fname in fnames:
        if fname.startswith('_') or not fname.endswith('.py'):
            continue
        mod_name = fname[:-3]
        try:
            mod = __import__('plugins.' + mod_name, fromlist=[mod_name])
        except Exception as e:
            print("[plugin] skip {}: {}".format(mod_name, e))
            continue

        for attr in dir(mod):
            obj = getattr(mod, attr)
            try:
                if obj is BasePlugin:
                    continue
                if isinstance(obj, type) and issubclass(obj, BasePlugin):
                    plugins.append(obj())
                    print("[plugin] loaded {} v{}".format(obj.name, obj.version))
            except TypeError:
                pass

    return plugins


def register_plugins(editor):
    """Instantiate all discovered plugins and call on_load."""
    plugins = discover_plugins()
    for p in plugins:
        p._editor = editor
        try:
            p.on_load(editor)
        except Exception as e:
            print("[plugin] {} on_load error: {}".format(p.name, e))
    return plugins
