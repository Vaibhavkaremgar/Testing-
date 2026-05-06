from datetime import datetime
from typing import Optional
from xml.dom import minidom
from xml.etree import ElementTree as ET


def append_text_element(parent: ET.Element, tag: str, value: Optional[str]) -> ET.Element:
    child = ET.SubElement(parent, tag)
    child.text = "" if value is None else str(value)
    return child


def format_datetime(value: Optional[datetime]) -> str:
    if value is None:
        return ""
    return value.isoformat()


def prettify_xml(root: ET.Element) -> bytes:
    raw_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    parsed_xml = minidom.parseString(raw_xml)
    pretty_xml = parsed_xml.toprettyxml(indent="    ", encoding="utf-8")
    return b"\n".join(line for line in pretty_xml.splitlines() if line.strip())


def validate_xml(xml_content: bytes) -> None:
    ET.fromstring(xml_content)
