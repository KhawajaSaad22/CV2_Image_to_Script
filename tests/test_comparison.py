import unittest
import numpy as np
from comparison import absolute_difference


class ComparisonTests(unittest.TestCase):
    def test_difference_avoids_uint8_wraparound_and_does_not_mutate_inputs(self):
        a=np.array([[0,255]],dtype=np.uint8);b=np.array([[255,0]],dtype=np.uint8)
        original=a.copy();result=absolute_difference(a,b)
        np.testing.assert_array_equal(result,[[255,255]])
        np.testing.assert_array_equal(a,original)
        self.assertEqual(result.dtype,np.uint8)
        np.testing.assert_array_equal(absolute_difference(a,a),np.zeros_like(a))

    def test_grayscale_rgb_broadcasting_both_directions(self):
        gray=np.array([[10]],dtype=np.uint8);rgb=np.array([[[5,10,20]]],dtype=np.uint8)
        np.testing.assert_array_equal(absolute_difference(gray,rgb),[[[5,0,10]]])
        np.testing.assert_array_equal(absolute_difference(rgb,gray),[[[5,0,10]]])

    def test_unsupported_shapes_types_and_dimensions_are_rejected(self):
        valid=np.zeros((2,3),dtype=np.uint8)
        for other in (np.zeros((3,2),dtype=np.uint8),np.zeros((2,3,4),dtype=np.uint8),
                      np.zeros((2,3),dtype=np.float32),np.zeros((0,3),dtype=np.uint8),[1,2]):
            with self.subTest(other=type(other)),self.assertRaises(ValueError):absolute_difference(valid,other)
