"""Test interface"""
from datetime import datetime
import pytest
import autolv

# pylint:disable=missing-function-docstring
# pylint:disable=no-member
# pylint:disable=redefined-outer-name


@pytest.fixture(scope="module")
def lv():
    _lv = autolv.App()
    yield _lv
    _lv.close()


def test_app(lv):
    # lv = autolv.App()
    assert lv.version == "20.0.1"
    vi = lv.get_VI(".\\tests\\numeric.vi")
    assert vi.input.value == 1.1
    vi.input.value = 2.0
    vi.run()
    assert vi.output.value == 4.0
    # lv.close()


def test_string(lv):
    # lv = autolv.App()
    vi = lv.get_VI(".\\tests\\string.vi")
    vi.in1 = "a"
    vi.in2 = "b"
    vi.run()
    assert vi.output.value == "ab"
    # lv.close()


def test_path(lv):
    # lv = autolv.App()
    vi = lv.get_VI(".\\tests\\path.vi")
    vi.input = ".\\tests\\path.vi"
    vi.run()
    assert vi.output.value == "tests\\path.vi"
    # lv.close()


def test_timestamp(lv):
    # lv = autolv.App()
    vi = lv.get_VI(".\\tests\\timestamp.vi")
    assert vi.timestamp.value == datetime(2021, 8, 4, 13, 42, 42, 440000)
    # lv.close()


def test_enum(lv):
    # lv = autolv.App()
    vi = lv.get_VI(".\\tests\\enum.vi")
    vi.fruit = 1
    vi.run()
    assert vi.selection.value == "bananna"
    # lv.close()


def test_error(lv):
    # lv = autolv.App()
    vi = lv.get_VI(".\\tests\\error.vi")
    vi.DAQmx = "PXI1Slot2"
    vi.run()
    code = vi["error out"].code.value
    assert code == -201237
    assert lv.explain_error(code).startswith(
        "Physical channel name specified is invalid"
    )
    # lv.close()


def test_boolean(lv):
    # lv = autolv.App()
    vi = lv.get_VI("./tests/boolean.vi")
    vi.input = False
    vi.run()
    assert bool(vi.output) is True
    vi.input = True
    vi.run()
    assert bool(vi.output) is False
    # lv.close()
