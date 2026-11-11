#!/usr/bin/env python3
"""Package a tested isolated core with a small native local-files launcher."""
import argparse
import json
import plistlib
import subprocess
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
WORK=ROOT/'work/local-editor-20261105'
EXTENSIONS=['doc','docx','docm','dot','dotx','dotm','wps','wpt',
            'xls','xlsx','xlsm','xlt','xltx','xltm','et','ett',
            'ppt','pptx','pptm','pot','potx','potm','pps','ppsx','ppsm','dps','dpt',
            'rtf','txt','csv','pdf']


def run(args):
    subprocess.run([str(x) for x in args],check=True)


def package(candidate, label, standalone=False):
    source=WORK/candidate/'HaihomeLocal.app'
    icon=Path(__file__).parent/'assets/HaihomeLocalDocuments.icns'
    if not icon.is_file() or icon.read_bytes()[:4] != b'icns':
        raise SystemExit('Missing or invalid local document app icon')
    run(['codesign','--verify','--deep','--strict',source])
    app=WORK/label/'海家本地文档.app'
    if app.parent.exists():raise SystemExit('Use a new output label')
    c=app/'Contents'
    for directory in ['MacOS','Resources/Templates','SharedSupport']:
        (c/directory).mkdir(parents=True,exist_ok=True)
    run(['cp','-cR',source,c/'SharedSupport/HaihomeEditor.app'])
    run(['swiftc','-O','-target','arm64-apple-macos12.0',Path(__file__).parent/'LocalDocuments.swift',
         '-o',c/'MacOS/HaihomeLocalDocuments'])
    folder=None if standalone else WORK/'我的文档'
    if folder:folder.mkdir(exist_ok=True)
    info={'CFBundleIdentifier':'com.haihome.localdocuments','CFBundleName':'海家本地文档',
          'CFBundleDisplayName':'海家本地文档','CFBundleExecutable':'HaihomeLocalDocuments',
          'CFBundlePackageType':'APPL','CFBundleShortVersionString':'0.1.1',
          'CFBundleVersion':'2','CFBundleIconFile':'HaihomeLocalDocuments.icns',
          'LSMinimumSystemVersion':'12.0','NSHighResolutionCapable':True,
          'NSPrincipalClass':'NSApplication',
          'CFBundleDocumentTypes':[{'CFBundleTypeName':'Local Office Document',
            'CFBundleTypeRole':'Editor','LSHandlerRank':'Alternate',
            'CFBundleTypeExtensions':EXTENSIONS}]}
    if folder:info['HaihomeDefaultFolder']=str(folder)
    (c/'Info.plist').write_bytes(plistlib.dumps(info,sort_keys=False))
    shutil.copy2(icon,c/'Resources/HaihomeLocalDocuments.icns')
    templates=c/'Resources/Templates'
    for ext in ['docx','xlsx','pptx']:
        shutil.copy2(Path(__file__).parent/'templates'/('blank.'+ext),templates/('blank.'+ext))
    ent={'com.apple.security.app-sandbox':True,
         'com.apple.security.files.user-selected.read-write':True,
         'com.apple.security.files.bookmarks.app-scope':True,
         'com.apple.security.temporary-exception.files.absolute-path.read-write':[str(WORK)+'/']}
    ep=app.parent/'launcher.entitlements.plist';ep.write_bytes(plistlib.dumps(ent))
    if standalone:
        ent.pop('com.apple.security.temporary-exception.files.absolute-path.read-write',None)
        ep.write_bytes(plistlib.dumps(ent))
    run(['codesign','--force','--sign','-','--timestamp=none','--options','runtime',
         '--identifier','com.haihome.localdocuments','--entitlements',ep,app])
    run(['codesign','--verify','--deep','--strict',app])
    (app.parent/'package-manifest.json').write_text(json.dumps({'app':str(app),
        'core_source':str(source),'bundle_id':info['CFBundleIdentifier'],
        'version':info['CFBundleShortVersionString'],'icon':info['CFBundleIconFile'],
        'standalone':standalone,'default_folder':str(folder) if folder else 'app-container/Documents/海家本地文档',
        'signature_verification':'passed'},ensure_ascii=False,indent=2)+'\n')
    print(app)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('candidate');p.add_argument('label')
    p.add_argument('--standalone',action='store_true')
    p.add_argument('--output-root',type=Path)
    a=p.parse_args()
    if a.output_root:WORK=a.output_root.expanduser().resolve()
    package(a.candidate,a.label,a.standalone)
