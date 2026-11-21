"""Estimated R100 full-width 16:9 field of view and its plan-view bearing envelope.

Canon R100 sensor width: 22.3 mm. Assumes landscape, level roll, no extra
movie crop or digital stabilization crop. A map wedge is not an aircraft match.
"""
import math

def field_of_view(config):
    focal=config.get('camera_focal_length_mm',100)
    if isinstance(focal,bool) or not isinstance(focal,(int,float)) or not math.isfinite(focal) or not 100<=focal<=400:focal=100
    elevation=config.get('camera_elevation_deg')
    if isinstance(elevation,bool) or not isinstance(elevation,(int,float)) or not math.isfinite(elevation) or not -90<=elevation<=90:elevation=None
    horizontal=22.3/(2*focal);vertical=horizontal*9/16
    pitch=math.radians(elevation or 0)
    forward=math.cos(pitch)-abs(math.sin(pitch))*vertical
    span=360 if forward<=0 else math.degrees(2*math.atan2(horizontal,forward))
    return dict(focal_length_mm=focal,horizontal_deg=math.degrees(2*math.atan(horizontal)),
                vertical_deg=math.degrees(2*math.atan(vertical)),azimuth_span_deg=span,
                elevation_deg=elevation,estimated=True)
