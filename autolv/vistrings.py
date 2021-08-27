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
    for element in [
        "NO_TITLE",
        "FONT",
        "LF",
        "CRLF",
        "SAME_AS_LABEL",
        "append",
    ]:
        vistr = re.subn(
            f"<{element}.*?>", lambda m: m.group() + f"</{element}>", vistr
        )[0]
    return vistr


def _de_embed_elements(vistr: str) -> str:
    """De-embed elements <<...>>"""
    # pylint: disable=cell-var-from-loop
    for element in [
        "B",
        "append",
    ]:
        vistr = re.subn(f"<(</?{element}>)>", lambda m: m.groups()[0], vistr)[0]
    vistr = re.subn("<<([0-9]+)>>", lambda m: "__" + m.groups()[0] + "__", vistr)[0]
    return vistr


class ClosedInterval:
    """closed interval 'span' from re.match"""

    def __init__(self, span):
        self.start, self.stop = span
        self.stop = self.stop - 1

    def __contains__(self, value):
        return self.start <= value <= self.stop

    def __repr__(self):
        return f"<[{self.start}, {self.stop}]>"


# XML escapes ' " & < > as &...;
# LabVIEW chose not to follow the standard
#   ' comes across as '
#   " -> ""
#   & -> &
#   < -> <<
#   > -> >>
PREDEFINEDS = {
    "&(?!lt;|gt;)": ("amp", 1),
    '""': ("quot", 2),
}


def _predefinedentities(vistr: str) -> str:
    """convert predefined entities"""
    # asumming embedded tags have been deembedded
    vistr = re.subn("<<", "&lt;", vistr)[0]
    vistr = re.subn(">>(?!>)", "&gt;", vistr)[0]
    # exclude altering text within tags
    tag_spans = []
    for tag in re.finditer("<[^<]/?.*?[^>]>", vistr):
        tag_spans.append(ClosedInterval(tag.span()))
    r_vistr = vistr
    for pd, (sub, l) in PREDEFINEDS.items():
        for matched_ch in re.finditer(pd, vistr):
            loc = matched_ch.start()
            if not any(map(lambda span, l=loc: l in span, tag_spans)):
                r_vistr = r_vistr[0:loc] + f"&{sub};" + r_vistr[loc + l :]
    return r_vistr


def _styledtext(vistr):
    """convert styled text to CDATA"""
    vistr = re.subn("<B>(.*?)</B>", lambda m: f"<![CDATA[{m.groups()[0]}]]>", vistr)[0]
    return vistr


def _removeparttext(vistr):
    """Remove <PART ... type="Text">"""
    vistr = re.subn(
        '(<PART .*?type="Text">)(.*?)(</PART>)',
        lambda m: f"{m.groups()[0]}{m.groups()[2]}",
        vistr,
    )[0]
    return vistr


def _vistr2xml(vistr: str) -> str:
    """Fix exported VI strings to compliant XML"""
    vistr = _removeparttext(vistr)
    vistr = _addquotes(vistr)
    vistr = _de_embed_elements(vistr)
    vistr = _close_elements(vistr)
    vistr = _predefinedentities(vistr)
    vistr = _styledtext(vistr)
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
            try:
                text = part.find("LABEL").find("STEXT").text
            except AttributeError:
                pass
            else:
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
