#!/usr/bin/env python3
"""Install the macOS county-only helper; OS location authorization remains interactive."""
import argparse,os,plistlib,subprocess
from pathlib import Path

def install(root):
    root=Path(root).resolve(strict=True)
    if not root.is_dir():raise ValueError('Station data volume must be mounted')
    cache=root/'station-location/build-cache';cache.mkdir(parents=True,exist_ok=True)
    app=Path.home()/'Applications/Field Station Location.app'
    exe=app/'Contents/MacOS/CoarseLocation';exe.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run(['swiftc',str(Path(__file__).with_name('CoarseLocation.swift')),'-module-cache-path',str(cache),'-o',str(exe),'-framework','AppKit','-framework','CoreLocation','-lsqlite3'],check=True)
    purpose='Automatically attach county and state to observations. The Field Station saves no coordinates or street addresses.'
    info=dict(CFBundleIdentifier='app.ufo-files.field.location',CFBundleName='Field Station Location',CFBundleDisplayName='Field Station Location',CFBundleExecutable='CoarseLocation',CFBundlePackageType='APPL',CFBundleVersion='1',LSUIElement=True,NSLocationUsageDescription=purpose,NSLocationWhenInUseUsageDescription=purpose)
    (app/'Contents/Info.plist').write_bytes(plistlib.dumps(info))
    subprocess.run(['codesign','--force','--sign','-',str(app)],check=True)
    label='app.ufo-files.field.location';domain='gui/'+str(os.getuid())
    agent=Path.home()/'Library/LaunchAgents'/(label+'.plist');agent.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run(['launchctl','bootout',domain+'/'+label],check=False,capture_output=True)
    agent.write_bytes(plistlib.dumps(dict(Label=label,ProgramArguments=[str(exe),str(root)],RunAtLoad=True,KeepAlive=True,ThrottleInterval=60,WorkingDirectory=str(Path.home()),StandardOutPath='/dev/null',StandardErrorPath='/dev/null',ProcessType='Background')))
    subprocess.run(['launchctl','bootstrap',domain,str(agent)],check=True)
    print('County-only location service installed. Allow Field Station Location in the macOS location prompt.')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--station-root',type=Path,required=True);a=p.parse_args();install(a.station_root)
