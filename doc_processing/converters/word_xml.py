"""Advanced Word document XML processing and extraction system."""

import io
import logging
import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


@dataclass
class WordElement:
    """Represents a Word document element with its properties."""

    element_type: str  # paragraph, run, table, image, etc.
    element_id: Optional[str]
    text_content: str
    formatting: Dict[str, Any]
    position: Dict[str, int]  # line, column, index
    children: List["WordElement"]
    attributes: Dict[str, Any]

    def __post_init__(self):
        if self.children is None:
            self.children = []
        if self.formatting is None:
            self.formatting = {}
        if self.attributes is None:
            self.attributes = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["children"] = [child.to_dict() for child in self.children]
        return data


@dataclass
class WordStyle:
    """Represents a Word document style definition."""

    style_id: str
    style_name: str
    style_type: str  # paragraph, character, table, numbering
    base_style: Optional[str]
    formatting_properties: Dict[str, Any]
    is_default: bool = False
    is_custom: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)


@dataclass
class WordDocument:
    """Represents a complete Word document structure."""

    document_properties: Dict[str, Any]
    styles: Dict[str, WordStyle]
    elements: List[WordElement]
    relationships: Dict[str, str]
    content_types: Dict[str, str]
    numbering: Dict[str, Any]
    themes: Dict[str, Any]
    settings: Dict[str, Any]

    def __post_init__(self):
        if self.styles is None:
            self.styles = {}
        if self.elements is None:
            self.elements = []
        if self.relationships is None:
            self.relationships = {}
        if self.content_types is None:
            self.content_types = {}
        if self.numbering is None:
            self.numbering = {}
        if self.themes is None:
            self.themes = {}
        if self.settings is None:
            self.settings = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["styles"] = {k: v.to_dict() for k, v in self.styles.items()}
        data["elements"] = [elem.to_dict() for elem in self.elements]
        return data


class WordNamespaces:
    """Word document XML namespaces."""

    WORD = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    RELATIONSHIPS = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    )
    CONTENT_TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"
    CORE_PROPERTIES = (
        "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
    )
    EXTENDED_PROPERTIES = (
        "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
    )
    DRAWING = "http://schemas.openxmlformats.org/drawingml/2006/main"
    PICTURE = "http://schemas.openxmlformats.org/drawingml/2006/picture"

    @classmethod
    def get_namespaces(cls) -> Dict[str, str]:
        """Get namespace mapping for XML parsing."""
        return {
            "w": cls.WORD,
            "r": cls.RELATIONSHIPS,
            "ct": cls.CONTENT_TYPES,
            "cp": cls.CORE_PROPERTIES,
            "ep": cls.EXTENDED_PROPERTIES,
            "a": cls.DRAWING,
            "pic": cls.PICTURE,
        }


class WordXMLExtractor:
    """Advanced XML extraction system for Word documents."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize XML extractor.

        Args:
            config: Configuration options for extraction
        """
        self.config = config or {}
        self.preserve_formatting = self.config.get("preserve_formatting", True)
        self.extract_embedded_objects = self.config.get(
            "extract_embedded_objects", True
        )
        self.include_hidden_text = self.config.get("include_hidden_text", False)
        self.process_headers_footers = self.config.get("process_headers_footers", True)
        self.extract_comments = self.config.get("extract_comments", True)
        self.extract_revisions = self.config.get("extract_revisions", True)

        self.namespaces = WordNamespaces.get_namespaces()

    def extract_document(self, word_file: Union[str, Path]) -> WordDocument:
        """Extract complete Word document structure.

        Args:
            word_file: Path to Word document

        Returns:
            WordDocument object with complete structure
        """
        word_path = Path(word_file)
        if not word_path.exists():
            raise FileNotFoundError(f"Word document not found: {word_path}")

        if not word_path.suffix.lower() in [".docx", ".docm"]:
            raise ValueError(f"Unsupported file format: {word_path.suffix}")

        try:
            with zipfile.ZipFile(word_path, "r") as zip_file:
                # Extract document properties
                doc_properties = self._extract_document_properties(zip_file)

                # Extract styles
                styles = self._extract_styles(zip_file)

                # Extract main document content
                elements = self._extract_document_content(zip_file)

                # Extract relationships
                relationships = self._extract_relationships(zip_file)

                # Extract content types
                content_types = self._extract_content_types(zip_file)

                # Extract numbering definitions
                numbering = self._extract_numbering(zip_file)

                # Extract themes
                themes = self._extract_themes(zip_file)

                # Extract settings
                settings = self._extract_settings(zip_file)

                return WordDocument(
                    document_properties=doc_properties,
                    styles=styles,
                    elements=elements,
                    relationships=relationships,
                    content_types=content_types,
                    numbering=numbering,
                    themes=themes,
                    settings=settings,
                )

        except zipfile.BadZipFile:
            raise ValueError(f"Invalid Word document format: {word_path}")
        except Exception as e:
            logger.error(f"Failed to extract Word document {word_path}: {e}")
            raise

    def _extract_document_properties(self, zip_file: zipfile.ZipFile) -> Dict[str, Any]:
        """Extract document properties from core.xml and app.xml."""
        properties = {}

        # Core properties
        try:
            with zip_file.open("docProps/core.xml") as core_file:
                core_root = ET.parse(core_file).getroot()

                for elem in core_root:
                    tag_name = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                    properties[f"core_{tag_name}"] = elem.text
        except KeyError:
            logger.warning("Core properties not found in document")

        # App properties
        try:
            with zip_file.open("docProps/app.xml") as app_file:
                app_root = ET.parse(app_file).getroot()

                for elem in app_root:
                    tag_name = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                    properties[f"app_{tag_name}"] = elem.text
        except KeyError:
            logger.warning("App properties not found in document")

        return properties

    def _extract_styles(self, zip_file: zipfile.ZipFile) -> Dict[str, WordStyle]:
        """Extract style definitions from styles.xml."""
        styles = {}

        try:
            with zip_file.open("word/styles.xml") as styles_file:
                styles_root = ET.parse(styles_file).getroot()

                for style_elem in styles_root.findall(".//w:style", self.namespaces):
                    style_id = style_elem.get(f"{{{self.namespaces['w']}}}styleId")
                    style_type = style_elem.get(f"{{{self.namespaces['w']}}}type")

                    # Get style name
                    name_elem = style_elem.find("w:name", self.namespaces)
                    style_name = (
                        name_elem.get(f"{{{self.namespaces['w']}}}val")
                        if name_elem is not None
                        else style_id
                    )

                    # Get base style
                    base_elem = style_elem.find("w:basedOn", self.namespaces)
                    base_style = (
                        base_elem.get(f"{{{self.namespaces['w']}}}val")
                        if base_elem is not None
                        else None
                    )

                    # Extract formatting properties
                    formatting_props = self._extract_formatting_properties(style_elem)

                    # Check if default or custom
                    is_default = (
                        style_elem.get(f"{{{self.namespaces['w']}}}default") == "1"
                    )
                    is_custom = (
                        style_elem.get(f"{{{self.namespaces['w']}}}customStyle") == "1"
                    )

                    styles[style_id] = WordStyle(
                        style_id=style_id,
                        style_name=style_name,
                        style_type=style_type,
                        base_style=base_style,
                        formatting_properties=formatting_props,
                        is_default=is_default,
                        is_custom=is_custom,
                    )

        except KeyError:
            logger.warning("Styles not found in document")

        return styles

    def _extract_formatting_properties(self, element: ET.Element) -> Dict[str, Any]:
        """Extract formatting properties from an XML element."""
        formatting = {}

        # Paragraph properties
        p_pr = element.find("w:pPr", self.namespaces)
        if p_pr is not None:
            formatting["paragraph"] = self._extract_paragraph_properties(p_pr)

        # Run properties (character formatting)
        r_pr = element.find("w:rPr", self.namespaces)
        if r_pr is not None:
            formatting["character"] = self._extract_character_properties(r_pr)

        # Table properties
        tbl_pr = element.find("w:tblPr", self.namespaces)
        if tbl_pr is not None:
            formatting["table"] = self._extract_table_properties(tbl_pr)

        return formatting

    def _extract_paragraph_properties(self, p_pr: ET.Element) -> Dict[str, Any]:
        """Extract paragraph formatting properties."""
        props = {}

        # Alignment
        jc = p_pr.find("w:jc", self.namespaces)
        if jc is not None:
            props["alignment"] = jc.get(f"{{{self.namespaces['w']}}}val")

        # Spacing
        spacing = p_pr.find("w:spacing", self.namespaces)
        if spacing is not None:
            props["spacing"] = {
                "before": spacing.get(f"{{{self.namespaces['w']}}}before"),
                "after": spacing.get(f"{{{self.namespaces['w']}}}after"),
                "line": spacing.get(f"{{{self.namespaces['w']}}}line"),
                "line_rule": spacing.get(f"{{{self.namespaces['w']}}}lineRule"),
            }

        # Indentation
        ind = p_pr.find("w:ind", self.namespaces)
        if ind is not None:
            props["indentation"] = {
                "left": ind.get(f"{{{self.namespaces['w']}}}left"),
                "right": ind.get(f"{{{self.namespaces['w']}}}right"),
                "first_line": ind.get(f"{{{self.namespaces['w']}}}firstLine"),
                "hanging": ind.get(f"{{{self.namespaces['w']}}}hanging"),
            }

        # Numbering
        num_pr = p_pr.find("w:numPr", self.namespaces)
        if num_pr is not None:
            props["numbering"] = {
                "id": (
                    num_pr.find("w:numId", self.namespaces).get(
                        f"{{{self.namespaces['w']}}}val"
                    )
                    if num_pr.find("w:numId", self.namespaces) is not None
                    else None
                ),
                "level": (
                    num_pr.find("w:ilvl", self.namespaces).get(
                        f"{{{self.namespaces['w']}}}val"
                    )
                    if num_pr.find("w:ilvl", self.namespaces) is not None
                    else None
                ),
            }

        return props

    def _extract_character_properties(self, r_pr: ET.Element) -> Dict[str, Any]:
        """Extract character formatting properties."""
        props = {}

        # Font
        r_fonts = r_pr.find("w:rFonts", self.namespaces)
        if r_fonts is not None:
            props["font"] = {
                "ascii": r_fonts.get(f"{{{self.namespaces['w']}}}ascii"),
                "h_ansi": r_fonts.get(f"{{{self.namespaces['w']}}}hAnsi"),
                "complex_script": r_fonts.get(f"{{{self.namespaces['w']}}}cs"),
            }

        # Font size
        sz = r_pr.find("w:sz", self.namespaces)
        if sz is not None:
            props["font_size"] = sz.get(f"{{{self.namespaces['w']}}}val")

        # Bold
        if r_pr.find("w:b", self.namespaces) is not None:
            props["bold"] = True

        # Italic
        if r_pr.find("w:i", self.namespaces) is not None:
            props["italic"] = True

        # Underline
        u = r_pr.find("w:u", self.namespaces)
        if u is not None:
            props["underline"] = u.get(f"{{{self.namespaces['w']}}}val")

        # Color
        color = r_pr.find("w:color", self.namespaces)
        if color is not None:
            props["color"] = color.get(f"{{{self.namespaces['w']}}}val")

        # Highlight
        highlight = r_pr.find("w:highlight", self.namespaces)
        if highlight is not None:
            props["highlight"] = highlight.get(f"{{{self.namespaces['w']}}}val")

        return props

    def _extract_table_properties(self, tbl_pr: ET.Element) -> Dict[str, Any]:
        """Extract table formatting properties."""
        props = {}

        # Table width
        tbl_w = tbl_pr.find("w:tblW", self.namespaces)
        if tbl_w is not None:
            props["width"] = {
                "value": tbl_w.get(f"{{{self.namespaces['w']}}}w"),
                "type": tbl_w.get(f"{{{self.namespaces['w']}}}type"),
            }

        # Table alignment
        jc = tbl_pr.find("w:jc", self.namespaces)
        if jc is not None:
            props["alignment"] = jc.get(f"{{{self.namespaces['w']}}}val")

        # Table borders
        tbl_borders = tbl_pr.find("w:tblBorders", self.namespaces)
        if tbl_borders is not None:
            props["borders"] = {}
            for border in ["top", "left", "bottom", "right", "insideH", "insideV"]:
                border_elem = tbl_borders.find(f"w:{border}", self.namespaces)
                if border_elem is not None:
                    props["borders"][border] = {
                        "val": border_elem.get(f"{{{self.namespaces['w']}}}val"),
                        "size": border_elem.get(f"{{{self.namespaces['w']}}}sz"),
                        "color": border_elem.get(f"{{{self.namespaces['w']}}}color"),
                    }

        return props

    def _extract_document_content(self, zip_file: zipfile.ZipFile) -> List[WordElement]:
        """Extract main document content from document.xml."""
        elements = []

        try:
            with zip_file.open("word/document.xml") as doc_file:
                doc_root = ET.parse(doc_file).getroot()
                body = doc_root.find("w:body", self.namespaces)

                if body is not None:
                    position_index = 0
                    for elem in body:
                        word_element = self._process_document_element(
                            elem, position_index
                        )
                        if word_element:
                            elements.append(word_element)
                            position_index += 1

        except KeyError:
            logger.error("Main document content not found")

        return elements

    def _process_document_element(
        self, elem: ET.Element, position_index: int
    ) -> Optional[WordElement]:
        """Process a single document element."""
        tag_name = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

        if tag_name == "p":  # Paragraph
            return self._process_paragraph(elem, position_index)
        elif tag_name == "tbl":  # Table
            return self._process_table(elem, position_index)
        elif tag_name == "sectPr":  # Section properties
            return self._process_section_properties(elem, position_index)
        else:
            # Generic element processing
            return WordElement(
                element_type=tag_name,
                element_id=elem.get("id"),
                text_content="",
                formatting={},
                position={"index": position_index},
                children=[],
                attributes=dict(elem.attrib),
            )

    def _process_paragraph(
        self, p_elem: ET.Element, position_index: int
    ) -> WordElement:
        """Process a paragraph element."""
        text_content = ""
        children = []
        formatting = {}

        # Extract paragraph properties
        p_pr = p_elem.find("w:pPr", self.namespaces)
        if p_pr is not None:
            formatting = self._extract_paragraph_properties(p_pr)

        # Process runs
        for run in p_elem.findall("w:r", self.namespaces):
            run_element = self._process_run(run, len(children))
            if run_element:
                children.append(run_element)
                text_content += run_element.text_content

        # Process hyperlinks
        for hyperlink in p_elem.findall("w:hyperlink", self.namespaces):
            hyperlink_element = self._process_hyperlink(hyperlink, len(children))
            if hyperlink_element:
                children.append(hyperlink_element)
                text_content += hyperlink_element.text_content

        return WordElement(
            element_type="paragraph",
            element_id=p_elem.get("id"),
            text_content=text_content,
            formatting=formatting,
            position={"index": position_index},
            children=children,
            attributes=dict(p_elem.attrib),
        )

    def _process_run(self, r_elem: ET.Element, position_index: int) -> WordElement:
        """Process a run (character formatting) element."""
        text_content = ""
        formatting = {}
        children = []

        # Extract run properties
        r_pr = r_elem.find("w:rPr", self.namespaces)
        if r_pr is not None:
            formatting = self._extract_character_properties(r_pr)

        # Extract text
        for t_elem in r_elem.findall("w:t", self.namespaces):
            if t_elem.text:
                text_content += t_elem.text

        # Handle tabs
        for tab in r_elem.findall("w:tab", self.namespaces):
            text_content += "\t"

        # Handle line breaks
        for br in r_elem.findall("w:br", self.namespaces):
            text_content += "\n"

        # Handle drawings/images
        for drawing in r_elem.findall("w:drawing", self.namespaces):
            drawing_element = self._process_drawing(drawing, len(children))
            if drawing_element:
                children.append(drawing_element)

        return WordElement(
            element_type="run",
            element_id=r_elem.get("id"),
            text_content=text_content,
            formatting=formatting,
            position={"index": position_index},
            children=children,
            attributes=dict(r_elem.attrib),
        )

    def _process_table(self, tbl_elem: ET.Element, position_index: int) -> WordElement:
        """Process a table element."""
        children = []
        formatting = {}

        # Extract table properties
        tbl_pr = tbl_elem.find("w:tblPr", self.namespaces)
        if tbl_pr is not None:
            formatting = self._extract_table_properties(tbl_pr)

        # Process table rows
        for tr in tbl_elem.findall("w:tr", self.namespaces):
            row_element = self._process_table_row(tr, len(children))
            if row_element:
                children.append(row_element)

        return WordElement(
            element_type="table",
            element_id=tbl_elem.get("id"),
            text_content="",
            formatting=formatting,
            position={"index": position_index},
            children=children,
            attributes=dict(tbl_elem.attrib),
        )

    def _process_table_row(
        self, tr_elem: ET.Element, position_index: int
    ) -> WordElement:
        """Process a table row element."""
        children = []

        # Process table cells
        for tc in tr_elem.findall("w:tc", self.namespaces):
            cell_element = self._process_table_cell(tc, len(children))
            if cell_element:
                children.append(cell_element)

        return WordElement(
            element_type="table_row",
            element_id=tr_elem.get("id"),
            text_content="",
            formatting={},
            position={"index": position_index},
            children=children,
            attributes=dict(tr_elem.attrib),
        )

    def _process_table_cell(
        self, tc_elem: ET.Element, position_index: int
    ) -> WordElement:
        """Process a table cell element."""
        children = []
        text_content = ""

        # Process paragraphs in cell
        for p in tc_elem.findall("w:p", self.namespaces):
            p_element = self._process_paragraph(p, len(children))
            if p_element:
                children.append(p_element)
                text_content += p_element.text_content + "\n"

        return WordElement(
            element_type="table_cell",
            element_id=tc_elem.get("id"),
            text_content=text_content.rstrip(),
            formatting={},
            position={"index": position_index},
            children=children,
            attributes=dict(tc_elem.attrib),
        )

    def _process_hyperlink(
        self, hyperlink_elem: ET.Element, position_index: int
    ) -> WordElement:
        """Process a hyperlink element."""
        text_content = ""
        children = []

        # Process runs within hyperlink
        for run in hyperlink_elem.findall("w:r", self.namespaces):
            run_element = self._process_run(run, len(children))
            if run_element:
                children.append(run_element)
                text_content += run_element.text_content

        return WordElement(
            element_type="hyperlink",
            element_id=hyperlink_elem.get("id"),
            text_content=text_content,
            formatting={},
            position={"index": position_index},
            children=children,
            attributes=dict(hyperlink_elem.attrib),
        )

    def _process_drawing(
        self, drawing_elem: ET.Element, position_index: int
    ) -> WordElement:
        """Process a drawing/image element."""
        # Extract image information
        image_info = {}

        # Find inline drawings
        inline = drawing_elem.find(
            ".//wp:inline",
            {
                "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
            },
        )
        if inline is not None:
            image_info["type"] = "inline"

        # Find anchored drawings
        anchor = drawing_elem.find(
            ".//wp:anchor",
            {
                "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
            },
        )
        if anchor is not None:
            image_info["type"] = "anchored"

        return WordElement(
            element_type="drawing",
            element_id=drawing_elem.get("id"),
            text_content="[IMAGE]",
            formatting=image_info,
            position={"index": position_index},
            children=[],
            attributes=dict(drawing_elem.attrib),
        )

    def _process_section_properties(
        self, sect_pr_elem: ET.Element, position_index: int
    ) -> WordElement:
        """Process section properties element."""
        return WordElement(
            element_type="section_properties",
            element_id=sect_pr_elem.get("id"),
            text_content="",
            formatting={},
            position={"index": position_index},
            children=[],
            attributes=dict(sect_pr_elem.attrib),
        )

    def _extract_relationships(self, zip_file: zipfile.ZipFile) -> Dict[str, str]:
        """Extract document relationships."""
        relationships = {}

        try:
            with zip_file.open("word/_rels/document.xml.rels") as rels_file:
                rels_root = ET.parse(rels_file).getroot()

                for rel in rels_root.findall(
                    "r:Relationship", {"r": self.namespaces["r"]}
                ):
                    rel_id = rel.get("Id")
                    target = rel.get("Target")
                    rel_type = rel.get("Type")

                    relationships[rel_id] = {"target": target, "type": rel_type}

        except KeyError:
            logger.warning("Document relationships not found")

        return relationships

    def _extract_content_types(self, zip_file: zipfile.ZipFile) -> Dict[str, str]:
        """Extract content type definitions."""
        content_types = {}

        try:
            with zip_file.open("[Content_Types].xml") as ct_file:
                ct_root = ET.parse(ct_file).getroot()

                for default in ct_root.findall(
                    "ct:Default", {"ct": self.namespaces["ct"]}
                ):
                    extension = default.get("Extension")
                    content_type = default.get("ContentType")
                    content_types[f"ext_{extension}"] = content_type

                for override in ct_root.findall(
                    "ct:Override", {"ct": self.namespaces["ct"]}
                ):
                    part_name = override.get("PartName")
                    content_type = override.get("ContentType")
                    content_types[part_name] = content_type

        except KeyError:
            logger.warning("Content types not found")

        return content_types

    def _extract_numbering(self, zip_file: zipfile.ZipFile) -> Dict[str, Any]:
        """Extract numbering definitions."""
        numbering = {}

        try:
            with zip_file.open("word/numbering.xml") as num_file:
                num_root = ET.parse(num_file).getroot()

                # Extract abstract numbering definitions
                for abstract_num in num_root.findall("w:abstractNum", self.namespaces):
                    abstract_id = abstract_num.get(
                        f"{{{self.namespaces['w']}}}abstractNumId"
                    )
                    numbering[f"abstract_{abstract_id}"] = {
                        "type": "abstract",
                        "levels": {},
                    }

                    # Extract level definitions
                    for lvl in abstract_num.findall("w:lvl", self.namespaces):
                        level_id = lvl.get(f"{{{self.namespaces['w']}}}ilvl")
                        numbering[f"abstract_{abstract_id}"]["levels"][level_id] = {
                            "format": (
                                lvl.find("w:numFmt", self.namespaces).get(
                                    f"{{{self.namespaces['w']}}}val"
                                )
                                if lvl.find("w:numFmt", self.namespaces) is not None
                                else None
                            ),
                            "text": (
                                lvl.find("w:lvlText", self.namespaces).get(
                                    f"{{{self.namespaces['w']}}}val"
                                )
                                if lvl.find("w:lvlText", self.namespaces) is not None
                                else None
                            ),
                        }

                # Extract concrete numbering instances
                for num in num_root.findall("w:num", self.namespaces):
                    num_id = num.get(f"{{{self.namespaces['w']}}}numId")
                    abstract_ref = num.find("w:abstractNumId", self.namespaces)
                    if abstract_ref is not None:
                        numbering[f"concrete_{num_id}"] = {
                            "type": "concrete",
                            "abstract_re": abstract_ref.get(
                                f"{{{self.namespaces['w']}}}val"
                            ),
                        }

        except KeyError:
            logger.warning("Numbering definitions not found")

        return numbering

    def _extract_themes(self, zip_file: zipfile.ZipFile) -> Dict[str, Any]:
        """Extract theme definitions."""
        themes = {}

        try:
            with zip_file.open("word/theme/theme1.xml") as theme_file:
                theme_root = ET.parse(theme_file).getroot()

                # Extract basic theme information
                themes["name"] = theme_root.get("name", "Default")

                # Extract color scheme
                color_scheme = theme_root.find(".//a:clrScheme", self.namespaces)
                if color_scheme is not None:
                    themes["color_scheme"] = color_scheme.get("name", "Default")

                # Extract font scheme
                font_scheme = theme_root.find(".//a:fontScheme", self.namespaces)
                if font_scheme is not None:
                    themes["font_scheme"] = font_scheme.get("name", "Default")

        except KeyError:
            logger.warning("Theme definitions not found")

        return themes

    def _extract_settings(self, zip_file: zipfile.ZipFile) -> Dict[str, Any]:
        """Extract document settings."""
        settings = {}

        try:
            with zip_file.open("word/settings.xml") as settings_file:
                settings_root = ET.parse(settings_file).getroot()

                # Extract various settings
                for setting in settings_root:
                    tag_name = (
                        setting.tag.split("}")[-1]
                        if "}" in setting.tag
                        else setting.tag
                    )
                    if setting.text:
                        settings[tag_name] = setting.text
                    elif setting.attrib:
                        settings[tag_name] = dict(setting.attrib)

        except KeyError:
            logger.warning("Document settings not found")

        return settings

    def extract_text_only(self, word_file: Union[str, Path]) -> str:
        """Extract only text content from Word document (fast operation).

        Args:
            word_file: Path to Word document

        Returns:
            Plain text content of the document
        """
        word_path = Path(word_file)
        text_content = []

        try:
            with zipfile.ZipFile(word_path, "r") as zip_file:
                with zip_file.open("word/document.xml") as doc_file:
                    # Use iterparse for memory efficiency with large documents
                    for event, elem in ET.iterparse(doc_file, events=("start", "end")):
                        if event == "end" and elem.tag.endswith("}t"):
                            if elem.text:
                                text_content.append(elem.text)
                            elem.clear()  # Free memory

        except Exception as e:
            logger.error(f"Failed to extract text from {word_path}: {e}")
            raise

        return "".join(text_content)

    def get_document_statistics(self, word_document: WordDocument) -> Dict[str, Any]:
        """Get comprehensive statistics about the document structure.

        Args:
            word_document: WordDocument object

        Returns:
            Dictionary with document statistics
        """
        stats = {
            "total_elements": len(word_document.elements),
            "element_types": {},
            "text_statistics": {},
            "formatting_complexity": {},
            "structure_analysis": {},
        }

        # Count element types
        total_text_length = 0
        total_paragraphs = 0
        total_tables = 0
        total_images = 0

        def count_elements(elements: List[WordElement]):
            nonlocal total_text_length, total_paragraphs, total_tables, total_images

            for element in elements:
                elem_type = element.element_type
                stats["element_types"][elem_type] = (
                    stats["element_types"].get(elem_type, 0) + 1
                )

                if element.text_content:
                    total_text_length += len(element.text_content)

                if elem_type == "paragraph":
                    total_paragraphs += 1
                elif elem_type == "table":
                    total_tables += 1
                elif elem_type == "drawing":
                    total_images += 1

                if element.children:
                    count_elements(element.children)

        count_elements(word_document.elements)

        # Text statistics
        stats["text_statistics"] = {
            "total_characters": total_text_length,
            "total_paragraphs": total_paragraphs,
            "total_tables": total_tables,
            "total_images": total_images,
            "estimated_words": (
                total_text_length // 5 if total_text_length > 0 else 0
            ),  # Rough estimate
        }

        # Formatting complexity
        stats["formatting_complexity"] = {
            "total_styles": len(word_document.styles),
            "custom_styles": len(
                [s for s in word_document.styles.values() if s.is_custom]
            ),
            "has_numbering": bool(word_document.numbering),
            "has_themes": bool(word_document.themes),
        }

        # Structure analysis
        stats["structure_analysis"] = {
            "max_nesting_level": self._calculate_max_nesting_level(
                word_document.elements
            ),
            "has_headers_footers": "header" in str(word_document.relationships)
            or "footer" in str(word_document.relationships),
            "has_embedded_objects": any(
                "object" in str(rel) for rel in word_document.relationships.values()
            ),
        }

        return stats

    def _calculate_max_nesting_level(
        self, elements: List[WordElement], current_level: int = 0
    ) -> int:
        """Calculate maximum nesting level in document structure."""
        max_level = current_level

        for element in elements:
            if element.children:
                child_max = self._calculate_max_nesting_level(
                    element.children, current_level + 1
                )
                max_level = max(max_level, child_max)

        return max_level
