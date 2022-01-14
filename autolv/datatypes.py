"""A Python emulation of LabVIEW's Cluster"""
from abc import ABC, abstractmethod
from collections.abc import Sequence
from numbers import Number
from enum import IntEnum
import re
import pathlib
from datetime import datetime, timezone
import numpy as np

READONLY_ATTRIBUTES = [
    "ID",
    "type",
    "name",
    "description",
    "tip",
    "caption",
    "unitlabel",
]


class DataFlow(IntEnum):
    """Data flow direction"""

    CONTROL = 1
    IN = 1
    INDICATOR = 2
    OUT = 2
    UNKNOWN = 3


def valididentifier(item: str) -> bool:
    """Test 'item' for valid Python identifier"""
    return bool(re.match(r"^[a-zA-Z][\w]+$", item))


class LV_Control(ABC):
    """Abstract base class for LabVIEW control types

    Parameters
    ----------
    kwargs
    """

    # LV control's Label is 'name' and must be unique
    def __init__(self, **kwargs):
        self.name = kwargs.pop("name")
        for attr in READONLY_ATTRIBUTES:
            try:
                setattr(self, attr, kwargs.pop(attr))
            except KeyError:
                pass
        # Exported VI strings does not indicate dataflow direction
        self._dataflow = DataFlow.UNKNOWN

    @abstractmethod
    def __repr__(self):
        raise NotImplementedError

    @abstractmethod
    def __str__(self):
        raise NotImplementedError

    def __setattr__(self, item, value):
        if item in self.__dict__ and item in READONLY_ATTRIBUTES:
            raise AttributeError(f"can't set {item}")
        super().__setattr__(item, value)

    def __hash__(self):
        return hash(self.name)

    def __dir__(self):
        attrs = [a for a in self.__dict__ if not a.startswith("_")]
        return attrs

    def set_dataflow(self, direction: str) -> None:
        """Set the control's dataflow direction

        Parameters
        ----------
        direction : str {'control', 'in', 'indicator', 'out'}
        """
        self._dataflow = DataFlow[direction.upper()]

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        tests = []
        for selfattr, otherattr in zip(self.__dict__.keys(), other.__dict__.keys()):
            tests.append(getattr(self, selfattr) == getattr(other, otherattr))
        return all(tests)


class Numeric(LV_Control):
    """Numeric"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.value = kwargs.pop("value", 0.0)

    def __setattr__(self, item, value):
        if item == "value":
            if not isinstance(value, Number):
                raise TypeError(f"'{value}' not a number")
        super().__setattr__(item, value)

    def __repr__(self):
        return f"{self.value}"

    def __str__(self):
        return f"{self.value}"


class Boolean(LV_Control):
    """Boolean"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.value = kwargs.pop("value", False)

    def __setattr__(self, item, value):
        if item == "value":
            if not isinstance(value, bool):
                raise TypeError(f"'{value}' not a boolean")
        super().__setattr__(item, value)

    def __repr__(self):
        return f"{self.value}"

    def __str__(self):
        return f"{self.value}"

    def __bool__(self):
        return self.value


class Array(LV_Control):
    """Array"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.value = kwargs.pop("value", np.array([]))

    def __setattr__(self, item, value):
        if item == "value":
            if isinstance(value, str) or not hasattr(value, "__iter__"):
                raise TypeError(f"'{value}' not array like")
            value = np.array(value)
        super().__setattr__(item, value)

    def __repr__(self):
        return f"{self.value}"

    def __str__(self):
        return f"{self.value}"


class Cluster(LV_Control, Sequence):
    """Cluster - A Python emulation of LabVIEW's Cluster

    A cluster in LabVIEW appears as a key-value mapping but is actually a C-struct
    where the variables (controls) have a set order and are arranged in a contiguous
    block of bytes. The ActiveX 'SetControlValue' expects a Sequence such as a 'list'
    or 'tuple' that follows the same ordering as in LabVIEW.

    In Python, a cluster is more naturally represented as a 'dict'. This 'Cluster'
    combines features of lists and dicts to facilitate communication with LabVIEW
    clusters.

    Parameters
    ----------
    kwargs
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._ctrls = {}
        for name, attrs in kwargs.get("ctrls", {}).items():
            self._ctrls[name] = make_control(**attrs)

    def __getitem__(self, control):
        if isinstance(control, int):
            control = list(self._ctrls)[control]
        return self._ctrls[control]

    def __setitem__(self, control, value):
        if isinstance(control, int):
            control = list(self._ctrls)[control]
        self._ctrls[control].value = value
        values = [ctrl.value for ctrl in self._ctrls]
        self._setfp(self.name, values)

    def __setattr__(self, item, value):
        if "_ctrls" in self.__dict__ and item in self._ctrls:
            self._ctrls[item].value = value
        elif item == "value":
            if isinstance(value, dict):
                self.update(value)
            else:
                for c, v in zip(self._ctrls, value):
                    self._ctrls[c].value = v
        else:
            super().__setattr__(item, value)

    def __getattr__(self, item):
        if item in self._ctrls:
            value = self._ctrls[item]
        elif item == "value":
            value = [c.value for c in self._ctrls.values()]
        else:
            value = super().__getattribute__(item)
        return value

    def __iter__(self):
        for _, ctrl in self._ctrls.items():
            yield ctrl

    def __len__(self):
        return len(self._ctrls)

    # pylint: disable=arguments-differ
    # Sequence.index start and stop parameters are recommended, not required
    def index(self, control):
        """Return the index of 'control'"""
        for idx, k in enumerate(self._ctrls):
            if k == control:
                return idx
        raise ValueError(f"{control} not in Cluster")

    def count(self, _):
        raise NotImplementedError

    def as_dict(self):
        """Return controls as a dict"""
        return self._ctrls

    def __repr__(self):
        return f"Cluster({self.as_dict()})"

    def __str__(self):
        return str(self.as_dict())

    def __contains__(self, control):
        return control in self._ctrls

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        tests = []
        for selfctrl, otherctrl in zip(self._ctrls.keys(), other._ctrls.keys()):
            tests.append(selfctrl == otherctrl)
            tests.append(getattr(self, selfctrl) == getattr(other, otherctrl))
        return all(tests)

    def __bool__(self):
        return len(self) > 0

    def update(self, controls: dict):
        """Update from a dict"""
        for name in controls:
            self._ctrls[name].value = controls[name]

    def __dir__(self):
        attrs = super().__dir__()
        attrs = [a for a in attrs if not a.startswith("_")]
        ctrls = []
        for ctrl in self._ctrls:
            if valididentifier(ctrl):
                ctrls.append(ctrl)
            else:
                ctrls.append(f"['{ctrl}']")
        methods = ["as_dict", "count", "index", "update", "value"]
        return attrs + ctrls + methods

    @property
    def value(self):
        """Return cluster's values as list"""
        values = []
        for _, ctrl in self._ctrls.items():
            values.append(ctrl.value)
        return values


class String(LV_Control):
    """String"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.value = kwargs.pop("value", "")

    def __setattr__(self, item, value):
        if item == "value":
            if not isinstance(value, str):
                raise TypeError(f"'{value}' not a string")
        super().__setattr__(item, value)

    def __repr__(self):
        return f"{self.value}"

    def __str__(self):
        return f"{self.value}"


class Path(LV_Control):
    """Path"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.value = pathlib.Path(kwargs.pop("value", ""))

    def __setattr__(self, item, value):
        if item == "value":
            if not isinstance(value, (str, pathlib.Path)):
                raise TypeError(f"'{value}' not a string")
            value = pathlib.Path(value)
        super().__setattr__(item, value)

    def __getattribute__(self, item):
        res = super().__getattribute__(item)
        return str(res) if item == "value" else res

    def __repr__(self):
        return f"{self.value}"

    def __str__(self):
        return f"{self.value}"


class TimeStamp(LV_Control):
    """Time Stamp"""

    # LV 'Time Stamp' comes across ActiveX as naive but pywin32 treats it as UTC
    # The approach here is to force the value that comes from ActiveX to naive
    LV_EPOCH = datetime(1904, 1, 1, tzinfo=timezone.utc)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.value = kwargs.pop("value", self.LV_EPOCH)

    def __setattr__(self, item, value):
        if item == "value":
            if not isinstance(value, datetime):
                raise TypeError(f"'{value}' not a datetime")
        super().__setattr__(item, value)

    def __repr__(self):
        return f"{self.value}"

    def __str__(self):
        return f"{self.value}"


class Enum(LV_Control):
    """Enum"""

    # LV Enum comes across ActiveX as an integer
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.value = kwargs.pop("value", 0)

    def __setattr__(self, item, value):
        if item == "value":
            if not isinstance(value, int):
                raise TypeError(f"'{value}' not an integer")
        super().__setattr__(item, value)

    def __repr__(self):
        return f"{self.value}"

    def __str__(self):
        return f"{self.value}"


class IORefNum(LV_Control):
    """I/O ref num"""

    # some I/O ref nums come across ActiveX as a tuple ('<str>', <int>)
    # but end user only needs to know the <str> e.g. PXI1Slot1
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.value = kwargs.pop("value", ("", 0))

    def __setattr__(self, item, value):
        if item == "value":
            if isinstance(value, str):
                value = (value, 0)
            if not isinstance(value, tuple):
                raise TypeError(f"'{value}' not a tuple (<str>, <int>)")
        super().__setattr__(item, value)

    def __repr__(self):
        return f"{self.value[0]}"

    def __str__(self):
        return f"{self.value[0]}"


class IVILogicalName(IORefNum):
    """IVI Logical Name"""


class VISAResourceName(IORefNum):
    """VISA resource name"""


class SharedVariable(IORefNum):
    """Shared Variable"""

class UDRefNum(IORefNum):
    """User Defined RefNum"""


class Ring(LV_Control):
    """Ring"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.value = kwargs.pop("value", 0)
        self.items = kwargs.pop("items", None)

    def __setattr__(self, item, value):
        if item == "value":
            if isinstance(value, str):
                value = self.items.index(value)
        super().__setattr__(item, value)

    def __repr__(self):
        return f"{self.items[self.value]}"

    def __str__(self):
        return f"{self.items[self.value]}"

class NotImplControl(LV_Control):
    """Control Not Implemented"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __repr__(self):
        return f"Not Implemented"

    def __str__(self):
        return f"Not Implemented"

LVControl_LU = {
    "Numeric": Numeric,
    "Boolean": Boolean,
    "String": String,
    "Path": Path,
    "Time Stamp": TimeStamp,
    "Enum": Enum,
    "IVI Logical Name": IVILogicalName,
    "Slide": Numeric,
    "Array": Array,
    "Cluster": Cluster,
    "Measurement Data": Cluster,
    "Classic DAQmx Physical Channel": String,
    "VISA resource name": VISAResourceName,
    "Classic Shared Variable Control": SharedVariable,
    "Ring": Ring,
    "User Defined Refnum Tag": UDRefNum,
    "Waveform Graph": Array,
    "XY Graph": Array
}


def make_control(**attrs: dict) -> LV_Control:
    """Make LV_Control from VI strings attributes"""
    control_type = attrs.pop("type")
    if control_type in LVControl_LU:
        LV_Control_cls = LVControl_LU[control_type]
    else:
        LV_Control_cls = NotImplControl
    return LV_Control_cls(**attrs)
