![Build Status](https://github.com/l-johnston/autolv/workflows/publish/badge.svg)
![PyPI](https://img.shields.io/pypi/v/autolv)
# autolv - Interact with LabVIEW VIs from Python

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

```python
>>> import autolv
>>> lv = autolv.LVApp()
>>> vi = lv.get_VI('test.vi')
>>> vi.input = 2.0
>>> vi.run()
>>> vi.output
4.0
```

Notes
-----
- LabVIEW's Cluster is supported, but not as nested clusters.
- LV Controls have a Label attribute. ActiveX calls this Label 'name' and this is
the only mechanism for set/get a Control. So, the Label must be unique among
the front panel controls.
- As a best practice, it is recommended to set the Label to a valid Python identifier.
This increases productivity when using dot-access in an interactive session such as
IPython.
- If your machine has multiple LabVIEW versions, launch the desired version first
before interacting with it in Python.
