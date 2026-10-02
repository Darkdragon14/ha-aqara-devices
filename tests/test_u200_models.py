from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONST_PATH = ROOT / "custom_components" / "ha_aqara_devices" / "const.py"
SPEC = importlib.util.spec_from_file_location("u200_const_under_test", CONST_PATH)
assert SPEC is not None and SPEC.loader is not None
const = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(const)


class U200ModelTests(unittest.TestCase):
    def test_standard_and_lite_models_are_detected_as_u200_locks(self):
        devices = [
            {"did": "standard", "model": "aqara.matter.4447_10242"},
            {"did": "lite", "model": "aqara.matter.4447_10247"},
            {"did": "u300", "model": "aqara.matter.4447_10241", "parentDid": ""},
            {"did": "u400", "model": "aqara.matter.4447_10244", "parentDid": ""},
            {"did": "other", "model": "unsupported.model"},
        ]

        u200_locks = [
            device for device in devices if device.get("model") in const.U200_MODELS
        ]

        self.assertEqual([device["did"] for device in u200_locks], ["standard", "lite", "u300", "u400"])

    def test_model_labels_preserve_u200_and_identify_new_locks(self):
        self.assertEqual(const.MATTER_LOCK_MODEL_LABELS[const.U200_MODEL], const.U200_DEVICE_LABEL)
        self.assertEqual(const.MATTER_LOCK_MODEL_LABELS[const.U200_LITE_MODEL], const.U200_DEVICE_LABEL)
        self.assertEqual(const.MATTER_LOCK_MODEL_LABELS[const.U300_MODEL], "Aqara Smart Lock U300")
        self.assertEqual(const.MATTER_LOCK_MODEL_LABELS[const.U400_MODEL], "Aqara Smart Lock U400")


if __name__ == "__main__":
    unittest.main()
