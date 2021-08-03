"""Test interface"""
import autolv

# pylint:disable=missing-function-docstring
def test_app():
    lv = autolv.App()
    assert lv.version == "20.0.1"
    vi = lv.get_VI(".\\tests\\numeric.vi")
    assert vi.input.value == 1.1
    vi.input.value = 2.0
    vi.run()
    assert vi.output.value == 4.0
