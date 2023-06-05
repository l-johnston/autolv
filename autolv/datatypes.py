"""A Python emulation of LabVIEW's Cluster"""
from abc import ABC, abstractmethod
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
    "pages",
]


class AutoLVError(Exception):
    """AutoLVError"""


class DataFlow(IntEnum):
    """Data flow direction"""

    CONTROL = 1
    IN = 1
    INDICATOR = 2
    OUT = 2
    UNKNOWN = 3


def valididentifier(item: str) -> bool:
    """Test 'item' for valid Python identifier"""
    return bool(re.match(r"^[a-zA-Z][\w]*$", item))


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
        self._supported = True
        self._value = None

    def __repr__(self):
        return repr(self.value)

    def __setattr__(self, item, value):
        if item in self.__dict__ and item in READONLY_ATTRIBUTES:
            raise AutoLVError(f"can't set {item}")
        super().__setattr__(item, value)

    def __hash__(self):
        return hash(self.name)

    def __dir__(self):
        attrs = [a for a in super().__dir__() if not a.startswith("_")]
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

    @property
    def supported(self) -> bool:
        """True if control type is supported"""
        return self._supported

    @supported.setter
    def supported(self, value: bool):
        self._supported = bool(value)

    @property
    @abstractmethod
    def value(self):
        """Return the control's value"""
        return None

    @value.setter
    @abstractmethod
    def value(self, new_value):
        pass


class Numeric(LV_Control):
    """Numeric"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.value = kwargs.pop("value", 0.0)

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, new_value):
        if not isinstance(new_value, Number):
            raise AutoLVError(f"'{new_value}' not a number")
        self._value = new_value


class Boolean(LV_Control):
    """Boolean"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.value = kwargs.pop("value", False)

    def __bool__(self):
        return self.value

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, new_value):
        if not isinstance(new_value, bool):
            raise AutoLVError(f"'{new_value}' not a boolean")
        self._value = new_value


class Array(LV_Control):
    """Array"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.value = kwargs.pop("value", np.array([]))

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, new_value):
        if isinstance(new_value, str) or not hasattr(new_value, "__iter__"):
            raise AutoLVError(f"'{new_value}' not array like")
        self._value = np.array(new_value)


class Cluster(LV_Control):
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

    def __setattr__(self, item, value):
        if "_ctrls" in self.__dict__ and item in self._ctrls:
            self._ctrls[item].value = value
        else:
            super().__setattr__(item, value)

    def __getattr__(self, item):
        if item in self._ctrls:
            value = self._ctrls[item]
        else:
            raise AttributeError(f"'{item}' not in Cluster")
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

    def __hash__(self):
        return hash(self.name)

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
        return sorted(attrs + ctrls)

    @property
    def value(self):
        """Return cluster's control values as tuple"""
        values = []
        for _, ctrl in self._ctrls.items():
            values.append(ctrl.value)
        return tuple(values)

    @value.setter
    def value(self, new_value):
        if isinstance(new_value, dict):
            self.update(new_value)
        elif new_value is None:
            pass
        else:
            try:
                for c, v in zip(self._ctrls, new_value):
                    self._ctrls[c].value = v
            except AutoLVError:
                if set(self._ctrls) == {"status", "code", "source"}:
                    self.reorder_controls(["status", "code", "source"])
                    try:
                        for c, v in zip(self._ctrls, new_value):
                            self._ctrls[c].value = v
                    except AutoLVError as exc:
                        raise AutoLVError(
                            f"{new_value} not a valid Cluster value"
                        ) from exc

    def reorder_controls(self, new_order: list):
        """Reorder the controls

        This function provides a work around to specify the ordering
        of controls of a cluster in the Silver style.

        Parameters
        ----------
        new_order: list of control names ordered as shown in LabVIEW
        """
        ctrls = self._ctrls.copy()
        self._ctrls = {}
        for name in new_order:
            self._ctrls[name] = ctrls[name]


class ArrayCluster(LV_Control):
    """Array of clusters"""

    def __init__(self, **kwargs):
        self._cluster = kwargs.pop("cluster", None)
        super().__init__(**kwargs)
        if self._cluster is not None:
            self._cluster = self._cluster.popitem()[1]
        self._value = kwargs.pop("value", [])

    @property
    def value(self):
        """Return array of clusters"""
        return self._value

    @value.setter
    def value(self, value):
        raise NotImplementedError("ArrayCluster.value setter not implemented")


def is_ragged(array, res):
    """Is 'array' ragged?"""

    def _len(array):
        sz = -1
        try:
            sz = len(array)
        except TypeError:
            pass
        return sz

    if _len(array) <= 0:
        return res
    elem0_sz = _len(array[0])
    for element in array:
        if _len(element) != elem0_sz:
            res = True
            break
    for element in array:
        res = res or is_ragged(element, res)
    return res


class WaveformGraph(LV_Control):
    """'Waveform Graph' can be either 1d, 2d Array or Cluster, but not Waveform Data Type"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._value = kwargs.pop("value", np.array([]))

    def __setattr__(self, item, value):
        try:
            index = ["t0", "dt", "Y"].index(item)
        except ValueError:
            pass
        else:
            lvalue = super().__getattribute__("value")
            lvalue[index] = value
            super().__setattr__("value", lvalue)
        super().__setattr__(item, value)

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        if isinstance(value, str) or not hasattr(value, "__iter__"):
            raise AutoLVError(f"'{value}' not array like")
        if not is_ragged(value, False):
            value = np.array(value)
        else:
            value = list(value)
            super().__setattr__("t0", value[0])
            super().__setattr__("dt", value[1])
            super().__setattr__("Y", np.array(value[2]))
        self._value = value


class String(LV_Control):
    """String"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._value = kwargs.pop("value", "")

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        if not isinstance(value, str):
            raise AutoLVError(f"'{value}' not a string")
        self._value = value


class Path(LV_Control):
    """Path"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._value = pathlib.Path(kwargs.pop("value", ""))

    def __getattribute__(self, item):
        res = super().__getattribute__(item)
        return str(res) if item == "value" else res

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        if not isinstance(value, (str, pathlib.Path)):
            raise AutoLVError(f"'{value}' not a string")
        self._value = pathlib.Path(value)


class TimeStamp(LV_Control):
    """Time Stamp"""

    # LV 'Time Stamp' comes across ActiveX as naive but pywin32 treats it as UTC
    # The approach here is to force the value that comes from ActiveX to naive
    LV_EPOCH = datetime(1904, 1, 1, tzinfo=timezone.utc)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._value = kwargs.pop("value", self.LV_EPOCH)

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        if isinstance(value, tuple):
            value = datetime(*value)
        if not isinstance(value, datetime):
            raise AutoLVError(f"'{value}' not a datetime")
        self._value = value


class Enum(LV_Control):
    """Enum"""

    # LV Enum comes across ActiveX as an integer
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._value = kwargs.pop("value", 0)

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        if isinstance(value, str):
            value = int(value)
        if not isinstance(value, int):
            raise AutoLVError(f"'{value}' not an integer")
        self._value = value


class IORefNum(LV_Control):
    """I/O ref num"""

    # some I/O ref nums come across ActiveX as a tuple ('<str>', <int>)
    # but end user only needs to know the <str> e.g. PXI1Slot1
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._value = kwargs.pop("value", ("", 0))

    def __repr__(self):
        return f"{self.value[0]}"

    def __str__(self):
        return f"{self.value[0]}"

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        if isinstance(value, str):
            value = (value, 0)
        if not isinstance(value, tuple):
            raise AutoLVError(f"'{value}' not a tuple (<str>, <int>)")
        self._value = value


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
        self._value = kwargs.pop("value", 0)
        self._items = kwargs.pop("items", None)

    def __repr__(self):
        return f"{self.items[self.value]}"

    def __str__(self):
        return f"{self.items[self.value]}"

    @property
    def items(self):
        """Ring's items"""
        return self._items

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        if isinstance(value, str):
            value = self.items.index(value)
        self._value = value


class TabControl(LV_Control):
    """Tab Control"""

    def __init__(self, **kwargs):
        pages = kwargs.pop("pages", {})
        super().__init__(**kwargs)
        self._pages = {}
        for name, ctrls in pages.items():
            self._pages[name] = TabControlPage(**ctrls)

    def __repr__(self):
        return "<Tab Control>"

    def __getitem__(self, page):
        if isinstance(page, int):
            page = list(self._pages)[page]
        return self._pages[page]

    def __len__(self):
        return len(self._pages)

    def __dir__(self):
        attrs = super().__dir__()
        attrs = [a for a in attrs if not a.startswith("_")]
        pages = []
        for page in self._pages:
            if valididentifier(page):
                pages.append(page)
            else:
                pages.append(f"['{page}']")
        return attrs + pages

    def __getattr__(self, item):
        if item in self._pages:
            value = self._pages[item]
        else:
            value = super().__getattribute__(item)
        return value

    def __iter__(self):
        for _, page in self._pages.items():
            yield page

    @property
    def value(self):
        """Tab Control's value"""
        return self._value

    @value.setter
    def value(self, _):
        self._value = None


class TabControlPage:
    """A page of a tab control"""

    def __init__(self, **ctrls):
        self._ctrls = {}
        for name, attrs in ctrls.items():
            self._ctrls[name] = make_control(**attrs)

    def __repr__(self):
        return "<Tab Control Page>"

    def __dir__(self):
        attrs = super().__dir__()
        attrs = [a for a in attrs if not a.startswith("_")]
        ctrls = []
        for ctrl in self._ctrls:
            if valididentifier(ctrl):
                ctrls.append(ctrl)
            else:
                ctrls.append(f"['{ctrl}']")
        return attrs + ctrls

    def __getattr__(self, item):
        if item in self._ctrls:
            value = self._ctrls[item]
        else:
            value = super().__getattribute__(item)
        return value

    def __len__(self):
        return len(self._ctrls)

    def __iter__(self):
        for _, ctrl in self._ctrls.items():
            yield ctrl

    def __setattr__(self, item, value):
        if "_ctrls" in self.__dict__ and item in self._ctrls:
            self._ctrls[item].value = value
        else:
            super().__setattr__(item, value)

    def __getitem__(self, control):
        if isinstance(control, int):
            control = list(self._ctrls)[control]
        return self._ctrls[control]


class NotImplControl(LV_Control):
    """Control Not Implemented"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._supported = False
        self._value = None

    def __repr__(self):
        return "<NotImplemented>"

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, _):
        self._value = None


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
    "Measurement Data": NotImplControl,  # see Azdo bug #1812742
    "Classic DAQmx Physical Channel": String,
    "VISA resource name": VISAResourceName,
    "Classic Shared Variable Control": SharedVariable,
    "Ring": Ring,
    "User Defined Refnum Tag": UDRefNum,
    "Waveform Graph": WaveformGraph,
    "XY Graph": Array,
    "Waveform Chart": Array,
    "Tab Control": TabControl,
    "ArrayCluster": ArrayCluster,
}


def make_control(**attrs: dict) -> LV_Control:
    """Make LV_Control from VI strings attributes"""
    control_type = attrs.pop("type")
    LV_Control_cls = LVControl_LU.get(control_type, NotImplControl)
    return LV_Control_cls(**attrs)
