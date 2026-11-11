#!/usr/bin/env python3
"""Build a version-pinned, isolated personal WPS local-editor experiment.

Never modifies /Applications or the source snapshot. Not a license patch.
"""
import argparse
import hashlib
import json
import plistlib
import re
import shutil
import struct
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'work/archive-20261105.noindex/debloat-20261105/source/wpsoffice.app'
WORK = ROOT / 'work/local-editor-20261105'
OLD_ID = 'com.kingsoft.wpsoffice.mac'
NEW_ID = 'com.haihome.wpslocal.macos'
EXPECTED_MAIN = 'ba9b1f18a0948bb3eee3265a18a15ba105553a31185f7bfdd74e17719bbc02b1'
FALSE_RET = bytes.fromhex('00008052c0035fd6')
TRUE_RET = bytes.fromhex('20008052c0035fd6')

# Optional features: removal is limited to these named addon directories.
REMOVE_RE = re.compile(r'^(?:kai.*|k.*copilot.*|k.*aigc.*|kwpsai.*|kwpsagentedit|kpdfai.*|ketai.*|'
                       r'kdocer.*|kadverhelper|khyperion|kstartpage|kappmarket|kappstore|kappmgr|'
                       r'kappcenter|kappconnectivity|kpromeappmarket|kcorppromotipsmgr|'
                       r'kpromotionstrategy|koperationstrategy|kcompanytabbutton|'
                       r'kcloudadapter|kclouddocs|kclouduploader|kcooperatearea|'
                       r'kcoworkdockpanel|kwpscowork|knewshare|kdevicecenter|kspacemanager|'
                       r'kusercenter|kpromeaccountpanel|kloginwelcome|knewdocs|kcreatefilepanel|'
                       r'kmessagecentersdk|kmessagecentersrv|messagepush|cloudpushsdk|'
                       r'kwpsserver|wpscloudsvrlaunch|qing|yunbox|officespace|'
                       r'kwhatsnew|kfeedback|ktipsmanager|ktipsclientmanager|klearningtips|'
                       r'kwpsupdateui|kapmsdk|crashhandlerimpl|kpluginconfigcenter|kplugindistributer|'
                       r'kcefpreload|kcefwidgetpool)$', re.I)
REMOVE_HELPERS = {'wpscloudsvr.app','kaideployserver.app','yunboxtool.app',
                  'crashhandler.app','WPS Office UpdateTool.app','wpsdiagnostictool.app',
                  'wpsquery.app','transerr.app'}


def run(args, **kwargs):
    r = subprocess.run([str(x) for x in args], capture_output=True, text=True, **kwargs)
    if r.returncode:
        raise RuntimeError(f'{args[:3]}: {r.stderr[-3000:]} {r.stdout[-1000:]}')
    return r.stdout


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def vaddr_offset(data, address):
    if data[:4] != b'\xcf\xfa\xed\xfe':
        raise ValueError('Expected thin 64-bit little endian Mach-O')
    if struct.unpack_from('<I', data, 4)[0] != 0x100000c:
        raise ValueError('Expected ARM64')
    ncmd = struct.unpack_from('<I', data, 16)[0]
    pos = 32
    for _ in range(ncmd):
        cmd, size = struct.unpack_from('<II', data, pos)
        if cmd == 0x19:
            va, vs, offset, fs = struct.unpack_from('<QQQQ', data, pos + 24)
            if va <= address < va + min(vs, fs):
                return offset + address - va
        pos += size
    raise ValueError(f'Address not backed by file: {address:x}')


def patch_export(app, library, symbol, expected, replacement, report):
    path = app / f'Contents/Frameworks/office6/{library}.framework/Versions/A/{library}'
    exports = run(['xcrun','llvm-objdump','--macho','--exports-trie',path])
    match = re.search(r'^(0x[0-9A-Fa-f]+)\s+' + re.escape(symbol) + r'$', exports, re.M)
    if not match:
        raise ValueError(f'Missing export {symbol}')
    address = int(match[1],16)
    data = bytearray(path.read_bytes())
    offset = vaddr_offset(data,address)
    original = bytes(data[offset:offset + len(replacement)])
    if original.hex() != expected:
        raise ValueError(f'Original bytes differ at {symbol}: {original.hex()}')
    data[offset:offset+len(replacement)] = replacement
    path.write_bytes(data)
    report.append({'library':library,'symbol':symbol,'address':hex(address),
                   'offset':offset,'before':original.hex(),'after':replacement.hex()})


def patch_address(app, library, address, expected, replacement, reason, report):
    path=app/f'Contents/Frameworks/office6/{library}.framework/Versions/A/{library}'
    data=bytearray(path.read_bytes());offset=vaddr_offset(data,address)
    old=bytes(data[offset:offset+len(replacement)])
    assert old.hex()==expected, f'Unexpected instruction at {address:x}'
    data[offset:offset+len(replacement)]=replacement;path.write_bytes(data)
    report.append({'library':library,'address':hex(address),'offset':offset,
                   'before':old.hex(),'after':replacement.hex(),'reason':reason})


def safe_id(value):
    return 'com.haihome.wpslocal.' + re.sub(r'[^A-Za-z0-9.-]','-',value)[-120:]


def install_policy(app, report, standalone=False):
    dylib=app/'Contents/Frameworks/haihome_local_policy.dylib'
    audit=Path('/dev/null') if standalone else app.parent/'policy-audit.log'
    run(['clang++','-dynamiclib','-std=c++17','-x','objective-c++','-framework','AppKit',
         '-arch','arm64','-mmacosx-version-min=12.0',
         '-Wl,-undefined,dynamic_lookup','-Wl,-install_name,@rpath/haihome_local_policy.dylib',
         '-DHAIHOME_AUDIT_PATH='+json.dumps(str(audit)),
         Path(__file__).parent/'local_policy.cpp','-o',dylib])
    executable=app/'Contents/MacOS/wpsoffice'
    data=bytearray(executable.read_bytes())
    assert data[:4]==b'\xcf\xfa\xed\xfe'
    ncmds,cmdsize=struct.unpack_from('<II',data,16)
    end=32+cmdsize
    name=b'@executable_path/../Frameworks/haihome_local_policy.dylib\0'
    size=(24+len(name)+7)&~7
    # Check segment section offsets, rather than assuming a header padding size.
    pos=32;sections=[]
    for _ in range(ncmds):
        cmd,sz=struct.unpack_from('<II',data,pos)
        if cmd==0x19:
            count=struct.unpack_from('<I',data,pos+64)[0]
            for j in range(count):
                offset=struct.unpack_from('<I',data,pos+72+80*j+48)[0]
                if offset:sections.append(offset)
        pos+=sz
    assert end+size <= min(sections) and not any(data[end:end+size]), 'No load-command padding'
    load=struct.pack('<IIIIII',0xc,size,24,2,0,0)+name
    data[end:end+size]=load.ljust(size,b'\0')
    struct.pack_into('<II',data,16,ncmds+1,cmdsize+size)
    executable.write_bytes(data)
    report['policy']={'source':'local_policy.cpp','audit_log':str(audit),
                      'load_command_offset':end,'load_command_bytes':size}


def prune_ui(app, report):
    """Remove optional command definitions and references, retaining native file I/O."""
    blocked = re.compile(r'copilot|aigc|docer|premium|CommonVipTab|WorkSpaceVip|'
                         r'CloudPage|SaveToCloud|CloudFile|FileRoaming|OnlineEditing|'
                         r'MemberCenter|SuperVip|Advertisement|Advertise|Promotion|'
                         r'AccompanyWrite|AiGlobalEntry',re.I)
    ai = re.compile(r'\bAI\b|(?<=[a-z])AI(?=[A-Z])|^AI(?=[A-Z])')
    protected = {'SaveFile','SaveAs','SaveAsFile','OpenFile','Open','FileOpen','CT_File',
                 'Table','TableVml','New','NewFile','Exit','Print','SaveAll'}
    unwanted = {'CT_PremiumServices','CT_Copilot','AccountMenus','AccountInfo',
                'Bindingphone','ExitAccount','Upgrade','KOSUserLoginTipRights',
                'KxDocerFakeTabCommand','TpOnlineTaskPaneCommands','ProxySet'}
    docs=[]
    for path in (app/'Contents/Resources/office6/res').rglob('*'):
        if path.suffix not in ['.kui','.kuip']:continue
        raw=path.read_text(encoding='utf-8')
        # Vendor resources contain unescaped '<' inside quoted attributes.
        # Normalize those attribute values without changing their parsed meaning.
        def escape_attribute(m):
            v=re.sub(r'&(?!#\d+;|#x[0-9a-fA-F]+;|amp;|lt;|gt;|quot;|apos;)', '&amp;',m[1])
            return '="'+v.replace('<','&lt;').replace('>','&gt;')+'"'
        raw=re.sub(r'="([^"]*)"',escape_attribute,raw)
        try: root=ET.fromstring(raw)
        except ET.ParseError as error:raise ValueError(f'Unparsed UI resource {path}: {error}')
        docs.append((path,root))
        for e in root.iter():
            ident=e.get('id','')
            if ident in protected:continue
            primary=' '.join([e.tag]+[e.get(k,'') for k in
                ['id','idKey','targetModule','pluginName','targetCommand','text']])
            if blocked.search(primary) or ai.search(primary):
                if ident: unwanted.add(ident)
    report['removed_ui']=[]
    for path,root in docs:
        removed=[]
        def prune(parent):
            for e in list(parent):
                if any(e.get(k) in unwanted for k in ['id','idQ','idRef','ref','refCmdId','targetId','referenceCommand']):
                    removed.append({'tag':e.tag,'id':e.get('id') or e.get('idRef') or e.get('ref')})
                    parent.remove(e)
                else:
                    for k in ['aiGenerateTableCmd','onlineCmd','accountMenuCommand']:
                        if k in e.attrib and (k=='accountMenuCommand' or e.get(k) in unwanted):
                            del e.attrib[k]
                    prune(e)
        prune(root)
        if removed:
            path.write_bytes(ET.tostring(root,encoding='utf-8',xml_declaration=True))
            ET.fromstring(path.read_bytes())
            report['removed_ui'].append({'file':str(path.relative_to(app)),'entries':removed})


def build(label, drop_shared_file_dialog=False, standalone=False):
    assert re.fullmatch(r'[a-z0-9-]+',label)
    app = WORK / label / 'HaihomeLocal.app'
    if app.parent.exists():
        raise RuntimeError('Build label already exists; use a new isolated label')
    icon = Path(__file__).parent / 'assets/HaihomeLocalDocuments.icns'
    if not icon.is_file() or icon.read_bytes()[:4] != b'icns':
        raise RuntimeError('Missing or invalid local document app icon')
    if sha(SOURCE/'Contents/MacOS/wpsoffice') != EXPECTED_MAIN:
        raise RuntimeError('Unexpected source version')
    run(['codesign','--verify','--deep','--strict',SOURCE])
    app.parent.mkdir(parents=True)
    run(['cp','-cR',SOURCE,app])
    report = {'source':str(SOURCE),'app':str(app),'version':'12.1.29182','bundle_id':NEW_ID,
              'drop_shared_file_dialog':drop_shared_file_dialog,
              'standalone':standalone,
              'built_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'patches':[],
              'removed_addons':[],'removed_helpers':[],'changed_identifiers':[],'removed_registrations':[]}

    # Remove optional addon binaries/resources and their registrations.
    for relative in ['Contents/Frameworks/office6/addons','Contents/Resources/office6/addons']:
        for path in sorted((app/relative).iterdir()):
            if REMOVE_RE.fullmatch(path.name) or (drop_shared_file_dialog and path.name=='kcloudfiledialog'):
                report['removed_addons'].append(str(path.relative_to(app)))
                if path.is_dir(): shutil.rmtree(path)
                else: path.unlink()
    for path in (app/'Contents/Resources/office6/setupplugincfg').glob('*.plg'):
        original=path.read_bytes()
        kept=[]
        for line in original.splitlines(keepends=True):
            names = re.findall(rb'(?:name|dllname)="([^"]+)"',line)
            if b'<plugin ' in line and (b'type="newweb"' in line or
                    any(REMOVE_RE.fullmatch(x.decode()) or (drop_shared_file_dialog and
                        x in [b'kwpscloudmodule',b'kcloudfiledialog']) for x in names)):
                report['removed_registrations'].append(line.decode().strip())
            else: kept.append(line)
        new=b''.join(kept)
        ET.fromstring(new)
        path.write_bytes(new)
    for base in [app/'Contents/SharedSupport', app/'Contents/Library/LoginItems']:
        if not base.exists(): continue
        for path in list(base.iterdir()):
            if path.name in REMOVE_HELPERS or 'LoginItems' in str(base):
                report['removed_helpers'].append(str(path.relative_to(app)))
                if path.is_dir(): shutil.rmtree(path)
                else: path.unlink()

    patch_export(app,'kprometheus','__ZN17KPromeApplication19shouldInitStartPageEv',
                 '00d840f9400000b4',FALSE_RET,report['patches'])
    patch_export(app,'kprometheus','__ZN13KPromeStartup19shouldInitStartPageEv',
                 'ff8301d1f65703a9',FALSE_RET,report['patches'])
    patch_export(app,'kprometheus','__ZNK13KPromeStartup17isEnableStartPageEv',
                 '00704039c0035fd6',FALSE_RET,report['patches'])
    patch_export(app,'ksolite','__ZN14KCloudSvrProxy16startQingProcessERKN6kso_qt7QStringEb',
                 'f44fbea9fd7b01a9',FALSE_RET,report['patches'])
    patch_export(app,'ksolite','__ZN11kacctoutsdk16KAccountSdkProxy5loginERKN6kso_qt4QMapINS1_7QStringENS1_8QVariantEEE',
                 'ff0302d1f65705a9',FALSE_RET,report['patches'])
    patch_export(app,'kprometheus','__ZN13KPromeStartup24isSupportShowLoginDialogEv',
                 'ffc300d1f44f01a9',FALSE_RET,report['patches'])
    patch_export(app,'kprometheus','__ZN13KPromeStartup15showLoginDialogEP18KPromeSplashScreen',
                 'ff4302d1f85f05a9',FALSE_RET,report['patches'])
    patch_export(app,'kprometheus','__ZN16KPromeMainWindow18_showForceLoginWinEb',
                 'ffc300d1f44f01a9',FALSE_RET,report['patches'])
    patch_export(app,'kprometheus','__ZN23KPromeOptionCenterProxy14isDocerTabShowEv',
                 'ff8301d1f44f04a9',FALSE_RET,report['patches'])
    patch_export(app,'kprometheus','__ZN23KPromeOptionCenterProxy17isSupportDocerTabEv',
                 '4020009000343a91',FALSE_RET,report['patches'])
    patch_export(app,'kprometheus','__ZN16KPromeMainWindow36_showFirstStartupGuideUrlAfterUpdateEv',
                 'ff0302d1f44f06a9',FALSE_RET,report['patches'])
    # Keep first-window creation. Count an already-visible window as handled on
    # Dock/reopen, rather than creating another empty start-page window.
    patch_address(app,'kprometheus',0x9885c,'80000034',bytes.fromhex('60000034'),
                  'Visible existing window sets handled flag on Dock/reopen',report['patches'])
    # startPageProxySubPage() is absent by design. Skip only its virtual call,
    # retaining temporary QString cleanup and all document-window setup.
    patch_address(app,'kprometheus',0x983ac,'a80240f9',bytes.fromhex('06000014'),
                  'Skip call through removed startPageProxySubPage',report['patches'])
    # QWidget::setVisible(false) on the account avatar's showEvent. The target is
    # the existing import stub, verified against otool's indirect symbol table.
    prome=app/'Contents/Frameworks/office6/kprometheus.framework/Versions/A/kprometheus'
    indirect=run(['otool','-Iv',prome])
    assert re.search(r'0x000000000080a710\s+\d+\s+__ZN6kso_qt7QWidget10setVisibleEb',indirect)
    branch=struct.pack('<I',0x14000000|(((0x80a710-(0x35097c+4))//4)&0x3ffffff))
    patch_export(app,'kprometheus','__ZN18KPromeHeaderAvatar9showEventEPN6kso_qt10QShowEventE',
                 'f44fbea9fd7b01a9',bytes.fromhex('01008052')+branch,report['patches'])
    prune_ui(app,report)

    # Equal length namespace replacement preserves Mach-O layout and offsets.
    assert len(OLD_ID)==len(NEW_ID)
    for path in sorted(app.rglob('*')):
        if not path.is_file() or path.is_symlink(): continue
        if '_CodeSignature' in path.parts or path.name=='embedded.provisionprofile': continue
        data=path.read_bytes()
        new=data.replace(OLD_ID.encode(),NEW_ID.encode())
        new=new.replace(OLD_ID.encode('utf-16le'),NEW_ID.encode('utf-16le'))
        if new!=data:
            path.write_bytes(new)
            report['changed_identifiers'].append(str(path.relative_to(app)))
    for path in app.rglob('embedded.provisionprofile'):
        path.unlink()
    for path in app.rglob('Info.plist'):
        if path.is_symlink(): continue
        try: info=plistlib.loads(path.read_bytes())
        except Exception: continue
        if info.get('CFBundleIdentifier'):
            info['CFBundleIdentifier']=safe_id(info['CFBundleIdentifier'])
        # No registration for vendor URLs or privileged/login services.
        for key in ['CFBundleURLTypes','SMPrivilegedExecutables','SMAuthorizedClients']:
            info.pop(key,None)
        if path==app/'Contents/Info.plist':
            info['CFBundleIdentifier']=NEW_ID
            info['CFBundleName']='Haihome Local'
            info['CFBundleDisplayName']='海家本地文档'
            info['CFBundleIconFile']='HaihomeLocalDocuments.icns'
            info.pop('CFBundleIconName',None)
            # Opening files explicitly remains supported without claiming defaults.
            for typ in info.get('CFBundleDocumentTypes',[]):
                typ['LSHandlerRank']='None'
        path.write_bytes(plistlib.dumps(info,sort_keys=False))

    for path in (app/'Contents/Resources').glob('*.lproj/InfoPlist.strings'):
        text=path.read_text(encoding='utf-8')
        text=re.sub(r'("CFBundle(?:DisplayName|Name)"\s*=\s*)"[^"]*"',
                    r'\1"Haihome Local Editor"',text)
        path.write_text(text,encoding='utf-8')

    shutil.copy2(icon,app/'Contents/Resources/HaihomeLocalDocuments.icns')
    report['app_icon']={'file':'Contents/Resources/HaihomeLocalDocuments.icns','sha256':sha(icon)}
    install_policy(app,report,standalone)

    ent={
        'com.apple.security.app-sandbox':True,
        'com.apple.security.files.user-selected.read-write':True,
        'com.apple.security.files.bookmarks.app-scope':True,
        'com.apple.security.print':True,
        'com.apple.security.cs.allow-jit':True,
        'com.apple.security.cs.allow-unsigned-executable-memory':True,
        'com.apple.security.cs.disable-library-validation':True,
        # Only synthetic test/work directory is pre-authorized; all real documents
        # require explicit user selection through the native file panel.
        'com.apple.security.temporary-exception.files.absolute-path.read-write':[str(WORK)+'/'],
    }
    entitlement=app.parent/'local-editor.entitlements.plist'
    if standalone:
        ent.pop('com.apple.security.temporary-exception.files.absolute-path.read-write',None)
    entitlement.write_bytes(plistlib.dumps(ent))
    # All nested identifiers/signatures belong to this personal build.
    machos=[]
    for path in app.rglob('*'):
        if not path.is_file() or path.is_symlink():continue
        with path.open('rb') as f:magic=f.read(4)
        if magic in [b'\xcf\xfa\xed\xfe',b'\xce\xfa\xed\xfe',b'\xca\xfe\xba\xbe']:
            machos.append(path)
    for path in machos:
        run(['codesign','--force','--sign','-','--timestamp=none','--identifier',safe_id(path.name),path])
    bundles=sorted([p for p in app.rglob('*') if not p.is_symlink() and p.is_dir()
                    and p.suffix in ['.framework','.app','.xpc','.appex']],key=lambda p:len(p.parts),reverse=True)
    for path in bundles:
        args=['codesign','--force','--sign','-','--timestamp=none','--identifier',safe_id(path.stem)]
        if path.suffix in ['.app','.xpc','.appex']:args+=['--entitlements',entitlement]
        run(args+[path])
    run(['codesign','--force','--sign','-','--timestamp=none','--options','runtime',
         '--identifier',NEW_ID,'--entitlements',entitlement,app])
    run(['codesign','--verify','--deep','--strict',app])
    report['macho_signed']=len(machos)
    report['signature_verification']='passed'
    (app.parent/'build-manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['app','bundle_id','macho_signed','signature_verification']},ensure_ascii=False))


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('label',help='New build directory name; existing builds are never overwritten')
    ap.add_argument('--drop-shared-file-dialog',action='store_true')
    ap.add_argument('--source',type=Path,help='Pristine WPS 12.1.29182 app; never modified')
    ap.add_argument('--output-root',type=Path,help='Directory containing versioned isolated builds')
    ap.add_argument('--standalone',action='store_true',help='No development-directory access or audit-log paths')
    args=ap.parse_args()
    if args.source: SOURCE=args.source.expanduser().resolve()
    elif not SOURCE.exists(): SOURCE=Path('/Applications/wpsoffice.app')
    if args.output_root: WORK=args.output_root.expanduser().resolve()
    build(args.label,args.drop_shared_file_dialog,args.standalone)
