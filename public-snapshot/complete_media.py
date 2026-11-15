"""Fill the small missing-media set without rescanning the entire training mirror."""
import argparse,hashlib,json,shutil
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
missing=set(json.loads((a.source/'missing-thumbnails.json').read_text()));path=a.output/'snapshot/objects.json';data=json.loads(path.read_text());fields={name:i for i,name in enumerate(data['fields'])}
for row in data['rows']:
 key=row[fields['id']]
 if key not in missing:continue
 name=hashlib.sha256(key.encode()).hexdigest()+'.webp';source=a.source/'media'/name
 if not source.is_file():continue
 shutil.copy2(source,a.output/'media'/name)
 for field in ('image_url','frame_url'):row[fields[field]]='/media/'+name
 missing.remove(key)
def save(path,value):
 temp=path.with_suffix('.next');temp.write_text(json.dumps(value,separators=(',',':'),allow_nan=False));temp.replace(path)
save(path,data);manifest=a.output/'snapshot/manifest.json';meta=json.loads(manifest.read_text());meta['missing_thumbnails']=len(missing);save(manifest,meta);save(a.source/'missing-thumbnails.json',sorted(missing));print(json.dumps(dict(remaining_missing_thumbnails=len(missing))))
