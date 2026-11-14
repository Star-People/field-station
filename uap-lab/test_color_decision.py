import io,unittest
from PIL import Image
from color_decision import apply
class ColorTests(unittest.TestCase):
 def raw(self,color):
  im=Image.new('RGB',(16,16),color);out=io.BytesIO();im.save(out,format='PNG');return out.getvalue()
 def test_disabled_is_exact_identity_and_does_not_decode(self):
  p={'scores':{'anomalous':.7,'not_anomalous':.3}};self.assertIs(apply(p,b'not-an-image',{}),p)
 def test_vivid_color_can_boost_but_white_cannot(self):
  p={'scores':{'anomalous':.75,'not_anomalous':.25}};policy={'color_decision':{'color_evidence':True}}
  red=apply(p,self.raw('red'),policy);white=apply(p,self.raw('white'),policy)
  self.assertAlmostEqual(red['scores']['anomalous'],.85);self.assertEqual(white['scores'],p['scores']);self.assertEqual(red['color_evidence']['raw_anomaly_score'],.75)
 def test_isolated_color_noise_does_not_boost(self):
  im=Image.new('RGB',(16,16),'black');im.putpixel((8,8),(255,0,0));out=io.BytesIO();im.save(out,format='PNG');p={'scores':{'anomalous':.75,'not_anomalous':.25}}
  self.assertEqual(apply(p,out.getvalue(),{'color_decision':{'color_evidence':True}})['scores'],p['scores'])
 def test_multicolor_bonus_is_bounded(self):
  im=Image.new('RGB',(16,16),'red');im.paste('blue',(0,0,8,16));out=io.BytesIO();im.save(out,format='PNG');p={'scores':{'anomalous':.5,'not_anomalous':.5}}
  result=apply(p,out.getvalue(),{'color_decision':{'color_evidence':True,'color_score_boost':.2,'multicolor_score_boost':.2}})
  self.assertTrue(result['color_evidence']['multicolor']);self.assertAlmostEqual(result['scores']['anomalous'],.7)
