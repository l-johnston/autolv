"""autolv - Interact with LabVIEW VIs from Python

The only export from autolv is App that opens an ActiveX connection to
LabVIEW through its VI Server. With a reference to LabVIEW it is then possible
to open an ActiveX connection to a specific VI. The primary use case for this
library is to set control values on the VI front panel from Python, run the VI,
and read the control values back into Python.

Example usage
-------------
Suppose the VI name is 'test.vi' and has a single Numeric control with the name (label)
'input' and a single Numeric indicator with the name 'output'. The VI implements
2*'input' -> 'output'

>>> import autolv
>>> lv = autolv.App()
>>> vi = lv.get_VI('test.vi')
>>> vi.input = 2.0
>>> vi.run()
>>> vi.output
4.0
"""
from autolv.interface import App

__version__ = "0.1.4"
__all__ = ["App"]


def __dir__():
    return __all__
