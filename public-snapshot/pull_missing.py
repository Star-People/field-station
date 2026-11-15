"""Fetch only thumbnails absent from the HQ frame mirror; no video downloads."""
import argparse,base64,io,json,shlex,subprocess,zipfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--helper',required=True);a=p.parse_args()
missing=set(json.loads((a.source/'missing-thumbnails.json').read_text()));rows=json.loads((a.source/'objects.json').read_text());targets=[(r['id'],r['image_url']) for r in rows if r['id'] in missing]
code='''import concurrent.futures,hashlib,urllib.request,io,zipfile,base64,json
from PIL import Image,ImageOps
from urllib.parse import urlsplit
pairs=TARGETS
failed=[]
def fetch(pair):
 key,url=pair
 try:
  u=urlsplit(url)
  if u.netloc or u.scheme or u.path not in ('/api/labeled-image','/api/label-queue/image'):raise ValueError('Invalid media route')
  with urllib.request.urlopen('http://127.0.0.1:8091'+url,timeout=8) as r:raw=r.read(8*1024*1024)
  with Image.open(io.BytesIO(raw)) as im:
   im=ImageOps.exif_transpose(im).convert('RGB');im.thumbnail((320,320));out=io.BytesIO();im.save(out,'WEBP',quality=78,exif=b'')
  return hashlib.sha256(key.encode()).hexdigest()+'.webp',out.getvalue()
 except Exception:failed.append(key);return None
out=io.BytesIO()
with zipfile.ZipFile(out,'w',zipfile.ZIP_STORED) as z:
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
  for item in pool.map(fetch,pairs):
   if item:z.writestr('media/'+item[0],item[1])
 z.writestr('unavailable-media.json',json.dumps(failed))
print(base64.b64encode(out.getvalue()).decode())
'''.replace('TARGETS',repr(targets))
r=subprocess.run(['/usr/bin/python3',a.helper,shlex.join(['/Users/ufo-field/ufo-field/venv/bin/python','-c',code])],check=True,stdout=subprocess.PIPE,timeout=900)
with zipfile.ZipFile(io.BytesIO(base64.b64decode(r.stdout))) as z:
 for name in z.namelist():
  dest=a.source/name
  if not dest.resolve().is_relative_to(a.source.resolve()):raise ValueError('Unsafe media path')
  dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(name))
print(json.dumps(dict(requested=len(targets),unavailable=len(json.loads((a.source/'unavailable-media.json').read_text())))))
