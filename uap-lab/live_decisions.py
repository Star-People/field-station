"""Classify exactly the complete RGB region shown to and labeled by a reviewer."""
import io
from PIL import Image
from binary_decision import decide
from night_context import predict
INPUT_CONTRACT='review-box-v1'

def prepare(raw,geometry):
 with Image.open(io.BytesIO(raw)) as source:
  image=source.convert('RGB')
  if geometry.get('context_size') and list(image.size)!=geometry['context_size']:raise ValueError('Saved review region dimensions changed')
  out=io.BytesIO();image.save(out,format='PNG');encoded=out.getvalue()
  return encoded,encoded,image.size

def classify(worker,images,contexts,geometries,policy,request_id):
 if not len(images)==len(contexts)==len(geometries):raise ValueError('Incomplete decision inputs')
 results=[]
 for start in range(0,len(images),32):
  # Context is already the primary image. No hidden subcrop or second-image veto.
  values=predict(worker,images[start:start+32],[],policy,f'{request_id}:{start}')
  if len(values)!=len(images[start:start+32]):raise ValueError('Incomplete model predictions')
  results.extend(dict(value,input_contract=INPUT_CONTRACT) for value in values)
 return results

def label(result,policy,size=None):
 if result.get('error'):raise ValueError(result['error'])
 # Minimum object size selects proposals before a review region is created.
 # It is not a veto on an already-existing, human-labeled review image.
 return decide(result['scores'],policy['thresholds']['anomalous'])
