"""Test context manager"""
import time
import autolv

# pylint:disable=missing-function-docstring
# pylint:disable=no-member
# pylint:disable=redefined-outer-name
def test_contextmanager():
    with autolv.App() as lv:
        assert isinstance(lv.version, str)
    assert lv._lv is None
    # resolve a race condition in win32com.client between closing LabVIEW
    # and opening again in the next test
    time.sleep(1)
