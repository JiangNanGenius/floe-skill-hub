#!/usr/bin/env python3
"""Narrow native ARM64 Linux qualification, with an explicit Node20 diagnostic."""
import hashlib
import json
import os
import platform
import signal
import stat
import struct
import subprocess
import time
import unicodedata
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path.cwd()
INPUT = ROOT / 'qualification/taste-arm64'
OUT = ROOT / 'taste-qa-evidence'
OUT.mkdir(exist_ok=False)
state = {'scope': 'Native ARM64 Debian Linux component execution; not App installation, model, Simulator or Mac-original acceptance',
         'passed': False, 'sourceCommit': os.environ.get('GITHUB_SHA'), 'checks': [], 'paidModelCalls': 0,
         'candidateMetadata': json.loads((INPUT / 'candidate.json').read_bytes())}

def save():
    (OUT / 'RESULT.json').write_text(json.dumps(state, indent=2) + '\n')

def check(name, condition, details=None):
    state['checks'].append({'name': name, 'passed': bool(condition), 'details': details})
    save()
    assert condition, name

def run(name, args, cwd, env, expected=(0,), timeout=180):
    started = time.monotonic()
    proc = subprocess.Popen(args, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
    try:
        output, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            output, _ = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            output, _ = proc.communicate()
        (OUT / (name + '.log')).write_text(output)
        check(name, False, {'timedOut': True, 'pidGroupTerminated': True})
    (OUT / (name + '.log')).write_text(output)
    check(name, proc.returncode in expected, {'exitCode': proc.returncode, 'expectedExitCodes': list(expected), 'seconds': round(time.monotonic() - started, 3)})
    return output

check('real-linux-arm64', platform.system() == 'Linux' and platform.machine() in ('aarch64', 'arm64'), {'os': platform.system(), 'machine': platform.machine()})
archive = INPUT / 'candidate.zip'
raw = archive.read_bytes()
meta = state['candidateMetadata']
check('exact-candidate-archive', hashlib.sha256(raw).hexdigest() == meta['archiveSHA256'] and len(raw) == meta['archiveBytes'])
check('unsigned-and-unpublished-input', meta['signed'] is False and meta['published'] is False)
source_files = {}
seen = set()
with zipfile.ZipFile(archive) as z:
    check('bounded-file-count', len(z.infolist()) == meta['files'] and len(z.infolist()) <= 2048)
    total = 0
    for item in z.infolist():
        name = item.filename
        path = PurePosixPath(name)
        assert not path.is_absolute() and '\\' not in name and '\0' not in name
        assert all(part not in ('', '.', '..') for part in name.split('/'))
        assert len(name.encode()) <= 512
        key = unicodedata.normalize('NFC', name).casefold()
        assert key not in seen
        seen.add(key)
        assert stat.S_IFMT(item.external_attr >> 16) in (0, stat.S_IFREG)
        assert item.file_size <= 2 * 1024 * 1024
        total += item.file_size
        assert total <= 64 * 1024 * 1024
        source_files[name] = z.read(item)
check('bounded-uncompressed-input', total == meta['uncompressedBytes'], {'bytes': total})
check('full-resources-retained', meta['fullUpstreamResourceSetRetained'] and len(source_files) > 1600)
check('normalized-curated-paths', all(name == 'SKILL.md' or name == 'floe.json' or name.startswith(('assets/', 'references/', 'scripts/')) for name in source_files))

node22 = '/usr/local/bin/node'
node20 = '/usr/bin/node'
base_env = {k: os.environ[k] for k in ('PATH', 'LANG', 'LC_ALL', 'TZ', 'HOME', 'USER', 'LOGNAME') if k in os.environ}
base_env.update({'CHROME_PATH': '/usr/bin/chromium', 'CHROME': '/usr/bin/chromium'})
state['packages'] = subprocess.check_output(['dpkg-query', '-W', '-f=${Package}\t${Version}\t${Architecture}\n'], text=True).splitlines()
state['kernel'] = subprocess.check_output(['uname', '-a'], text=True).strip()
state['interpreters'] = {name: subprocess.check_output([exe, '-p', 'JSON.stringify({version:process.versions.node,arch:process.arch,platform:process.platform})'], text=True).strip() for name, exe in [('node22', node22), ('node20', node20)]}
check('official-node22-arm64', json.loads(state['interpreters']['node22'])['arch'] == 'arm64' and int(json.loads(state['interpreters']['node22'])['version'].split('.')[0]) == 22)
check('debian-node20-control', int(json.loads(state['interpreters']['node20'])['version'].split('.')[0]) == 20)

fixture = '''<!doctype html><html lang="en" data-type="software"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="page-type" content="software"><meta name="site-kind" content="software"><title>Taste Linux qualification</title><style>*{box-sizing:border-box}html,body{margin:0;overflow-x:visible;background:#f1eee7;color:#183735;font:18px system-ui}main{min-height:100svh;padding:44px 24px}h1{font-size:40px;line-height:1.05;letter-spacing:-1px}p{line-height:1.5}.overflow-control{display:block;width:1600px;height:80px;background:#183735;color:white;border:0;font:18px system-ui;text-align:left;padding:20px}</style><main><h1>ARM64 Linux<br>Taste Skill</h1><p>Known overflow control for the browser inspector.</p><button class="overflow-control">Deliberately wide control</button></main></html>'''

for label, exe in [('node22', node22), ('node20', node20)]:
    work = ROOT / ('taste-work-' + label)
    skill = work / 'skill'
    skill.mkdir(parents=True)
    for name, body in source_files.items():
        path = skill / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    env = {**base_env, 'TASTE_SKILL_TMP': str(work / 'tmp'), 'TASTE_SKILL_ICON_CACHE': str(work / 'icon-cache'), 'TMPDIR': str(work / 'tmp'), 'XDG_CACHE_HOME': str(work / 'xdg-cache')}
    (work / 'tmp').mkdir()
    page = work / 'index.html'
    page.write_text(fixture)
    if label == 'node22':
        probe = json.loads(run('node22-preflight', [exe, str(skill / 'scripts/floe-preflight.mjs')], work, env))
        check('node22-runtime-ready', probe['state'] == 'ready' and probe['target'] == {'os': 'linux', 'arch': 'aarch64'})
        syntax = []
        for module in sorted(skill.rglob('*.mjs')):
            result = subprocess.run([exe, '--check', str(module)], cwd=work, env=env, capture_output=True, text=True)
            syntax.append({'path': module.relative_to(skill).as_posix(), 'exitCode': result.returncode, 'output': result.stdout + result.stderr})
        (OUT / 'node22-syntax.json').write_text(json.dumps(syntax, indent=2) + '\n')
        check('all-adapted-es-modules-parse', all(row['exitCode'] == 0 for row in syntax), {'modules': len(syntax)})
    else:
        probe = json.loads(run('node20-minimum-version-refusal', [exe, str(skill / 'scripts/floe-preflight.mjs')], work, env, expected=(3,)))
        check('upstream-minimum-not-silently-lowered', probe['state'] == 'requires-runtime' and any('22' in missing for missing in probe['missing']))
        # This is a diagnostic for a later explicitly tested compatibility adaptation, not release qualification.
        env['NODE_OPTIONS'] = '--experimental-websocket'
        env['PATH'] = '/usr/bin:/bin:/usr/local/bin'
    text = run(label + '-palette', [exe, str(skill / 'scripts/start.mjs'), 'deal', '--page', 'software', '--no-recent'], work, env)
    check(label + '-data-library-import', 'PALETTES' in text and 'TYPE for software' in text)
    run(label + '-templates', [exe, str(skill / 'scripts/effects.mjs'), 'gallery'], work, env)
    check(label + '-relocated-templates', all((skill / 'assets/effects' / name).is_file() for name in ['gallery.html', 'lab.html']))
    shot = OUT / (label + '-390.png')
    run(label + '-chromium-shot', [exe, str(skill / 'scripts/shoot.mjs'), '--url', str(page), '--w', '390', '--h', '844', '--out', str(shot), '--profile', str(work / '.taste-skill/chrome-shoot'), '--no-tiles'], work, env)
    png = shot.read_bytes()
    check(label + '-real-framebuffer', png[:8] == b'\x89PNG\r\n\x1a\n' and struct.unpack('>II', png[16:24])[0] == 390, {'sha256': hashlib.sha256(png).hexdigest(), 'dimensions': list(struct.unpack('>II', png[16:24]))})
    report_dir = OUT / (label + '-inspector')
    run(label + '-inspector', [exe, str(skill / 'scripts/consistency.mjs'), str(page), '--profile', str(work / '.taste-skill/chrome-inspector'), '--widths', '390', '--rhythm-widths', '390', '--out', str(report_dir), '--quick', '--no-slow', '--no-reduced', '--no-hidden', '--no-motion-hooks', '--no-gl-fallback', '--no-sweep', '--no-tiles'], work, env, expected=(1,))
    report = json.loads((report_dir / 'report.json').read_bytes())
    check(label + '-known-overflow-detected', report['checks'].get('overflow') == 'FAIL', {'overflow': report['checks'].get('overflow'), 'notChecked': report.get('notChecked', [])})
    remaining = [line for line in subprocess.check_output(['ps', '-eo', 'pid=,args='], text=True).splitlines() if str(work) in line and ('chromium' in line or 'consistency.mjs' in line or 'shoot.mjs' in line)]
    check(label + '-owned-workers-stopped', remaining == [], {'remaining': remaining})

state['passed'] = True
state['node20DiagnosticOnly'] = 'The current exact package still requires Node22; Node20 commands were separately tested with its experimental WebSocket flag. Any compatibility package needs its own frozen qualification.'
state['appOrInstallationAcceptanceClaimed'] = False
state['signedOrPublished'] = False
save()
print(json.dumps({'passed': True, 'checks': len(state['checks']), 'scope': state['scope'], 'archiveSHA256': meta['archiveSHA256'], 'node20DiagnosticOnly': True}))
