#!/usr/bin/env python3
"""记录文档关联；遇到系统确认即停止，避免批量堆叠弹窗。"""
import argparse
import json
import plistlib
import shutil
import subprocess
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('app', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--apply', action='store_true', help='逐项设置，需系统确认时停止；确认后可用同一报告续跑')
    args = parser.parse_args()
    app = args.app.expanduser().resolve()
    info = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
    bundle_id = info['CFBundleIdentifier']
    if bundle_id != 'com.haihome.localdocuments':
        raise SystemExit('应用标识不匹配。')
    subprocess.run(['codesign', '--verify', '--deep', '--strict', str(app)], check=True)
    duti = shutil.which('duti')
    if not duti:
        raise SystemExit('需要 duti：brew install duti。应用运行本身不依赖该工具。')
    extensions = sorted({ext for item in info['CFBundleDocumentTypes'] for ext in item['CFBundleTypeExtensions']})

    def current(ext):
        return subprocess.run([duti, '-x', ext], capture_output=True, text=True)

    def matches(result):
        lines = result.stdout.strip().splitlines()
        return result.returncode == 0 and len(lines) >= 3 and lines[1] == str(app) and lines[2] == bundle_id

    if args.report.exists():
        report = json.loads(args.report.read_text())
        if report.get('app') != str(app) or report.get('bundle_id') != bundle_id:
            raise SystemExit('现有报告属于其他安装位置；请提供新的报告路径。')
        if {item['extension'] for item in report['extensions']} != set(extensions):
            raise SystemExit('现有报告格式列表不匹配；请提供新的报告路径。')
    else:
        report = {'at': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'app': str(app),
                  'bundle_id': bundle_id, 'extensions': []}
        for ext in extensions:
            before = current(ext)
            report['extensions'].append({'extension': ext, 'before': before.stdout.strip(),
                                         'before_status': before.returncode})

    def save():
        args.report.parent.mkdir(parents=True, exist_ok=True)
        report['checked_at'] = time.strftime('%Y-%m-%dT%H:%M:%S%z')
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')

    # Persist the original state of every extension before changing anything.
    save()
    pending = None
    for item in report['extensions']:
        result = current(item['extension'])
        if args.apply and not matches(result):
            changed = subprocess.run([duti, '-s', bundle_id, '.' + item['extension'], 'all'],
                                     capture_output=True, text=True)
            item['set_status'] = changed.returncode
            item['set_error'] = changed.stderr.strip()
            result = current(item['extension'])
            # LaunchServices can return success before the user confirms.
            # Never submit another change while this one remains unverified.
            if changed.returncode != 0 or not matches(result):
                pending = item['extension']
        item['after'] = result.stdout.strip()
        item['passed'] = matches(result)
        save()
        if pending:
            break

    remaining = [item['extension'] for item in report['extensions'] if not item.get('passed')]
    report['pending_confirmation'] = pending
    save()
    print(json.dumps({'extensions': len(extensions), 'remaining': remaining,
                      'pending_confirmation': pending, 'report': str(args.report)}, ensure_ascii=False))
    if pending:
        print('本次已停止。请处理这一项系统确认，再用相同命令和报告继续；已完成项不会重复提交。')
        return 2
    return 1 if remaining else 0


if __name__ == '__main__':
    raise SystemExit(main())
