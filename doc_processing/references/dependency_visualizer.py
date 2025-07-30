"""Dependency visualization for document references."""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .reference_scanner import ReferenceScanner
from .uri_system import DocumentReference, URISystem

logger = logging.getLogger(__name__)


@dataclass
class DependencyNode:
    """Represents a node in the dependency graph."""

    node_id: str
    document_path: str
    document_type: str  # document, template, external
    title: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)


@dataclass
class DependencyEdge:
    """Represents an edge in the dependency graph."""

    edge_id: str
    source_node: str
    target_node: str
    reference_type: str  # explicit, implicit, citation
    reference_count: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)


@dataclass
class DependencyAlert:
    """Alert for dependency changes."""

    alert_id: str
    alert_type: str  # broken_reference, circular_dependency, orphaned_document
    severity: str  # high, medium, low
    source_document: str
    target_document: Optional[str] = None
    description: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    resolved: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


class DependencyVisualizer:
    """Visualizes document dependencies and generates alerts."""

    def __init__(
        self,
        uri_system: Optional[URISystem] = None,
        scanner: Optional[ReferenceScanner] = None,
    ):
        """Initialize dependency visualizer.

        Args:
            uri_system: Optional URISystem instance
            scanner: Optional ReferenceScanner instance
        """
        self.uri_system = uri_system or URISystem()
        self.scanner = scanner or ReferenceScanner(self.uri_system)
        self.nodes: Dict[str, DependencyNode] = {}
        self.edges: Dict[str, DependencyEdge] = {}
        self.alerts: List[DependencyAlert] = []

    def build_dependency_graph(self, repo_path: Path) -> Dict[str, Any]:
        """Build complete dependency graph for repository.

        Args:
            repo_path: Path to repository

        Returns:
            Graph data for visualization
        """
        logger.info(f"Building dependency graph for {repo_path}")

        # Clear existing data
        self.nodes.clear()
        self.edges.clear()
        self.alerts.clear()

        # Scan repository for references
        all_refs = self.scanner.scan_repository(repo_path)

        # Build nodes
        self._build_nodes(repo_path, all_refs)

        # Build edges
        self._build_edges(all_refs)

        # Detect issues
        self._detect_circular_dependencies()
        self._detect_orphaned_documents()
        self._detect_broken_references()

        # Generate visualization data
        return self._generate_visualization_data()

    def get_document_impact_map(self, document_path: str) -> Dict[str, Any]:
        """Get impact map for a specific document.

        Args:
            document_path: Path to document

        Returns:
            Impact visualization data
        """
        # Get direct dependencies
        dependencies = self.uri_system.get_document_dependencies(document_path)
        dependents = self.uri_system.get_document_dependents(document_path)

        # Build impact levels
        impact_levels = {
            "direct_dependencies": list(dependencies.keys()),
            "direct_dependents": list(dependents.keys()),
            "indirect_dependencies": set(),
            "indirect_dependents": set(),
        }

        # Find indirect dependencies (2 levels deep)
        for dep in dependencies.keys():
            indirect_deps = self.uri_system.get_document_dependencies(dep)
            impact_levels["indirect_dependencies"].update(indirect_deps.keys())

        for dep in dependents.keys():
            indirect_deps = self.uri_system.get_document_dependents(dep)
            impact_levels["indirect_dependents"].update(indirect_deps.keys())

        # Convert sets to lists
        impact_levels["indirect_dependencies"] = list(
            impact_levels["indirect_dependencies"]
        )
        impact_levels["indirect_dependents"] = list(
            impact_levels["indirect_dependents"]
        )

        # Calculate impact score
        impact_score = (
            len(impact_levels["direct_dependents"]) * 10
            + len(impact_levels["indirect_dependents"]) * 5
            + len(impact_levels["direct_dependencies"]) * 3
            + len(impact_levels["indirect_dependencies"]) * 1
        )

        return {
            "document": document_path,
            "impact_levels": impact_levels,
            "impact_score": impact_score,
            "risk_level": self._calculate_risk_level(impact_score),
            "recommendations": self._generate_impact_recommendations(impact_levels),
        }

    def generate_change_alerts(
        self, document_path: str, old_content: str, new_content: str
    ) -> List[DependencyAlert]:
        """Generate alerts for document changes.

        Args:
            document_path: Path to changed document
            old_content: Previous content
            new_content: New content

        Returns:
            List of alerts
        """
        alerts = []

        # Analyze impact
        impact_report = self.scanner.analyze_change_impact(
            document_path, old_content, new_content
        )

        # Generate alerts based on impact
        for impact in impact_report.impacts:
            if impact.severity == "high":
                for ref in impact.affected_references:
                    alert = DependencyAlert(
                        alert_id=self._generate_alert_id(),
                        alert_type="broken_reference",
                        severity="high",
                        source_document=ref.source_document,
                        target_document=document_path,
                        description=f"High severity change: {impact.description}",
                    )
                    alerts.append(alert)

            elif impact.severity == "medium" and len(impact.affected_references) > 3:
                alert = DependencyAlert(
                    alert_id=self._generate_alert_id(),
                    alert_type="multiple_references_affected",
                    severity="medium",
                    source_document=document_path,
                    description=f"{len(impact.affected_references)} references affected by changes",
                )
                alerts.append(alert)

        # Check for substantial changes
        if len(impact_report.affected_documents) > 5:
            alert = DependencyAlert(
                alert_id=self._generate_alert_id(),
                alert_type="widespread_impact",
                severity="high",
                source_document=document_path,
                description=f"Changes affect {len(impact_report.affected_documents)} documents",
            )
            alerts.append(alert)

        # Store alerts
        self.alerts.extend(alerts)

        return alerts

    def export_graph_data(self, format: str = "json") -> str:
        """Export graph data in specified format.

        Args:
            format: Export format (json, dot, mermaid)

        Returns:
            Exported data string
        """
        if format == "json":
            return self._export_json()
        elif format == "dot":
            return self._export_dot()
        elif format == "mermaid":
            return self._export_mermaid()
        else:
            raise ValueError(f"Unsupported format: {format}")

    def _build_nodes(
        self, repo_path: Path, all_refs: Dict[str, List[DocumentReference]]
    ):
        """Build nodes from repository scan."""
        # Add nodes for all documents with references
        for doc_path in all_refs.keys():
            node_id = self._path_to_node_id(doc_path)

            node = DependencyNode(
                node_id=node_id,
                document_path=doc_path,
                document_type=self._determine_doc_type(doc_path),
                title=Path(doc_path).stem,
                metadata={
                    "references_count": len(all_refs[doc_path]),
                    "last_scanned": datetime.now().isoformat(),
                },
            )

            self.nodes[node_id] = node

        # Add nodes for referenced documents
        for refs in all_refs.values():
            for ref in refs:
                target = self._get_target_from_ref(ref)
                if target:
                    node_id = self._path_to_node_id(target)

                    if node_id not in self.nodes:
                        node = DependencyNode(
                            node_id=node_id,
                            document_path=target,
                            document_type=self._determine_doc_type(target),
                            title=Path(target).stem,
                        )
                        self.nodes[node_id] = node

    def _build_edges(self, all_refs: Dict[str, List[DocumentReference]]):
        """Build edges from references."""
        edge_counts = {}

        for doc_path, refs in all_refs.items():
            source_id = self._path_to_node_id(doc_path)

            for ref in refs:
                target = self._get_target_from_ref(ref)
                if target and target != doc_path:
                    target_id = self._path_to_node_id(target)

                    # Track edge counts
                    edge_key = (source_id, target_id, ref.reference_type)
                    if edge_key in edge_counts:
                        edge_counts[edge_key] += 1
                    else:
                        edge_counts[edge_key] = 1

        # Create edges
        for (source, target, ref_type), count in edge_counts.items():
            edge_id = f"{source}->{target}"

            edge = DependencyEdge(
                edge_id=edge_id,
                source_node=source,
                target_node=target,
                reference_type=ref_type,
                reference_count=count,
            )

            self.edges[edge_id] = edge

    def _detect_circular_dependencies(self):
        """Detect circular dependencies in the graph."""
        # Build adjacency list
        graph = {}
        for edge in self.edges.values():
            if edge.source_node not in graph:
                graph[edge.source_node] = []
            graph[edge.source_node].append(edge.target_node)

        # DFS to detect cycles
        visited = set()
        rec_stack = set()

        def has_cycle(node: str, path: List[str]) -> Optional[List[str]]:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            if node in graph:
                for neighbor in graph[node]:
                    if neighbor not in visited:
                        cycle = has_cycle(neighbor, path.copy())
                        if cycle:
                            return cycle
                    elif neighbor in rec_stack:
                        # Found cycle
                        cycle_start = path.index(neighbor)
                        return path[cycle_start:] + [neighbor]

            rec_stack.remove(node)
            return None

        # Check all nodes
        for node in self.nodes:
            if node not in visited:
                cycle = has_cycle(node, [])
                if cycle:
                    alert = DependencyAlert(
                        alert_id=self._generate_alert_id(),
                        alert_type="circular_dependency",
                        severity="high",
                        source_document=self.nodes[cycle[0]].document_path,
                        description=f"Circular dependency detected: {' -> '.join(cycle)}",
                    )
                    self.alerts.append(alert)

    def _detect_orphaned_documents(self):
        """Detect documents with no incoming or outgoing references."""
        # Find nodes with no edges
        connected_nodes = set()

        for edge in self.edges.values():
            connected_nodes.add(edge.source_node)
            connected_nodes.add(edge.target_node)

        # Check for orphans
        for node_id, node in self.nodes.items():
            if node_id not in connected_nodes:
                alert = DependencyAlert(
                    alert_id=self._generate_alert_id(),
                    alert_type="orphaned_document",
                    severity="low",
                    source_document=node.document_path,
                    description="Document has no references to or from other documents",
                )
                self.alerts.append(alert)

    def _detect_broken_references(self):
        """Detect references to non-existent documents."""
        # Check all edges
        for edge in self.edges.values():
            if edge.target_node not in self.nodes:
                source_doc = self.nodes[edge.source_node].document_path

                alert = DependencyAlert(
                    alert_id=self._generate_alert_id(),
                    alert_type="broken_reference",
                    severity="high",
                    source_document=source_doc,
                    description=f"Reference to non-existent document: {edge.target_node}",
                )
                self.alerts.append(alert)

    def _generate_visualization_data(self) -> Dict[str, Any]:
        """Generate data for visualization."""
        return {
            "nodes": [node.to_dict() for node in self.nodes.values()],
            "edges": [edge.to_dict() for edge in self.edges.values()],
            "alerts": [alert.to_dict() for alert in self.alerts],
            "statistics": {
                "total_documents": len(self.nodes),
                "total_references": len(self.edges),
                "total_alerts": len(self.alerts),
                "high_severity_alerts": sum(
                    1 for a in self.alerts if a.severity == "high"
                ),
                "circular_dependencies": sum(
                    1 for a in self.alerts if a.alert_type == "circular_dependency"
                ),
            },
        }

    def _export_json(self) -> str:
        """Export graph as JSON."""
        data = self._generate_visualization_data()
        return json.dumps(data, indent=2)

    def _export_dot(self) -> str:
        """Export graph as DOT format for Graphviz."""
        lines = ["digraph DocumentDependencies {"]
        lines.append("  rankdir=LR;")
        lines.append("  node [shape=box];")

        # Add nodes
        for node in self.nodes.values():
            color = {
                "template": "lightblue",
                "document": "lightgreen",
                "external": "lightgray",
            }.get(node.document_type, "white")

            lines.append(
                f'  "{node.node_id}" [label="{node.title}", fillcolor={color}, style=filled];'
            )

        # Add edges
        for edge in self.edges.values():
            style = "dashed" if edge.reference_type == "implicit" else "solid"
            label = f"{edge.reference_count}" if edge.reference_count > 1 else ""

            lines.append(
                f'  "{edge.source_node}" -> "{edge.target_node}" [style={style}, label="{label}"];'
            )

        lines.append("}")
        return "\n".join(lines)

    def _export_mermaid(self) -> str:
        """Export graph as Mermaid format."""
        lines = ["graph LR"]

        # Add nodes
        for node in self.nodes.values():
            shape = {"template": "((", "document": "[", "external": "{{"}.get(
                node.document_type, "["
            )

            close_shape = {"template": "))", "document": "]", "external": "}}"}.get(
                node.document_type, "]"
            )

            lines.append(f'    {node.node_id}{shape}"{node.title}"{close_shape}')

        # Add edges
        for edge in self.edges.values():
            arrow = "-->" if edge.reference_type == "explicit" else "-.->"
            label = f"|{edge.reference_count}|" if edge.reference_count > 1 else ""

            lines.append(f"    {edge.source_node} {arrow}{label} {edge.target_node}")

        return "\n".join(lines)

    def _calculate_risk_level(self, impact_score: int) -> str:
        """Calculate risk level from impact score."""
        if impact_score >= 50:
            return "high"
        elif impact_score >= 20:
            return "medium"
        else:
            return "low"

    def _generate_impact_recommendations(
        self, impact_levels: Dict[str, List[str]]
    ) -> List[str]:
        """Generate recommendations based on impact levels."""
        recommendations = []

        if len(impact_levels["direct_dependents"]) > 10:
            recommendations.append(
                "This document is heavily referenced. Consider creating a stable API "
                "or interface to minimize breaking changes."
            )

        if len(impact_levels["direct_dependencies"]) > 15:
            recommendations.append(
                "This document has many dependencies. Consider refactoring to reduce coupling."
            )

        if len(impact_levels["indirect_dependents"]) > 20:
            recommendations.append(
                "Changes to this document have far-reaching effects. "
                "Implement comprehensive testing before modifications."
            )

        return recommendations

    def _path_to_node_id(self, path: str) -> str:
        """Convert document path to node ID."""
        return path.replace("/", "_").replace(".", "_")

    def _determine_doc_type(self, path: str) -> str:
        """Determine document type from path."""
        if "template" in path.lower():
            return "template"
        elif path.startswith("http"):
            return "external"
        else:
            return "document"

    def _get_target_from_ref(self, ref: DocumentReference) -> Optional[str]:
        """Get target document from reference."""
        uri = ref.target_uri
        if uri.repository and uri.document:
            return f"{uri.repository}/{uri.document}"
        return None

    def _generate_alert_id(self) -> str:
        """Generate unique alert ID."""
        import uuid

        return str(uuid.uuid4())[:8]
