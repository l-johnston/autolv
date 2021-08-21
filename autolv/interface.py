"""Interact with LabVIEW VIs from Python"""
from pathlib import Path
from tempfile import TemporaryDirectory
from enum import IntEnum
import asyncio
from datetime import timezone
import itertools
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
        else:
            for ctrl in self._ctrls.values():
                if ctrl._dataflow in [DataFlow.INDICATOR, DataFlow.UNKNOWN]:
                    value = self._vi.GetControlValue(ctrl.name)
                    if isinstance(ctrl, TimeStamp):
                        value = value.replace(tzinfo=None)
                    ctrl.value = value

    async def _spinner(self):
        spinner = ["-", "\\", "|", "/", "-", "|"]
        glyph = itertools.cycle(spinner)
        try:
            while True:
                print(next(glyph), end="\r")
                await asyncio.sleep(0.2)
                if ExecState(self._vi.ExecState) == ExecState.eIdle:
                    break
        except asyncio.CancelledError:
            pass
        print(" ", end="\r")

    async def _task(self):
        try:
            await asyncio.gather(self._run(), self._spinner())
        except asyncio.CancelledError:
            pass

    def run(self, timeout: float = None) -> None:
        """Run the VI and retrieve front panel indicator values

        Parameters
        ----------
        timeout: float
            Allows the VI to run up to timeout seconds. A timeout forces
            the VI to abort. Default of None disables the timeout. This
            function is synchronous and blocks until the VI stops.

        Notes
        -----
        Jupyter has a running event loop and we have to await this function from
        within the notebook:

        In [1]: import autolv
        In [2]: lv = autolv.App()
        In [3]: vi = lv.get_VI(<file>)
        In [4]: await vi.run()

        """
        for ctrl in self._ctrls.values():
            if ctrl._dataflow in [DataFlow.CONTROL, DataFlow.UNKNOWN]:
                value = ctrl.value
                # special case TimeStamp due to timezone issue - see TimeStamp definition
                if isinstance(ctrl, TimeStamp):
                    value = value.replace(tzinfo=timezone.utc)
                self._vi.SetControlValue(ctrl.name, value)
        task = asyncio.wait_for(self._task(), timeout=timeout)
        try:
            asyncio.run(task)
        except asyncio.TimeoutError as exc:
            raise asyncio.TimeoutError(f"{self.name} did not complete") from exc
        except RuntimeError:
            # there's a running event loop already, e.g. Jupyter
            return task
        return None


# pylint:disable=attribute-defined-outside-init
class App:
    """ActiveX connection to LabVIEW application"""

    def __init__(self):
        self.__enter__()

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

    def explain_error(self, code: int) -> str:
        """Explain Error

        Parameters
        ----------
        code : int
            error code from error cluster

        Returns
        -------
        explanation : str
            possible reason as found in LabVIEW's error database
        """
        self._errvi.SetControlValue("Error Code", code)
        self._errvi.Run()
        return self._errvi.GetControlValue("Error Text")

    def close(self):
        """Close LabVIEW"""
        try:
            self._lv.Quit()
        except (TypeError, AttributeError):
            # Quit() raises a Windows fatal exception: code 0x800706ba
            pass
        self._lv = None
        self._errvi = None

    def __enter__(self):
        if not hasattr(self, "_lv") or self._lv is None:
            self._lv = win32com.client.Dispatch("LabVIEW.Application")
            errvipath = str(
                Path(self._lv.ApplicationDirectory)
                .joinpath(r"vi.lib\Utility\error.llb\Error Code Database.vi")
                .absolute()
            )
            self._errvi = self._lv.GetVIReference(errvipath)
            self._errvi._FlagAsMethod("Run")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def __repr__(self):
        if self._lv is None:
            return "<LabVIEW not running>"
        return f"<LabVIEW {self.version}>"
