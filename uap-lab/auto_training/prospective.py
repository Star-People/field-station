"""Shared, label-blind recording holdout. Never delete source evidence.
Registry failures fail training closed; unrelated installations opt in via pointer.
Historical exposure is development data, never independent evaluation evidence.
"""
import hashlib,json,sqlite3,time
from pathlib import Path

def keys(row):
    aliases=row.get('group_aliases') or [row.get('generation') or row.get('group')]
    gs={'g:'+str(g).removeprefix('generation:').removeprefix('machine:') for g in aliases if g}
    pixel=row.get('pixel_sha256')
    if not gs or not pixel:return []
    return sorted(gs)+['p:'+pixel]

def partition(root,rows,exposed=False):
    pointer=Path(root)/'research-protocol.json'
    if not pointer.exists():return rows,dict(enabled=False)
    config=json.loads(pointer.read_text());db=Path(config['registry'])
    if not db.exists() and not exposed:raise ValueError('Research holdout registry missing; refusing unguarded training')
    con=sqlite3.connect(db,timeout=120)
    try:
        con.execute('BEGIN IMMEDIATE')
        con.execute('CREATE TABLE IF NOT EXISTS protocol (id INTEGER PRIMARY KEY CHECK(id=1), identity TEXT NOT NULL)')
        identity=json.dumps({k:config.get(k) for k in ('id','salt','holdout_percent','started_epoch')},sort_keys=True)
        saved=con.execute('SELECT identity FROM protocol WHERE id=1').fetchone()
        if saved and saved[0]!=identity:raise ValueError('Research protocol changed; create a new protocol instead of changing the held-out test')
        con.execute('INSERT OR IGNORE INTO protocol VALUES (1,?)',(identity,))
        con.execute('CREATE TABLE IF NOT EXISTS nodes (id TEXT PRIMARY KEY, role TEXT NOT NULL)')
        con.execute('CREATE TABLE IF NOT EXISTS edges (a TEXT,b TEXT,PRIMARY KEY(a,b))')
        parent={};roles={}
        def find(k):
            parent.setdefault(k,k)
            while parent[k]!=k:parent[k]=parent[parent[k]];k=parent[k]
            return k
        def link(a,b):parent[find(a)]=find(b)
        for k,role in con.execute('SELECT id,role FROM nodes'):parent[k]=k;roles[k]=role
        for a,b in con.execute('SELECT a,b FROM edges'):link(a,b)
        rowkeys=[keys(r) for r in rows]
        edges=[]
        for ks in rowkeys:
            for k in ks:find(k)
            for k in ks[1:]:link(ks[0],k);edges.append((ks[0],k))
            if exposed:
                for k in ks:roles[k]='exposed'
        components={}
        for k in parent:components.setdefault(find(k),[]).append(k)
        assigned={};component_ids={}
        for members in components.values():
            previous={roles[k] for k in members if k in roles};g=sorted(k for k in members if k.startswith('g:'))
            if 'quarantine' in previous or ('holdout' in previous and previous&{'exposed','development'}):role='quarantine'
            elif 'exposed' in previous:role='exposed'
            elif previous:role=next(iter(previous))
            elif not g:role='quarantine'
            else:role='holdout' if int(hashlib.sha256((config['salt']+g[0]).encode()).hexdigest()[:8],16)%100 < config['holdout_percent'] else 'development'
            component_id=hashlib.sha256('\n'.join(g).encode()).hexdigest()
            for k in members:assigned[k]=role;component_ids[k]=component_id
        con.executemany('INSERT INTO nodes VALUES (?,?) ON CONFLICT(id) DO UPDATE SET role=excluded.role',assigned.items())
        con.executemany('INSERT OR IGNORE INTO edges VALUES (?,?)',edges)
        kept=[];excluded=[]
        for row,ks in zip(rows,rowkeys):
            role=assigned[ks[0]] if ks else 'missing_provenance'
            if role in ('exposed','development'):kept.append(row)
            else:excluded.append(dict(component_group=component_ids.get(ks[0]) if ks else None,origin=row.get('origin',row.get('id')),role=role,pixel_sha256=row.get('pixel_sha256'),groups=[k[2:] for k in ks if k.startswith('g:')]))
        con.commit()
        return kept,dict(enabled=True,protocol=config['id'],checked=len(rows),included=len(kept),excluded=excluded,registry=str(db),scope='prospective recording holdout; historical or linked-to-training evidence is not independent')
    finally:con.close()
