"""Same-role renewal: isolated ephemeral keys and real local Git commits."""
import base64
import copy
import datetime as dt
import json
import pathlib
import shutil
import os
import subprocess
import sys
import tempfile
import unittest
sys.dont_write_bytecode = True
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import hubcore
import transport_manifest as tm
import transport_renewal as renewal
from test_automatic_transport import _init_repo, _write, _commit_all, _git


class Renewal(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = _init_repo(pathlib.Path(self.temp.name)/'hub')
        Key, _, serialization, _ = hubcore._load_ed25519()
        self.key = Key.generate()
        public = base64.b64encode(self.key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
        self.trust = {hubcore.PRODUCTION_KEY_ID: public}
        _write(self.root, 'public-key.json', hubcore.encoded({'keyID': hubcore.PRODUCTION_KEY_ID, 'publicKey': public}))
        for rel in renewal.FROZEN_CODE:
            if rel != 'public-key.json':
                _write(self.root, rel, (ROOT/rel).read_bytes())
        self.now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        stamp = lambda value: value.isoformat(timespec='seconds').replace('+00:00', 'Z')
        self.raw = tm.build_payload(8, stamp(self.now-dt.timedelta(days=7)), stamp(self.now+dt.timedelta(days=7)), now=self.now)
        self.signature = hubcore.sign_envelope(tm.DOMAIN+self.raw, self.key, hubcore.PRODUCTION_KEY_ID)
        _write(self.root, tm.PAYLOAD_PATH, self.raw); _write(self.root, tm.SIGNATURE_PATH, self.signature)
        self.base = self.tooling = _commit_all(self.root, 'isolated reviewed fixture')

    def bundle(self):
        return renewal.signed_bundle(self.root, self.base, self.root, self.tooling, self.key,
            now=self.now, workflow_commit='e'*40, run_id='1234')

    def resign(self, files, field, value):
        receipt = json.loads(files[renewal.RECEIPT]); receipt[field] = value
        files[renewal.RECEIPT] = tm.canonical(receipt)
        files[renewal.RECEIPT_SIG] = hubcore.sign_envelope(renewal.RECEIPT_DOMAIN+files[renewal.RECEIPT], self.key, hubcore.PRODUCTION_KEY_ID)

    def test_exact_same_roles_due_and_expired_floor(self):
        files = self.bundle(); receipt = renewal.verify_bundle(files, self.root, self.trust, self.now)
        value = tm.validate_payload(files[renewal.FLAT_PAYLOAD], self.now)
        self.assertEqual(value['generation'], 9); self.assertEqual(value['roles'], tm.DEFAULT_ROLES)
        self.assertEqual(tm.timestamp(value['expiresAt'])-tm.timestamp(value['issuedAt']), dt.timedelta(days=14))
        self.assertEqual(receipt['baseCommit'], self.base)
        later = self.now+dt.timedelta(days=10)
        proposed = renewal.renewal_payload(self.raw, self.signature, self.trust, later)
        self.assertEqual(tm.validate_payload(proposed, later)['generation'], 9)

    def test_not_due_signs_nothing(self):
        earlier = self.now-dt.timedelta(seconds=1)
        self.assertIsNone(renewal.renewal_payload(self.raw, self.signature, self.trust, earlier))
        self.assertIsNone(renewal.signed_bundle(self.root, self.base, self.root, self.tooling, self.key,
            now=earlier, workflow_commit='e'*40, run_id='1234'))

    def test_role_order_host_generation_and_lifetime_cannot_be_renewed(self):
        good = json.loads(self.bundle()[renewal.FLAT_PAYLOAD])
        variants = []
        for field, val in [('generation',8),('generation',10),('expiresAt','2026-12-31T00:00:00Z')]:
            v=copy.deepcopy(good);v[field]=val;variants.append(v)
        v=copy.deepcopy(good);v['roles']['rawFiles'].reverse();variants.append(v)
        v=copy.deepcopy(good);v['roles']['releaseAssets']=['ghfast.top'];variants.append(v)
        v=copy.deepcopy(good);v['roles']['rawFiles']=['unapproved.invalid'];variants.append(v)
        for value in variants:
            with self.subTest(value=value), self.assertRaises(hubcore.HubError):
                renewal.verify_same_roles(self.raw,self.signature,tm.canonical(value),self.trust,self.now)

    def test_relay_requires_both_domain_separated_signatures(self):
        for name in [renewal.FLAT_SIGNATURE, renewal.RECEIPT_SIG]:
            files=self.bundle()
            signed=files[renewal.FLAT_PAYLOAD] if name==renewal.FLAT_SIGNATURE else files[renewal.RECEIPT]
            files[name]=hubcore.sign_envelope(signed,self.key,hubcore.PRODUCTION_KEY_ID)
            with self.assertRaises(hubcore.HubError):renewal.verify_bundle(files,self.root,self.trust,self.now)

    def test_receipt_fields_bound_even_with_valid_official_test_signature(self):
        for field,value in [('baseTree','f'*40),('basePayloadSHA256','0'*64),('requestID','0'*64),
                            ('generation',True),('outputs',{}),('runID','not-a-run')]:
            files=self.bundle();self.resign(files,field,value)
            with self.subTest(field=field),self.assertRaises(hubcore.HubError):
                renewal.verify_bundle(files,self.root,self.trust,self.now)

    def test_truncated_extra_symlink_and_oversize_artifacts_rejected(self):
        files=self.bundle()
        for extra in [dict(files,other=b'x'),{name:raw for name,raw in files.items() if name!=renewal.RECEIPT},
                      dict(files,**{renewal.RECEIPT:b'x'*16_385})]:
            with self.assertRaises(hubcore.HubError):renewal.verify_bundle(extra,self.root,self.trust,self.now)
        out=pathlib.Path(self.temp.name)/'bundle';out.mkdir()
        for name,raw in files.items():(out/name).write_bytes(raw)
        (out/'other').write_text('unexpected')
        with self.assertRaises(hubcore.HubError):renewal.read_bundle(out)
        (out/'other').unlink();(out/renewal.FLAT_PAYLOAD).unlink()
        (out/renewal.FLAT_PAYLOAD).symlink_to(self.root/tm.PAYLOAD_PATH)
        with self.assertRaises(hubcore.HubError):renewal.read_bundle(out)

    def test_publication_commit_is_deterministic_two_files_only(self):
        files=self.bundle()
        relay=renewal.data_commit(self.root,None,{renewal.RELAY_PREFIX+n:raw for n,raw in files.items()},'isolated relay',json.loads(files[renewal.RECEIPT])['issuedAt'])
        self.assertEqual(renewal.committed_relay(self.root,relay),files)
        first=renewal.publication_plan(self.root,self.base,relay,files,self.now)
        second=renewal.publication_plan(self.root,self.base,relay,files,self.now)
        self.assertEqual(first,second)
        self.assertEqual(set(_git(self.root,'diff-tree','--no-commit-id','--name-only','-r',self.base,first['commit']).splitlines()),{tm.PAYLOAD_PATH,tm.SIGNATURE_PATH})
        self.assertEqual(_git(self.root,'rev-parse',first['commit']+'^').strip(),self.base)
        recovered=renewal.publication_plan(self.root,first['commit'],relay,files,self.now)
        self.assertEqual(recovered['action'],'already-published')

    def test_stale_base_does_not_publish_over_unrelated_main(self):
        files=self.bundle();_write(self.root,'sources/independent.md',b'preserve')
        current=_commit_all(self.root,'independent content')
        verdict=renewal.publication_plan(self.root,current,'d'*40,files,self.now)
        self.assertEqual(verdict['action'],'stale-base')
        self.assertNotIn('commit',verdict)

    def test_tooling_drift_is_not_approved_by_receipt(self):
        _write(self.root,'scripts/transport_renewal.py',b'changed verifier')
        current=_commit_all(self.root,'unreviewed helper change')
        files=renewal.signed_bundle(self.root,current,self.root,self.tooling,self.key,
            now=self.now,workflow_commit='e'*40,run_id='1234')
        with self.assertRaisesRegex(hubcore.HubError,'code differs'):
            renewal.publication_plan(self.root,current,'d'*40,files,self.now)

    def test_immutable_blob_bounds_and_relay_foreign_files(self):
        _write(self.root,'oversize',b'x'*101);large=_commit_all(self.root,'bounded input')
        with self.assertRaisesRegex(hubcore.HubError,'size'):renewal.blob(self.root,large,'oversize',100)
        relay=renewal.data_commit(self.root,None,{'foreign':b'x'},'foreign metadata',json.loads(self.bundle()[renewal.RECEIPT])['issuedAt'])
        with self.assertRaisesRegex(hubcore.HubError,'beyond'):renewal.committed_relay(self.root,relay)

    def test_stale_valid_signed_proposal_expires_and_keys_are_not_read_by_plan(self):
        files=self.bundle()
        with self.assertRaises(hubcore.HubError):renewal.verify_bundle(files,self.root,self.trust,self.now+dt.timedelta(days=2))
        # Pure plan has no environment-key input or signing operation.
        proposed=renewal.renewal_payload(self.raw,self.signature,self.trust,self.now)
        self.assertEqual(tm.validate_payload(proposed,self.now)['roles'],tm.DEFAULT_ROLES)

    def test_completed_relay_remains_idempotent_after_one_day(self):
        files=self.bundle();first=renewal.publication_plan(self.root,self.base,'d'*40,files,self.now)
        recovered=renewal.publication_plan(self.root,first['commit'],'d'*40,files,self.now+dt.timedelta(days=2))
        self.assertEqual(recovered['action'],'already-published')
        self.assertEqual(recovered['commit'],first['commit'])
        with self.assertRaises(hubcore.HubError):
            renewal.publication_plan(self.root,self.base,'d'*40,files,self.now+dt.timedelta(days=2))

    def test_actual_plan_cli_verifies_snapshots_and_reads_no_key(self):
        out=pathlib.Path(self.temp.name)/'plan-output'
        env=os.environ.copy();env.pop('FLOE_SKILL_HUB_SIGNING_KEY',None)
        command=[sys.executable,'-I',str(self.root/'scripts/transport_renewal.py'),'plan',
            '--root',str(self.root),'--base',self.base,'--tooling',str(self.root),
            '--tooling-commit',self.tooling,'--out',str(out)]
        result=subprocess.run(command,env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads((out/'status.json').read_bytes())['action'],'renew')
        self.assertEqual(set(p.name for p in out.iterdir()),{'status.json'})
        # An untracked shadow is rejected before planning/signing.
        _write(self.root,'shadow.py',b'not executed')
        result=subprocess.run(command[:-1]+[str(pathlib.Path(self.temp.name)/'rejected')],env=env,capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)

    def test_relay_replay_is_unchanged_and_older_metadata_cannot_replace_it(self):
        files=self.bundle();issued=json.loads(files[renewal.RECEIPT])['issuedAt']
        empty=renewal.data_commit(self.root,None,{},'empty isolated relay',issued)
        first=renewal.relay_plan(self.root,empty,files,self.root,self.trust,self.now)
        same=renewal.relay_plan(self.root,first['commit'],files,self.root,self.trust,self.now)
        self.assertEqual(same['action'],'relay-unchanged');self.assertEqual(same['commit'],first['commit'])
        later=renewal.signed_bundle(self.root,self.base,self.root,self.tooling,self.key,
            now=self.now+dt.timedelta(seconds=10),workflow_commit='e'*40,run_id='1235')
        newer=renewal.relay_plan(self.root,first['commit'],later,self.root,self.trust,self.now+dt.timedelta(seconds=10))
        with self.assertRaisesRegex(hubcore.HubError,'older or conflicting'):
            renewal.relay_plan(self.root,newer['commit'],files,self.root,self.trust,self.now+dt.timedelta(seconds=10))


if __name__=='__main__':unittest.main()
