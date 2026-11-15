"""Pull one immutable export over authenticated SSH into HQ external storage."""
import argparse,base64,json,subprocess,shlex,zipfile,io,os
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--helper',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
if not Path('/Volumes/UFO-Work').is_mount():raise SystemExit('HQ SSD is unavailable')
code=Path(__file__).with_name('export_field.py').read_text()
r=subprocess.run(['/usr/bin/python3',a.helper,shlex.join(['/Users/ufo-field/ufo-field/venv/bin/python','-c',code])],check=True,stdout=subprocess.PIPE,timeout=600)
raw=base64.b64decode(r.stdout,validate=False)
a.output.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(io.BytesIO(raw)) as z:
 for name in z.namelist():
  dest=a.output/name
  if not dest.resolve().is_relative_to(a.output.resolve()):raise ValueError('Unsafe export path')
  dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(name))
print((a.output/'snapshot.json').read_text())
