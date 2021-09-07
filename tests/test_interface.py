"""Test interface"""
from datetime import datetime
import pytest
import numpy as np
from autolv.interface import App, FPState
from autolv.vistrings import _removeparttext


# pylint:disable=missing-function-docstring
# pylint:disable=no-member
# pylint:disable=redefined-outer-name


@pytest.fixture(scope="module")
def lv() -> App:
    _lv = App()
    yield _lv
    _lv.close()


def test_app(lv: App):
    assert lv.version == "20.0.1"
    vi = lv.open(".\\tests\\numeric.vi")
    assert vi.input.value == 1.1
    vi.input.value = 2.0
    vi.run()
    assert vi.output.value == 4.0


def test_string(lv):
    vi = lv.open(".\\tests\\string.vi")
    vi.in1 = "a"
    vi.in2 = "b"
    vi.run()
    assert vi.output.value == "ab"


def test_path(lv):
    vi = lv.open(".\\tests\\path.vi")
    vi.input = ".\\tests\\path.vi"
    vi.run()
    assert vi.output.value == "tests\\path.vi"


def test_timestamp(lv):
    vi = lv.open(".\\tests\\timestamp.vi")
    assert vi.timestamp.value == datetime(2021, 8, 4, 13, 42, 42, 440000)


def test_enum(lv):
    vi = lv.open(".\\tests\\enum.vi")
    vi.fruit = 1
    vi.run()
    assert vi.selection.value == "bananna"


def test_error(lv):
    vi = lv.open(".\\tests\\error.vi")
    vi.DAQmx = "PXI1Slot2"
    vi.run()
    code = vi["error out"].code.value
    assert code == -201237
    assert lv.explain_error(code).startswith(
        "Physical channel name specified is invalid"
    )


def test_boolean(lv):
    vi = lv.open("./tests/boolean.vi")
    vi.input = False
    vi.run()
    assert bool(vi.output) is True
    vi.input = True
    vi.run()
    assert bool(vi.output) is False


def test_iorefnum(lv):
    vi = lv.open("./tests/io_refnum.vi")
    vi.ivi = "PXI1Slot1"
    vi.run()
    assert vi.ivi.value[0] == "PXI1Slot1"


def test_getVIwarning(lv):
    with pytest.warns(FutureWarning):
        lv.get_VI("./tests/boolean.vi")


def test_fp(lv):
    vi = lv.open("./tests/boolean.vi")
    assert vi.frontpanel_state == FPState.Closed
    vi.frontpanel_state = FPState.Standard
    assert vi.frontpanel_state == FPState.Standard


def test_getimage(lv):
    vi = lv.open("./tests/image.vi")
    img = vi.get_frontpanel_image()
    assert img.shape == (268, 366, 4)
    assert np.all(np.unique(img) == np.array([221, 255]))


def test_predefinedentities(lv):
    vi = lv.open("./tests/predefined_entities.vi")
    assert vi.numeric.description == """' " & < >"""


def test_styledtext(lv):
    vi = lv.open("./tests/styledtext.vi")
    assert vi.numeric.description == "numeric"


def test_removeparttext():
    vistr = '<PART ID=11 order=0 type="Text"><LABEL><STEXT>a<LF>b<LF>c</STEXT></LABEL></PART>'
    assert _removeparttext(vistr) == '<PART ID=11 order=0 type="Text"></PART>'


def test_stringdefaultvalue(lv):
    vi = lv.open("./tests/string_defaultvalue.vi")
    vi.run()
    assert vi.string.value == "a\nb\nc"
    vi.string.value = "abc"
    vi.run()
    assert vi.string.value == "abc"
    vi.reinitialize_values()
    vi.run()
    assert vi.string.value == "a\nb\nc"


def test_call(lv):
    vi = lv.open("./tests/boolean.vi")
    vi(input=False, output=True)
    assert vi.output.value is True
    vi = lv.open("./tests/numeric.vi")
    vi(input=2, output=0)
    assert vi.output.value == 4
    vi = lv.open("./tests/array.vi")
    vi(input=[1, 2, 3], output=[])
    assert np.all(vi.output.value == [2, 4, 6])
    vi = lv.open("./tests/cluster.vi")
    vi(Input={"gain": 2, "Array": [3, 4]}, Output={})
    assert vi.Output.sum.value == 14.0
    vi = lv.open("./tests/string.vi")
    vi(in1="a", in2="b", output="")
    assert vi.output.value == "ab"


def test_call_testvi_clusters(lv):
    vi = lv.open("./tests/test.vi")
    vi(data_in={"input": 3}, data_out={})
    assert vi.data_out.output.value == 6


def test_call_invalididentifiers(lv):
    vi = lv.open("./tests/numeric_invalididentifiers.vi")
    vi(**{"x in": 2, "y out": 0})
    assert vi["y out"].value == 4


def test_call_iorefnum(lv):
    vi = lv.open("./tests/io_refnum.vi")
    vi(ivi="MVR1")
    assert vi.ivi.value[0] == "MVR1"


def test_ring(lv):
    vi = lv.open("./tests/ring.vi")
    assert vi.input.value == 0
    vi.input = "x3"
    vi.run()
    assert vi.input.value == 1


def test_typedef(lv):
    vi = lv.open("./tests/ring_typedef.vi")
    assert vi.State.value == 0
    vi.State = "s1"
    vi.run()
    assert vi.State.value == 1


def test_ringtest(lv):
    vi = lv.open("./tests/test_ring.vi")
    vi(a=2, operator="+", b=3, c=0)
    assert vi.c.value == 5
    vi(a=4, operator="*", b=5, c=0)
    assert vi.c.value == 20
