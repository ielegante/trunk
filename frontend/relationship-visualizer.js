// Legal Git Chrome Extension - Document Relationship Visualizer
// Handles interactive visualization of document relationships and reference networks

class RelationshipVisualizer {
  constructor(referenceManager, documentConverter) {
    this.referenceManager = referenceManager;
    this.documentConverter = documentConverter;
    this.visualizationData = new Map();
    this.activeVisualization = null;
    this.visualizerOpen = false;
    this.selectedNode = null;
    this.d3 = null; // Will be loaded dynamically
    this.init();
  }

  init() {
    this.setupVisualizerEventListeners();
    this.injectVisualizerStyles();
    this.loadD3Library();
  }

  // Setup event listeners
  setupVisualizerEventListeners() {
    window.addEventListener('showRelationshipGraph', (event) => {
      this.showVisualizationModal(event.detail);
    });

    window.addEventListener('updateRelationships', (event) => {
      this.updateVisualization(event.detail);
    });

    window.addEventListener('highlightRelationship', (event) => {
      this.highlightRelationship(event.detail);
    });
  }

  // Inject visualization styles
  injectVisualizerStyles() {
    const styleId = 'legal-git-visualizer-styles';
    if (document.getElementById(styleId)) return;

    const style = document.createElement('style');
    style.id = styleId;
    style.textContent = `
      .legal-git-viz-container {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.9);
        z-index: 28000;
        display: flex;
        align-items: center;
        justify-content: center;
        font-family: 'Google Sans', Roboto, Arial, sans-serif;
      }

      .legal-git-viz-modal {
        background: #1a1a1a;
        border-radius: 12px;
        box-shadow: 0 12px 40px rgba(0,0,0,0.6);
        width: 95vw;
        height: 90vh;
        max-width: 1800px;
        display: flex;
        flex-direction: column;
        overflow: hidden;
      }

      .legal-git-viz-header {
        padding: 20px 24px;
        border-bottom: 2px solid #2196f3;
        background: linear-gradient(135deg, #1e3c72, #2a5298);
        display: flex;
        justify-content: space-between;
        align-items: center;
        color: white;
      }

      .legal-git-viz-title {
        font-size: 20px;
        font-weight: 600;
        display: flex;
        align-items: center;
        gap: 12px;
      }

      .legal-git-viz-controls {
        display: flex;
        gap: 12px;
        align-items: center;
      }

      .legal-git-viz-control-btn {
        background: rgba(255, 255, 255, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.3);
        color: white;
        padding: 8px 16px;
        border-radius: 6px;
        font-size: 14px;
        cursor: pointer;
        transition: all 0.2s ease;
        display: flex;
        align-items: center;
        gap: 6px;
      }

      .legal-git-viz-control-btn:hover {
        background: rgba(255, 255, 255, 0.2);
        transform: translateY(-1px);
      }

      .legal-git-viz-control-btn.active {
        background: #2196f3;
        border-color: #2196f3;
      }

      .legal-git-viz-close {
        background: none;
        border: none;
        color: white;
        font-size: 28px;
        cursor: pointer;
        padding: 8px;
        border-radius: 50%;
        transition: all 0.2s ease;
      }

      .legal-git-viz-close:hover {
        background: rgba(255, 255, 255, 0.1);
      }

      .legal-git-viz-content {
        display: flex;
        flex: 1;
        overflow: hidden;
      }

      .legal-git-viz-sidebar {
        width: 320px;
        background: #2a2a2a;
        border-right: 1px solid #444;
        display: flex;
        flex-direction: column;
        color: white;
      }

      .legal-git-viz-sidebar-section {
        padding: 20px;
        border-bottom: 1px solid #444;
      }

      .legal-git-viz-sidebar-title {
        font-size: 14px;
        font-weight: 600;
        text-transform: uppercase;
        color: #888;
        margin-bottom: 12px;
      }

      .legal-git-viz-main {
        flex: 1;
        position: relative;
        background: #1a1a1a;
        overflow: hidden;
      }

      .legal-git-viz-svg {
        width: 100%;
        height: 100%;
      }

      .legal-git-viz-node {
        cursor: pointer;
      }

      .legal-git-viz-node-circle {
        fill: #2196f3;
        stroke: #fff;
        stroke-width: 3;
        transition: all 0.3s ease;
      }

      .legal-git-viz-node-circle:hover {
        fill: #1976d2;
        stroke-width: 4;
      }

      .legal-git-viz-node-circle.selected {
        fill: #ff5722;
        stroke: #ffeb3b;
        stroke-width: 4;
      }

      .legal-git-viz-node-circle.current {
        fill: #4caf50;
      }

      .legal-git-viz-node-circle.broken {
        fill: #f44336;
      }

      .legal-git-viz-node-label {
        fill: white;
        text-anchor: middle;
        font-size: 12px;
        pointer-events: none;
        text-shadow: 0 0 3px rgba(0,0,0,0.8);
      }

      .legal-git-viz-link {
        fill: none;
        stroke: #666;
        stroke-width: 2;
        opacity: 0.6;
        transition: all 0.3s ease;
      }

      .legal-git-viz-link.valid {
        stroke: #4caf50;
      }

      .legal-git-viz-link.broken {
        stroke: #f44336;
        stroke-dasharray: 5, 5;
      }

      .legal-git-viz-link.highlighted {
        stroke: #ffeb3b;
        stroke-width: 4;
        opacity: 1;
      }

      .legal-git-viz-link-label {
        fill: white;
        font-size: 10px;
        text-anchor: middle;
        opacity: 0;
        transition: opacity 0.3s ease;
      }

      .legal-git-viz-link:hover + .legal-git-viz-link-label {
        opacity: 1;
      }

      .legal-git-viz-legend {
        position: absolute;
        bottom: 20px;
        left: 20px;
        background: rgba(42, 42, 42, 0.9);
        border: 1px solid #444;
        border-radius: 8px;
        padding: 16px;
        color: white;
      }

      .legal-git-viz-legend-title {
        font-size: 14px;
        font-weight: 600;
        margin-bottom: 8px;
      }

      .legal-git-viz-legend-item {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 6px;
        font-size: 12px;
      }

      .legal-git-viz-legend-color {
        width: 16px;
        height: 16px;
        border-radius: 50%;
        border: 2px solid white;
      }

      .legal-git-viz-info-panel {
        position: absolute;
        top: 20px;
        right: 20px;
        background: rgba(42, 42, 42, 0.95);
        border: 1px solid #444;
        border-radius: 8px;
        padding: 20px;
        color: white;
        min-width: 300px;
        max-width: 400px;
        display: none;
      }

      .legal-git-viz-info-panel.visible {
        display: block;
      }

      .legal-git-viz-info-title {
        font-size: 16px;
        font-weight: 600;
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        gap: 8px;
      }

      .legal-git-viz-info-content {
        font-size: 14px;
        line-height: 1.6;
      }

      .legal-git-viz-info-stat {
        display: flex;
        justify-content: space-between;
        padding: 8px 0;
        border-bottom: 1px solid #444;
      }

      .legal-git-viz-info-stat:last-child {
        border-bottom: none;
      }

      .legal-git-viz-zoom-controls {
        position: absolute;
        bottom: 20px;
        right: 20px;
        background: rgba(42, 42, 42, 0.9);
        border: 1px solid #444;
        border-radius: 8px;
        padding: 8px;
        display: flex;
        flex-direction: column;
        gap: 4px;
      }

      .legal-git-viz-zoom-btn {
        background: rgba(255, 255, 255, 0.1);
        border: 1px solid #666;
        color: white;
        width: 36px;
        height: 36px;
        border-radius: 4px;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 18px;
        transition: all 0.2s ease;
      }

      .legal-git-viz-zoom-btn:hover {
        background: rgba(255, 255, 255, 0.2);
      }

      .legal-git-viz-filter-section {
        padding: 16px;
      }

      .legal-git-viz-filter-input {
        width: 100%;
        padding: 10px 14px;
        background: #1a1a1a;
        border: 1px solid #444;
        border-radius: 6px;
        color: white;
        font-size: 14px;
        margin-bottom: 12px;
      }

      .legal-git-viz-filter-input:focus {
        outline: none;
        border-color: #2196f3;
      }

      .legal-git-viz-filter-options {
        display: flex;
        flex-direction: column;
        gap: 8px;
      }

      .legal-git-viz-filter-option {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px;
        border-radius: 4px;
        cursor: pointer;
        transition: all 0.2s ease;
      }

      .legal-git-viz-filter-option:hover {
        background: rgba(255, 255, 255, 0.1);
      }

      .legal-git-viz-filter-checkbox {
        width: 16px;
        height: 16px;
      }

      .legal-git-viz-stats-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 12px;
      }

      .legal-git-viz-stat-card {
        background: #1a1a1a;
        border: 1px solid #444;
        border-radius: 6px;
        padding: 12px;
        text-align: center;
      }

      .legal-git-viz-stat-value {
        font-size: 24px;
        font-weight: 600;
        color: #2196f3;
        margin-bottom: 4px;
      }

      .legal-git-viz-stat-label {
        font-size: 12px;
        color: #888;
        text-transform: uppercase;
      }

      .legal-git-viz-tooltip {
        position: absolute;
        background: rgba(42, 42, 42, 0.95);
        border: 1px solid #666;
        border-radius: 6px;
        padding: 12px;
        color: white;
        font-size: 14px;
        pointer-events: none;
        opacity: 0;
        transition: opacity 0.2s ease;
        z-index: 1000;
      }

      .legal-git-viz-tooltip.visible {
        opacity: 1;
      }

      .legal-git-viz-minimap {
        position: absolute;
        top: 20px;
        left: 20px;
        width: 200px;
        height: 150px;
        background: rgba(42, 42, 42, 0.9);
        border: 1px solid #666;
        border-radius: 8px;
        overflow: hidden;
      }

      .legal-git-viz-minimap-viewport {
        position: absolute;
        border: 2px solid #2196f3;
        background: rgba(33, 150, 243, 0.2);
        pointer-events: none;
      }
    `;
    document.head.appendChild(style);
  }

  // Load D3.js library dynamically
  loadD3Library() {
    if (window.d3) {
      this.d3 = window.d3;
      return;
    }

    const script = document.createElement('script');
    script.src = 'https://d3js.org/d3.v7.min.js';
    script.onload = () => {
      this.d3 = window.d3;
      console.log('D3.js loaded successfully');
    };
    document.head.appendChild(script);
  }

  // Show visualization modal
  showVisualizationModal(options = {}) {
    if (this.visualizerOpen) return;

    const modalHtml = `
      <div class="legal-git-viz-container">
        <div class="legal-git-viz-modal">
          <div class="legal-git-viz-header">
            <div class="legal-git-viz-title">
              <span>🕸️</span>
              <span>Document Relationship Network</span>
            </div>
            <div class="legal-git-viz-controls">
              <button class="legal-git-viz-control-btn" id="viz-layout-force">
                <span>⚡</span>
                <span>Force Layout</span>
              </button>
              <button class="legal-git-viz-control-btn" id="viz-layout-tree">
                <span>🌳</span>
                <span>Tree Layout</span>
              </button>
              <button class="legal-git-viz-control-btn" id="viz-layout-radial">
                <span>☀️</span>
                <span>Radial Layout</span>
              </button>
              <button class="legal-git-viz-control-btn" id="viz-fullscreen">
                <span>⛶</span>
              </button>
            </div>
            <button class="legal-git-viz-close">&times;</button>
          </div>

          <div class="legal-git-viz-content">
            <div class="legal-git-viz-sidebar">
              <div class="legal-git-viz-sidebar-section">
                <div class="legal-git-viz-sidebar-title">Statistics</div>
                <div class="legal-git-viz-stats-grid">
                  <div class="legal-git-viz-stat-card">
                    <div class="legal-git-viz-stat-value" id="stat-documents">0</div>
                    <div class="legal-git-viz-stat-label">Documents</div>
                  </div>
                  <div class="legal-git-viz-stat-card">
                    <div class="legal-git-viz-stat-value" id="stat-references">0</div>
                    <div class="legal-git-viz-stat-label">References</div>
                  </div>
                  <div class="legal-git-viz-stat-card">
                    <div class="legal-git-viz-stat-value" id="stat-valid">0</div>
                    <div class="legal-git-viz-stat-label">Valid Links</div>
                  </div>
                  <div class="legal-git-viz-stat-card">
                    <div class="legal-git-viz-stat-value" id="stat-broken">0</div>
                    <div class="legal-git-viz-stat-label">Broken Links</div>
                  </div>
                </div>
              </div>

              <div class="legal-git-viz-sidebar-section">
                <div class="legal-git-viz-sidebar-title">Filters</div>
                <div class="legal-git-viz-filter-section">
                  <input type="text" class="legal-git-viz-filter-input" placeholder="Search documents...">
                  <div class="legal-git-viz-filter-options">
                    <label class="legal-git-viz-filter-option">
                      <input type="checkbox" class="legal-git-viz-filter-checkbox" id="filter-valid" checked>
                      <span>Show Valid References</span>
                    </label>
                    <label class="legal-git-viz-filter-option">
                      <input type="checkbox" class="legal-git-viz-filter-checkbox" id="filter-broken" checked>
                      <span>Show Broken References</span>
                    </label>
                    <label class="legal-git-viz-filter-option">
                      <input type="checkbox" class="legal-git-viz-filter-checkbox" id="filter-case" checked>
                      <span>Case Citations</span>
                    </label>
                    <label class="legal-git-viz-filter-option">
                      <input type="checkbox" class="legal-git-viz-filter-checkbox" id="filter-statute" checked>
                      <span>Statutes</span>
                    </label>
                    <label class="legal-git-viz-filter-option">
                      <input type="checkbox" class="legal-git-viz-filter-checkbox" id="filter-contract" checked>
                      <span>Contract Clauses</span>
                    </label>
                  </div>
                </div>
              </div>

              <div class="legal-git-viz-sidebar-section">
                <div class="legal-git-viz-sidebar-title">Selected Document</div>
                <div id="selected-document-info" style="color: #888;">
                  No document selected
                </div>
              </div>
            </div>

            <div class="legal-git-viz-main">
              <svg class="legal-git-viz-svg" id="relationship-svg"></svg>

              <div class="legal-git-viz-legend">
                <div class="legal-git-viz-legend-title">Legend</div>
                <div class="legal-git-viz-legend-item">
                  <div class="legal-git-viz-legend-color" style="background: #4caf50;"></div>
                  <span>Current Document</span>
                </div>
                <div class="legal-git-viz-legend-item">
                  <div class="legal-git-viz-legend-color" style="background: #2196f3;"></div>
                  <span>Referenced Document</span>
                </div>
                <div class="legal-git-viz-legend-item">
                  <div class="legal-git-viz-legend-color" style="background: #f44336;"></div>
                  <span>Broken Reference</span>
                </div>
                <div class="legal-git-viz-legend-item">
                  <svg width="40" height="16">
                    <line x1="0" y1="8" x2="40" y2="8" stroke="#4caf50" stroke-width="2"/>
                  </svg>
                  <span>Valid Link</span>
                </div>
                <div class="legal-git-viz-legend-item">
                  <svg width="40" height="16">
                    <line x1="0" y1="8" x2="40" y2="8" stroke="#f44336" stroke-width="2" stroke-dasharray="5,5"/>
                  </svg>
                  <span>Broken Link</span>
                </div>
              </div>

              <div class="legal-git-viz-zoom-controls">
                <button class="legal-git-viz-zoom-btn" id="zoom-in">+</button>
                <button class="legal-git-viz-zoom-btn" id="zoom-reset">⟲</button>
                <button class="legal-git-viz-zoom-btn" id="zoom-out">−</button>
              </div>

              <div class="legal-git-viz-info-panel" id="info-panel">
                <div class="legal-git-viz-info-title">
                  <span>📄</span>
                  <span id="info-title">Document Details</span>
                </div>
                <div class="legal-git-viz-info-content" id="info-content">
                  <!-- Dynamic content -->
                </div>
              </div>

              <div class="legal-git-viz-minimap">
                <svg id="minimap-svg" width="200" height="150"></svg>
                <div class="legal-git-viz-minimap-viewport"></div>
              </div>

              <div class="legal-git-viz-tooltip" id="viz-tooltip"></div>
            </div>
          </div>
        </div>
      </div>
    `;

    const modalElement = document.createElement('div');
    modalElement.innerHTML = modalHtml;
    document.body.appendChild(modalElement);

    this.visualizerOpen = true;
    this.attachVisualizerEventListeners();

    // Wait for D3 to load then initialize visualization
    this.waitForD3(() => {
      this.initializeVisualization(options);
    });
  }

  // Wait for D3 to load
  waitForD3(callback) {
    if (this.d3) {
      callback();
    } else {
      setTimeout(() => this.waitForD3(callback), 100);
    }
  }

  // Initialize visualization
  initializeVisualization(options) {
    const { documentId, layout = 'force' } = options;

    // Get visualization data
    const data = this.prepareVisualizationData(documentId);

    // Update statistics
    this.updateStatistics(data);

    // Create visualization based on layout
    switch (layout) {
      case 'tree':
        this.createTreeLayout(data);
        break;
      case 'radial':
        this.createRadialLayout(data);
        break;
      default:
        this.createForceLayout(data);
    }

    // Create minimap
    this.createMinimap(data);
  }

  // Prepare visualization data
  prepareVisualizationData(documentId) {
    const nodes = [];
    const links = [];
    const nodeMap = new Map();

    // Get all documents and references
    const references = this.referenceManager.documentReferences;
    const graph = this.referenceManager.referenceGraph;

    // Create nodes for all documents
    let nodeId = 0;
    for (const [docId, docRefs] of references) {
      const node = {
        id: nodeId++,
        docId: docId,
        name: this.getDocumentName(docId),
        type: docId === documentId ? 'current' : 'referenced',
        referenceCount: docRefs.length,
        brokenCount: docRefs.filter(r => !r.valid).length
      };

      nodes.push(node);
      nodeMap.set(docId, node);
    }

    // Create links from reference graph
    for (const [sourceDocId, edges] of graph) {
      const sourceNode = nodeMap.get(sourceDocId);
      if (!sourceNode) continue;

      edges.forEach(edge => {
        const targetNode = nodeMap.get(edge.target);
        if (targetNode) {
          links.push({
            source: sourceNode.id,
            target: targetNode.id,
            type: edge.type,
            valid: edge.valid
          });
        }
      });
    }

    return { nodes, links };
  }

  // Create force-directed layout
  createForceLayout(data) {
    const svg = this.d3.select('#relationship-svg');
    const width = svg.node().getBoundingClientRect().width;
    const height = svg.node().getBoundingClientRect().height;

    // Clear previous content
    svg.selectAll('*').remove();

    // Create zoom behavior
    const zoom = this.d3.zoom()
      .scaleExtent([0.1, 10])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
        this.updateMinimap(event.transform);
      });

    svg.call(zoom);

    // Create main group
    const g = svg.append('g');

    // Create simulation
    const simulation = this.d3.forceSimulation(data.nodes)
      .force('link', this.d3.forceLink(data.links).id(d => d.id).distance(150))
      .force('charge', this.d3.forceManyBody().strength(-300))
      .force('center', this.d3.forceCenter(width / 2, height / 2))
      .force('collision', this.d3.forceCollide().radius(50));

    // Create links
    const link = g.append('g')
      .selectAll('line')
      .data(data.links)
      .join('line')
      .attr('class', d => `legal-git-viz-link ${d.valid ? 'valid' : 'broken'}`)
      .on('mouseover', (event, d) => this.showLinkTooltip(event, d))
      .on('mouseout', () => this.hideTooltip());

    // Create nodes
    const node = g.append('g')
      .selectAll('g')
      .data(data.nodes)
      .join('g')
      .attr('class', 'legal-git-viz-node')
      .call(this.d3.drag()
        .on('start', (event, d) => this.dragStarted(event, d, simulation))
        .on('drag', (event, d) => this.dragged(event, d))
        .on('end', (event, d) => this.dragEnded(event, d, simulation)));

    // Add circles
    node.append('circle')
      .attr('class', d => {
        let classes = 'legal-git-viz-node-circle';
        if (d.type === 'current') classes += ' current';
        if (d.brokenCount > 0) classes += ' broken';
        return classes;
      })
      .attr('r', d => 20 + Math.sqrt(d.referenceCount) * 5)
      .on('click', (event, d) => this.selectNode(d))
      .on('mouseover', (event, d) => this.showNodeTooltip(event, d))
      .on('mouseout', () => this.hideTooltip());

    // Add labels
    node.append('text')
      .attr('class', 'legal-git-viz-node-label')
      .attr('dy', '0.3em')
      .text(d => d.name.substring(0, 20) + (d.name.length > 20 ? '...' : ''));

    // Update positions on tick
    simulation.on('tick', () => {
      link
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y);

      node.attr('transform', d => `translate(${d.x},${d.y})`);
    });

    // Store references
    this.activeVisualization = {
      simulation,
      nodes: node,
      links: link,
      zoom,
      g
    };

    // Setup zoom controls
    this.setupZoomControls(zoom, g);
  }

  // Create tree layout
  createTreeLayout(data) {
    const svg = this.d3.select('#relationship-svg');
    const width = svg.node().getBoundingClientRect().width;
    const height = svg.node().getBoundingClientRect().height;

    // Clear previous content
    svg.selectAll('*').remove();

    // Convert to hierarchical data
    const root = this.createHierarchy(data);

    // Create tree layout
    const treeLayout = this.d3.tree()
      .size([width - 100, height - 100]);

    const treeData = treeLayout(root);

    // Create zoom behavior
    const zoom = this.d3.zoom()
      .scaleExtent([0.1, 10])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
        this.updateMinimap(event.transform);
      });

    svg.call(zoom);

    // Create main group
    const g = svg.append('g')
      .attr('transform', 'translate(50, 50)');

    // Create links
    const link = g.append('g')
      .selectAll('path')
      .data(treeData.links())
      .join('path')
      .attr('class', 'legal-git-viz-link')
      .attr('d', this.d3.linkVertical()
        .x(d => d.x)
        .y(d => d.y));

    // Create nodes
    const node = g.append('g')
      .selectAll('g')
      .data(treeData.descendants())
      .join('g')
      .attr('class', 'legal-git-viz-node')
      .attr('transform', d => `translate(${d.x},${d.y})`);

    // Add circles
    node.append('circle')
      .attr('class', d => {
        let classes = 'legal-git-viz-node-circle';
        if (d.data.type === 'current') classes += ' current';
        if (d.data.brokenCount > 0) classes += ' broken';
        return classes;
      })
      .attr('r', d => 15 + Math.sqrt(d.data.referenceCount || 0) * 3)
      .on('click', (event, d) => this.selectNode(d.data))
      .on('mouseover', (event, d) => this.showNodeTooltip(event, d.data))
      .on('mouseout', () => this.hideTooltip());

    // Add labels
    node.append('text')
      .attr('class', 'legal-git-viz-node-label')
      .attr('dy', '0.3em')
      .attr('x', d => d.children ? -10 : 10)
      .style('text-anchor', d => d.children ? 'end' : 'start')
      .text(d => d.data.name);

    // Store references
    this.activeVisualization = {
      nodes: node,
      links: link,
      zoom,
      g
    };

    // Setup zoom controls
    this.setupZoomControls(zoom, g);
  }

  // Create radial layout
  createRadialLayout(data) {
    const svg = this.d3.select('#relationship-svg');
    const width = svg.node().getBoundingClientRect().width;
    const height = svg.node().getBoundingClientRect().height;
    const radius = Math.min(width, height) / 2 - 100;

    // Clear previous content
    svg.selectAll('*').remove();

    // Create zoom behavior
    const zoom = this.d3.zoom()
      .scaleExtent([0.1, 10])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
        this.updateMinimap(event.transform);
      });

    svg.call(zoom);

    // Create main group
    const g = svg.append('g')
      .attr('transform', `translate(${width / 2},${height / 2})`);

    // Position nodes in circle
    const angleStep = (2 * Math.PI) / data.nodes.length;
    data.nodes.forEach((node, i) => {
      const angle = i * angleStep;
      node.x = Math.cos(angle) * radius;
      node.y = Math.sin(angle) * radius;
    });

    // Create links
    const link = g.append('g')
      .selectAll('path')
      .data(data.links)
      .join('path')
      .attr('class', d => `legal-git-viz-link ${d.valid ? 'valid' : 'broken'}`)
      .attr('d', d => {
        const source = data.nodes[d.source];
        const target = data.nodes[d.target];
        return `M ${source.x} ${source.y} Q 0 0 ${target.x} ${target.y}`;
      })
      .on('mouseover', (event, d) => this.showLinkTooltip(event, d))
      .on('mouseout', () => this.hideTooltip());

    // Create nodes
    const node = g.append('g')
      .selectAll('g')
      .data(data.nodes)
      .join('g')
      .attr('class', 'legal-git-viz-node')
      .attr('transform', d => `translate(${d.x},${d.y})`);

    // Add circles
    node.append('circle')
      .attr('class', d => {
        let classes = 'legal-git-viz-node-circle';
        if (d.type === 'current') classes += ' current';
        if (d.brokenCount > 0) classes += ' broken';
        return classes;
      })
      .attr('r', d => 20 + Math.sqrt(d.referenceCount) * 5)
      .on('click', (event, d) => this.selectNode(d))
      .on('mouseover', (event, d) => this.showNodeTooltip(event, d))
      .on('mouseout', () => this.hideTooltip());

    // Add labels
    node.append('text')
      .attr('class', 'legal-git-viz-node-label')
      .attr('dy', '0.3em')
      .attr('transform', (d, i) => {
        const angle = i * angleStep;
        const rotate = angle > Math.PI ? angle * 180 / Math.PI + 180 : angle * 180 / Math.PI;
        return `rotate(${rotate})`;
      })
      .attr('text-anchor', (d, i) => {
        const angle = i * angleStep;
        return angle > Math.PI ? 'end' : 'start';
      })
      .attr('x', (d, i) => {
        const angle = i * angleStep;
        return angle > Math.PI ? -30 : 30;
      })
      .text(d => d.name);

    // Store references
    this.activeVisualization = {
      nodes: node,
      links: link,
      zoom,
      g
    };

    // Setup zoom controls
    this.setupZoomControls(zoom, g);
  }

  // Create hierarchy from flat data
  createHierarchy(data) {
    // Find root node (current document or most referenced)
    const rootNode = data.nodes.find(n => n.type === 'current') ||
                    data.nodes.reduce((max, n) => n.referenceCount > max.referenceCount ? n : max);

    // Build hierarchy
    const hierarchy = {
      ...rootNode,
      children: []
    };

    // Add children based on links
    const addChildren = (parent, visited = new Set()) => {
      visited.add(parent.id);

      data.links
        .filter(l => l.source === parent.id && !visited.has(l.target))
        .forEach(link => {
          const child = data.nodes.find(n => n.id === link.target);
          if (child) {
            const childWithChildren = {
              ...child,
              children: []
            };
            parent.children.push(childWithChildren);
            addChildren(childWithChildren, visited);
          }
        });
    };

    addChildren(hierarchy);

    return this.d3.hierarchy(hierarchy);
  }

  // Drag event handlers
  dragStarted(event, d, simulation) {
    if (!event.active) simulation.alphaTarget(0.3).restart();
    d.fx = d.x;
    d.fy = d.y;
  }

  dragged(event, d) {
    d.fx = event.x;
    d.fy = event.y;
  }

  dragEnded(event, d, simulation) {
    if (!event.active) simulation.alphaTarget(0);
    d.fx = null;
    d.fy = null;
  }

  // Select node
  selectNode(node) {
    // Update UI
    this.selectedNode = node;

    // Update node styles
    this.d3.selectAll('.legal-git-viz-node-circle')
      .classed('selected', d => d.id === node.id);

    // Show info panel
    this.showNodeInfo(node);

    // Update sidebar
    this.updateSelectedDocumentInfo(node);

    // Highlight connected links
    this.highlightConnections(node);
  }

  // Show node info panel
  showNodeInfo(node) {
    const infoPanel = document.getElementById('info-panel');
    const infoTitle = document.getElementById('info-title');
    const infoContent = document.getElementById('info-content');

    if (!infoPanel || !infoTitle || !infoContent) return;

    infoTitle.textContent = node.name;

    infoContent.innerHTML = `
      <div class="legal-git-viz-info-stat">
        <span>Document ID</span>
        <span>${node.docId}</span>
      </div>
      <div class="legal-git-viz-info-stat">
        <span>Total References</span>
        <span>${node.referenceCount}</span>
      </div>
      <div class="legal-git-viz-info-stat">
        <span>Valid References</span>
        <span>${node.referenceCount - node.brokenCount}</span>
      </div>
      <div class="legal-git-viz-info-stat">
        <span>Broken References</span>
        <span style="color: ${node.brokenCount > 0 ? '#f44336' : '#4caf50'};">${node.brokenCount}</span>
      </div>
      <div class="legal-git-viz-info-stat">
        <span>Document Type</span>
        <span>${node.type === 'current' ? 'Current Document' : 'Referenced Document'}</span>
      </div>
    `;

    infoPanel.classList.add('visible');
  }

  // Update selected document info in sidebar
  updateSelectedDocumentInfo(node) {
    const infoDiv = document.getElementById('selected-document-info');
    if (!infoDiv) return;

    const references = this.referenceManager.documentReferences.get(node.docId) || [];

    let html = `
      <div style="color: white;">
        <strong>${node.name}</strong>
        <div style="margin-top: 8px; font-size: 12px;">
          <div>References: ${references.length}</div>
          <div style="margin-top: 4px;">Types:</div>
          <ul style="margin: 4px 0 0 20px; padding: 0;">
    `;

    // Count reference types
    const typeCounts = new Map();
    references.forEach(ref => {
      const count = typeCounts.get(ref.type) || 0;
      typeCounts.set(ref.type, count + 1);
    });

    for (const [type, count] of typeCounts) {
      const typeConfig = this.referenceManager.referenceTypes.get(type);
      html += `<li>${typeConfig.displayName}: ${count}</li>`;
    }

    html += `
          </ul>
        </div>
      </div>
    `;

    infoDiv.innerHTML = html;
  }

  // Highlight connections for selected node
  highlightConnections(node) {
    // Reset all links
    this.d3.selectAll('.legal-git-viz-link')
      .classed('highlighted', false);

    // Highlight connected links
    this.d3.selectAll('.legal-git-viz-link')
      .classed('highlighted', d =>
        (d.source.id || d.source) === node.id ||
        (d.target.id || d.target) === node.id
      );
  }

  // Show node tooltip
  showNodeTooltip(event, node) {
    const tooltip = document.getElementById('viz-tooltip');
    if (!tooltip) return;

    tooltip.innerHTML = `
      <strong>${node.name}</strong><br>
      References: ${node.referenceCount}<br>
      ${node.brokenCount > 0 ? `<span style="color: #f44336;">Broken: ${node.brokenCount}</span>` : 'All references valid'}
    `;

    tooltip.style.left = (event.pageX + 10) + 'px';
    tooltip.style.top = (event.pageY - 10) + 'px';
    tooltip.classList.add('visible');
  }

  // Show link tooltip
  showLinkTooltip(event, link) {
    const tooltip = document.getElementById('viz-tooltip');
    if (!tooltip) return;

    const typeConfig = this.referenceManager.referenceTypes.get(link.type);

    tooltip.innerHTML = `
      <strong>Reference Type:</strong> ${typeConfig ? typeConfig.displayName : 'Unknown'}<br>
      <strong>Status:</strong> ${link.valid ? 'Valid' : 'Broken'}
    `;

    tooltip.style.left = (event.pageX + 10) + 'px';
    tooltip.style.top = (event.pageY - 10) + 'px';
    tooltip.classList.add('visible');
  }

  // Hide tooltip
  hideTooltip() {
    const tooltip = document.getElementById('viz-tooltip');
    if (tooltip) {
      tooltip.classList.remove('visible');
    }
  }

  // Setup zoom controls
  setupZoomControls(zoom, g) {
    document.getElementById('zoom-in')?.addEventListener('click', () => {
      zoom.scaleBy(this.d3.select('#relationship-svg').transition().duration(300), 1.3);
    });

    document.getElementById('zoom-out')?.addEventListener('click', () => {
      zoom.scaleBy(this.d3.select('#relationship-svg').transition().duration(300), 0.7);
    });

    document.getElementById('zoom-reset')?.addEventListener('click', () => {
      this.d3.select('#relationship-svg').transition().duration(300)
        .call(zoom.transform, this.d3.zoomIdentity);
    });
  }

  // Create minimap
  createMinimap(data) {
    const minimapSvg = this.d3.select('#minimap-svg');
    const width = 200;
    const height = 150;

    // Scale nodes to fit minimap
    const xScale = this.d3.scaleLinear()
      .domain(this.d3.extent(data.nodes, d => d.x || 0))
      .range([10, width - 10]);

    const yScale = this.d3.scaleLinear()
      .domain(this.d3.extent(data.nodes, d => d.y || 0))
      .range([10, height - 10]);

    // Draw minimap nodes
    minimapSvg.selectAll('circle')
      .data(data.nodes)
      .join('circle')
      .attr('cx', d => xScale(d.x || 0))
      .attr('cy', d => yScale(d.y || 0))
      .attr('r', 2)
      .attr('fill', d => {
        if (d.type === 'current') return '#4caf50';
        if (d.brokenCount > 0) return '#f44336';
        return '#2196f3';
      });
  }

  // Update minimap viewport indicator
  updateMinimap(transform) {
    const viewport = document.querySelector('.legal-git-viz-minimap-viewport');
    if (!viewport) return;

    const svg = document.getElementById('relationship-svg');
    const svgRect = svg.getBoundingClientRect();

    // Calculate viewport position and size
    const scale = transform.k;
    const x = -transform.x / scale / svgRect.width * 200;
    const y = -transform.y / scale / svgRect.height * 150;
    const width = 200 / scale;
    const height = 150 / scale;

    viewport.style.left = x + 'px';
    viewport.style.top = y + 'px';
    viewport.style.width = width + 'px';
    viewport.style.height = height + 'px';
  }

  // Update statistics
  updateStatistics(data) {
    document.getElementById('stat-documents').textContent = data.nodes.length;
    document.getElementById('stat-references').textContent = data.links.length;
    document.getElementById('stat-valid').textContent = data.links.filter(l => l.valid).length;
    document.getElementById('stat-broken').textContent = data.links.filter(l => !l.valid).length;
  }

  // Attach event listeners
  attachVisualizerEventListeners() {
    // Close button
    document.querySelector('.legal-git-viz-close')?.addEventListener('click', () => {
      this.closeVisualizerModal();
    });

    // Layout buttons
    document.getElementById('viz-layout-force')?.addEventListener('click', () => {
      this.switchLayout('force');
    });

    document.getElementById('viz-layout-tree')?.addEventListener('click', () => {
      this.switchLayout('tree');
    });

    document.getElementById('viz-layout-radial')?.addEventListener('click', () => {
      this.switchLayout('radial');
    });

    // Fullscreen
    document.getElementById('viz-fullscreen')?.addEventListener('click', () => {
      this.toggleFullscreen();
    });

    // Filters
    document.querySelector('.legal-git-viz-filter-input')?.addEventListener('input', (e) => {
      this.filterNodes(e.target.value);
    });

    document.querySelectorAll('.legal-git-viz-filter-checkbox').forEach(checkbox => {
      checkbox.addEventListener('change', () => {
        this.applyFilters();
      });
    });

    // Click outside info panel to close
    document.addEventListener('click', (e) => {
      const infoPanel = document.getElementById('info-panel');
      if (infoPanel && !infoPanel.contains(e.target) && !e.target.closest('.legal-git-viz-node')) {
        infoPanel.classList.remove('visible');
      }
    });
  }

  // Switch layout
  switchLayout(layout) {
    // Update active button
    document.querySelectorAll('.legal-git-viz-control-btn').forEach(btn => {
      btn.classList.remove('active');
    });
    document.getElementById(`viz-layout-${layout}`)?.classList.add('active');

    // Recreate visualization with new layout
    const data = this.prepareVisualizationData(this.selectedNode?.docId);

    switch (layout) {
      case 'tree':
        this.createTreeLayout(data);
        break;
      case 'radial':
        this.createRadialLayout(data);
        break;
      default:
        this.createForceLayout(data);
    }
  }

  // Toggle fullscreen
  toggleFullscreen() {
    const modal = document.querySelector('.legal-git-viz-modal');
    if (!modal) return;

    if (!document.fullscreenElement) {
      modal.requestFullscreen();
    } else {
      document.exitFullscreen();
    }
  }

  // Filter nodes
  filterNodes(searchText) {
    const searchLower = searchText.toLowerCase();

    this.d3.selectAll('.legal-git-viz-node')
      .style('opacity', d => {
        return d.name.toLowerCase().includes(searchLower) ? 1 : 0.2;
      });

    this.d3.selectAll('.legal-git-viz-link')
      .style('opacity', d => {
        const source = typeof d.source === 'object' ? d.source : this.activeVisualization.nodes.data()[d.source];
        const target = typeof d.target === 'object' ? d.target : this.activeVisualization.nodes.data()[d.target];

        return source.name.toLowerCase().includes(searchLower) ||
               target.name.toLowerCase().includes(searchLower) ? 0.6 : 0.1;
      });
  }

  // Apply filters
  applyFilters() {
    const showValid = document.getElementById('filter-valid')?.checked;
    const showBroken = document.getElementById('filter-broken')?.checked;
    const showCase = document.getElementById('filter-case')?.checked;
    const showStatute = document.getElementById('filter-statute')?.checked;
    const showContract = document.getElementById('filter-contract')?.checked;

    this.d3.selectAll('.legal-git-viz-link')
      .style('display', d => {
        if (!showValid && d.valid) return 'none';
        if (!showBroken && !d.valid) return 'none';

        const typeFilters = {
          'case_citation': showCase,
          'statute': showStatute,
          'contract_clause': showContract
        };

        if (typeFilters[d.type] === false) return 'none';

        return 'block';
      });
  }

  // Get document name
  getDocumentName(docId) {
    // Mock implementation - would get from actual document metadata
    const names = [
      'Employment Agreement',
      'Service Contract',
      'License Agreement',
      'NDA Template',
      'Purchase Agreement',
      'Lease Agreement',
      'Settlement Agreement',
      'Partnership Agreement'
    ];

    return names[Math.floor(Math.random() * names.length)];
  }

  // Close visualizer modal
  closeVisualizerModal() {
    const container = document.querySelector('.legal-git-viz-container');
    if (container) {
      container.remove();
    }
    this.visualizerOpen = false;
    this.activeVisualization = null;
    this.selectedNode = null;
  }

  // Update visualization with new data
  updateVisualization(data) {
    if (!this.activeVisualization) return;

    // Update with new data and restart simulation if force layout
    if (this.activeVisualization.simulation) {
      this.activeVisualization.simulation
        .nodes(data.nodes)
        .force('link').links(data.links);

      this.activeVisualization.simulation.alpha(1).restart();
    }
  }

  // Highlight specific relationship
  highlightRelationship(detail) {
    const { sourceId, targetId, type } = detail;

    // Find and highlight the specific link
    this.d3.selectAll('.legal-git-viz-link')
      .classed('highlighted', d => {
        const source = d.source.docId || d.source;
        const target = d.target.docId || d.target;
        return source === sourceId && target === targetId && d.type === type;
      });

    // Optionally pan to show the relationship
    if (this.activeVisualization && this.activeVisualization.zoom) {
      const sourceNode = this.activeVisualization.nodes.data()
        .find(n => n.docId === sourceId);
      const targetNode = this.activeVisualization.nodes.data()
        .find(n => n.docId === targetId);

      if (sourceNode && targetNode) {
        const centerX = (sourceNode.x + targetNode.x) / 2;
        const centerY = (sourceNode.y + targetNode.y) / 2;

        const svg = this.d3.select('#relationship-svg');
        const width = svg.node().getBoundingClientRect().width;
        const height = svg.node().getBoundingClientRect().height;

        svg.transition().duration(750).call(
          this.activeVisualization.zoom.transform,
          this.d3.zoomIdentity
            .translate(width / 2, height / 2)
            .scale(1.5)
            .translate(-centerX, -centerY)
        );
      }
    }
  }
}
