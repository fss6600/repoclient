import unittest

from collections import OrderedDict
from eiisclient.core.utils import to_json, from_json

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

    def test_to_json(self):
        res = to_json(TEST_DICT)
        self.assertIsNotNone(res)
        self.assertIsInstance(res, str)
        for item in ('KEY_1', 'KEY_2', 'KEY_3', 'DATA_1', 'DATA_2', 'null'):
            self.assertTrue(item in res)

    def test_from_json(self):
        res = from_json(TEST_JSON)
        self.assertIsNotNone(res)
        self.assertIsInstance(res, dict)
        for key in ('KEY_1', 'KEY_2', 'KEY_3'):
            self.assertTrue(key in res.keys())

    def test_dict_comparison(self):
        dict_1 = from_json(TEST_JSON)
        self.assertTrue(dict_1 == TEST_DICT)

if __name__ == '__main__':
    unittest.main()
