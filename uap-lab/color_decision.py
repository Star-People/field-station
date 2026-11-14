"""Optional color evidence bonus; never calls a colored object anomalous alone."""
import io,math
import numpy as np
from PIL import Image
DEFAULTS=dict(color_evidence=False,color_score_boost=.1,multicolor_score_boost=.05,minimum_color_saturation=.45,minimum_color_fraction=.2,minimum_color_diversity=.2,minimum_colored_pixels=8,color_brightness_floor=.15,color_foreground_quantile=.65,color_clipping_limit=.95,color_analysis_size=128,color_bonus_cap=.2)

def features(raw,minimum_saturation=.45,settings=None):
 rule={**DEFAULTS,**(settings or {})}
 with Image.open(io.BytesIO(raw)) as source:
  image=source.convert('RGB');image.thumbnail((int(rule['color_analysis_size']),int(rule['color_analysis_size'])));rgb=np.asarray(image,dtype=np.float32)/255
 maximum=rgb.max(axis=2);minimum=rgb.min(axis=2);saturation=(maximum-minimum)/np.maximum(maximum,1e-6)
 # Exclude black background, near-white clipping, and isolated colored pixels.
 foreground=(maximum>=max(rule['color_brightness_floor'],float(np.quantile(maximum,rule['color_foreground_quantile']))))&(minimum<rule['color_clipping_limit'])
 bright=int(foreground.sum());colored=foreground&(saturation>=minimum_saturation);count=int(colored.sum())
 diversity=0.
 if count>=rule['minimum_colored_pixels']:
  hsv=np.asarray(image.convert('HSV'),dtype=np.float32)/255;hues=hsv[:,:,0][colored]
  resultant=abs(np.exp(2j*np.pi*hues).mean());diversity=float(1-resultant)
 return dict(bright_pixels=bright,colored_pixels=count,colored_fraction=count/bright if bright else 0.,diversity=diversity)

def apply(prediction,raw,policy):
 rule=dict(DEFAULTS,**policy.get('color_decision',{}))
 if not rule['color_evidence'] or prediction.get('error'):return prediction
 stats=features(raw,rule['minimum_color_saturation'],rule);qualified=stats['colored_pixels']>=rule['minimum_colored_pixels'] and stats['colored_fraction']>=rule['minimum_color_fraction'];multicolor=qualified and stats['diversity']>=rule['minimum_color_diversity']
 raw_score=prediction['scores']['anomalous'];bonus=min(rule['color_bonus_cap'],(rule['color_score_boost'] if qualified else 0.)+(rule['multicolor_score_boost'] if multicolor else 0.));score=min(1.,raw_score+bonus)
 return dict(prediction,scores=dict(anomalous=score,not_anomalous=1-score),color_evidence=dict(stats,qualified=qualified,multicolor=multicolor,raw_anomaly_score=raw_score,bonus=bonus,rule=rule))
