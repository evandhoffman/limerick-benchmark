import unittest

from benchmark.agent import _parse_tool_arguments


class ParseToolArgumentsTests(unittest.TestCase):
    def test_rejects_invalid_json(self) -> None:
        with self.assertRaises(ValueError):
            _parse_tool_arguments('{"command": ')

    def test_rejects_non_object_json(self) -> None:
        with self.assertRaises(ValueError):
            _parse_tool_arguments('["pwd"]')

    def test_accepts_valid_object_json(self) -> None:
        self.assertEqual(_parse_tool_arguments('{"command": "pwd"}'), {"command": "pwd"})
