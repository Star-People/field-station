"""Publish a validated generated snapshot on its own branch; never push app source."""
import argparse,json,subprocess,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--site',type=Path,required=True);p.add_argument('--repo',default='starpeopleai/field-station');a=p.parse_args();site=a.site.resolve()
if not str(site).startswith('/Volumes/') or not Path('/Volumes/UFO-Work').is_mount():raise SystemExit('External snapshot storage unavailable')
manifest=json.loads((site/'snapshot/manifest.json').read_text())
if not manifest.get('objects') or manifest.get('missing_thumbnails'):raise SystemExit('Snapshot is incomplete; previous publication preserved')
if sum(p.stat().st_size for p in site.rglob('*') if p.is_file() and '.git' not in p.parts)>800*1024**2:raise SystemExit('Snapshot exceeds publication budget')
def run(*args):return subprocess.run(args,cwd=site,check=True,stdout=subprocess.PIPE,text=True).stdout
if not (site/'.git').exists():
 run('git','init','-b','public-snapshot');run('git','remote','add','origin','https://github.com/'+a.repo+'.git')
run('git','config','user.name','ufo-files');run('git','config','user.email','297273897+ufo-files@users.noreply.github.com')
if run('git','branch','--show-current').strip()!='public-snapshot':raise SystemExit('Wrong publication branch')
run('git','add','--all')
changed=subprocess.run(['git','diff','--cached','--quiet'],cwd=site).returncode!=0
old=run('git','rev-parse','HEAD').strip() if subprocess.run(['git','rev-parse','--verify','HEAD'],cwd=site,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0 else None
if changed:
 tree=run('git','write-tree').strip()
 commit=run('git','commit-tree',tree,'-m','Public Field Station snapshot '+time.strftime('%Y-%m-%d %H:%M UTC',time.gmtime(manifest['captured_epoch']))).strip()
 args=['git','update-ref','refs/heads/public-snapshot',commit]
 if old:args.append(old)
 run(*args)
else:commit=old
tracking=subprocess.run(['git','rev-parse','--verify','refs/remotes/origin/public-snapshot'],cwd=site,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
expected=tracking.stdout.strip() if tracking.returncode==0 else ''
if commit==expected:print('Snapshot unchanged');raise SystemExit(0)
run('git','push','--force-with-lease=refs/heads/public-snapshot:'+expected,'origin',commit+':refs/heads/public-snapshot')
# This repository contains generated output only. Do not accumulate raw snapshot history.
run('git','reflog','expire','--expire=now','--all');run('git','gc','--prune=now')
print(json.dumps(dict(published=True,objects=manifest['objects'],commit=commit)))
