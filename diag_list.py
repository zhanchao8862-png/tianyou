# -*- coding: utf-8 -*-
import sys, os
os.chdir(r'C:\Users\Administrator\.qclaw\workspace-tfxjjhfnjialcuju\tianyounew\tianyou_editor')
sys.path.insert(0, os.getcwd())
import tianyou_editor as M

app = M.TianyouEditor()
app.root.update_idletasks()

# Check if MOD path is set
print("mod_path:", repr(app.mod_path))
print("source_path:", repr(app.source_path))

if app.mod_path and os.path.isdir(app.mod_path):
    print("\n--- Triggering auto_load ---")
    app._auto_load()
    app.root.update_idletasks()
    app.root.after(100)  # wait for async
    app.root.update_idletasks()
    app.root.update()
    app.root.update_idletasks()

# Check routing
print("\n_troop_module.troops_entries count:", len(app._troop_module.troops_entries))
print("_troop_module._loaded:", app._troop_module._loaded)
print("_troop_module._built:", app._troop_module._built)
print("_troop_module.panel is not None:", app._troop_module.panel is not None)
print("_troop_module.troop_lb:", app._troop_module.troop_lb is not None)

if app._troop_module.troop_lb is not None:
    size = app._troop_module.troop_lb.size()
    print("troop_lb size:", size)
    if size > 0:
        print("troop_lb items[0]:", app._troop_module.troop_lb.get(0))
    else:
        print("troop_lb EMPTY!")

# Check if panel contains troop_lb as a child
if app._troop_module.panel:
    children = []
    def collect(w):
        children.append(w)
        for c in w.winfo_children():
            collect(c)
    collect(app._troop_module.panel)
    listboxes = [w for w in children if 'listbox' in str(type(w)).lower()]
    print("Listboxes in panel:", len(listboxes))
    for lb in listboxes:
        print("  Listbox size:", lb.size())
        if lb.size() > 0:
            print("  Listbox[0]:", lb.get(0))

app.root.destroy()
print("\nDONE")
