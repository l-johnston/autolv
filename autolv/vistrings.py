"""Parse Exported VI Strings"""
import re
import io
import xml.etree.ElementTree as ET


def _quote(match: re.Match) -> str:
    """Add quotes to '=attribute'"""
    attr, end = match.groups()
    return f'="{attr}"{end}'


def _addquotes(vistr: str) -> str:
    """Add quotes to '=attribute' attributes"""
    vistr = re.subn(r'=(?!")(.*?)([\s>])', _quote, vistr)[0]
    return vistr


def _close_elements(vistr: str) -> str:
    """Close elements NO_TITLE CRLF LF"""
    # pylint: disable=cell-var-from-loop
    for element in ["NO_TITLE", "FONT", "LF", "CRLF", "SAME_AS_LABEL"]:
        vistr = re.subn(
            f"<{element}.*?>", lambda m: m.group() + f"</{element}>", vistr
        )[0]
    return vistr


def _vistr2xml(vistr: str) -> str:
    """Fix exported VI strings to compliant XML"""
    vistr = _addquotes(vistr)
    vistr = _close_elements(vistr)
    return vistr


def _recurse_ctrls(element: ET.Element) -> dict:
    controls = {}
    element = element.find("CONTENT")
    if element is None:
        return controls
    for control in element.iterfind("CONTROL"):
        attrs = {}
        attrs.update(control.attrib)
        desc = control.find("DESC").text
        tip = control.find("TIP").text
        attrs.update({"description": desc, "tip": tip})
        for part in control.find("PARTS"):
            parttype = part.attrib["type"].lower().replace(" ", "")
            text = part.find("LABEL").find("STEXT").text
            attrs.update({parttype: text})
        controls[attrs["name"]] = attrs
        if attrs["type"] == "Cluster":
            controls[attrs["name"]]["ctrls"] = _recurse_ctrls(control)
    return controls


def parse_vistrings(vistr: str) -> dict:
    """Parse exported VI strings pseudo-XML to extract controls"""
    vixml = io.StringIO(_vistr2xml(vistr))
    tree = ET.parse(vixml)
    root = tree.getroot()
    return _recurse_ctrls(root)
