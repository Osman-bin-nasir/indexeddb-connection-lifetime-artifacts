"""Offline validator tests. Synthetic fixtures are never experimental records."""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parents[1]
sys.path.insert(0, str(HERE))
import pin_contract as pin


def function(path, name):
    return next(node for node in ast.parse(path.read_text()).body
                if isinstance(node, ast.FunctionDef) and node.name == name)


class ValidatorTests(unittest.TestCase):
    def events(self, family):
        return [dict(kind='WORKER_EXECUTABLE_SOURCE', recovery=recovery,
                     path=path, sha256=digest)
                for recovery, path, digest in pin.expected_events(family)]

    def test_actual_311_events_match_scientific_pin(self):
        path = CAMPAIGN / 'scientific/attempts/scientific-target_byte_diagnostics-00001/events.jsonl'
        self.assertTrue(pin.verify_worker_events([json.loads(line) for line in path.read_text().splitlines()],
                                                'target_byte_diagnostics'))

    def test_byte_and_timeline_accept_only_expected_contract(self):
        for family in ['target_byte_diagnostics', 'trace_category_timelines']:
            with self.subTest(family=family):
                self.assertTrue(pin.verify_worker_events(self.events(family), family))

    def test_negative_event_cases(self):
        for family in ['target_byte_diagnostics', 'trace_category_timelines']:
            valid = self.events(family)
            cases = {'missing_all': [], 'missing_reader': valid[:1],
                     'extra_source': valid + [valid[1]], 'reversed': valid[::-1]}
            for position in [0, 1]:
                for key, value in [('path', '/opt/idbv2/worker/guest_worker.py'),
                                   ('path', '/opt/idbv2/unregistered-worker.py'),
                                   ('sha256', '055980789fa5993910dce05eebdec01fcbc026ed94680c2182865ed5ce0b0fda'),
                                   ('sha256', '0' * 64),
                                   ('recovery', not valid[position]['recovery']),
                                   ('recovery', int(valid[position]['recovery']))]:
                    events = copy.deepcopy(valid)
                    events[position][key] = value
                    cases[f'{position}:{key}:{value}'] = events
                for key in ['path', 'sha256', 'recovery']:
                    events = copy.deepcopy(valid)
                    del events[position][key]
                    cases[f'{position}:missing:{key}'] = events
            for name, events in cases.items():
                with self.subTest(family=family, name=name):
                    self.assertFalse(pin.verify_worker_events(events, family))

    def test_wrong_family_is_rejected(self):
        with self.assertRaises(RuntimeError):
            pin.verify_worker_events([], 'unregistered')

    def test_changed_original_lock_is_rejected(self):
        with patch.object(pin, 'sha', return_value='0' * 64):
            with self.assertRaisesRegex(RuntimeError, 'lock changed'):
                pin.frozen_pins()

    def test_changed_scientific_source_is_rejected(self):
        original = pin.sha
        def altered(path):
            return '0' * 64 if Path(path).name == 'guest_worker.py' else original(path)
        with patch.object(pin, 'sha', side_effect=altered):
            with self.assertRaisesRegex(RuntimeError, 'executable source changed'):
                pin.frozen_pins()

    def test_every_other_audit_predicate_is_identical(self):
        for number, filename, check, family in [('012', 'audit_bytes_v1.py', 'pinned_measurement_and_reader', 'target_byte_diagnostics'),
                                                 ('011', 'audit_timelines_v1.py', 'pinned_oracle_reader', 'trace_category_timelines')]:
            original = function(CAMPAIGN / f'operator/backend_v1/engine/repairs/{number}/independent_audit.py', 'audit')
            adjusted = copy.deepcopy(original)
            adjusted.name = '_audit_body'
            matches = 0
            for node in ast.walk(adjusted):
                if isinstance(node, ast.Assign) and len(node.targets) == 1:
                    target = node.targets[0]
                    if (isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name)
                        and target.value.id == 'checks' and isinstance(target.slice, ast.Constant)
                        and target.slice.value == check):
                        node.value = ast.parse(f"verify_worker_events(events, '{family}')", mode='eval').body
                        matches += 1
            self.assertEqual(matches, 1)
            actual = function(HERE / filename, '_audit_body')
            self.assertEqual(ast.dump(adjusted, include_attributes=False), ast.dump(actual, include_attributes=False))


if __name__ == '__main__':
    unittest.main(verbosity=2)
