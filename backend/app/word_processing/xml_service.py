import io
import logging
import re
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from xml.dom import minidom

from app.word_processing.word_xml_parser import WordDocumentStructure, WordXMLParser
from defusedxml import ElementTree as safe_ET

logger = logging.getLogger(__name__)


class WordXMLService:
    """Service for advanced Word XML processing and manipulation"""

    def __init__(self):
        self.xml_parser = WordXMLParser()
        self.namespaces = self.xml_parser.NAMESPACES

    def extract_xml_structure(self, docx_bytes: bytes) -> Dict[str, Any]:
        """Extract detailed XML structure from DOCX file"""
        try:
            xml_structure = {}

            with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as docx_zip:
                # Extract all XML files
                xml_files = [f for f in docx_zip.namelist() if f.endswith(".xml")]

                for xml_file in xml_files:
                    try:
                        xml_content = docx_zip.read(xml_file)
                        xml_root = safe_ET.fromstring(xml_content)

                        xml_structure[xml_file] = {
                            "file_path": xml_file,
                            "root_tag": xml_root.tag,
                            "namespaces": self._extract_namespaces(xml_root),
                            "element_count": len(list(xml_root.iter())),
                            "structure": self._analyze_xml_structure(xml_root),
                        }
                    except Exception as e:
                        logger.warning(f"Failed to parse {xml_file}: {str(e)}")
                        xml_structure[xml_file] = {"error": str(e)}

            return {
                "success": True,
                "xml_files": xml_structure,
                "file_count": len(xml_structure),
            }

        except Exception as e:
            logger.error(f"Failed to extract XML structure: {str(e)}")
            return {"success": False, "error": str(e)}

    def _extract_namespaces(self, xml_root: ET.Element) -> Dict[str, str]:
        """Extract namespaces from XML element"""
        namespaces = {}

        # Get namespaces from root element
        for prefix, uri in xml_root.attrib.items():
            if prefix.startswith("xmlns"):
                if prefix == "xmlns":
                    namespaces["default"] = uri
                else:
                    prefix_name = prefix.split(":", 1)[1]
                    namespaces[prefix_name] = uri

        return namespaces

    def _analyze_xml_structure(self, xml_root: ET.Element) -> Dict[str, Any]:
        """Analyze XML structure for insights"""
        structure = {
            "depth": self._calculate_depth(xml_root),
            "element_types": {},
            "attributes": {},
            "text_content_elements": 0,
        }

        # Analyze all elements
        for element in xml_root.iter():
            # Count element types
            tag_name = element.tag.split("}")[-1] if "}" in element.tag else element.tag
            structure["element_types"][tag_name] = (
                structure["element_types"].get(tag_name, 0) + 1
            )

            # Count attributes
            for attr_name in element.attrib:
                attr_name = attr_name.split("}")[-1] if "}" in attr_name else attr_name
                structure["attributes"][attr_name] = (
                    structure["attributes"].get(attr_name, 0) + 1
                )

            # Count text content
            if element.text and element.text.strip():
                structure["text_content_elements"] += 1

        return structure

    def _calculate_depth(self, xml_root: ET.Element) -> int:
        """Calculate maximum depth of XML tree"""

        def _depth(element, current_depth=0):
            if not list(element):
                return current_depth
            return max(_depth(child, current_depth + 1) for child in element)

        return _depth(xml_root)

    def extract_custom_xml_parts(self, docx_bytes: bytes) -> Dict[str, Any]:
        """Extract custom XML parts from DOCX"""
        try:
            custom_parts = {}

            with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as docx_zip:
                # Look for custom XML parts
                custom_xml_files = [f for f in docx_zip.namelist() if "customXml" in f]

                for xml_file in custom_xml_files:
                    try:
                        xml_content = docx_zip.read(xml_file)

                        # Try to parse as XML
                        if xml_file.endswith(".xml"):
                            xml_root = safe_ET.fromstring(xml_content)
                            custom_parts[xml_file] = {
                                "type": "xml",
                                "content": self._xml_to_dict(xml_root),
                                "size": len(xml_content),
                            }
                        else:
                            # Store as raw content
                            custom_parts[xml_file] = {
                                "type": "binary",
                                "size": len(xml_content),
                                "encoding": "base64",
                            }
                    except Exception as e:
                        logger.warning(
                            f"Failed to process custom XML {xml_file}: {str(e)}"
                        )

            return {
                "success": True,
                "custom_parts": custom_parts,
                "part_count": len(custom_parts),
            }

        except Exception as e:
            logger.error(f"Failed to extract custom XML parts: {str(e)}")
            return {"success": False, "error": str(e)}

    def _xml_to_dict(self, xml_element: ET.Element) -> Dict:
        """Convert XML element to dictionary"""
        result = {}

        # Add attributes
        if xml_element.attrib:
            result["@attributes"] = xml_element.attrib

        # Add text content
        if xml_element.text and xml_element.text.strip():
            result["@text"] = xml_element.text.strip()

        # Add child elements
        for child in xml_element:
            child_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            child_dict = self._xml_to_dict(child)

            if child_tag in result:
                # Convert to list if multiple elements with same tag
                if not isinstance(result[child_tag], list):
                    result[child_tag] = [result[child_tag]]
                result[child_tag].append(child_dict)
            else:
                result[child_tag] = child_dict

        return result

    def extract_document_variables(self, docx_bytes: bytes) -> Dict[str, Any]:
        """Extract document variables from Word document"""
        try:
            variables = {}

            with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as docx_zip:
                # Check settings.xml for document variables
                if "word/settings.xml" in docx_zip.namelist():
                    settings_content = docx_zip.read("word/settings.xml")
                    settings_root = safe_ET.fromstring(settings_content)

                    # Extract document variables
                    doc_vars = settings_root.findall(".//w:docVar", self.namespaces)
                    for var in doc_vars:
                        var_name = var.get(f'{{{self.namespaces["w"]}}}name')
                        var_val = var.get(f'{{{self.namespaces["w"]}}}val')
                        if var_name:
                            variables[var_name] = var_val

                # Check for custom properties
                if "docProps/custom.xml" in docx_zip.namelist():
                    custom_content = docx_zip.read("docProps/custom.xml")
                    custom_root = safe_ET.fromstring(custom_content)

                    # Extract custom properties
                    for prop in custom_root:
                        prop_name = prop.get("name")
                        prop_value = prop.text
                        if prop_name:
                            variables[f"custom_{prop_name}"] = prop_value

            return {
                "success": True,
                "variables": variables,
                "variable_count": len(variables),
            }

        except Exception as e:
            logger.error(f"Failed to extract document variables: {str(e)}")
            return {"success": False, "error": str(e)}

    def extract_form_fields(self, docx_bytes: bytes) -> Dict[str, Any]:
        """Extract form fields from Word document"""
        try:
            form_fields = []

            with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as docx_zip:
                if "word/document.xml" in docx_zip.namelist():
                    document_content = docx_zip.read("word/document.xml")
                    document_root = safe_ET.fromstring(document_content)

                    # Find form fields (fldSimple and fldChar elements)
                    simple_fields = document_root.findall(
                        ".//w:fldSimple", self.namespaces
                    )
                    for field in simple_fields:
                        field_info = {
                            "type": "simple",
                            "instruction": field.get(
                                f'{{{self.namespaces["w"]}}}instr'
                            ),
                            "text": self._get_field_text(field),
                        }
                        form_fields.append(field_info)

                    # Find complex fields
                    complex_fields = self._extract_complex_fields(document_root)
                    form_fields.extend(complex_fields)

                    # Find content controls
                    content_controls = document_root.findall(
                        ".//w:sdt", self.namespaces
                    )
                    for cc in content_controls:
                        cc_info = self._extract_content_control_info(cc)
                        if cc_info:
                            form_fields.append(cc_info)

            return {
                "success": True,
                "form_fields": form_fields,
                "field_count": len(form_fields),
            }

        except Exception as e:
            logger.error(f"Failed to extract form fields: {str(e)}")
            return {"success": False, "error": str(e)}

    def _get_field_text(self, field_element: ET.Element) -> str:
        """Get text content from a field element"""
        text_parts = []

        for text_elem in field_element.findall(".//w:t", self.namespaces):
            if text_elem.text:
                text_parts.append(text_elem.text)

        return "".join(text_parts)

    def _extract_complex_fields(self, document_root: ET.Element) -> List[Dict]:
        """Extract complex field information"""
        complex_fields = []

        # Find field characters that mark complex fields
        field_chars = document_root.findall(".//w:fldChar", self.namespaces)
        current_field = None

        for field_char in field_chars:
            field_type = field_char.get(f'{{{self.namespaces["w"]}}}fldCharType')

            if field_type == "begin":
                current_field = {
                    "type": "complex",
                    "instruction": "",
                    "text": "",
                    "properties": {},
                }
            elif field_type == "separate" and current_field:
                # Field instruction is complete, result follows
                pass
            elif field_type == "end" and current_field:
                # Field is complete
                complex_fields.append(current_field)
                current_field = None

        return complex_fields

    def _extract_content_control_info(self, cc_element: ET.Element) -> Optional[Dict]:
        """Extract content control information"""
        try:
            cc_props = cc_element.find(".//w:sdtPr", self.namespaces)
            if cc_props is None:
                return None

            cc_info = {"type": "content_control", "properties": {}, "content": ""}

            # Extract properties
            for prop in cc_props:
                prop_tag = prop.tag.split("}")[-1] if "}" in prop.tag else prop.tag
                if prop.attrib:
                    cc_info["properties"][prop_tag] = prop.attrib
                elif prop.text:
                    cc_info["properties"][prop_tag] = prop.text
                else:
                    cc_info["properties"][prop_tag] = True

            # Extract content
            cc_content = cc_element.find(".//w:sdtContent", self.namespaces)
            if cc_content is not None:
                content_text = []
                for text_elem in cc_content.findall(".//w:t", self.namespaces):
                    if text_elem.text:
                        content_text.append(text_elem.text)
                cc_info["content"] = "".join(content_text)

            return cc_info

        except Exception as e:
            logger.warning(f"Failed to extract content control info: {str(e)}")
            return None

    def extract_hyperlinks(self, docx_bytes: bytes) -> Dict[str, Any]:
        """Extract hyperlinks from Word document"""
        try:
            hyperlinks = []

            with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as docx_zip:
                # Load relationships to resolve hyperlink targets
                relationships = {}
                if "word/_rels/document.xml.rels" in docx_zip.namelist():
                    rels_content = docx_zip.read("word/_rels/document.xml.rels")
                    rels_root = safe_ET.fromstring(rels_content)

                    for rel in rels_root.findall(".//Relationship"):
                        rel_id = rel.get("Id")
                        target = rel.get("Target")
                        rel_type = rel.get("Type")

                        if rel_id and "hyperlink" in rel_type.lower():
                            relationships[rel_id] = target

                # Extract hyperlinks from document
                if "word/document.xml" in docx_zip.namelist():
                    document_content = docx_zip.read("word/document.xml")
                    document_root = safe_ET.fromstring(document_content)

                    # Find hyperlink elements
                    hyperlink_elements = document_root.findall(
                        ".//w:hyperlink", self.namespaces
                    )

                    for hyperlink in hyperlink_elements:
                        rel_id = hyperlink.get(f'{{{self.namespaces["r"]}}}id')
                        anchor = hyperlink.get(f'{{{self.namespaces["w"]}}}anchor')

                        # Get hyperlink text
                        link_text = self._get_field_text(hyperlink)

                        hyperlink_info = {
                            "text": link_text,
                            "target": relationships.get(rel_id) if rel_id else None,
                            "anchor": anchor,
                            "type": (
                                "external"
                                if rel_id and relationships.get(rel_id)
                                else "internal"
                            ),
                        }

                        hyperlinks.append(hyperlink_info)

            return {
                "success": True,
                "hyperlinks": hyperlinks,
                "link_count": len(hyperlinks),
            }

        except Exception as e:
            logger.error(f"Failed to extract hyperlinks: {str(e)}")
            return {"success": False, "error": str(e)}

    def analyze_xml_complexity(self, docx_bytes: bytes) -> Dict[str, Any]:
        """Analyze XML complexity of Word document"""
        try:
            xml_structure = self.extract_xml_structure(docx_bytes)

            if not xml_structure["success"]:
                return xml_structure

            complexity_analysis = {
                "overall_complexity": "low",
                "complexity_factors": [],
                "recommendations": [],
            }

            total_elements = 0
            max_depth = 0
            xml_file_count = len(xml_structure["xml_files"])

            for file_path, file_info in xml_structure["xml_files"].items():
                if "error" not in file_info:
                    total_elements += file_info["element_count"]
                    max_depth = max(max_depth, file_info["structure"]["depth"])

            # Calculate complexity score
            complexity_score = 0

            # Factor 1: Number of XML files
            if xml_file_count > 20:
                complexity_score += 3
                complexity_analysis["complexity_factors"].append(
                    "High number of XML files"
                )
            elif xml_file_count > 10:
                complexity_score += 1

            # Factor 2: Total elements
            if total_elements > 10000:
                complexity_score += 3
                complexity_analysis["complexity_factors"].append("High element count")
            elif total_elements > 5000:
                complexity_score += 2
            elif total_elements > 1000:
                complexity_score += 1

            # Factor 3: XML depth
            if max_depth > 20:
                complexity_score += 2
                complexity_analysis["complexity_factors"].append("Deep XML nesting")
            elif max_depth > 15:
                complexity_score += 1

            # Determine overall complexity
            if complexity_score >= 5:
                complexity_analysis["overall_complexity"] = "high"
                complexity_analysis["recommendations"].extend(
                    [
                        "Consider simplifying document structure",
                        "Review use of complex formatting",
                        "Consider breaking into smaller documents",
                    ]
                )
            elif complexity_score >= 3:
                complexity_analysis["overall_complexity"] = "medium"
                complexity_analysis["recommendations"].extend(
                    [
                        "Document has moderate complexity",
                        "Processing may require additional resources",
                    ]
                )
            else:
                complexity_analysis["overall_complexity"] = "low"
                complexity_analysis["recommendations"].append(
                    "Document has simple structure"
                )

            complexity_analysis.update(
                {
                    "complexity_score": complexity_score,
                    "xml_file_count": xml_file_count,
                    "total_elements": total_elements,
                    "max_depth": max_depth,
                }
            )

            return {"success": True, "analysis": complexity_analysis}

        except Exception as e:
            logger.error(f"Failed to analyze XML complexity: {str(e)}")
            return {"success": False, "error": str(e)}
