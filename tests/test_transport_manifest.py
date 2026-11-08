"""Transport v1: isolated ephemeral keys/repos, no real signing or network."""
import base64
import copy
import datetime as dt
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
sys.dont_write_bytecode = True
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import hubcore
import transport_manifest as tm


def test_key():
    Key, _, s, _ = hubcore._load_ed25519(); key = Key.generate()
    seed = key.private_bytes(s.Encoding.Raw, s.PrivateFormat.Raw, s.NoEncryption())
    pub = base64.b64encode(key.public_key().public_bytes(s.Encoding.Raw, s.PublicFormat.Raw)).decode()
    return key, seed, pub


class Contract(unittest.TestCase):
    def setUp(self):
        self.key, _, public = test_key(); self.trust = {'isolated-test': public}
        self.now = dt.datetime(2026, 11, 8, 11, tzinfo=dt.timezone.utc)
        self.raw = tm.build_payload(1, '2026-11-08T10:00:00Z', '2026-11-15T10:00:00Z', now=self.now)
    def sign(self, raw, domain=tm.DOMAIN): return hubcore.sign_envelope(domain + raw, self.key, 'isolated-test')
    def test_domain_and_canonical_positive(self):
        v, kid = tm.verify_manifest(self.raw, self.sign(self.raw), self.trust, self.now)
        self.assertEqual(v['roles'], tm.DEFAULT_ROLES); self.assertEqual(kid, 'isolated-test')
        for signature, trust in [(self.sign(self.raw, b''), self.trust), (self.sign(self.raw), {})]:
            with self.assertRaises(hubcore.HubError): tm.verify_manifest(self.raw, signature, trust, self.now)
    def test_signed_noncanonical_encodings_refused(self):
        for raw in [self.raw+b'\n', b'\xef\xbb\xbf'+self.raw, b'{"schemaVersion":1,'+self.raw[1:],
                    self.raw.replace(b'"generation":1', b'"generation":1.0'), json.dumps(json.loads(self.raw), indent=2).encode()]:
            with self.subTest(raw=raw[:30]), self.assertRaises(hubcore.HubError):
                tm.verify_manifest(raw, self.sign(raw), self.trust, self.now)
    def test_exact_shape_and_id_integer_limits(self):
        mutations = [('generation', x) for x in [True, 0, -1, tm.MAX_GENERATION+1]]
        mutations += [('schemaVersion', True), ('url', 'https://unapproved.invalid'), ('purpose', 'catalog')]
        for field, bad in mutations:
            v = json.loads(self.raw); v[field] = bad
            with self.subTest(field=field, bad=bad), self.assertRaises(hubcore.HubError): tm.validate_payload(tm.canonical(v), self.now)
        for roles in [{'rawFiles':['new.invalid'],'atom':[],'releaseAssets':[]},
                      {'rawFiles':['ghfast.top','ghfast.top'],'atom':[],'releaseAssets':[]},
                      {'rawFiles':[],'atom':[]}, {'rawFiles':[],'atom':[],'releaseAssets':[],'keys':[]}]:
            v=json.loads(self.raw);v['roles']=roles
            with self.assertRaises(hubcore.HubError): tm.validate_payload(tm.canonical(v), self.now)
        v=json.loads(self.raw);v['generation']=tm.MAX_GENERATION;tm.validate_payload(tm.canonical(v),self.now)
    def test_calendar_skew_expiry_bounds(self):
        for field, bad in [('issuedAt','2026-11-08T11:05:01Z'),('issuedAt','2026-02-30T10:00:00Z'),
                           ('issuedAt','2026-11-08T10:00:00+00:00'),('issuedAt','2026-11-08T10:00:00.0Z'),
                           ('expiresAt','2026-11-08T11:00:00Z'),('expiresAt','2026-12-08T10:00:01Z'),('expiresAt','2026-11-08T09:00:00Z')]:
            v=json.loads(self.raw);v[field]=bad
            with self.subTest(field=field,bad=bad),self.assertRaises(hubcore.HubError):tm.validate_payload(tm.canonical(v),self.now)
        v=json.loads(self.raw);v['issuedAt']='2026-11-08T11:05:00Z';tm.validate_payload(tm.canonical(v),self.now)
        tm.validate_payload(self.raw,self.now+dt.timedelta(days=20),allow_expired=True)
        with self.assertRaises(hubcore.HubError):tm.validate_payload(self.raw,self.now+dt.timedelta(days=20))
    def test_sizes_and_monotonic_generation(self):
        for payload,sig in [(b'x'*16385,b'x'),(self.raw,b'x'*8193)]:
            with self.assertRaises(hubcore.HubError):tm.verify_manifest(payload,sig,self.trust,self.now)
        v=json.loads(self.raw);higher=dict(v,generation=2)
        self.assertEqual(tm.enforce_generation(self.raw,v),'initial')
        self.assertEqual(tm.enforce_generation(self.raw,v,self.raw,v),'unchanged')
        self.assertEqual(tm.enforce_generation(tm.canonical(higher),higher,self.raw,v),'advanced')
        with self.assertRaises(hubcore.HubError):tm.enforce_generation(self.raw,v,tm.canonical(higher),higher)
        changed=copy.deepcopy(v);changed['roles']['rawFiles']=[]
        with self.assertRaises(hubcore.HubError):tm.enforce_generation(tm.canonical(changed),changed,self.raw,v)


class Maintenance(unittest.TestCase):
    def test_health_failures_only_make_unsigned_monotonic_renewal(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('FLOE_TEST_SCRATCH')) as temp:
            root=pathlib.Path(temp)/'root';out=pathlib.Path(temp)/'output';(root/'transport').mkdir(parents=True)
            key,_,public=test_key();now=dt.datetime(2026,11,8,11,tzinfo=dt.timezone.utc)
            raw=tm.build_payload(8,'2026-11-08T10:00:00Z','2026-11-15T10:00:00Z',now=now)
            (root/tm.PAYLOAD_PATH).write_bytes(raw);(root/tm.SIGNATURE_PATH).write_bytes(hubcore.sign_envelope(tm.DOMAIN+raw,key,hubcore.PRODUCTION_KEY_ID))
            (root/'public-key.json').write_bytes(hubcore.encoded({'keyID':hubcore.PRODUCTION_KEY_ID,'publicKey':public}))
            urls=[]
            def probe(url):urls.append(url);return 503,b''
            report=tm.maintenance(root,out,'a'*40,now,probe)
            self.assertEqual(len(urls),3);self.assertTrue(all(u.startswith(('https://ghfast.top/','https://gh-proxy.com/')) for u in urls))
            self.assertEqual(report['renewal'],'unsigned-candidate-only');self.assertFalse(report['policyChanged'])
            candidate=tm.validate_payload((out/'mirrors.v1.candidate.json').read_bytes(),now)
            self.assertEqual(candidate['generation'],9);self.assertEqual(candidate['roles'],tm.DEFAULT_ROLES)
            self.assertFalse((out/tm.SIGNATURE_PATH).exists());self.assertEqual((root/tm.PAYLOAD_PATH).read_bytes(),raw)
    def test_unsigned_list_cannot_drive_health_or_renewal(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('FLOE_TEST_SCRATCH')) as temp:
            root=pathlib.Path(temp)/'root';out=pathlib.Path(temp)/'output';(root/'transport').mkdir(parents=True)
            (root/tm.PAYLOAD_PATH).write_bytes(b'{}')
            with self.assertRaises(hubcore.HubError):tm.maintenance(root,out,'a'*40,probe=lambda _:self.fail('unverified probe'))
            self.assertEqual((root/tm.PAYLOAD_PATH).read_bytes(),b'{}')
    def test_not_initialized_is_reported_without_inventing_a_list(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('FLOE_TEST_SCRATCH')) as temp:
            root=pathlib.Path(temp)/'root';root.mkdir();out=pathlib.Path(temp)/'output'
            report=tm.maintenance(root,out,'a'*40)
            self.assertEqual(report['status'],'not-initialized');self.assertFalse((out/'mirrors.v1.candidate.json').exists())


class Bridge(unittest.TestCase):
    def git(self, root, *args):
        p=subprocess.run(['git','-C',str(root),*args],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr);return p.stdout.strip()
    def commit(self,root):
        self.git(root,'add','.')
        self.git(root,'-c','user.name=Transport Test','-c','user.email=transport@test.invalid','-c','commit.gpgsign=false','commit','-qm','isolated TEST snapshot')
        return self.git(root,'rev-parse','HEAD')
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=os.environ.get('FLOE_TEST_SCRATCH'));self.addCleanup(self.temp.cleanup)
        self.base=pathlib.Path(self.temp.name);self.tooling=self.base/'tooling';self.data=self.base/'data'
        for path in [self.tooling,self.data]:
            path.mkdir();self.git(path,'init','-q');self.git(path,'remote','add','origin','https://github.com/JiangNanGenius/floe-skill-hub.git')
        self.key,self.seed,self.public=test_key();(self.tooling/'scripts').mkdir()
        for name in ['sign_publication','hubcore','build_catalog','catalog_views','runtime_dependency','dependency_declaration','publication_immutability','transport_manifest']:
            shutil.copyfile(ROOT/f'scripts/{name}.py',self.tooling/f'scripts/{name}.py')
        (self.tooling/'public-key.json').write_bytes(hubcore.encoded({'keyID':hubcore.PRODUCTION_KEY_ID,'publicKey':self.public}))
        self.baseline=self.commit(self.tooling)
        now=dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        stamp=lambda x:x.isoformat(timespec='seconds').replace('+00:00','Z')
        self.raw=tm.build_payload(1,stamp(now),stamp(now+dt.timedelta(days=7)))
        (self.data/'transport').mkdir();(self.data/tm.PAYLOAD_PATH).write_bytes(self.raw)
        (self.data/'scripts').mkdir();(self.data/'scripts/transport_manifest.py').write_text('raise RuntimeError("CANDIDATE CODE EXECUTED")\n')
        self.source=self.commit(self.data)
    def run_bridge(self,key=True,baseline=True):
        env=os.environ.copy();env.pop('FLOE_SKILL_HUB_SIGNING_KEY',None)
        if key:env['FLOE_SKILL_HUB_SIGNING_KEY']=base64.b64encode(self.seed).decode()
        out=self.base/('out-'+os.urandom(4).hex())
        command=[sys.executable,'-I',str(self.tooling/'scripts/sign_publication.py'),'--mode','transport','--source-commit',self.source,'--data',str(self.data),'--tooling',str(self.tooling),'--out',str(out)]
        if baseline:command+=['--published-y',self.baseline]
        return subprocess.run(command,cwd=self.base,env=env,capture_output=True,text=True),out
    def publish_baseline(self,raw):
        (self.tooling/'transport').mkdir(exist_ok=True);(self.tooling/tm.PAYLOAD_PATH).write_bytes(raw)
        (self.tooling/tm.SIGNATURE_PATH).write_bytes(hubcore.sign_envelope(tm.DOMAIN+raw,self.key,hubcore.PRODUCTION_KEY_ID))
        self.baseline=self.commit(self.tooling)
    def test_real_data_only_bridge_and_context_receipt(self):
        result,out=self.run_bridge();self.assertEqual(result.returncode,0,result.stderr)
        raw=(out/tm.PAYLOAD_PATH).read_bytes();sig=(out/tm.SIGNATURE_PATH).read_bytes()
        self.assertEqual(raw,self.raw);tm.verify_manifest(raw,sig,{hubcore.PRODUCTION_KEY_ID:self.public})
        with self.assertRaises(hubcore.HubError):hubcore.verify_envelope(raw,sig,{hubcore.PRODUCTION_KEY_ID:self.public})
        receipt=json.loads((out/'signing-receipt.json').read_bytes())
        self.assertEqual(receipt['mode'],'transport');self.assertEqual(receipt['signatureDomain'],tm.DOMAIN.decode())
        self.assertEqual(receipt['sourceCommit'],self.source);self.assertEqual(receipt['generationTransition'],'initial')
        self.assertEqual(set(p.relative_to(out).as_posix() for p in out.rglob('*') if p.is_file()),{tm.PAYLOAD_PATH,tm.SIGNATURE_PATH,'signing-receipt.json','signing-receipt.json.sig'})
        self.assertEqual(self.git(self.data,'status','--porcelain'),'')
    def test_missing_key_or_baseline_refuses(self):
        for key,baseline in [(False,True),(True,False)]:
            result,out=self.run_bridge(key,baseline);self.assertNotEqual(result.returncode,0);self.assertFalse(out.exists())
    def test_lower_and_reused_generation_refused(self):
        v=json.loads(self.raw);v['generation']=5;self.publish_baseline(tm.canonical(v))
        result,out=self.run_bridge();self.assertNotEqual(result.returncode,0);self.assertFalse(out.exists())
        v['generation']=1;self.publish_baseline(tm.canonical(v));v['roles']['rawFiles']=[]
        (self.data/tm.PAYLOAD_PATH).write_bytes(tm.canonical(v));self.source=self.commit(self.data)
        result,out=self.run_bridge();self.assertNotEqual(result.returncode,0);self.assertFalse(out.exists())
    def test_identical_refresh_is_noop(self):
        self.publish_baseline(self.raw);result,out=self.run_bridge();self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads((out/'signing-receipt.json').read_bytes())['generationTransition'],'unchanged')
    def test_incomplete_pair_and_deleted_history_refused(self):
        self.publish_baseline(self.raw);(self.tooling/tm.SIGNATURE_PATH).unlink();self.baseline=self.commit(self.tooling)
        result,out=self.run_bridge();self.assertNotEqual(result.returncode,0);self.assertFalse(out.exists())
        (self.tooling/tm.PAYLOAD_PATH).unlink();self.baseline=self.commit(self.tooling)
        result,out=self.run_bridge();self.assertNotEqual(result.returncode,0);self.assertFalse(out.exists())
    def test_shadow_data_refused(self):
        (self.data/'untracked-shadow').write_text('not committed')
        result,out=self.run_bridge();self.assertNotEqual(result.returncode,0);self.assertFalse(out.exists())


if __name__=='__main__':unittest.main()
