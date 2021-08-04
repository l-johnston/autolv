"""Interact with LabVIEW VIs from Python"""
from pathlib import Path
from tempfile import TemporaryDirectory
from enum import IntEnum
import asyncio
from datetime import timezone
import win32com.client
from autolv.vistrings import parse_vistrings
from autolv.datatypes import make_control, DataFlow, valididentifier, TimeStamp


class ExecState(IntEnum):
    """ActiveX ExecStateEnum"""

    eBad = 0
    eIdle = 1
    eRunTopLevel = 2
    eRunning = 3


class VI:
    """ActiveX connection to a VI

    Parameters
    ----------
    viref : win32com.client.CDispatch
    """

    def __init__(self, viref: win32com.client.CDispatch):
        self._vi = viref
        self.name = self._vi.Name
        methods = [
            "ExportVIStrings",
            "SetControlValue",
            "GetControlValue",
            "Call",
            "Run",
            "Abort",
        ]
        for method in methods:
            self._vi._FlagAsMethod(method)
        self.name = self._vi.Name
        with TemporaryDirectory() as tmpdir:
            file = Path(tmpdir).joinpath(self.name)
            self._vi.ExportVIStrings(str(file.absolute()))
            with open(file, "r") as f:
                vistr = f.read()
        self._ctrls = {k: make_control(**v) for k, v in parse_vistrings(vistr).items()}
        for ctrl in self._ctrls.values():
            value = self._vi.GetControlValue(ctrl.name)
            if isinstance(ctrl, TimeStamp):
                value = value.replace(tzinfo=None)
            ctrl.value = value

    def __getitem__(self, item):
        return self._ctrls[item]

    def __dir__(self):
        ctrls = []
        for ctrl in self._ctrls:
            if valididentifier(ctrl):
                ctrls.append(ctrl)
            else:
                ctrls.append(f"['{ctrl}']")
        attrs = super().__dir__()
        attrs = [a for a in attrs if not a.startswith("_")]
        return ctrls + attrs

    def __getattr__(self, item):
        try:
            value = self._ctrls[item]
        except KeyError:
            value = super().__getattribute__(item)
        return value

    def __setitem__(self, item, value):
        self.__setattr__(item, value)

    def __setattr__(self, item, value):
        if "_ctrls" in self.__dict__ and item in self._ctrls:
            self._ctrls[item].value = value
        else:
            super().__setattr__(item, value)

    async def _run(self):
        try:
            self._vi.Run(True)
            while True:
                await asyncio.sleep(0.1)
                if ExecState(self._vi.ExecState) == ExecState.eIdle:
                    break
        except asyncio.CancelledError:
            self._vi.Abort()

    def run(self, timeout: float = None) -> None:
        """Run the VI and retrieve front panel indicator values

        Parameters
        ----------
        timeout: float
            Allows the VI to run up to timeout seconds. A timeout forces
            the VI to abort. Default of None disables the timeout. This
            function is synchronous and blocks until the VI stops.
        """
        for ctrl in self._ctrls.values():
            if ctrl._dataflow in [DataFlow.CONTROL, DataFlow.UNKNOWN]:
                value = ctrl.value
                # special case TimeStamp due to timezone issue - see TimeStamp definition
                if isinstance(ctrl, TimeStamp):
                    value = value.replace(tzinfo=timezone.utc)
                self._vi.SetControlValue(ctrl.name, value)
        try:
            asyncio.run(asyncio.wait_for(self._run(), timeout=timeout))
        except asyncio.TimeoutError as exc:
            raise asyncio.TimeoutError(f"{self.name} did not complete") from exc
        else:
            for ctrl in self._ctrls.values():
                if ctrl._dataflow in [DataFlow.INDICATOR, DataFlow.UNKNOWN]:
                    value = self._vi.GetControlValue(ctrl.name)
                    if isinstance(ctrl, TimeStamp):
                        value = value.replace(tzinfo=None)
                    ctrl.value = value


class App:
    """ActiveX connection to LabVIEW application"""

    def __init__(self):
        self._lv = win32com.client.Dispatch("LabVIEW.Application")

    @property
    def version(self) -> str:
        """LabVIEW version"""
        return self._lv.Version

    def get_VI(self, vi_name: str) -> VI:
        """Instantiate a VI object

        Parameters
        ----------
        vi_name : str or path-like
        """
        vipath = Path(vi_name)
        viref = self._lv.GetVIReference(str(vipath.absolute()))
        return VI(viref)
