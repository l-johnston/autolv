"""Test interface"""
from datetime import datetime
import pathlib
import pytest
import numpy as np
from autolv.interface import App, FPState
from autolv.vistrings import _removeparttext
from autolv.datatypes import AutoLVError, NotImplControl


# pylint:disable=missing-function-docstring
# pylint:disable=no-member
# pylint:disable=redefined-outer-name


@pytest.fixture(scope="module")
def lv() -> App:
    _lv = App()
    yield _lv
    _lv.close()


@pytest.fixture()
def testdir() -> pathlib.Path:
    yield pathlib.Path("./tests").resolve()


def test_app(lv, testdir):
    assert isinstance(lv.version, str)
    vi = lv.open(testdir / "numeric.vi")
    assert vi.input.value == 1.1
    vi.input.value = 2.0
    vi.run()
    assert vi.output.value == 4.0


def test_string(lv, testdir):
    vi = lv.open(testdir / "string.vi")
    vi.in1 = "a"
    vi.in2 = "b"
    vi.run()
    assert vi.output.value == "ab"


def test_path(lv, testdir):
    vi = lv.open(testdir / "path.vi")
    vi.input = ".\\tests\\path.vi"
    vi.run()
    assert vi.output.value == "tests\\path.vi"


def test_timestamp(lv, testdir):
    vi = lv.open(testdir / "timestamp.vi")
    assert vi.timestamp.value == datetime(2021, 8, 4, 13, 42, 42, 440000)


def test_enum(lv, testdir):
    vi = lv.open(testdir / "enum.vi")
    vi.fruit = 1
    vi.run()
    assert vi.selection.value == "bananna"


def test_error(lv, testdir):
    vi = lv.open(testdir / "error.vi")
    vi.DAQmx = "PXI1Slot2"
    vi.run()
    code = vi["error out"].code.value
    assert code == -201237
    assert lv.explain_error(code).startswith(
        "Physical channel name specified is invalid"
    )


def test_boolean(lv, testdir):
    vi = lv.open(testdir / "boolean.vi")
    vi.input = False
    vi.run()
    assert bool(vi.output) is True
    vi.input = True
    vi.run()
    assert bool(vi.output) is False


def test_iorefnum(lv, testdir):
    vi = lv.open(testdir / "io_refnum.vi")
    vi.ivi = "PXI1Slot1"
    vi.run()
    assert vi.ivi.value[0] == "PXI1Slot1"


def test_fp(lv, testdir):
    vi = lv.open(testdir / "boolean.vi")
    assert vi.frontpanel_state == FPState.Closed
    vi.frontpanel_state = FPState.Standard
    assert vi.frontpanel_state == FPState.Standard


def test_getimage(lv, testdir):
    vi = lv.open(testdir / "image.vi")
    img = vi.get_frontpanel_image()
    assert img.shape == (268, 366, 4)
    assert np.all(np.unique(img) == np.array([221, 255]))


def test_predefinedentities(lv, testdir):
    vi = lv.open(testdir / "predefined_entities.vi")
    assert vi.numeric.description == """' " & < >"""


def test_styledtext(lv, testdir):
    vi = lv.open(testdir / "styledtext.vi")
    assert vi.numeric.description == "numeric"


def test_removeparttext():
    vistr = '<PART ID=11 order=0 type="Text"><LABEL><STEXT>a<LF>b<LF>c</STEXT></LABEL></PART>'
    assert _removeparttext(vistr) == '<PART ID=11 order=0 type="Text"></PART>'


def test_stringdefaultvalue(lv, testdir):
    vi = lv.open(testdir / "string_defaultvalue.vi")
    vi.run()
    assert vi.string.value == "a\nb\nc"
    vi.string.value = "abc"
    vi.run()
    assert vi.string.value == "abc"
    vi.reinitialize_values()
    vi.run()
    assert vi.string.value == "a\nb\nc"


def test_call(lv, testdir):
    vi = lv.open(testdir / "boolean.vi")
    vi(input=False, output=True)
    assert vi.output.value is True
    vi = lv.open(testdir / "numeric.vi")
    vi(input=2, output=0)
    assert vi.output.value == 4
    vi = lv.open(testdir / "array.vi")
    vi(input=[1, 2, 3], output=[])
    assert np.all(vi.output.value == [2, 4, 6])
    vi = lv.open(testdir / "cluster.vi")
    vi(Input={"gain": 2, "Array": [3, 4]}, Output={})
    assert vi.Output.sum.value == 14.0
    vi = lv.open(testdir / "string.vi")
    vi(in1="a", in2="b", output="")
    assert vi.output.value == "ab"


def test_call_testvi_clusters(lv, testdir):
    vi = lv.open(testdir / "test.vi")
    vi(data_in={"input": 3}, data_out={})
    assert vi.data_out.output.value == 6


def test_call_invalididentifiers(lv, testdir):
    vi = lv.open(testdir / "numeric_invalididentifiers.vi")
    vi(**{"x in": 2, "y out": 0})
    assert vi["y out"].value == 4


def test_call_iorefnum(lv, testdir):
    vi = lv.open(testdir / "io_refnum.vi")
    vi(ivi="MVR1")
    assert vi.ivi.value[0] == "MVR1"


def test_ring(lv, testdir):
    vi = lv.open(testdir / "ring.vi")
    assert vi.input.value == 0
    vi.input = "x3"
    vi.run()
    assert vi.input.value == 1


def test_typedef(lv, testdir):
    vi = lv.open(testdir / "ring_typedef.vi")
    assert vi.State.value == 0
    vi.State = "s1"
    vi.run()
    assert vi.State.value == 1


def test_ringtest(lv, testdir):
    vi = lv.open(testdir / "test_ring.vi")
    vi(a=2, operator="+", b=3, c=0)
    assert vi.c.value == 5
    vi(a=4, operator="*", b=5, c=0)
    assert vi.c.value == 20


def test_graph(lv, testdir):
    vi = lv.open(testdir / "graph.vi")
    vi.run()
    assert (vi.Graph.value == np.array([3, 3, 3])).all()


def test_graph1d(lv, testdir):
    vi = lv.open(testdir / "graph_1d.vi")
    vi.run()
    assert (vi.graph.value == np.arange(0, 10)).all()


def test_graph2d(lv, testdir):
    vi = lv.open(testdir / "graph_2d.vi")
    vi.run()
    arr = np.arange(0, 10)
    assert (vi.graph.value == np.array([arr, arr])).all()


def test_graph_cluster(lv, testdir):
    vi = lv.open(testdir / "graph_cluster.vi")
    vi.run()
    assert vi.graph.t0 == 0.0
    assert vi.graph.dt == 1.0
    assert (vi.graph.Y == np.arange(0, 10)).all()


def test_graph_xy(lv, testdir):
    vi = lv.open(testdir / "graph_xy.vi")
    vi.run()
    arr = np.arange(0, 10)
    assert (vi.graph.value == np.array([arr, arr])).all()


def test_graph1dcontrol(lv, testdir):
    vi = lv.open(testdir / "graph_1d_control.vi")
    vi.graph.value = range(0, 10)
    vi.run()
    assert (vi.Y.value == np.arange(0, 10)).all()


def test_graphchart(lv, testdir):
    vi = lv.open(testdir / "graph_chart.vi")
    vi.run()
    assert (vi.graph.value == np.arange(0, 10)).all()


def test_tabcontrol(lv, testdir):
    vi = lv.open(testdir / "tab control.vi")
    vi.a = 1
    vi.tabcontrol.page1.cluster.b = 2
    vi.tabcontrol.page1.cluster.c = 3
    vi.run()
    assert vi.tabcontrol.page2.d.value == 9.0


def test_predefined_entities(lv, testdir):
    vi = lv.open(testdir / "predefined_entities2.vi")
    assert (
        vi["Resource Name"].description
        == "resource name “PXI1Slot2” Measurement & Automation"
    )


def test_arrayofclusters(lv, testdir):
    vi = lv.open(testdir / "array of clusters.vi")
    assert vi.array.value[0].a.value == 1.0


def test_silvercluster(lv, testdir):
    vi = lv.open(testdir / "silver error cluster.vi")
    cluster = vi["error in"]
    cluster.reorder_controls(["status", "code", "source"])
    vi.read_controls()
    values = list(map(lambda v: v.value, cluster.as_dict().values()))
    expected = [True, 1, "abc"]
    assert values == expected


def test_reorder_cluster(lv, testdir):
    vi = lv.open(testdir / "reorder cluster.vi")
    cluster = vi.cluster
    keys = list(cluster.as_dict().keys())
    expected = ["a", "b", "c"]
    assert keys == expected
    values = list(map(lambda v: v.value, cluster.as_dict().values()))
    expected = [1, 2, 3]
    assert values == expected
    cluster.reorder_controls(["c", "a", "b"])
    vi.read_controls()
    keys = list(cluster.as_dict().keys())
    expected = ["c", "a", "b"]
    assert keys == expected
    values = list(map(lambda v: v.value, cluster.as_dict().values()))
    expected = [1, 2, 3]
    assert values == expected


def test_cantsetreadonlyattribute(lv, testdir):
    vi = lv.open(testdir / "boolean.vi")
    with pytest.raises(AutoLVError):
        vi.input.name = "abc"


def test_fxp(lv, testdir):
    vi = lv.open(testdir / "fxp.vi")
    assert vi.input.value is None


def test_notimplementedcontrol(lv, testdir):
    vi = lv.open(testdir / "wdt.vi")
    assert issubclass(type(vi.wdt), NotImplControl)


def test_project(lv, testdir):
    project = lv.open(testdir / "project.lvproj")
    vi = project.open(testdir / "project vi.vi")
    assert vi.a.value == 1.0


def test_unimplementrefs(lv, testdir):
    vi = lv.open(testdir / "unimplemented_refs.vi")
    assert isinstance(vi.References.Panel, NotImplControl)


def test_pathseptag(lv, testdir):
    vi = lv.open(testdir / "path_septag.vi")
    assert vi.Path.value == "file"


def test_grouping(lv, testdir):
    vi = lv.open(testdir / "grouping.vi")
    vi.x1 = 1.0
    vi.x2 = 2.0
    vi.run()
    assert vi.x1.value == 1.0
    assert vi.x2.value == 2.0
    assert vi.O1.y1.value == 2.0
    assert vi.O2.y2.value == 6.0
