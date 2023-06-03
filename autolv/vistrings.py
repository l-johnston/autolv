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
        "NON_STRING",
        "SEP",
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
    tag_span_subs = []
    for pd, sub in PREDEFINEDS.items():
        for matched_ch in re.finditer(pd, vistr):
            loc = matched_ch.start()
            if not any(map(lambda span, l=loc: l in span, tag_spans)):
                tag_span_subs.append((loc, sub))
    x = 0
    for loc, (s, l) in sorted(tag_span_subs):
        vistr = vistr[0 : loc + x] + f"&{s};" + vistr[loc + x + l :]
        x += len(s) + 2 - l
    return vistr


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
        flags=re.DOTALL,
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
    for grouper in element.iterfind("GROUPER"):
        for parts in grouper.iterfind("PARTS"):
            controls.update(_recurse_ctrls(parts))
    for control in element.iterfind("CONTROL"):
        if control.attrib["type"] == "Type Definition":
            for part in control.find("PARTS").iterfind("PART"):
                if part.attrib["type"] == "Type Def's Control":
                    attrs = _recurse_ctrls(part).pop("")
                    attrs["name"] = control.attrib["name"]
                    break
            desc = control.find("DESC").text
            tip = control.find("TIP").text
            attrs.update({"description": desc, "tip": tip})
            controls[attrs["name"]] = attrs
        elif control.attrib["type"] == "Tab Control":
            attrs = {}
            attrs.update(control.attrib)
            desc = control.find("DESC").text
            tip = control.find("TIP").text
            attrs.update({"description": desc, "tip": tip})
            pages = []
            for page in control.iterfind("PAGE"):
                pages.append(_recurse_ctrls(page))
            pagecaptions = []
            for caption in (
                control.find("PRIV").find("PAGE_CAPTIONS").iterfind("STRING")
            ):
                pagecaptions.append(caption.text)
            attrs["pages"] = dict(zip(pagecaptions, pages))
            controls[attrs["name"]] = attrs
        elif control.attrib["type"] == "Array":
            attrs = {}
            attrs["cluster"] = None
            attrs.update(control.attrib)
            desc = control.find("DESC").text
            tip = control.find("TIP").text
            attrs.update({"description": desc, "tip": tip})
            element_ctrl = control.find("CONTENT").find("CONTROL")
            if element_ctrl.attrib["type"] == "Cluster":
                attrs["type"] = "ArrayCluster"
                attrs["cluster"] = _recurse_ctrls(control.find("CONTENT"))
            controls[attrs["name"]] = attrs
        else:
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
                if parttype in ["ringtext"]:
                    items = []
                    for item in part.find("MLABEL").find("STRINGS").iterfind("STRING"):
                        items.append(item.text)
                    attrs.update({"items": items})
            controls[attrs["name"]] = attrs
            if attrs["type"] == "Cluster":
                controls[attrs["name"]]["ctrls"] = _recurse_ctrls(
                    control.find("CONTENT")
                )
    return controls


def parse_vistrings(vistr: str) -> dict:
    """Parse exported VI strings pseudo-XML to extract controls"""
    vixml = io.StringIO(_vistr2xml(vistr))
    tree = ET.parse(vixml)
    root = tree.getroot()
    return _recurse_ctrls(root.find("CONTENT"))
