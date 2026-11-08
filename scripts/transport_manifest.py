#!/usr/bin/env python3
"""Strict, domain-separated signed GitHub transport list v1.

The list only orders/disables compiled IDs. It supplies no URL, trust root,
content identity or permission. Signing is done by sign_publication.py from
reviewed tooling against immutable data; this CLI never reads private keys.
"""
import argparse
import datetime as dt
import json
import pathlib
import re
import hashlib
import urllib.error
import urllib.request

import hubcore

PAYLOAD_PATH = 'transport/mirrors.v1.json'
SIGNATURE_PATH = PAYLOAD_PATH + '.sig'
DOMAIN = b'FLOE-GITHUB-TRANSPORT-MIRRORS-V1\n'
PURPOSE = 'floe-github-transport-mirrors'
MAX_PAYLOAD = 16384
MAX_SIGNATURE = 8192
MAX_GENERATION = 9007199254740991
MAX_VALIDITY = dt.timedelta(days=30)
APPROVED_IDS = frozenset({'ghfast.top', 'gh-proxy.com'})
ROLE_NAMES = frozenset({'rawFiles', 'atom', 'releaseAssets'})
DEFAULT_ROLES = {'rawFiles': ['ghfast.top', 'gh-proxy.com'], 'atom': ['gh-proxy.com'], 'releaseAssets': []}
FIELDS = {'schemaVersion', 'purpose', 'generation', 'issuedAt', 'expiresAt', 'roles'}
STAMP = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii') + b'\n'


def timestamp(value):
    if not isinstance(value, str) or not STAMP.fullmatch(value):
        raise hubcore.HubError('transport time must be UTC RFC3339 seconds with Z')
    try:
        parsed = dt.datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=dt.timezone.utc)
    except ValueError:
        raise hubcore.HubError('transport time is not a real UTC calendar value') from None
    return parsed


def utc_now(now=None):
    value = now if now is not None else dt.datetime.now(dt.timezone.utc)
    if value.tzinfo is None:
        raise hubcore.HubError('transport verifier requires an aware UTC clock')
    return value.astimezone(dt.timezone.utc)


def validate_payload(raw, now=None, allow_expired=False):
    if not isinstance(raw, bytes) or not 1 <= len(raw) <= MAX_PAYLOAD:
        raise hubcore.HubError('transport payload exceeds its byte bound')
    try:
        raw.decode('ascii')
        value = json.loads(raw)
    except (UnicodeError, ValueError):
        raise hubcore.HubError('transport payload must be ASCII JSON') from None
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise hubcore.HubError('transport payload requires exactly six fixed fields')
    if canonical(value) != raw:
        raise hubcore.HubError('transport payload is not canonical sorted compact JSON plus one LF')
    if type(value['schemaVersion']) is not int or value['schemaVersion'] != 1 or value['purpose'] != PURPOSE:
        raise hubcore.HubError('transport schema/purpose mismatch')
    if type(value['generation']) is not int or not 1 <= value['generation'] <= MAX_GENERATION:
        raise hubcore.HubError('transport generation outside strict integer bounds')
    roles = value['roles']
    if not isinstance(roles, dict) or set(roles) != ROLE_NAMES:
        raise hubcore.HubError('transport roles must be rawFiles/atom/releaseAssets only')
    for role, ids in roles.items():
        if (not isinstance(ids, list) or len(ids) > 2 or any(type(x) is not str or x not in APPROVED_IDS for x in ids)
                or len(set(ids)) != len(ids)):
            raise hubcore.HubError(f'transport role {role} requires at most two distinct approved IDs')
    issued, expiry, clock = timestamp(value['issuedAt']), timestamp(value['expiresAt']), utc_now(now)
    if not dt.timedelta(0) < expiry - issued <= MAX_VALIDITY or issued - clock > dt.timedelta(seconds=300):
        raise hubcore.HubError('transport issue/expiry interval is invalid')
    if not allow_expired and expiry <= clock:
        raise hubcore.HubError('transport payload has expired')
    return value


def verify_manifest(payload, signature, trusted_keys, now=None, allow_expired=False):
    if not isinstance(payload, bytes) or not 1 <= len(payload) <= MAX_PAYLOAD:
        raise hubcore.HubError('transport payload exceeds its byte bound')
    if not isinstance(signature, bytes) or not 1 <= len(signature) <= MAX_SIGNATURE:
        raise hubcore.HubError('transport signature exceeds its byte bound')
    # Verify first; no downloaded field influences the trust configuration.
    key_id = hubcore.verify_envelope(DOMAIN + payload, signature, trusted_keys)
    return validate_payload(payload, now, allow_expired), key_id


def enforce_generation(candidate_bytes, candidate, prior_bytes=None, prior=None):
    if prior is None:
        return 'initial'
    if candidate['generation'] < prior['generation']:
        raise hubcore.HubError('transport generation rollback refused')
    if candidate['generation'] == prior['generation']:
        if candidate_bytes == prior_bytes:
            return 'unchanged'
        raise hubcore.HubError('transport generation reused for different bytes')
    return 'advanced'


def build_payload(generation, issued_at, expires_at, roles=None, now=None):
    value = {'schemaVersion': 1, 'purpose': PURPOSE, 'generation': generation,
             'issuedAt': issued_at, 'expiresAt': expires_at,
             'roles': roles if roles is not None else {k: list(v) for k, v in DEFAULT_ROLES.items()}}
    raw = canonical(value)
    validate_payload(raw, now)
    return raw


def maintenance(root, output, publication_commit, now=None, probe=None):
    """Advisory checks plus unsigned renewal proposal, never signing/pushing."""
    root, output = pathlib.Path(root), pathlib.Path(output)
    if not re.fullmatch(r"[0-9a-f]{40}", publication_commit):
        raise hubcore.HubError("maintenance requires the checkout's immutable publication commit")
    clock = utc_now(now)
    paths = [root / PAYLOAD_PATH, root / SIGNATURE_PATH]
    if not any(p.exists() for p in paths):
        output.mkdir(parents=True, exist_ok=True)
        report = {'status': 'not-initialized', 'renewal': 'initial signed publication required'}
        (output / 'maintenance.json').write_bytes(canonical(report))
        return report
    if not all(p.is_file() and not p.is_symlink() for p in paths):
        raise hubcore.HubError('maintenance signed pair is missing or unsafe')
    if paths[0].stat().st_size > MAX_PAYLOAD or paths[1].stat().st_size > MAX_SIGNATURE:
        raise hubcore.HubError('maintenance signed pair exceeds bounds')
    trust_doc = json.loads((root / 'public-key.json').read_bytes())
    if trust_doc.get('keyID') != hubcore.PRODUCTION_KEY_ID:
        raise hubcore.HubError('maintenance requires the configured official key identity')
    trust = {trust_doc['keyID']: trust_doc['publicKey']}
    payload = paths[0].read_bytes()
    value, key_id = verify_manifest(payload, paths[1].read_bytes(), trust, clock, allow_expired=True)
    expiry = timestamp(value['expiresAt'])
    report = {'status': 'expired' if expiry <= clock else 'verified',
              'observedFrom': 'GitHub Actions runner (not the user device)',
              'publicationCommit': publication_commit, 'generation': value['generation'],
              'keyID': key_id, 'payloadSHA256': hashlib.sha256(payload).hexdigest(),
              'expiresAt': value['expiresAt'], 'health': [], 'renewal': 'not-due',
              'policyChanged': False}
    expected = (root / 'catalog-full.sig').read_bytes() if (root / 'catalog-full.sig').is_file() else None
    if probe is None:
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        opener = urllib.request.build_opener(NoRedirect())
        def probe(url):
            try:
                with opener.open(urllib.request.Request(url, headers={'User-Agent': 'Floe-Transport-Health'}), timeout=10) as response:
                    raw = response.read(65_537)
                    return response.status, raw
            except urllib.error.HTTPError as error:
                return error.code, b''
    for role, ids in value['roles'].items():
        if role == 'releaseAssets':
            if ids: report['health'].append({'role': role, 'status': 'caller-not-qualified'})
            continue
        original = (f'https://raw.githubusercontent.com/JiangNanGenius/floe-skill-hub/{publication_commit}/catalog-full.sig'
                    if role == 'rawFiles' else 'https://github.com/JiangNanGenius/floe-skill-hub/commits/main.atom')
        for identifier in ids:
            url = 'https://' + identifier + '/' + original
            row = {'role': role, 'id': identifier, 'url': url}
            try:
                status, raw = probe(url)
                row.update(httpStatus=status, byteCount=len(raw), sha256=hashlib.sha256(raw).hexdigest())
                row['status'] = ('oversized' if len(raw) > 65_536 else
                                 'sample-mismatch' if role == 'rawFiles' and status == 200 and expected is not None and raw != expected else
                                 'http-200' if status == 200 else 'http-failure')
            except Exception as error:
                row.update(status='network-failure', errorType=type(error).__name__)
            report['health'].append(row)
    output.mkdir(parents=True, exist_ok=True)
    if expiry - clock <= dt.timedelta(days=7):
        if value['generation'] == MAX_GENERATION:
            report['renewal'] = 'generation-exhausted'
        else:
            stamp = lambda moment: moment.replace(microsecond=0).isoformat(timespec='seconds').replace('+00:00', 'Z')
            proposed = build_payload(value['generation'] + 1, stamp(clock), stamp(clock + dt.timedelta(days=14)),
                                     roles=value['roles'], now=clock)
            (output / 'mirrors.v1.candidate.json').write_bytes(proposed)
            report['renewal'] = 'unsigned-candidate-only'
            report['candidateSHA256'] = hashlib.sha256(proposed).hexdigest()
            report['candidateGeneration'] = value['generation'] + 1
    (output / 'maintenance.json').write_bytes(canonical(report))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest='command', required=True)
    generate = sub.add_parser('generate')
    generate.add_argument('--generation', type=int, required=True)
    generate.add_argument('--issued-at', required=True)
    generate.add_argument('--expires-at', required=True)
    generate.add_argument('--out', type=pathlib.Path, required=True)
    check = sub.add_parser('check')
    check.add_argument('--payload', type=pathlib.Path, required=True)
    check.add_argument('--signature', type=pathlib.Path)
    check.add_argument('--trust', type=pathlib.Path)
    maintain = sub.add_parser('maintenance')
    maintain.add_argument('--root', type=pathlib.Path, required=True)
    maintain.add_argument('--out', type=pathlib.Path, required=True)
    maintain.add_argument('--publication-commit', required=True)
    args = parser.parse_args()
    if args.command == 'generate':
        raw = build_payload(args.generation, args.issued_at, args.expires_at)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        if args.out.exists():
            raise SystemExit('refusing to overwrite an existing transport payload')
        args.out.write_bytes(raw)
        print('canonical transport candidate generated; no signature or publication')
    elif args.command == 'maintenance':
        report = maintenance(args.root, args.out, args.publication_commit)
        print('transport maintenance: ' + report['status'] + ', ' + report['renewal'])
    else:
        raw = args.payload.read_bytes()
        if args.signature:
            if not args.trust:
                raise SystemExit('--trust is required for detached signature verification')
            trust_doc = json.loads(args.trust.read_bytes())
            trust = {trust_doc['keyID']: trust_doc['publicKey']}
            value, key_id = verify_manifest(raw, args.signature.read_bytes(), trust)
            print(f'verified transport generation {value["generation"]}, key {key_id}')
        else:
            value = validate_payload(raw)
            print(f'valid unsigned transport candidate generation {value["generation"]}; not trusted')


if __name__ == '__main__':
    try:
        main()
    except hubcore.HubError as error:
        raise SystemExit(str(error)) from None
