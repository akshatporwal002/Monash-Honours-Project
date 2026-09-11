"""Regression checks for the pinned scanner's nonfunctional positive control."""

import math
import unittest
from collections import Counter

from secret_scan import positive_control_value


class PositiveControlTests(unittest.TestCase):
    def test_control_is_stable_and_above_the_pinned_entropy_threshold(self):
        value = positive_control_value()
        self.assertEqual(value, positive_control_value())
        self.assertEqual(len(value), 48)
        self.assertEqual(set(value), set("0123456789abcdef"))
        entropy = -sum(
            (count / len(value)) * math.log2(count / len(value))
            for count in Counter(value).values()
        )
        self.assertEqual(entropy, 4.0)
        self.assertGreater(entropy, 3.5)

    def test_control_avoids_pinned_generic_rule_hex_stopwords(self):
        # Hex-compatible entries in Gitleaks 8.28.0's generic-api-key stopwords.
        for word in (
            "000000",
            "6fe4476ee5a1832882e326b506d14126",
            "aaaaaa",
            "dead",
            "feed",
        ):
            with self.subTest(stopword=word):
                self.assertNotIn(word, positive_control_value())


if __name__ == "__main__":
    unittest.main()
