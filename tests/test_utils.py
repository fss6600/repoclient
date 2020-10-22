import unittest
from collections import OrderedDict

from eiisclient.functions import unjsonify, jsonify

TEST_DICT = OrderedDict({'KEY_1': 'DATA_1',
             'KEY_2': ['DATA_2'],
             'KEY_3': [None]})

TEST_JSON = """{
    "KEY_1": "DATA_1",
    "KEY_2": [
        "DATA_2"
        ],
    "KEY_3": [
        null
        ]
    }
"""


class CoreUtils(unittest.TestCase):
    def setUp(self):
        pass

    def test_1_to_json(self):
        res = jsonify(TEST_DICT)
        self.assertIsNotNone(res)
        self.assertIsInstance(res, str)
        for item in ('KEY_1', 'KEY_2', 'KEY_3', 'DATA_1', 'DATA_2', 'null'):
            self.assertTrue(item in res)

    def test_2_from_json(self):
        res = unjsonify(TEST_JSON)
        self.assertIsNotNone(res)
        self.assertIsInstance(res, dict)
        for key in ('KEY_1', 'KEY_2', 'KEY_3'):
            self.assertTrue(key in res.keys())

    def test_3_dict_comparison(self):
        dict_1 = unjsonify(TEST_JSON)
        self.assertTrue(dict_1 == TEST_DICT)


if __name__ == '__main__':  # pragma: nocover
    unittest.main()
