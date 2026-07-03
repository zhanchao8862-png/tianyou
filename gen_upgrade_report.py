# -*- coding: utf-8 -*-
"""Generate detailed upgrade tree report"""
import sys, io, json

_real = sys.stdout
sys.stdout = io.StringIO()
sys.path.insert(0, 'C:/Users/Administrator/.qclaw/workspace-tfxjjhfnjialcuju/tianyou_editor')
import tianyou_editor
sys.stdout = _real

# Load saved tree
with open('upgrade_tree.json') as f:
    tree = json.load(f)

# Build parents map
parents = {}
for tid, info in tree.items():
    for target in [info['upgrade1'], info['upgrade2']]:
        if target and target != '0':
            parents.setdefault(target, []).append(tid)

roots = [tid for tid in tree if tid not in parents]
leafs = [tid for tid, info in tree.items() 
         if info['upgrade1'] == '0' and info['upgrade2'] == '0']
branches = [(tid, info) for tid, info in tree.items() 
            if info['upgrade1'] != '0' and info['upgrade2'] != '0']

# Build full upgrade tree chains
out = []
out.append('='*70)
out.append('Mount & Blade Warband - Ahao MOD Upgrade Tree Analysis')
out.append('='*70)
out.append('')
out.append('Summary:')
total = len(tree)
with_upgrade = sum(1 for v in tree.values() if v['upgrade1'] != '0' or v['upgrade2'] != '0')
out.append('  Total troops: %d' % total)
out.append('  With upgrades: %d' % with_upgrade)
out.append('  Roots (no parent): %d' % len(roots))
out.append('  Leafs (no children): %d' % len(leafs))
out.append('  Branches (2 children): %d' % len(branches))

# Build chains
out.append('')
out.append('-'*70)
out.append('Upgrade Chains (depth-first from roots)')
out.append('-'*70)

# Find unique chains (each troop only in one chain)
unvisited = set(tree.keys())
chains = []
for tid in roots:
    if tid not in unvisited:
        continue
    # Trace forward from root
    chain = []
    cur = tid
    visited = set()
    while cur and cur != '0' and cur not in visited:
        visited.add(cur)
        chain.append(cur)
        info = tree.get(cur, {})
        up1 = info.get('upgrade1', '0')
        up2 = info.get('upgrade2', '0')
        nxt = up2 if up2 != '0' else (up1 if up1 != '0' else None)
        cur = nxt
        if len(chain) > 20:
            break
    if len(chain) > 1:
        chains.append(chain)
        for c in chain:
            unvisited.discard(c)

# Sort chains by length (longest first)
chains.sort(key=len, reverse=True)
for i, chain in enumerate(chains[:50]):
    # Build display with names
    parts = []
    for tid in chain:
        info = tree.get(tid, {})
        name = info.get('name', tid)
        parts.append('%s(%s)' % (tid, name))
    out.append('  Chain %d (depth=%d):' % (i+1, len(chain)))
    out.append('    ' + ' -> '.join(parts))

# Also show recursive depth stats
out.append('')
out.append('-'*70)
out.append('Max Depth per Troop')
out.append('-'*70)

def max_depth(tid, visited=None):
    if visited is None:
        visited = set()
    if tid in visited or tid not in tree or tid == '0':
        return 0
    visited.add(tid)
    info = tree[tid]
    d1 = max_depth(info['upgrade1'], visited.copy()) if info['upgrade1'] != '0' else 0
    d2 = max_depth(info['upgrade2'], visited.copy()) if info['upgrade2'] != '0' else 0
    return 1 + max(d1, d2)

depths = [(tid, max_depth(tid)) for tid in tree]
depths.sort(key=lambda x: -x[1])
for tid, d in depths[:20]:
    info = tree[tid]
    out.append('  %s (%s) -> max depth %d' % (tid, info.get('name','?'), d))

with open('upgrade_tree_full_report.txt', 'w') as f:
    f.write('\n'.join(out))

print 'Saved upgrade_tree_full_report.txt'
print 'Chains found: %d' % len(chains)
print 'Longest chain depth: %d' % (len(chains[0]) if chains else 0)
print 'Top depths:'
for tid, d in depths[:10]:
    info = tree[tid]
    print '  %s (%s) -> %d' % (tid, info.get('name','?'), d)
