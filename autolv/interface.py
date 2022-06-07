"""Interact with LabVIEW VIs from Python"""
# pylint:disable=no-name-in-module
# pylint:disable=protected-access
from pathlib import Path
from tempfile import TemporaryDirectory
from enum import IntEnum
import asyncio
from datetime import timezone
import itertools
import struct
import pythoncom
from pythoncom import VT_ARRAY, VT_BYREF, VT_I2, VT_UI4, VT_UI1, VT_VARIANT, com_error
import pywintypes
import win32com.client
from win32com.client import VARIANT
import numpy as np
from autolv.vistrings import parse_vistrings
from autolv.datatypes import (
    IORefNum,
    make_control,
    DataFlow,
    valididentifier,
    TimeStamp,
    Array,
    Cluster,
    TabControl,
    ArrayCluster,
    Numeric,
    AutoLVError,
)


class ExecState(IntEnum):
    """ActiveX ExecStateEnum"""

    eBad = 0
    eIdle = 1
    eRunTopLevel = 2
    eRunning = 3


class FPState(IntEnum):
    """Front panel state"""

    Invalid = 0
    Standard = 1
    Closed = 2
    Hidden = 3
    Minimized = 4
    Maximized = 5


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
            "OpenFrontPanel",
            "GetPanelImage",
            "CloseFrontPanel",
            "ReinitializeAllToDefault",
        ]
        for method in methods:
            self._vi._FlagAsMethod(method)
        self.name = self._vi.Name
        with TemporaryDirectory() as tmpdir:
            file = Path(tmpdir).joinpath(self.name)
            self._vi.ExportVIStrings(str(file.absolute()))
            with open(file, "r", encoding="ansi") as f:
                vistr = f.read()
        self._ctrls = {k: make_control(**v) for k, v in parse_vistrings(vistr).items()}
        for ctrl in self._ctrls.values():
            if isinstance(ctrl, TabControl):
                for page in ctrl:
                    for c in page:
                        v = self._vi.GetControlValue(c.name)
                        if isinstance(c, TimeStamp):
                            v = v.replace(tzinfo=None)
                        try:
                            c.value = v
                        except AutoLVError:
                            pass
            elif isinstance(ctrl, ArrayCluster):
                rawvalues = self._vi.GetControlValue(ctrl.name)
                clstrvalues = []
                for value in rawvalues:
                    clstrvalue = Cluster(**ctrl._cluster)
                    try:
                        clstrvalue.update(dict(zip(clstrvalue._ctrls, value)))
                    except AutoLVError:
                        pass
                    clstrvalues.append(clstrvalue)
                ctrl.value = clstrvalues
            elif isinstance(ctrl, Numeric):
                try:
                    value = self._vi.GetControlValue(ctrl.name)
                except com_error:
                    # FXP not supported through LabVIEW's ActiveX server
                    value = np.nan
                ctrl.value = value
            else:
                value = self._vi.GetControlValue(ctrl.name)
                if isinstance(ctrl, TimeStamp):
                    value = value.replace(tzinfo=None)
                try:
                    ctrl.value = value
                except AutoLVError:
                    pass

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
                if isinstance(ctrl, TabControl):
                    for page in ctrl:
                        for c in page:
                            if c._dataflow in [DataFlow.INDICATOR, DataFlow.UNKNOWN]:
                                v = self._vi.GetControlValue(c.name)
                                if isinstance(c, TimeStamp):
                                    v = v.replace(tzinfo=None)
                                c.value = v
                elif isinstance(ctrl, ArrayCluster):
                    rawvalues = self._vi.GetControlValue(ctrl.name)
                    clstrvalues = []
                    for value in rawvalues:
                        clstrvalue = Cluster(**ctrl._cluster)
                        clstrvalue.update(dict(zip(clstrvalue._ctrls, value)))
                        clstrvalues.append(clstrvalue)
                    ctrl.value = clstrvalues
                elif isinstance(ctrl, Numeric):
                    try:
                        value = self._vi.GetControlValue(ctrl.name)
                    except com_error:
                        # FXP not supported through LabVIEW's ActiveX server
                        value = np.nan
                    ctrl.value = value
                elif ctrl._dataflow in [DataFlow.INDICATOR, DataFlow.UNKNOWN]:
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
        In [3]: vi = lv.open(<file>)
        In [4]: await vi.run()

        """
        for ctrl in self._ctrls.values():
            if isinstance(ctrl, TabControl):
                for page in ctrl:
                    for c in page:
                        if c._dataflow in [DataFlow.CONTROL, DataFlow.UNKNOWN]:
                            v = c.value
                            if isinstance(c, TimeStamp):
                                v = v.replace(tzinfo=timezone.utc)
                            self._vi.SetControlValue(c.name, v)
            elif ctrl._dataflow in [DataFlow.CONTROL, DataFlow.UNKNOWN]:
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

    @property
    def frontpanel_state(self) -> FPState:
        """Set the front panel state

        Parameters
        ----------
        value : FPState
        """
        return FPState(self._vi.FPState)

    @frontpanel_state.setter
    def frontpanel_state(self, value: FPState) -> None:
        current_state = self._vi.FPState
        if current_state == FPState.Closed:
            self._vi.OpenFrontPanel(True, value)
        elif current_state != FPState.Closed and value == FPState.Closed:
            self._vi.CloseFrontPanel()
        else:
            self._vi.FPState = value

    def get_frontpanel_image(self) -> np.ndarray:
        """Get the front panel image as 8-bit RBGA formatted array

        Returns
        -------
        image : numpy.ndarray
        """

        def rgba(bmp, clrs):
            img = []
            for row in bmp:
                pixels = []
                for pixel in row:
                    color = int(clrs[pixel])  # 24-bit color value
                    rgb = struct.unpack(">BBB", color.to_bytes(3, "big"))
                    pixel = list(rgb) + [255]
                    pixels.append(pixel)
                img.append(pixels)
            return np.array(img)

        # GetPanelImage() returns 8-bit 256 color image regardless of color_depth
        color_depth = 256
        fpsize = self._vi.FPSize
        bitmap = VARIANT(VT_ARRAY | VT_BYREF | VT_UI1, [0] * fpsize)
        colors = VARIANT(VT_ARRAY | VT_BYREF | VT_UI4, [0] * color_depth)
        bounds = VARIANT(VT_ARRAY | VT_BYREF | VT_I2, [0] * 4)
        self._vi.GetPanelImage(True, color_depth, bitmap, colors, bounds)
        # bounds appears to be (0, 0, cols, rows)
        cols, rows = np.array(bounds.value)[2:4]
        bitmap = np.array(bitmap.value).reshape((rows, cols))
        colors = np.array(colors.value)
        return rgba(bitmap, colors)

    def read_controls(self):
        """Read control values from front panel"""
        for ctrl in self._ctrls.values():
            if isinstance(ctrl, TabControl):
                for page in ctrl:
                    for c in page:
                        v = self._vi.GetControlValue(c.name)
                        if isinstance(c, TimeStamp):
                            v = v.replace(tzinfo=None)
                        c.value = v
            elif isinstance(ctrl, ArrayCluster):
                rawvalues = self._vi.GetControlValue(ctrl.name)
                clstrvalues = []
                for value in rawvalues:
                    clstrvalue = Cluster(**ctrl._cluster)
                    clstrvalue.update(dict(zip(clstrvalue._ctrls, value)))
                    clstrvalues.append(clstrvalue)
                ctrl.value = clstrvalues
            elif isinstance(ctrl, Numeric):
                try:
                    value = self._vi.GetControlValue(ctrl.name)
                except com_error:
                    # FXP not supported through LabVIEW's ActiveX server
                    value = np.nan
                ctrl.value = value
            else:
                value = self._vi.GetControlValue(ctrl.name)
                if isinstance(ctrl, TimeStamp):
                    value = value.replace(tzinfo=None)
                ctrl.value = value

    def reinitialize_values(self):
        """Reinitialize all controls to default values

        Same as Edit->Reinitialize Values to Default
        """
        self._vi.ReinitializeAllToDefault()
        self.read_controls()

    def __call__(self, **kwargs):
        """Call the VI as a subVI where the VI is in memory and not visible

        Parameters
        ----------
        kwargs : dict
            control name: value

        Notes
        -----
        Wire all controls to the connector pane.
        The underlying ActiveX call is blocking without a timeout mechanism.
        Set the VI to reentrant if making multiple simultaneous calls to the VI.

        Example
        -------
        Suppose 'test.vi' has one numeric control called 'input' and one numeric
        indicator called 'output' and equals 2*'input'.

        >>> lv = autolv.App()
        >>> vi = lv.open('test.vi')
        >>> vi(input=2, output=0)
        >>> vi.input
        2
        >>> vi.output
        4.0
        """
        ctrls = []
        values = []
        for name, value in kwargs.items():
            ctrl = self._ctrls[name]
            ctrls.append(name)
            if isinstance(ctrl, Array):
                ctrl.value = value
                value = VARIANT(VT_ARRAY | VT_VARIANT, ctrl.value)
            elif isinstance(ctrl, Cluster):
                ctrl.update(value)
                clstr_values = []
                for clstr_ctrl in ctrl.as_dict().values():
                    cvalue = clstr_ctrl.value
                    if isinstance(clstr_ctrl, Array):
                        cvalue = VARIANT(VT_ARRAY | VT_VARIANT, cvalue)
                    clstr_values.append(cvalue)
                value = VARIANT(VT_ARRAY | VT_VARIANT, clstr_values)
            elif isinstance(ctrl, IORefNum):
                _, num = ctrl.value
                value = VARIANT(VT_ARRAY | VT_VARIANT, [value, num])
            else:
                ctrl.value = value
                value = ctrl.value
            values.append(value)
        ctrls = VARIANT(VT_ARRAY | VT_BYREF | VT_VARIANT, ctrls)
        values = VARIANT(VT_ARRAY | VT_BYREF | VT_VARIANT, values)
        self._vi.Call(ctrls, values)
        for ctrl, value in zip(ctrls.value, values.value):
            self._ctrls[ctrl].value = value


class Project:
    """LabVIEW Project

    Currently supports opening a VI using the LabVIEW version the project
    was last saved in.
    """

    def __init__(self, lvproj_ref: win32com.client.CDispatch):
        self._proj = lvproj_ref
        self._lv = self._proj.Application

    def open(self, file_name: str | Path) -> VI:
        """Open a LabVIEW VI

        Parameters
        ----------
        file_name : str or path-like
            VI to open

        Returns
        -------
        VI
        """
        file = Path(file_name)
        if file.suffix == ".vi":
            viref = self._lv.GetVIReference(str(file.absolute()))
            return VI(viref)
        raise NotImplementedError(f"'*{file.suffix}' not supported")


# pylint:disable=attribute-defined-outside-init
class App:
    """ActiveX connection to LabVIEW application"""

    def __init__(self):
        self.__enter__()

    @property
    def version(self) -> str:
        """LabVIEW version"""
        return self._lv.Version

    def open(self, file_name: str | Path) -> VI:
        """Open a LabVIEW VI or Project

        Parameters
        ----------
        file_name : str or path-like
            VI or project to open

        Returns
        -------
        VI or Project
        """
        file = Path(file_name)
        if file.suffix == ".vi":
            viref = self._lv.GetVIReference(str(file.absolute()))
            return VI(viref)
        if file.suffix == ".lvproj":
            lvproject_ref = self._lv.OpenProject(str(file.absolute()))
            return Project(lvproject_ref)
        raise NotImplementedError(f"'*{file.suffix}' not supported")

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
        """Exit LabVIEW (File -> Exit) if the application was not already running.

        Notes
        -----
        LabVIEW will remain open if the application was already running prior to
        instantiating App. If successfully closed, the App object will be invalid.
        """
        try:
            self._lv.Quit()
        except AttributeError:
            # AttributeError: _lv doesn't yet exist - user needs to __enter__()
            pass
        else:
            # workaround to determine if LabVIEW still running
            try:
                self._lv.Version
            # pylint:disable=no-member
            except (pywintypes.com_error, AttributeError):
                # LabVIEW is actually closed at this point
                self._lv = None
                self._errvi = None

    def __enter__(self):
        if not hasattr(self, "_lv") or self._lv is None:
            # CoInitialize to support running under various processes
            # e.g. rpyc server
            pythoncom.CoInitialize()  # pylint:disable=no-member
            self._lv = win32com.client.Dispatch("LabVIEW.Application")
            methods = ["Quit", "OpenProject"]
            for method in methods:
                self._lv._FlagAsMethod(method)
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
