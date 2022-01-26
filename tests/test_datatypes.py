"""Test datatypes"""
from autolv.datatypes import Numeric, DataFlow, Cluster, String, is_ragged

# pylint:disable=missing-function-docstring
# pylint:disable=no-member
def test_numeric():
    kwargs = {
        "ID": 83,
        "name": "x",
        "description": "a numeric",
        "tip": "input",
        "unitlabel": "V",
    }
    n = Numeric(**kwargs)
    assert n.name == "x"
    n.value = 2.0
    assert n.value == 2.0
    assert n._dataflow == DataFlow.UNKNOWN
    n.set_dataflow("control")
    assert n._dataflow == DataFlow.CONTROL
    nn = Numeric(**kwargs)
    nn.value = 2.0
    nn.set_dataflow("control")
    assert n == nn


def test_cluster():
    kwargs = {
        "ID": 80,
        "name": "input",
        "type": "Cluster",
        "ctrls": {
            "x": {"ID": 83, "name": "x", "type": "Numeric"},
            "y": {"ID": 83, "name": "y", "type": "Boolean"},
        },
    }
    c = Cluster(**kwargs)
    assert c.name == "input"
    assert c.x.name == "x"
    c.x = 2.0
    assert c.x.value == 2.0
    c.y = True
    values = c.value
    assert values == [2.0, True]
    assert c[0] == c.x
    assert c["y"] == c.y
    assert c.as_dict() == {"x": c.x, "y": c.y}
    assert len(c) == 2
    assert bool(c) is True
    cc = Cluster(**kwargs)
    cc.x = 2.0
    cc.y = True
    assert c == cc
    assert "x" in c
    cc.update({"x": 3, "y": False})
    assert cc.x.value == 3
    assert cc.y.value is False


def test_string():
    kwargs = {"ID": 81, "name": "input", "type": "String", "value": "a"}
    s = String(**kwargs)
    assert s.name == "input"
    assert s.value == "a"


def test_isragged():
    arr = [1, 2, 3]
    assert not is_ragged(arr, False)
    arr = [[1, 2], [3, 4]]
    assert not is_ragged(arr, False)
    arr = [1, 2, [3, 4]]
    assert is_ragged(arr, False)
    arr = [[[1, 2], [3, 4]], [[1, 2], [3, 4, 5]]]
    assert is_ragged(arr, False)
