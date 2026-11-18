#!/usr/bin/env python3
"""Apply only the reviewed TV-standby controller change on a legacy display."""

import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time


BASELINE_MAIN_SHA256 = '2b88c41a05066b17ea354faf14fae04950fab9882b0397155aebfcb16784553e'
RUNTIME = Path('/home/opensurv/lib')
SOURCES = Path(__file__).resolve().parents[1] / 'surveillance'
FILES = ('surveillance.py', 'core/MonitorSession.py')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def controller_pids():
    pids = []
    for proc in Path('/proc').glob('[0-9]*'):
        try:
            if (proc / 'cwd').resolve() == RUNTIME and b'surveillance.py' in (proc / 'cmdline').read_bytes().split(b'\0'):
                pids.append(int(proc.name))
        except OSError:
            pass
    return pids


def apply():
    if os.geteuid() != 0:
        raise SystemExit('Run this update with sudo.')
    if socket.gethostname() != 'rr-pubdisplay':
        raise SystemExit('This recovery bundle is restricted to the Bethel display host.')
    current_main = RUNTIME / 'surveillance.py'
    if digest(current_main) not in (BASELINE_MAIN_SHA256, digest(SOURCES / 'surveillance.py')):
        raise SystemExit('Installed controller differs from the reviewed baseline; nothing changed.')
    for relative in FILES:
        source, target = SOURCES / relative, RUNTIME / relative
        compile(source.read_text(), str(source), 'exec')
        if target.is_symlink():
            raise SystemExit('Unexpected runtime symlink; nothing changed.')
        if relative != 'surveillance.py' and target.exists() and digest(target) != digest(source):
            raise SystemExit('Existing monitor-session module differs; nothing changed.')

    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = Path('/var/backups/rewind-display') / ('tv-standby-' + stamp)
    backup.mkdir(parents=True, mode=0o700)
    os.chmod(backup, 0o700)
    original = {}
    default_stat = current_main.stat()
    for relative in FILES:
        target = RUNTIME / relative
        if target.exists():
            stat = target.stat()
            original[relative] = {'uid': stat.st_uid, 'gid': stat.st_gid, 'mode': stat.st_mode & 0o777}
            saved = backup / relative
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, saved)
        else:
            original[relative] = None
    (backup / 'original.json').write_text(json.dumps(original, indent=2))
    rollback = '''#!/usr/bin/python3
import json, os, pathlib, shutil, subprocess
backup = pathlib.Path(__file__).resolve().parent
runtime = pathlib.Path('/home/opensurv/lib')
for relative, metadata in json.loads((backup/'original.json').read_text()).items():
    target = runtime/relative
    if metadata is None:
        target.unlink(missing_ok=True)
    else:
        shutil.copy2(backup/relative, target)
        os.chown(target, metadata['uid'], metadata['gid'])
        os.chmod(target, metadata['mode'])
subprocess.run(['systemctl', 'restart', 'lightdm'], check=True, timeout=30)
print('Restored pre-update controller and restarted LightDM.')
'''
    (backup / 'rollback.py').write_text(rollback)
    os.chmod(backup / 'rollback.py', 0o700)
    print('Rollback: sudo python3 ' + str(backup / 'rollback.py'), flush=True)

    try:
        for relative in FILES:
            target = RUNTIME / relative
            temporary = target.with_name(target.name + '.tv-standby-new')
            shutil.copy2(SOURCES / relative, temporary)
            metadata = original[relative] or {'uid': default_stat.st_uid, 'gid': default_stat.st_gid, 'mode': 0o644}
            os.chown(temporary, metadata['uid'], metadata['gid'])
            os.chmod(temporary, metadata['mode'])
            os.replace(temporary, target)
        subprocess.run(['systemctl', 'restart', 'lightdm'], check=True, timeout=30)
        time.sleep(5)
        first = controller_pids()
        time.sleep(5)
        if not first or not set(first).intersection(controller_pids()):
            raise RuntimeError('Updated controller did not remain running.')
        subprocess.run(['systemctl', 'is-active', 'lightdm', 'cloudflared'], check=True, timeout=10)
        print('Rewind Display 1.3-rr.3 controller is running; PIDs:', controller_pids())
        print('With no connected TV, this is standby; camera players start when a monitor appears.')
    except Exception:
        subprocess.run(['python3', str(backup / 'rollback.py')], check=True, timeout=40)
        raise


if __name__ == '__main__':
    apply()
