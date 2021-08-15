"""Test interface"""
from datetime import datetime
import autolv

# pylint:disable=missing-function-docstring
# pylint:disable=no-member
def test_app():
    lv = autolv.App()
    assert lv.version == "20.0.1"
    vi = lv.get_VI(".\\tests\\numeric.vi")
    assert vi.input.value == 1.1
    vi.input.value = 2.0
    vi.run()
    assert vi.output.value == 4.0


def test_string():
    lv = autolv.App()
    vi = lv.get_VI(".\\tests\\string.vi")
    vi.in1 = "a"
    vi.in2 = "b"
    vi.run()
    assert vi.output.value == "ab"


def test_path():
    lv = autolv.App()
    vi = lv.get_VI(".\\tests\\path.vi")
    vi.input = ".\\tests\\path.vi"
    vi.run()
    assert vi.output.value == "tests\\path.vi"


def test_timestamp():
    lv = autolv.App()
    vi = lv.get_VI(".\\tests\\timestamp.vi")
    assert vi.timestamp.value == datetime(2021, 8, 4, 13, 42, 42, 440000)


def test_enum():
    lv = autolv.App()
    vi = lv.get_VI(".\\tests\\enum.vi")
    vi.fruit = 1
    vi.run()
    assert vi.selection.value == "bananna"


def test_error():
    lv = autolv.App()
    vi = lv.get_VI(".\\tests\\error.vi")
    vi.DAQmx = "PXI1Slot2"
    vi.run()
    code = vi["error out"].code.value
    assert code == -201237
    assert lv.explain_error(code).startswith(
        "Physical channel name specified is invalid"
    )
