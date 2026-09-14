import unittest

from lumolift.monitoring import PostureThresholds, classify_posture


class PostureClassificationTests(unittest.TestCase):
    def test_default_thresholds_match_original_app(self):
        self.assertEqual(classify_posture("sit_good", 84.9), "forward")
        self.assertEqual(classify_posture("sit_good", 85.0), "good")
        self.assertEqual(classify_posture("stand", 95.0), "good")
        self.assertEqual(classify_posture("stand", 95.1), "back")

    def test_not_worn_states(self):
        self.assertEqual(classify_posture("not_worn", 90), "not worn")
        self.assertEqual(classify_posture("inactive", 90), "not worn")
        self.assertEqual(classify_posture(None, None), "not worn")

    def test_custom_thresholds(self):
        thresholds = PostureThresholds(80, 100)
        self.assertEqual(classify_posture("stand", 82, thresholds), "good")

    def test_invalid_threshold_order(self):
        with self.assertRaisesRegex(ValueError, "forward threshold"):
            PostureThresholds(95, 85)
