"""Mirror DATA refresh: real disposable Git histories, isolated fixture key.

No production signing key, network, account or App execution is involved.
"""
import datetime as dt
import json
import pathlib
import tempfile
import unittest
import sys
sys.dont_write_bytecode = True
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import automatic_transport as at
import transport_manifest as tm
import hubcore
import test_automatic_transport as fixtures
from test_automatic_transport import (TEST_KEY, TEST_PUB,
    _init_repo, _write, _commit_all, _git)


class TransportHistory(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = _init_repo(pathlib.Path(self.temp.name)/'hub')
        _write(self.root, 'public-key.json', hubcore.encoded({'keyID': hubcore.PRODUCTION_KEY_ID, 'publicKey': TEST_PUB}))
        self.anchor = _commit_all(self.root, 'isolated trusted anchor')
        self.now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)

    def pair(self, generation=1, *, roles=None, key=TEST_KEY, domain=tm.DOMAIN, expired=False):
        now = self.now-dt.timedelta(days=20) if expired else self.now
        stamp = lambda value: value.isoformat(timespec='seconds').replace('+00:00', 'Z')
        payload = tm.build_payload(generation, stamp(now), stamp(now+dt.timedelta(days=14)), roles=roles, now=now)
        return payload, hubcore.sign_envelope(domain+payload, key, hubcore.PRODUCTION_KEY_ID)

    def commit_pair(self, pair):
        _write(self.root, tm.PAYLOAD_PATH, pair[0]); _write(self.root, tm.SIGNATURE_PATH, pair[1])
        return _commit_all(self.root, 'isolated transport data')

    def verify(self, tip):
        return at.verify_transport_history(self.root, self.anchor, tip)

    def test_only_fixed_pair_paths_are_data(self):
        for path in [tm.PAYLOAD_PATH, tm.SIGNATURE_PATH]:
            self.assertTrue(at.is_refresh_data_path(path))
        for path in ['transport/other.json', tm.PAYLOAD_PATH+'/child', tm.PAYLOAD_PATH+'.bak',
                     'scripts/transport_manifest.py', '.github/workflows/transport-renewal.yml', 'public-key.json']:
            self.assertFalse(at.is_refresh_data_path(path))

    def test_initial_and_advanced_signed_history(self):
        one = self.commit_pair(self.pair())
        self.assertEqual(self.verify(one), 1)
        two = self.commit_pair(self.pair(2))
        self.assertEqual(self.verify(two), 2)

    def test_expired_history_retains_floor(self):
        self.commit_pair(self.pair(4, expired=True))
        tip = self.commit_pair(self.pair(5))
        self.assertEqual(self.verify(tip), 2)

    def test_unsigned_intermediate_cannot_hide_behind_valid_endpoint(self):
        one = self.pair(); self.commit_pair(one)
        bad = self.pair(2); self.commit_pair((bad[0], one[1]))
        tip = self.commit_pair(self.pair(3))
        with self.assertRaisesRegex(at.TransportError, 'transport history refused'):
            self.verify(tip)

    def test_rollback_intermediate_cannot_hide_behind_later_advance(self):
        self.commit_pair(self.pair(3)); self.commit_pair(self.pair(2))
        tip = self.commit_pair(self.pair(4))
        with self.assertRaisesRegex(at.TransportError, 'rollback'):
            self.verify(tip)

    def test_changed_roles_at_same_generation_refused(self):
        self.commit_pair(self.pair())
        roles = dict(tm.DEFAULT_ROLES, releaseAssets=['ghfast.top'])
        tip = self.commit_pair(self.pair(roles=roles))
        with self.assertRaisesRegex(at.TransportError, 'generation reused'):
            self.verify(tip)

    def test_signature_representation_cannot_change_at_same_generation(self):
        pair = self.pair(); self.commit_pair(pair)
        tip = self.commit_pair((pair[0], json.dumps(json.loads(pair[1]), indent=2).encode()))
        with self.assertRaisesRegex(at.TransportError, 'signature changed'):
            self.verify(tip)

    def test_partial_pair_and_deletion_fail(self):
        _write(self.root, tm.PAYLOAD_PATH, self.pair()[0])
        tip = _commit_all(self.root, 'partial pair')
        with self.assertRaisesRegex(at.TransportError, 'partial'):
            self.verify(tip)
        tip = self.commit_pair(self.pair())
        self.anchor = tip
        (self.root/tm.PAYLOAD_PATH).unlink(); (self.root/tm.SIGNATURE_PATH).unlink()
        removed = _commit_all(self.root, 'pair removed')
        with self.assertRaisesRegex(at.TransportError, 'disappear'):
            self.verify(removed)

    def test_wrong_signature_domain_fails(self):
        tip = self.commit_pair(self.pair(domain=b''))
        with self.assertRaises(at.TransportError):
            self.verify(tip)

    def test_oversize_and_executable_pair_fail_before_blob_trust(self):
        tip = self.commit_pair((b'x'*(tm.MAX_PAYLOAD+1), self.pair()[1]))
        with self.assertRaisesRegex(at.TransportError, 'byte bounds'):
            self.verify(tip)
        pair = self.pair(); self.anchor = self.commit_pair(pair)
        (self.root/tm.PAYLOAD_PATH).chmod(0o755)
        tip = _commit_all(self.root, 'executable mode')
        with self.assertRaisesRegex(at.TransportError, 'non-executable'):
            self.verify(tip)

    def test_full_existing_history_gate_accepts_signed_pair_without_weakening_ledger(self):
        # Exercise the actual existing ledger/feed validator, not a mock.
        fixture = fixtures.HistoryRefreshTestCase()
        with tempfile.TemporaryDirectory() as temp:
            fixture.build_hub(temp)
            payload, signature = self.pair()
            _write(fixture.root, tm.PAYLOAD_PATH, payload)
            _write(fixture.root, tm.SIGNATURE_PATH, signature)
            live = _commit_all(fixture.root, 'official-domain isolated mirror fixture')
            verdict = fixture.refresh(live)
            self.assertEqual(verdict['status'], 'refresh-ok')
            self.assertEqual(verdict['transportStatesVerified'], 1)
            self.assertEqual(verdict['appendedLedgerRows'], 0)
            self.assertGreater(verdict['baselineHistoricalFacts'], 0)


if __name__ == '__main__':
    unittest.main()
