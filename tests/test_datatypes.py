"""Test datatypes"""
import numpy as np
import pytest
from autolv.datatypes import (
    Numeric,
    DataFlow,
    Cluster,
    String,
    is_ragged,
    AutoLVError,
    Boolean,
    Array,
    ArrayCluster,
)


# pylint:disable=missing-function-docstring
# pylint:disable=no-member
# pylint:disable=protected-access
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
    assert repr(n) == "2.0"
    assert str(n) == "2.0"
    assert dir(n) == [
        "ID",
        "description",
        "name",
        "set_dataflow",
        "supported",
        "tip",
        "unitlabel",
        "value",
    ]
    assert (n == "n") is False
    with pytest.raises(AutoLVError):
        n.value = "a"


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
    assert values == (2.0, True)
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
    c["x"] = 3.1
    assert c.x.value == 3.1
    assert list(map(lambda x: x.value, c)) == [3.1, True]
    with pytest.raises(AttributeError):
        getattr(c, "sfdskjd")
    assert c.index("x") == 0
    assert repr(c) == "Cluster({'x': 3.1, 'y': True})"
    assert str(c) == "{'x': 3.1, 'y': True}"
    assert (c == 1) is False
    assert dir(c) == [
        "ID",
        "as_dict",
        "index",
        "name",
        "reorder_controls",
        "set_dataflow",
        "supported",
        "type",
        "update",
        "value",
        "x",
        "y",
    ]


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


def test_boolean():
    kwargs = {"ID": 81, "name": "input", "type": "Boolean", "value": True}
    b = Boolean(**kwargs)
    assert b.value is True
    with pytest.raises(AutoLVError):
        b.value = 1


def test_array():
    kwargs = {"ID": 83, "name": "x", "type": "Array", "value": [1, 2, 3]}
    a = Array(**kwargs)
    assert np.allclose(a.value, [1, 2, 3])
    with pytest.raises(AutoLVError):
        a.value = 1


def test_arraycluster():
    kwargs = {
        "ID": 82,
        "name": "x",
        "type": "ArrayCluster",
        "cluster": {
            "ID": "83",
            "type": "Cluster",
            "name": "cluster",
            "description": None,
            "tip": None,
            "ctrls": {
                "a": {
                    "ID": "80",
                    "type": "Numeric",
                    "name": "a",
                    "description": None,
                    "tip": None,
                }
            },
        },
    }
    ac = ArrayCluster(**kwargs)
    with pytest.raises(NotImplementedError):
        ac.value = 1
