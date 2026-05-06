import re
from datetime import datetime
from typing import Optional
from xml.dom import minidom
from xml.etree import ElementTree as ET


INVALID_XML_CHARS_RE = re.compile(
    "[^\u0009\u000A\u000D\u0020-\uD7FF\uE000-\uFFFD]"
)


def sanitize_xml_text(value: Optional[str]) -> str:
    if value is None:
        return ""
    sanitized = INVALID_XML_CHARS_RE.sub("", str(value))
    return sanitized.strip()


def append_text_element(parent: ET.Element, tag: str, value: Optional[str]) -> ET.Element:
    child = ET.SubElement(parent, tag)
    child.text = sanitize_xml_text(value)
    return child


def format_datetime(value: Optional[datetime]) -> str:
    if value is None:
        return ""
    iso_value = value.isoformat()
    if iso_value.endswith("+00:00"):
        return iso_value.replace("+00:00", "Z")
    return iso_value


def prettify_xml(root: ET.Element) -> bytes:
    raw_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    parsed_xml = minidom.parseString(raw_xml)
    pretty_xml = parsed_xml.toprettyxml(indent="    ", encoding="utf-8")
    cleaned_xml = b"\n".join(line for line in pretty_xml.splitlines() if line.strip())
    return cleaned_xml.replace(b'encoding="utf-8"', b'encoding="UTF-8"', 1)


def validate_xml(xml_content: bytes) -> None:
    ET.fromstring(xml_content)
