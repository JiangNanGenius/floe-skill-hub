#!/usr/bin/env python3
"""Actions-only same-role renewal; no new hosts, roles, credentials or URLs.

Root derives a renewal from an already signed immutable Hub base. Only its
isolated signing step reads the existing key. A key-free public relay and
the Hub's own token publish exactly two files using the existing exact CAS.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import hubcore
import transport_manifest as tm
import sign_publication as sp

APP = 'JiangNanGenius/floe-agent'
HUB = 'JiangNanGenius/floe-skill-hub'
RELAY_BRANCH = 'transport-mirror-signing-relay'
RELAY_PREFIX = 'transport-renewal/'
RECEIPT = 'renewal-receipt.json'
RECEIPT_SIG = RECEIPT+'.sig'
RECEIPT_DOMAIN = b'FLOE-GITHUB-TRANSPORT-RENEWAL-RECEIPT-V1\n'
FLAT_PAYLOAD = 'mirrors.v1.json'
FLAT_SIGNATURE = FLAT_PAYLOAD+'.sig'
LIMITS = {FLAT_PAYLOAD: tm.MAX_PAYLOAD, FLAT_SIGNATURE: tm.MAX_SIGNATURE,
          RECEIPT: 16_384, RECEIPT_SIG: tm.MAX_SIGNATURE}
COMMIT = re.compile(r'[0-9a-f]{40}')
DIGEST = re.compile(r'[0-9a-f]{64}')
FIELDS = {'schemaVersion', 'purpose', 'baseCommit', 'baseTree', 'basePayloadSHA256',
          'baseSignatureSHA256', 'toolingCommit', 'toolingTree', 'requestID',
          'generation', 'issuedAt', 'expiresAt', 'outputs', 'workflowCommit', 'runID'}
FROZEN_CODE = ('scripts/transport_renewal.py', 'scripts/transport_manifest.py',
               'scripts/hubcore.py', 'scripts/sign_publication.py', 'public-key.json')


def fail(reason):
    raise hubcore.HubError('transport renewal refused: '+reason)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical_object(raw, keys, cap):
    if not isinstance(raw, bytes) or not 1 <= len(raw) <= cap:
        fail('metadata byte bound')
    try:
        value = json.loads(raw)
    except ValueError:
        fail('metadata JSON')
    if not isinstance(value, dict) or set(value) != keys or tm.canonical(value) != raw:
        fail('metadata canonical shape')
    return value


def git(root, args, data=None, *, index=None, date=None):
    # Keep inherited Git redirects/config out. This helper never accesses a
    # token; the two workflow push steps own their own scoped authentication.
    env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
               GIT_TERMINAL_PROMPT='0', GIT_NO_REPLACE_OBJECTS='1')
    if index is not None:
        env['GIT_INDEX_FILE'] = str(index)
    if date is not None:
        env.update(GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date,
                   GIT_AUTHOR_NAME='floe-transport-renewal', GIT_COMMITTER_NAME='floe-transport-renewal',
                   GIT_AUTHOR_EMAIL='automation@users.noreply.github.com',
                   GIT_COMMITTER_EMAIL='automation@users.noreply.github.com')
    result = subprocess.run(['git', '-C', str(root), '-c', 'core.hooksPath=/dev/null',
        '-c', 'core.fsmonitor=false', *args], input=data, capture_output=True, env=env)
    if result.returncode:
        fail('fixed Git operation failed: '+args[0])
    return result.stdout


def blob(root, commit, rel, cap):
    if not COMMIT.fullmatch(commit):
        fail('immutable commit required')
    entries = git(root, ['ls-tree', '-r', commit, '--', rel]).decode().splitlines()
    if len(entries) != 1:
        fail('missing fixed blob '+rel)
    meta, actual = entries[0].split('\t', 1)
    mode, kind, oid = meta.split()
    if actual != rel or mode != '100644' or kind != 'blob':
        fail('fixed blob mode '+rel)
    size = int(git(root, ['cat-file', '-s', oid]))
    if not 1 <= size <= cap:
        fail('fixed blob size '+rel)
    return git(root, ['cat-file', 'blob', oid])


def trust_at(root, commit):
    raw = blob(root, commit, 'public-key.json', 8192)
    value = json.loads(raw)
    if value.get('keyID') != hubcore.PRODUCTION_KEY_ID or not isinstance(value.get('publicKey'), str):
        fail('official pinned public identity required')
    return {hubcore.PRODUCTION_KEY_ID: value['publicKey']}


def pair_at(root, commit, trust, now=None, *, historical=False):
    raw = blob(root, commit, tm.PAYLOAD_PATH, tm.MAX_PAYLOAD)
    signature = blob(root, commit, tm.SIGNATURE_PATH, tm.MAX_SIGNATURE)
    value, _ = tm.verify_manifest(raw, signature, trust, now, allow_expired=historical)
    return raw, signature, value


def renewal_payload(base_raw, base_signature, trust, now=None):
    clock = tm.utc_now(now).replace(microsecond=0)
    base, _ = tm.verify_manifest(base_raw, base_signature, trust, clock, allow_expired=True)
    if tm.timestamp(base['expiresAt'])-clock > dt.timedelta(days=7):
        return None
    if base['generation'] == tm.MAX_GENERATION:
        fail('generation exhausted')
    stamp = lambda value: value.isoformat(timespec='seconds').replace('+00:00', 'Z')
    return tm.build_payload(base['generation']+1, stamp(clock), stamp(clock+dt.timedelta(days=14)),
                            roles=base['roles'], now=clock)


def verify_same_roles(base_raw, base_signature, proposed, trust, now=None, *, historical=False):
    clock = tm.utc_now(now)
    base, _ = tm.verify_manifest(base_raw, base_signature, trust, clock, allow_expired=True)
    value = tm.validate_payload(proposed, clock, allow_expired=historical)
    issued = tm.timestamp(value['issuedAt'])
    if (value['generation'] != base['generation']+1 or value['roles'] != base['roles']
            or tm.timestamp(value['expiresAt'])-issued != dt.timedelta(days=14)
            or tm.timestamp(base['expiresAt'])-issued > dt.timedelta(days=7)
            or (not historical and clock-issued > dt.timedelta(days=1))):
        fail('only due same-role generation+1 fourteen-day renewal is admitted')
    return value


def request_id(base_commit, proposed):
    return sha(b'FLOE-TRANSPORT-RENEWAL-REQUEST-V1\n'+base_commit.encode('ascii')+b'\n'+proposed)


def signed_bundle(base_root, base_commit, tooling_root, tooling_commit, key, *, now=None,
                  workflow_commit, run_id):
    trust = trust_at(tooling_root, tooling_commit)
    base_raw, base_sig, _ = pair_at(base_root, base_commit, trust, now, historical=True)
    proposed = renewal_payload(base_raw, base_sig, trust, now)
    if proposed is None:
        return None
    value = verify_same_roles(base_raw, base_sig, proposed, trust, now)
    if not COMMIT.fullmatch(workflow_commit) or not re.fullmatch(r'[1-9][0-9]{0,19}', run_id):
        fail('fixed workflow provenance')
    files = {FLAT_PAYLOAD: proposed,
             FLAT_SIGNATURE: hubcore.sign_envelope(tm.DOMAIN+proposed, key, hubcore.PRODUCTION_KEY_ID)}
    receipt = {'schemaVersion': 1, 'purpose': 'floe-transport-renewal', 'baseCommit': base_commit,
        'baseTree': git(base_root, ['rev-parse', base_commit+'^{tree}']).decode().strip(),
        'basePayloadSHA256': sha(base_raw), 'baseSignatureSHA256': sha(base_sig),
        'toolingCommit': tooling_commit, 'toolingTree': git(tooling_root, ['rev-parse', tooling_commit+'^{tree}']).decode().strip(),
        'requestID': request_id(base_commit, proposed), 'generation': value['generation'],
        'issuedAt': value['issuedAt'], 'expiresAt': value['expiresAt'],
        'outputs': {name: {'size': len(data), 'sha256': sha(data)} for name, data in files.items()},
        'workflowCommit': workflow_commit, 'runID': run_id}
    files[RECEIPT] = tm.canonical(receipt)
    files[RECEIPT_SIG] = hubcore.sign_envelope(RECEIPT_DOMAIN+files[RECEIPT], key, hubcore.PRODUCTION_KEY_ID)
    verify_bundle(files, base_root, trust, now)
    return files


def verify_bundle(files, root, trust, now=None, *, historical=False):
    if set(files) != set(LIMITS) or any(not 1 <= len(raw) <= LIMITS[name] for name, raw in files.items()):
        fail('relay requires four bounded metadata files')
    hubcore.verify_envelope(RECEIPT_DOMAIN+files[RECEIPT], files[RECEIPT_SIG], trust)
    receipt = canonical_object(files[RECEIPT], FIELDS, LIMITS[RECEIPT])
    if type(receipt['schemaVersion']) is not int or receipt['schemaVersion'] != 1 or receipt['purpose'] != 'floe-transport-renewal':
        fail('receipt purpose/version')
    for name in ['baseCommit', 'baseTree', 'toolingCommit', 'toolingTree', 'workflowCommit']:
        if not isinstance(receipt[name], str) or not COMMIT.fullmatch(receipt[name]):
            fail('receipt commit shape')
    for name in ['requestID', 'basePayloadSHA256', 'baseSignatureSHA256']:
        if not isinstance(receipt[name], str) or not DIGEST.fullmatch(receipt[name]):
            fail('receipt digest shape')
    if not isinstance(receipt['runID'], str) or not re.fullmatch(r'[1-9][0-9]{0,19}', receipt['runID']):
        fail('receipt run provenance')
    if not isinstance(receipt['outputs'], dict) or set(receipt['outputs']) != {FLAT_PAYLOAD, FLAT_SIGNATURE}:
        fail('receipt output set')
    for name in [FLAT_PAYLOAD, FLAT_SIGNATURE]:
        binding = receipt['outputs'][name]
        if (not isinstance(binding, dict) or set(binding) != {'size', 'sha256'}
                or type(binding['size']) is not int or binding['size'] != len(files[name]) or binding['sha256'] != sha(files[name])):
            fail('receipt output binding')
    base_commit = receipt['baseCommit']
    if git(root, ['rev-parse', base_commit+'^{tree}']).decode().strip() != receipt['baseTree']:
        fail('receipt base tree binding')
    raw, signature, _ = pair_at(root, base_commit, trust, now, historical=True)
    if sha(raw) != receipt['basePayloadSHA256'] or sha(signature) != receipt['baseSignatureSHA256']:
        fail('receipt original pair binding')
    value, _ = tm.verify_manifest(files[FLAT_PAYLOAD], files[FLAT_SIGNATURE], trust, now, allow_expired=historical)
    verify_same_roles(raw, signature, files[FLAT_PAYLOAD], trust, now, historical=historical)
    if (type(receipt['generation']) is not int or receipt['generation'] != value['generation']
            or receipt['issuedAt'] != value['issuedAt'] or receipt['expiresAt'] != value['expiresAt']
            or receipt['requestID'] != request_id(base_commit, files[FLAT_PAYLOAD])):
        fail('receipt payload identity')
    return receipt


def read_bundle(directory):
    root = pathlib.Path(directory)
    if root.is_symlink() or not root.is_dir() or any(path.name not in set(LIMITS) | {'status.json'} for path in root.iterdir()):
        fail('unexpected relay artifact member')
    files = {}
    for name, cap in LIMITS.items():
        path = root/name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > cap:
            fail('unsafe relay member')
        files[name] = path.read_bytes()
    return files


def committed_relay(root, commit):
    entries = git(root, ['ls-tree', '-r', '--name-only', commit]).decode().splitlines()
    if set(entries) != {RELAY_PREFIX+name for name in LIMITS}:
        fail('relay commit contains paths beyond its four metadata members')
    return {name: blob(root, commit, RELAY_PREFIX+name, cap) for name, cap in LIMITS.items()}


def data_commit(root, parent, files, message, date):
    """Construct an exact data-only tree using an isolated temporary index."""
    if parent is not None and not COMMIT.fullmatch(parent):
        fail('commit parent')
    with tempfile.TemporaryDirectory(prefix='floe-transport-index-') as temp:
        index = pathlib.Path(temp)/'index'
        git(root, ['read-tree', parent] if parent else ['read-tree', '--empty'], index=index)
        for rel, raw in sorted(files.items()):
            oid = git(root, ['hash-object', '-w', '--stdin'], raw).decode().strip()
            git(root, ['update-index', '--add', '--cacheinfo', '100644', oid, rel], index=index)
        tree = git(root, ['write-tree'], index=index).decode().strip()
        args = ['commit-tree', tree]+(['-p', parent] if parent else [])
        return git(root, args, message.encode(), date=date).decode().strip()


def relay_plan(root, parent, files, proof_root, trust, now=None):
    receipt = verify_bundle(files, proof_root, trust, now)
    committed = {RELAY_PREFIX+name: raw for name, raw in files.items()}
    existing = git(root, ['ls-tree', '-r', '--name-only', parent]).decode().splitlines()
    if any(rel not in committed for rel in existing):
        fail('relay branch contains foreign tracked paths')
    if existing:
        previous = committed_relay(root, parent)
        prior = verify_bundle(previous, proof_root, trust, now, historical=True)
        if (previous[FLAT_PAYLOAD] == files[FLAT_PAYLOAD] and previous[FLAT_SIGNATURE] == files[FLAT_SIGNATURE]
                and prior['baseCommit'] == receipt['baseCommit']):
            return {'action': 'relay-unchanged', 'commit': parent, 'requestID': prior['requestID']}
        if (prior['generation'] > receipt['generation'] or
                (prior['generation'] == receipt['generation'] and prior['issuedAt'] >= receipt['issuedAt'])):
            fail('older or conflicting relay cannot replace newer signed metadata')
    commit = data_commit(root, parent, committed,
        f'transport-relay: {receipt["requestID"]} [skip ci]\n', receipt['issuedAt'])
    return {'action': 'relay', 'commit': commit, 'requestID': receipt['requestID']}


def publication_plan(root, current, relay_commit, files, now=None):
    trust = trust_at(root, current)
    receipt = verify_bundle(files, root, trust, now, historical=True)
    tooling = receipt['toolingCommit']
    git(root, ['merge-base', '--is-ancestor', tooling, current])
    if git(root, ['rev-parse', tooling+'^{tree}']).decode().strip() != receipt['toolingTree']:
        fail('tooling tree binding')
    current_raw, current_signature, current_value = pair_at(root, current, trust, now, historical=True)
    already = current_raw == files[FLAT_PAYLOAD] and current_signature == files[FLAT_SIGNATURE]
    if not already and receipt['baseCommit'] != current:
        return {'action': 'stale-base', 'generation': current_value['generation']}
    if not already:
        verify_bundle(files, root, trust, now)  # a new publication must be fresh/live
        for rel in FROZEN_CODE:
            before = git(root, ['ls-tree', tooling, '--', rel])
            after = git(root, ['ls-tree', current, '--', rel])
            if not before or before != after:
                fail('renewal verification code differs from signed tooling')
    if not COMMIT.fullmatch(relay_commit):
        fail('immutable relay commit')
    outputs = {tm.PAYLOAD_PATH: files[FLAT_PAYLOAD], tm.SIGNATURE_PATH: files[FLAT_SIGNATURE]}
    source = receipt['baseCommit']
    commit = data_commit(root, source, outputs,
        f'transport: renew generation {receipt["generation"]} [skip ci]\n\n'
        f'Request: {receipt["requestID"]}\nOfficial relay: https://github.com/{APP}/tree/{relay_commit}/{RELAY_PREFIX}\n',
        receipt['issuedAt'])
    changed = git(root, ['diff-tree', '--no-commit-id', '--name-only', '-r', source, commit]).decode().splitlines()
    if set(changed) != set(outputs):
        fail('publication must change only the exact pair')
    return {'action': 'already-published' if already else 'publish', 'baseCommit': current,
        'publicationCommit': current if already else commit, 'commit': commit, 'requestID': receipt['requestID'],
        'generation': receipt['generation'], 'candidateRef': 'refs/heads/auto/transport-renewal-'+receipt['requestID']}


def fresh_main(root, expected):
    lines = git(root, ['ls-remote', '--exit-code', 'https://github.com/'+HUB+'.git', 'refs/heads/main']).decode().splitlines()
    if len(lines) != 1 or lines[0].split()[0] != expected:
        fail('official main moved before signing; next scheduled run rederives')


def write_status(out, value):
    out.mkdir(parents=True, exist_ok=True)
    sp.write_outputs(out, {'status.json': tm.canonical(value)})


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('command', choices=['plan', 'sign', 'relay', 'publish', 'readback'])
    p.add_argument('--root', type=pathlib.Path, required=True)
    p.add_argument('--base', required=True)
    p.add_argument('--tooling', type=pathlib.Path)
    p.add_argument('--tooling-commit')
    p.add_argument('--bundle', type=pathlib.Path)
    p.add_argument('--relay-commit')
    p.add_argument('--out', type=pathlib.Path, required=True)
    a = p.parse_args()
    if not COMMIT.fullmatch(a.base):
        fail('immutable base')
    if a.command in ['plan', 'sign']:
        if not a.tooling or not a.tooling_commit or not COMMIT.fullmatch(a.tooling_commit):
            fail('reviewed literal tooling commit required')
        sp.verify_exact_snapshot('tooling', a.tooling, a.tooling_commit)
        sp.verify_exact_snapshot('base', a.root, a.base)
        out = sp.validate_out_root(a.out, a.root, a.tooling)
        trust = trust_at(a.tooling, a.tooling_commit)
        raw, signature, value = pair_at(a.root, a.base, trust, historical=True)
        proposed = renewal_payload(raw, signature, trust)
        if a.command == 'plan' or proposed is None:
            write_status(out, {'action': 'renew' if proposed else 'not-due', 'baseCommit': a.base,
                               'generation': value['generation'], 'expiresAt': value['expiresAt']})
            return
        fresh_main(a.root, a.base)  # before load_signing_key
        if (os.environ.get('GITHUB_REPOSITORY') != APP or os.environ.get('GITHUB_REF') != 'refs/heads/main'
                or os.environ.get('GITHUB_EVENT_NAME') not in ['schedule', 'workflow_dispatch']):
            fail('signing is restricted to the official default-branch Actions workflow')
        key = sp.load_signing_key(hubcore, trust)
        files = signed_bundle(a.root, a.base, a.tooling, a.tooling_commit, key,
            workflow_commit=os.environ.get('GITHUB_SHA', ''), run_id=os.environ.get('GITHUB_RUN_ID', ''))
        sp.write_outputs(out, files)
        write_status(out, {'action': 'signed', 'baseCommit': a.base})
    elif a.command == 'relay':
        if not a.tooling or not a.tooling_commit:
            fail('literal tooling required')
        if sp._origin_owner_repo(git(a.root, ['remote', 'get-url', 'origin']).decode().strip()) != APP:
            fail('relay writer requires the fixed official App origin')
        files = read_bundle(a.bundle)
        receipt = verify_bundle(files, a.tooling, trust_at(a.tooling, a.tooling_commit))
        if receipt['toolingCommit'] != a.tooling_commit:
            fail('relay tooling differs from literal Root pin')
        # The old tip is an independently fetched immutable ref, or the
        # workflow's known empty root. Replaying a completed relay is a no-op.
        plan = relay_plan(a.root, a.base, files, a.tooling, trust_at(a.tooling, a.tooling_commit))
        if plan['action'] != 'relay-unchanged':
            fresh_main(a.tooling, receipt['baseCommit'])
        write_status(a.out, plan)
    elif a.command == 'publish':
        sp.verify_exact_snapshot('publication base', a.root, a.base)
        files = committed_relay(a.root, a.relay_commit)
        plan = publication_plan(a.root, a.base, a.relay_commit, files)
        write_status(a.out, plan)
    else:
        import automatic_publication as publication
        trust = trust_at(a.root, a.base)
        expected = committed_relay(a.root, a.relay_commit)
        actual = {}
        for rel, name in [(tm.PAYLOAD_PATH, FLAT_PAYLOAD), (tm.SIGNATURE_PATH, FLAT_SIGNATURE)]:
            _, raw = publication.fetch_public_raw(a.base, rel, max_bytes=LIMITS[name])
            if raw != expected[name]:
                fail('anonymous publication read-back differs')
            actual[name] = raw
        value, _ = tm.verify_manifest(actual[FLAT_PAYLOAD], actual[FLAT_SIGNATURE], trust)
        write_status(a.out, {'action': 'readback-verified', 'publicationCommit': a.base,
                            'generation': value['generation'], 'payloadSHA256': sha(actual[FLAT_PAYLOAD])})


if __name__ == '__main__':
    try:
        main()
    except (hubcore.HubError, sp.SigningError) as error:
        raise SystemExit(str(error)) from None
