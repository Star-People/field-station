import io,sys,unittest,tempfile,json,hashlib
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import numpy as np
base=Path(__file__).resolve().parent;sys.path[:0]=[str(base),str(base/'recognition'),str(base/'auto_training')]
from live_decisions import prepare,classify,label
from model_test_worker import score
from benchmark_context import collect
from crop_geometry import review_region
from recognition_alerts import render_screenshot
class Tests(unittest.TestCase):
 def test_entire_visible_box_is_classified_not_hidden_tiny_proposal(self):
  image=Image.new('RGB',(64,64));image.putpixel((5,5),(255,0,0));image.putpixel((30,40),(255,255,255));out=io.BytesIO();image.save(out,format='PNG');raw=out.getvalue()
  geometry=dict(scope='detection_context',context_size=[64,64],box=[28,38,6,8],captured_epoch=1794500000)
  encoded,context,size=prepare(raw,geometry);self.assertEqual(size,(64,64));self.assertEqual(Image.open(io.BytesIO(encoded)).tobytes(),image.tobytes())
  calls=[]
  class Worker:
   def predict(self,images,request):
    calls.append(request);self_image=Image.open(io.BytesIO(images[0]));assert self_image.getpixel((5,5))==(255,0,0)
    return [dict(scores=dict(anomalous=.99,not_anomalous=.01)) for _ in images]
  policy=dict(version='v',input_color_space='RGB',thresholds={'anomalous':.85},minimum_native_size=10,night_context_confirmation=dict(enabled=True,version='v',minimum_context_score=.001))
  result=classify(Worker(),[encoded],[context],[geometry],policy,'test')[0]
  self.assertEqual(len(calls),1);self.assertEqual(label(result,policy,(6,8)),'anomalous');self.assertEqual(result['input_contract'],'review-box-v1')
  from classification_policy import eligible
  self.assertFalse(eligible(dict(box=[28,38,6,8]),policy)) # Proposal filtering is separate from classification of an existing box.
 def test_live_pixels_equal_saved_review_and_training_pixels_at_edges(self):
  frame=np.arange(100*120*3,dtype=np.uint8).reshape(100,120,3)
  with tempfile.TemporaryDirectory() as tmp:
   for bounds in ([0,0,6,8],[110,90,6,8],[40,40,8,12]):
    pixels,box=review_region(frame,bounds);path=Path(tmp)/'view.png';actual=render_screenshot(frame,bounds,path)
    self.assertEqual(box,actual)
    with Image.open(path.with_name('native-object.png')) as saved:self.assertEqual(saved.convert('RGB').tobytes(),pixels.tobytes())
 def test_current_pixels_and_labels_required_but_hidden_geometry_not_required(self):
  with tempfile.TemporaryDirectory() as d:
   data=Path(d)/'uap-lab';aid='a'*32;folder=data/'email-reviews/examples'/aid;folder.mkdir(parents=True)
   out=io.BytesIO();im=Image.new('RGB',(64,64));im.save(out,format='PNG');raw=out.getvalue();(folder/'native-object.png').write_bytes(raw)
   record=dict(event_id=aid,human_confirmed=True,label='not_anomalous',bounds=[0,0,64,64],native_crop_sha256=hashlib.sha256(raw).hexdigest());(folder/'review.json').write_text(json.dumps(record))
   row=dict(origin='email:'+aid,label='not_anomalous',pixel_sha256=hashlib.sha256(b'64x64:RGB:'+im.tobytes()).hexdigest())
   self.assertEqual(collect(data,[row])[0]['geometry']['scope'],'review_box');self.assertIn('excluded',collect(data,[dict(row,label='anomalous')])[0])
if __name__=='__main__':unittest.main()
