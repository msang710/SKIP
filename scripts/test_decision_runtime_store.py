import tempfile
import unittest
from pathlib import Path

from scripts.decision_runtime_store import RuntimeStore, StoreError


class RuntimeStoreTest(unittest.TestCase):
    def test_exclusive_event_and_rebuildable_projection(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = RuntimeStore(Path(temporary) / ".skip")
            event = {"sequence": 1, "event_id": "one", "previous_event_id": None}
            projection = {"head": "one"}
            store.commit(event, projection)
            store.commit(event, projection)
            self.assertEqual(store.events(), [event])
            store.projection_path.unlink()
            store.recover(projection)
            self.assertTrue(store.projection_path.exists())

    def test_lock_contention_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = RuntimeStore(Path(temporary) / ".skip")
            with store.lock():
                with self.assertRaises(StoreError) as raised:
                    with store.lock():
                        pass
            self.assertEqual(raised.exception.code, "LEDGER_CONFLICT")


if __name__ == "__main__":
    unittest.main()
