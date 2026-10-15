"""Independent boundary cases for evaluator arithmetic; no model imports."""
import math
import unittest
from cpu_latent_audit import decomposition, vote_bounds


class ArithmeticTests(unittest.TestCase):
    def test_scale_invariance(self):
        d = decomposition([1., -2., 3.], [7., -14., 21.])
        self.assertAlmostEqual(d["cosine"], 1.)
        self.assertEqual(d["sign_penalty"], 0.)

    def test_all_signs_flip(self):
        d = decomposition([1., -2., 3.], [-1., 2., -3.])
        self.assertAlmostEqual(d["cosine"], -1.)
        self.assertAlmostEqual(d["sign_penalty"], 2.)

    def test_weighted_error_is_not_coordinate_error(self):
        d = decomposition([1., 3.], [-1., 3.])
        self.assertEqual(d["coordinate_sign_agreement"], .5)
        self.assertAlmostEqual(d["weighted_sign_error"], .1)
        self.assertAlmostEqual(d["cosine"], .8)

    def test_same_sign_different_magnitude(self):
        d = decomposition([1., 2.], [2., 1.])
        self.assertAlmostEqual(d["magnitude_deficit"], .2)
        self.assertEqual(d["sign_penalty"], 0.)

    def test_reject_invalid(self):
        for a,b in [([], []), ([1.], [1.,2.]), ([0.],[1.]), ([math.nan],[1.]), ([1.],[math.inf])]:
            with self.assertRaises(ValueError):
                decomposition(a,b)

    def test_votes_and_tie_bounds(self):
        # Four replicas, three bits: correct-majority, tie, incorrect-majority.
        a = [1.]*12
        b = [1.,1.,-1., 1.,1.,-1., 1.,-1.,-1., -1.,-1.,1.]
        d = vote_bounds(a,b,width=3,repetitions=4)
        self.assertEqual(d["vote_accuracy_lower"], 1/3)
        self.assertEqual(d["vote_accuracy_upper"], 2/3)
        self.assertEqual(d["tied_message_positions"], 1)


if __name__ == "__main__":
    unittest.main()
