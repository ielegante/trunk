import io
import logging
import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import defusedxml.ElementTree as safe_ET
import xmltodict

logger = logging.getLogger(__name__)


class WordElementType(Enum):
    """Types of Word document elements"""

    PARAGRAPH = "paragraph"
    RUN = "run"
    TABLE = "table"
    HEADING = "heading"
    LIST = "list"
    IMAGE = "image"
    HYPERLINK = "hyperlink"
    FOOTNOTE = "footnote"
    ENDNOTE = "endnote"
    COMMENT = "comment"


@dataclass
class WordElement:
    """Represents a Word document element"""

    element_type: WordElementType
    content: str
    properties: Dict[str, Any]
    style: Optional[str] = None
    level: Optional[int] = None
    children: List["WordElement"] = None

    def __post_init__(self):
        if self.children is None:
            self.children = []


@dataclass
class WordDocumentStructure:
    """Represents the structure of a Word document"""

    elements: List[WordElement]
    styles: Dict[str, Dict]
    metadata: Dict[str, Any]
    relationships: Dict[str, str]
    images: List[Dict]
    tables: List[Dict]
    footnotes: List[Dict]
    endnotes: List[Dict]
    comments: List[Dict]


class WordXMLParser:
    """Parser for Word document XML content"""

    # Word XML namespaces
    NAMESPACES = {
        "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
        "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
        "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
        "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
        "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
        "dc": "http://purl.org/dc/elements/1.1/",
        "dcterms": "http://purl.org/dc/terms/",
        "dcmitype": "http://purl.org/dc/dcmitype/",
        "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    }

    def __init__(self):
        self.register_namespaces()

    def register_namespaces(self):
        """Register XML namespaces for parsing"""
        for prefix, uri in self.NAMESPACES.items():
            ET.register_namespace(prefix, uri)

    def parse_docx_file(self, file_path: str) -> WordDocumentStructure:
        """Parse a .docx file and extract structure"""
        try:
            with zipfile.ZipFile(file_path, "r") as docx_zip:
                return self._parse_docx_zip(docx_zip)
        except Exception as e:
            logger.error(f"Failed to parse DOCX file {file_path}: {str(e)}")
            raise

    def parse_docx_bytes(self, docx_bytes: bytes) -> WordDocumentStructure:
        """Parse DOCX content from bytes"""
        try:
            with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as docx_zip:
                return self._parse_docx_zip(docx_zip)
        except Exception as e:
            logger.error(f"Failed to parse DOCX bytes: {str(e)}")
            raise

    def _parse_docx_zip(self, docx_zip: zipfile.ZipFile) -> WordDocumentStructure:
        """Parse DOCX content from zip file"""
        # Extract main document XML
        document_xml = self._get_document_xml(docx_zip)

        # Extract styles
        styles = self._extract_styles(docx_zip)

        # Extract metadata
        metadata = self._extract_metadata(docx_zip)

        # Extract relationships
        relationships = self._extract_relationships(docx_zip)

        # Parse document structure
        elements = self._parse_document_elements(document_xml, styles)

        # Extract additional components
        images = self._extract_images(docx_zip, relationships)
        tables = self._extract_tables(document_xml)
        footnotes = self._extract_footnotes(docx_zip)
        endnotes = self._extract_endnotes(docx_zip)
        comments = self._extract_comments(docx_zip)

        return WordDocumentStructure(
            elements=elements,
            styles=styles,
            metadata=metadata,
            relationships=relationships,
            images=images,
            tables=tables,
            footnotes=footnotes,
            endnotes=endnotes,
            comments=comments,
        )

    def _get_document_xml(self, docx_zip: zipfile.ZipFile) -> ET.Element:
        """Extract main document XML"""
        try:
            document_content = docx_zip.read("word/document.xml")
            return safe_ET.fromstring(document_content)
        except Exception as e:
            logger.error(f"Failed to extract document XML: {str(e)}")
            raise

    def _extract_styles(self, docx_zip: zipfile.ZipFile) -> Dict[str, Dict]:
        """Extract style definitions"""
        styles = {}
        try:
            if "word/styles.xml" in docx_zip.namelist():
                styles_content = docx_zip.read("word/styles.xml")
                styles_root = safe_ET.fromstring(styles_content)

                for style in styles_root.findall(".//w:style", self.NAMESPACES):
                    style_id = style.get(f'{{{self.NAMESPACES["w"]}}}styleId')
                    style_name = style.find(".//w:name", self.NAMESPACES)

                    if style_id:
                        styles[style_id] = {
                            "name": (
                                style_name.get(f'{{{self.NAMESPACES["w"]}}}val')
                                if style_name is not None
                                else style_id
                            ),
                            "type": style.get(f'{{{self.NAMESPACES["w"]}}}type'),
                            "properties": self._extract_style_properties(style),
                        }
        except Exception as e:
            logger.warning(f"Failed to extract styles: {str(e)}")

        return styles

    def _extract_style_properties(self, style_element: ET.Element) -> Dict:
        """Extract properties from a style element"""
        properties = {}

        # Character properties
        char_props = style_element.find(".//w:rPr", self.NAMESPACES)
        if char_props is not None:
            properties["character"] = self._parse_character_properties(char_props)

        # Paragraph properties
        para_props = style_element.find(".//w:pPr", self.NAMESPACES)
        if para_props is not None:
            properties["paragraph"] = self._parse_paragraph_properties(para_props)

        return properties

    def _parse_character_properties(self, char_props: ET.Element) -> Dict:
        """Parse character formatting properties"""
        props = {}

        # Bold
        bold = char_props.find(".//w:b", self.NAMESPACES)
        if bold is not None:
            props["bold"] = (
                bold.get(f'{{{self.NAMESPACES["w"]}}}val', "true") != "false"
            )

        # Italic
        italic = char_props.find(".//w:i", self.NAMESPACES)
        if italic is not None:
            props["italic"] = (
                italic.get(f'{{{self.NAMESPACES["w"]}}}val', "true") != "false"
            )

        # Underline
        underline = char_props.find(".//w:u", self.NAMESPACES)
        if underline is not None:
            props["underline"] = underline.get(
                f'{{{self.NAMESPACES["w"]}}}val', "single"
            )

        # Font size
        font_size = char_props.find(".//w:sz", self.NAMESPACES)
        if font_size is not None:
            props["font_size"] = font_size.get(f'{{{self.NAMESPACES["w"]}}}val')

        # Font family
        font_family = char_props.find(".//w:rFonts", self.NAMESPACES)
        if font_family is not None:
            props["font_family"] = font_family.get(f'{{{self.NAMESPACES["w"]}}}ascii')

        # Color
        color = char_props.find(".//w:color", self.NAMESPACES)
        if color is not None:
            props["color"] = color.get(f'{{{self.NAMESPACES["w"]}}}val')

        return props

    def _parse_paragraph_properties(self, para_props: ET.Element) -> Dict:
        """Parse paragraph formatting properties"""
        props = {}

        # Alignment
        alignment = para_props.find(".//w:jc", self.NAMESPACES)
        if alignment is not None:
            props["alignment"] = alignment.get(f'{{{self.NAMESPACES["w"]}}}val')

        # Indentation
        indentation = para_props.find(".//w:ind", self.NAMESPACES)
        if indentation is not None:
            props["indentation"] = {
                "left": indentation.get(f'{{{self.NAMESPACES["w"]}}}left'),
                "right": indentation.get(f'{{{self.NAMESPACES["w"]}}}right'),
                "first_line": indentation.get(f'{{{self.NAMESPACES["w"]}}}firstLine'),
            }

        # Spacing
        spacing = para_props.find(".//w:spacing", self.NAMESPACES)
        if spacing is not None:
            props["spacing"] = {
                "before": spacing.get(f'{{{self.NAMESPACES["w"]}}}before'),
                "after": spacing.get(f'{{{self.NAMESPACES["w"]}}}after'),
                "line": spacing.get(f'{{{self.NAMESPACES["w"]}}}line'),
            }

        # Numbering
        numbering = para_props.find(".//w:numPr", self.NAMESPACES)
        if numbering is not None:
            num_id = numbering.find(".//w:numId", self.NAMESPACES)
            level = numbering.find(".//w:ilvl", self.NAMESPACES)
            props["numbering"] = {
                "id": (
                    num_id.get(f'{{{self.NAMESPACES["w"]}}}val')
                    if num_id is not None
                    else None
                ),
                "level": (
                    level.get(f'{{{self.NAMESPACES["w"]}}}val')
                    if level is not None
                    else "0"
                ),
            }

        return props

    def _extract_metadata(self, docx_zip: zipfile.ZipFile) -> Dict[str, Any]:
        """Extract document metadata"""
        metadata = {}

        try:
            # Core properties
            if "docProps/core.xml" in docx_zip.namelist():
                core_content = docx_zip.read("docProps/core.xml")
                core_root = safe_ET.fromstring(core_content)

                metadata.update(
                    {
                        "title": self._get_element_text(core_root, ".//dc:title"),
                        "creator": self._get_element_text(core_root, ".//dc:creator"),
                        "subject": self._get_element_text(core_root, ".//dc:subject"),
                        "description": self._get_element_text(
                            core_root, ".//dc:description"
                        ),
                        "created": self._get_element_text(
                            core_root, ".//dcterms:created"
                        ),
                        "modified": self._get_element_text(
                            core_root, ".//dcterms:modified"
                        ),
                        "last_modified_by": self._get_element_text(
                            core_root, ".//cp:lastModifiedBy"
                        ),
                        "revision": self._get_element_text(core_root, ".//cp:revision"),
                    }
                )

            # App properties
            if "docProps/app.xml" in docx_zip.namelist():
                app_content = docx_zip.read("docProps/app.xml")
                app_root = safe_ET.fromstring(app_content)

                metadata.update(
                    {
                        "application": self._get_element_text(
                            app_root, ".//Application"
                        ),
                        "doc_security": self._get_element_text(
                            app_root, ".//DocSecurity"
                        ),
                        "lines": self._get_element_text(app_root, ".//Lines"),
                        "paragraphs": self._get_element_text(app_root, ".//Paragraphs"),
                        "characters": self._get_element_text(app_root, ".//Characters"),
                        "characters_with_spaces": self._get_element_text(
                            app_root, ".//CharactersWithSpaces"
                        ),
                        "words": self._get_element_text(app_root, ".//Words"),
                        "pages": self._get_element_text(app_root, ".//Pages"),
                    }
                )

        except Exception as e:
            logger.warning(f"Failed to extract metadata: {str(e)}")

        return metadata

    def _get_element_text(self, root: ET.Element, xpath: str) -> Optional[str]:
        """Get text content of an element by XPath"""
        element = root.find(xpath, self.NAMESPACES)
        return element.text if element is not None else None

    def _extract_relationships(self, docx_zip: zipfile.ZipFile) -> Dict[str, str]:
        """Extract document relationships"""
        relationships = {}

        try:
            if "word/_rels/document.xml.rels" in docx_zip.namelist():
                rels_content = docx_zip.read("word/_rels/document.xml.rels")
                rels_root = safe_ET.fromstring(rels_content)

                for rel in rels_root.findall(".//Relationship"):
                    rel_id = rel.get("Id")
                    target = rel.get("Target")
                    rel_type = rel.get("Type")

                    if rel_id and target:
                        relationships[rel_id] = {"target": target, "type": rel_type}

        except Exception as e:
            logger.warning(f"Failed to extract relationships: {str(e)}")

        return relationships

    def _parse_document_elements(
        self, document_xml: ET.Element, styles: Dict
    ) -> List[WordElement]:
        """Parse document elements from XML"""
        elements = []

        body = document_xml.find(".//w:body", self.NAMESPACES)
        if body is None:
            return elements

        for child in body:
            element = self._parse_element(child, styles)
            if element:
                elements.append(element)

        return elements

    def _parse_element(
        self, xml_element: ET.Element, styles: Dict
    ) -> Optional[WordElement]:
        """Parse a single XML element into WordElement"""
        tag = (
            xml_element.tag.split("}")[-1]
            if "}" in xml_element.tag
            else xml_element.tag
        )

        if tag == "p":
            return self._parse_paragraph(xml_element, styles)
        elif tag == "tbl":
            return self._parse_table(xml_element, styles)
        elif tag == "sectPr":
            # Section properties - skip for now
            return None
        else:
            # Handle other elements
            return WordElement(
                element_type=WordElementType.PARAGRAPH, content="", properties={}
            )

    def _parse_paragraph(self, para_xml: ET.Element, styles: Dict) -> WordElement:
        """Parse a paragraph element"""
        content_parts = []
        style_id = None
        properties = {}

        # Extract paragraph properties
        para_props = para_xml.find(".//w:pPr", self.NAMESPACES)
        if para_props is not None:
            style_ref = para_props.find(".//w:pStyle", self.NAMESPACES)
            if style_ref is not None:
                style_id = style_ref.get(f'{{{self.NAMESPACES["w"]}}}val')

            properties = self._parse_paragraph_properties(para_props)

        # Extract runs (text with formatting)
        runs = para_xml.findall(".//w:r", self.NAMESPACES)
        for run in runs:
            run_text = self._extract_run_text(run)
            if run_text:
                content_parts.append(run_text)

        # Determine element type based on style
        element_type = WordElementType.PARAGRAPH
        level = None

        if style_id and style_id in styles:
            style_name = styles[style_id].get("name", "").lower()
            if "heading" in style_name:
                element_type = WordElementType.HEADING
                # Extract heading level
                level_match = re.search(r"heading\s*(\d+)", style_name)
                if level_match:
                    level = int(level_match.group(1))

        # Check for list formatting
        if properties.get("numbering"):
            element_type = WordElementType.LIST
            level = int(properties["numbering"].get("level", "0"))

        return WordElement(
            element_type=element_type,
            content=" ".join(content_parts),
            properties=properties,
            style=style_id,
            level=level,
        )

    def _extract_run_text(self, run_xml: ET.Element) -> str:
        """Extract text from a run element"""
        text_parts = []

        # Regular text
        text_elements = run_xml.findall(".//w:t", self.NAMESPACES)
        for text_elem in text_elements:
            if text_elem.text:
                text_parts.append(text_elem.text)

        # Tab characters
        tabs = run_xml.findall(".//w:tab", self.NAMESPACES)
        for _ in tabs:
            text_parts.append("\t")

        # Line breaks
        breaks = run_xml.findall(".//w:br", self.NAMESPACES)
        for _ in breaks:
            text_parts.append("\n")

        return "".join(text_parts)

    def _parse_table(self, table_xml: ET.Element, styles: Dict) -> WordElement:
        """Parse a table element"""
        # Extract table content - simplified for now
        content = "[TABLE]"

        return WordElement(
            element_type=WordElementType.TABLE, content=content, properties={}
        )

    def _extract_images(
        self, docx_zip: zipfile.ZipFile, relationships: Dict
    ) -> List[Dict]:
        """Extract image information"""
        images = []
        # Implementation would extract image data and metadata
        return images

    def _extract_tables(self, document_xml: ET.Element) -> List[Dict]:
        """Extract table information"""
        tables = []
        # Implementation would extract detailed table structure
        return tables

    def _extract_footnotes(self, docx_zip: zipfile.ZipFile) -> List[Dict]:
        """Extract footnotes"""
        footnotes = []
        # Implementation would extract footnote content
        return footnotes

    def _extract_endnotes(self, docx_zip: zipfile.ZipFile) -> List[Dict]:
        """Extract endnotes"""
        endnotes = []
        # Implementation would extract endnote content
        return endnotes

    def _extract_comments(self, docx_zip: zipfile.ZipFile) -> List[Dict]:
        """Extract comments"""
        comments = []
        # Implementation would extract comment content
        return comments
