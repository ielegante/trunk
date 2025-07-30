// Legal Git Chrome Extension - Cross-Document Reference Management
// Handles reference tracking, relationship visualization, and broken reference detection

class ReferenceManager {
  constructor(documentConverter, gitOpsManager) {
    this.documentConverter = documentConverter;
    this.gitOpsManager = gitOpsManager;
    this.documentReferences = new Map();
    this.referenceGraph = new Map();
    this.brokenReferences = new Map();
    this.referenceTypes = new Map();
    this.referenceViewOpen = false;
    this.selectedReference = null;
    this.init();
  }

  init() {
    this.setupReferenceTypes();
    this.setupReferenceEventListeners();
    this.injectReferenceStyles();
    this.loadReferenceData();
  }

  // Setup reference type definitions
  setupReferenceTypes() {
    // Legal document reference types
    this.referenceTypes.set('case_citation', {
      pattern: /\b\d+\s+[A-Z]\.\d+\s+\d+\b/g,
      displayName: 'Case Citation',
      icon: '⚖️',
      color: '#1976d2',
      priority: 'high',
      validator: this.validateCaseCitation.bind(this)
    });

    this.referenceTypes.set('statute', {
      pattern: /\b\d+\s+U\.S\.C\.\s+§\s*\d+\b/g,
      displayName: 'Federal Statute',
      icon: '📜',
      color: '#388e3c',
      priority: 'high',
      validator: this.validateStatute.bind(this)
    });

    this.referenceTypes.set('contract_clause', {
      pattern: /\b(?:Section|Article|Clause)\s+\d+(?:\.\d+)*\b/gi,
      displayName: 'Contract Clause',
      icon: '📄',
      color: '#7b1fa2',
      priority: 'medium',
      validator: this.validateContractClause.bind(this)
    });

    this.referenceTypes.set('exhibit', {
      pattern: /\bExhibit\s+[A-Z]\d*\b/g,
      displayName: 'Exhibit Reference',
      icon: '📎',
      color: '#e64a19',
      priority: 'medium',
      validator: this.validateExhibit.bind(this)
    });

    this.referenceTypes.set('internal_ref', {
      pattern: /\b(?:see|refer to|as defined in)\s+(?:Section|Paragraph|Article)\s+\d+(?:\.\d+)*\b/gi,
      displayName: 'Internal Reference',
      icon: '🔗',
      color: '#0097a7',
      priority: 'low',
      validator: this.validateInternalReference.bind(this)
    });

    this.referenceTypes.set('document_ref', {
      pattern: /\b(?:Agreement|Contract|Document)\s+dated\s+[A-Za-z]+\s+\d{1,2},?\s+\d{4}\b/gi,
      displayName: 'Document Reference',
      icon: '📋',
      color: '#f57c00',
      priority: 'medium',
      validator: this.validateDocumentReference.bind(this)
    });

    this.referenceTypes.set('definition', {
      pattern: /["']([A-Z][a-zA-Z\s]+)["']\s+(?:means|shall mean|has the meaning)/g,
      displayName: 'Definition',
      icon: '📖',
      color: '#455a64',
      priority: 'low',
      validator: this.validateDefinition.bind(this)
    });

    this.referenceTypes.set('party_reference', {
      pattern: /\b(?:Plaintiff|Defendant|Party|Parties|Client|Company)\b/g,
      displayName: 'Party Reference',
      icon: '👥',
      color: '#6d4c41',
      priority: 'medium',
      validator: this.validatePartyReference.bind(this)
    });
  }

  // Setup event listeners for reference management
  setupReferenceEventListeners() {
    window.addEventListener('legalGitShowReferences', (event) => {
      this.showReferenceModal(event.detail);
    });

    window.addEventListener('documentScanned', (event) => {
      this.scanDocumentReferences(event.detail.documentId);
    });

    window.addEventListener('referenceClicked', (event) => {
      this.handleReferenceClick(event.detail);
    });

    window.addEventListener('referenceGraphRequested', (event) => {
      this.showReferenceGraph(event.detail.documentId);
    });

    window.addEventListener('brokenReferenceCheck', (event) => {
      this.checkBrokenReferences(event.detail.documentId);
    });
  }

  // Inject CSS styles for reference UI
  injectReferenceStyles() {
    const styleId = 'legal-git-reference-styles';
    if (document.getElementById(styleId)) return;

    const style = document.createElement('style');
    style.id = styleId;
    style.textContent = `
      .legal-git-reference-container {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.85);
        z-index: 27000;
        display: flex;
        align-items: center;
        justify-content: center;
        font-family: 'Google Sans', Roboto, Arial, sans-serif;
      }

      .legal-git-reference-modal {
        background: white;
        border-radius: 12px;
        box-shadow: 0 12px 40px rgba(0,0,0,0.4);
        width: 95vw;
        height: 90vh;
        max-width: 1600px;
        display: flex;
        flex-direction: column;
        overflow: hidden;
      }

      .legal-git-reference-header {
        padding: 20px 24px;
        border-bottom: 2px solid #1976d2;
        background: linear-gradient(135deg, #e3f2fd, #bbdefb);
        display: flex;
        justify-content: space-between;
        align-items: center;
      }

      .legal-git-reference-title {
        font-size: 20px;
        font-weight: 600;
        color: #1976d2;
        display: flex;
        align-items: center;
        gap: 12px;
      }

      .legal-git-reference-close {
        background: none;
        border: none;
        font-size: 28px;
        cursor: pointer;
        color: #5f6368;
        padding: 8px;
        border-radius: 50%;
        transition: all 0.2s ease;
      }

      .legal-git-reference-close:hover {
        background: #e0e0e0;
        color: #1976d2;
      }

      .legal-git-reference-content {
        display: flex;
        flex: 1;
        overflow: hidden;
      }

      .legal-git-reference-sidebar {
        width: 280px;
        background: #f5f5f5;
        border-right: 1px solid #e0e0e0;
        padding: 20px;
        overflow-y: auto;
      }

      .legal-git-reference-main {
        flex: 1;
        padding: 20px;
        overflow-y: auto;
        background: #fafafa;
      }

      .legal-git-reference-graph {
        width: 400px;
        background: white;
        border-left: 1px solid #e0e0e0;
        padding: 20px;
        overflow-y: auto;
      }

      .legal-git-reference-section {
        margin-bottom: 24px;
      }

      .legal-git-reference-section-title {
        font-size: 16px;
        font-weight: 600;
        color: #424242;
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        gap: 8px;
      }

      .legal-git-reference-filter {
        width: 100%;
        padding: 10px 14px;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        font-size: 14px;
        margin-bottom: 16px;
        transition: all 0.2s ease;
      }

      .legal-git-reference-filter:focus {
        outline: none;
        border-color: #1976d2;
        box-shadow: 0 0 0 3px rgba(25, 118, 210, 0.1);
      }

      .legal-git-reference-type-list {
        list-style: none;
        padding: 0;
        margin: 0;
      }

      .legal-git-reference-type-item {
        padding: 10px 12px;
        border-radius: 8px;
        cursor: pointer;
        transition: all 0.2s ease;
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 6px;
      }

      .legal-git-reference-type-item:hover {
        background: white;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
      }

      .legal-git-reference-type-item.active {
        background: #1976d2;
        color: white;
      }

      .legal-git-reference-type-icon {
        font-size: 18px;
        width: 24px;
        text-align: center;
      }

      .legal-git-reference-type-name {
        flex: 1;
        font-size: 14px;
      }

      .legal-git-reference-type-count {
        background: rgba(0,0,0,0.1);
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 500;
      }

      .legal-git-reference-list {
        display: grid;
        gap: 12px;
      }

      .legal-git-reference-card {
        background: white;
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        padding: 16px;
        transition: all 0.2s ease;
        cursor: pointer;
      }

      .legal-git-reference-card:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        transform: translateY(-2px);
      }

      .legal-git-reference-card-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 8px;
      }

      .legal-git-reference-card-icon {
        font-size: 24px;
        width: 40px;
        height: 40px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: #f5f5f5;
        border-radius: 8px;
      }

      .legal-git-reference-card-title {
        flex: 1;
        font-size: 16px;
        font-weight: 600;
        color: #212121;
      }

      .legal-git-reference-card-status {
        padding: 4px 12px;
        border-radius: 16px;
        font-size: 12px;
        font-weight: 500;
      }

      .legal-git-reference-card-status.valid {
        background: #e8f5e9;
        color: #2e7d32;
      }

      .legal-git-reference-card-status.broken {
        background: #ffebee;
        color: #c62828;
      }

      .legal-git-reference-card-status.warning {
        background: #fff8e1;
        color: #f57f17;
      }

      .legal-git-reference-card-content {
        font-size: 14px;
        color: #616161;
        line-height: 1.6;
        margin-bottom: 12px;
      }

      .legal-git-reference-card-meta {
        display: flex;
        gap: 16px;
        font-size: 12px;
        color: #757575;
      }

      .legal-git-reference-graph-container {
        background: #f5f5f5;
        border-radius: 8px;
        padding: 16px;
        height: 400px;
        position: relative;
        overflow: hidden;
      }

      .legal-git-reference-graph-svg {
        width: 100%;
        height: 100%;
      }

      .legal-git-reference-node {
        cursor: pointer;
        transition: all 0.2s ease;
      }

      .legal-git-reference-node:hover {
        filter: brightness(1.2);
      }

      .legal-git-reference-link {
        fill: none;
        stroke: #9e9e9e;
        stroke-width: 2;
        marker-end: url(#arrowhead);
      }

      .legal-git-reference-link.broken {
        stroke: #f44336;
        stroke-dasharray: 5, 5;
      }

      .legal-git-reference-link.valid {
        stroke: #4caf50;
      }

      .legal-git-reference-stats {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 12px;
        margin-bottom: 20px;
      }

      .legal-git-reference-stat {
        background: white;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 12px;
        text-align: center;
      }

      .legal-git-reference-stat-value {
        font-size: 24px;
        font-weight: 600;
        color: #1976d2;
        margin-bottom: 4px;
      }

      .legal-git-reference-stat-label {
        font-size: 12px;
        color: #757575;
        text-transform: uppercase;
      }

      .legal-git-reference-actions {
        display: flex;
        gap: 8px;
        margin-top: 20px;
      }

      .legal-git-reference-action-btn {
        flex: 1;
        padding: 10px 16px;
        border: none;
        border-radius: 8px;
        font-size: 14px;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s ease;
      }

      .legal-git-reference-action-btn.primary {
        background: #1976d2;
        color: white;
      }

      .legal-git-reference-action-btn.primary:hover {
        background: #1565c0;
        box-shadow: 0 2px 8px rgba(25, 118, 210, 0.3);
      }

      .legal-git-reference-action-btn.secondary {
        background: white;
        color: #1976d2;
        border: 1px solid #1976d2;
      }

      .legal-git-reference-action-btn.secondary:hover {
        background: #e3f2fd;
      }

      .legal-git-reference-highlight {
        background: #ffeb3b;
        padding: 2px 4px;
        border-radius: 3px;
        cursor: pointer;
        transition: all 0.2s ease;
      }

      .legal-git-reference-highlight:hover {
        background: #ffc107;
      }

      .legal-git-reference-tooltip {
        position: absolute;
        background: #424242;
        color: white;
        padding: 8px 12px;
        border-radius: 6px;
        font-size: 12px;
        white-space: nowrap;
        z-index: 1000;
        pointer-events: none;
        opacity: 0;
        transition: opacity 0.2s ease;
      }

      .legal-git-reference-tooltip.visible {
        opacity: 1;
      }
    `;
    document.head.appendChild(style);
  }

  // Load reference data
  async loadReferenceData() {
    // Load saved references from storage
    const savedReferences = await chrome.storage.local.get(['documentReferences', 'referenceGraph']);

    if (savedReferences.documentReferences) {
      this.documentReferences = new Map(Object.entries(savedReferences.documentReferences));
    }

    if (savedReferences.referenceGraph) {
      this.referenceGraph = new Map(Object.entries(savedReferences.referenceGraph));
    }
  }

  // Scan document for references
  async scanDocumentReferences(documentId) {
    console.log('Scanning document for references:', documentId);

    const documentContent = await this.getDocumentContent(documentId);
    if (!documentContent) return;

    const references = new Map();
    const documentReferences = [];

    // Scan for each reference type
    for (const [typeId, typeConfig] of this.referenceTypes) {
      const matches = [...documentContent.matchAll(typeConfig.pattern)];

      for (const match of matches) {
        const reference = {
          id: this.generateReferenceId(),
          type: typeId,
          text: match[0],
          position: match.index,
          documentId: documentId,
          timestamp: Date.now(),
          valid: true,
          targetDocument: null,
          metadata: this.extractReferenceMetadata(match, typeId)
        };

        // Validate reference
        const validation = await typeConfig.validator(reference);
        reference.valid = validation.valid;
        reference.targetDocument = validation.targetDocument;
        reference.validationMessage = validation.message;

        references.set(reference.id, reference);
        documentReferences.push(reference);
      }
    }

    // Store references
    this.documentReferences.set(documentId, documentReferences);

    // Update reference graph
    this.updateReferenceGraph(documentId, documentReferences);

    // Check for broken references
    await this.checkBrokenReferences(documentId);

    // Save to storage
    await this.saveReferences();

    // Notify UI
    window.dispatchEvent(new CustomEvent('referencesScanned', {
      detail: {
        documentId,
        referenceCount: documentReferences.length,
        brokenCount: documentReferences.filter(r => !r.valid).length
      }
    }));
  }

  // Show reference modal
  showReferenceModal(options = {}) {
    if (this.referenceViewOpen) return;

    const modalHtml = `
      <div class="legal-git-reference-container">
        <div class="legal-git-reference-modal">
          <div class="legal-git-reference-header">
            <div class="legal-git-reference-title">
              <span>🔗</span>
              <span>Document References</span>
            </div>
            <button class="legal-git-reference-close">&times;</button>
          </div>

          <div class="legal-git-reference-content">
            <div class="legal-git-reference-sidebar">
              <div class="legal-git-reference-section">
                <input type="text" class="legal-git-reference-filter" placeholder="Search references...">
              </div>

              <div class="legal-git-reference-section">
                <div class="legal-git-reference-section-title">
                  <span>📊</span>
                  <span>Reference Types</span>
                </div>
                <ul class="legal-git-reference-type-list">
                  ${this.renderReferenceTypes()}
                </ul>
              </div>

              <div class="legal-git-reference-section">
                <div class="legal-git-reference-stats">
                  <div class="legal-git-reference-stat">
                    <div class="legal-git-reference-stat-value">0</div>
                    <div class="legal-git-reference-stat-label">Total</div>
                  </div>
                  <div class="legal-git-reference-stat">
                    <div class="legal-git-reference-stat-value">0</div>
                    <div class="legal-git-reference-stat-label">Broken</div>
                  </div>
                </div>
              </div>
            </div>

            <div class="legal-git-reference-main">
              <div class="legal-git-reference-section">
                <div class="legal-git-reference-section-title">
                  <span>📄</span>
                  <span>Document References</span>
                </div>
                <div class="legal-git-reference-list" id="reference-list">
                  <!-- References will be loaded here -->
                </div>
              </div>
            </div>

            <div class="legal-git-reference-graph">
              <div class="legal-git-reference-section">
                <div class="legal-git-reference-section-title">
                  <span>🕸️</span>
                  <span>Reference Graph</span>
                </div>
                <div class="legal-git-reference-graph-container" id="reference-graph">
                  <!-- Graph visualization will be rendered here -->
                </div>
              </div>

              <div class="legal-git-reference-actions">
                <button class="legal-git-reference-action-btn primary" id="check-references">
                  Check All References
                </button>
                <button class="legal-git-reference-action-btn secondary" id="export-references">
                  Export Report
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;

    const modalElement = document.createElement('div');
    modalElement.innerHTML = modalHtml;
    document.body.appendChild(modalElement);

    this.referenceViewOpen = true;
    this.attachModalEventListeners();
    this.loadReferencesIntoModal(options.documentId);
    this.renderReferenceGraph(options.documentId);
  }

  // Render reference types list
  renderReferenceTypes() {
    let html = '';

    for (const [typeId, typeConfig] of this.referenceTypes) {
      const count = this.getTypeReferenceCount(typeId);
      html += `
        <li class="legal-git-reference-type-item" data-type="${typeId}">
          <span class="legal-git-reference-type-icon">${typeConfig.icon}</span>
          <span class="legal-git-reference-type-name">${typeConfig.displayName}</span>
          <span class="legal-git-reference-type-count">${count}</span>
        </li>
      `;
    }

    return html;
  }

  // Get reference count by type
  getTypeReferenceCount(typeId) {
    let count = 0;

    for (const [docId, refs] of this.documentReferences) {
      count += refs.filter(r => r.type === typeId).length;
    }

    return count;
  }

  // Load references into modal
  loadReferencesIntoModal(documentId) {
    const referenceList = document.getElementById('reference-list');
    if (!referenceList) return;

    let references = [];

    if (documentId) {
      references = this.documentReferences.get(documentId) || [];
    } else {
      // Load all references
      for (const [docId, docRefs] of this.documentReferences) {
        references = references.concat(docRefs);
      }
    }

    // Sort references by type priority
    references.sort((a, b) => {
      const aPriority = this.referenceTypes.get(a.type).priority;
      const bPriority = this.referenceTypes.get(b.type).priority;
      const priorityOrder = { high: 0, medium: 1, low: 2 };
      return priorityOrder[aPriority] - priorityOrder[bPriority];
    });

    let html = '';

    for (const reference of references) {
      const typeConfig = this.referenceTypes.get(reference.type);
      html += this.renderReferenceCard(reference, typeConfig);
    }

    referenceList.innerHTML = html || '<p style="text-align: center; color: #757575;">No references found</p>';

    // Update stats
    this.updateReferenceStats(references);
  }

  // Render reference card
  renderReferenceCard(reference, typeConfig) {
    const statusClass = reference.valid ? 'valid' : 'broken';
    const statusText = reference.valid ? 'Valid' : 'Broken';

    return `
      <div class="legal-git-reference-card" data-reference-id="${reference.id}">
        <div class="legal-git-reference-card-header">
          <div class="legal-git-reference-card-icon" style="background: ${typeConfig.color}20;">
            ${typeConfig.icon}
          </div>
          <div class="legal-git-reference-card-title">${reference.text}</div>
          <div class="legal-git-reference-card-status ${statusClass}">${statusText}</div>
        </div>

        <div class="legal-git-reference-card-content">
          ${this.renderReferenceDetails(reference)}
        </div>

        <div class="legal-git-reference-card-meta">
          <span>Type: ${typeConfig.displayName}</span>
          <span>Document: ${this.getDocumentName(reference.documentId)}</span>
          ${reference.targetDocument ? `<span>Target: ${this.getDocumentName(reference.targetDocument)}</span>` : ''}
        </div>
      </div>
    `;
  }

  // Render reference details
  renderReferenceDetails(reference) {
    if (reference.validationMessage) {
      return `<p>${reference.validationMessage}</p>`;
    }

    if (reference.metadata) {
      let details = '<ul style="margin: 0; padding-left: 20px;">';

      for (const [key, value] of Object.entries(reference.metadata)) {
        details += `<li>${this.formatMetadataKey(key)}: ${value}</li>`;
      }

      details += '</ul>';
      return details;
    }

    return '<p>No additional details available</p>';
  }

  // Format metadata key for display
  formatMetadataKey(key) {
    return key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  }

  // Get document name
  getDocumentName(documentId) {
    // Mock implementation - would get from actual document metadata
    return `Document ${documentId.substring(0, 8)}...`;
  }

  // Update reference stats
  updateReferenceStats(references) {
    const totalStat = document.querySelector('.legal-git-reference-stat-value');
    const brokenStat = document.querySelectorAll('.legal-git-reference-stat-value')[1];

    if (totalStat) totalStat.textContent = references.length;
    if (brokenStat) brokenStat.textContent = references.filter(r => !r.valid).length;
  }

  // Render reference graph visualization
  renderReferenceGraph(documentId) {
    const graphContainer = document.getElementById('reference-graph');
    if (!graphContainer) return;

    // Create SVG for graph
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.classList.add('legal-git-reference-graph-svg');

    // Add arrow marker definition
    const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
    const marker = document.createElementNS('http://www.w3.org/2000/svg', 'marker');
    marker.setAttribute('id', 'arrowhead');
    marker.setAttribute('markerWidth', '10');
    marker.setAttribute('markerHeight', '7');
    marker.setAttribute('refX', '9');
    marker.setAttribute('refY', '3.5');
    marker.setAttribute('orient', 'auto');

    const polygon = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
    polygon.setAttribute('points', '0 0, 10 3.5, 0 7');
    polygon.setAttribute('fill', '#9e9e9e');

    marker.appendChild(polygon);
    defs.appendChild(marker);
    svg.appendChild(defs);

    // Get graph data
    const nodes = this.getGraphNodes(documentId);
    const links = this.getGraphLinks(documentId);

    // Simple force-directed layout
    const width = graphContainer.offsetWidth;
    const height = 368; // Fixed height minus padding

    // Position nodes
    nodes.forEach((node, index) => {
      const angle = (2 * Math.PI * index) / nodes.length;
      node.x = width / 2 + Math.cos(angle) * 100;
      node.y = height / 2 + Math.sin(angle) * 100;
    });

    // Render links
    links.forEach(link => {
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.classList.add('legal-git-reference-link');
      if (!link.valid) line.classList.add('broken');
      line.setAttribute('x1', link.source.x);
      line.setAttribute('y1', link.source.y);
      line.setAttribute('x2', link.target.x);
      line.setAttribute('y2', link.target.y);
      svg.appendChild(line);
    });

    // Render nodes
    nodes.forEach(node => {
      const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      g.classList.add('legal-git-reference-node');
      g.setAttribute('transform', `translate(${node.x}, ${node.y})`);

      const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      circle.setAttribute('r', '30');
      circle.setAttribute('fill', node.color || '#1976d2');
      circle.setAttribute('stroke', 'white');
      circle.setAttribute('stroke-width', '3');

      const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      text.setAttribute('text-anchor', 'middle');
      text.setAttribute('dy', '0.3em');
      text.setAttribute('fill', 'white');
      text.setAttribute('font-size', '20');
      text.textContent = node.icon;

      g.appendChild(circle);
      g.appendChild(text);

      // Add tooltip
      g.addEventListener('mouseenter', (e) => {
        this.showTooltip(e, node.name);
      });

      g.addEventListener('mouseleave', () => {
        this.hideTooltip();
      });

      svg.appendChild(g);
    });

    graphContainer.innerHTML = '';
    graphContainer.appendChild(svg);
  }

  // Get graph nodes
  getGraphNodes(documentId) {
    const nodes = [];
    const nodeMap = new Map();

    // Add current document as center node
    if (documentId) {
      nodeMap.set(documentId, {
        id: documentId,
        name: this.getDocumentName(documentId),
        icon: '📄',
        color: '#1976d2',
        type: 'current'
      });
    }

    // Add referenced documents
    for (const [docId, refs] of this.documentReferences) {
      if (!nodeMap.has(docId)) {
        nodeMap.set(docId, {
          id: docId,
          name: this.getDocumentName(docId),
          icon: '📋',
          color: '#757575',
          type: 'document'
        });
      }

      // Add target documents
      refs.forEach(ref => {
        if (ref.targetDocument && !nodeMap.has(ref.targetDocument)) {
          nodeMap.set(ref.targetDocument, {
            id: ref.targetDocument,
            name: this.getDocumentName(ref.targetDocument),
            icon: '🎯',
            color: ref.valid ? '#4caf50' : '#f44336',
            type: 'target'
          });
        }
      });
    }

    return Array.from(nodeMap.values());
  }

  // Get graph links
  getGraphLinks(documentId) {
    const links = [];
    const nodes = this.getGraphNodes(documentId);
    const nodeMap = new Map(nodes.map(n => [n.id, n]));

    for (const [docId, refs] of this.documentReferences) {
      const sourceNode = nodeMap.get(docId);
      if (!sourceNode) continue;

      refs.forEach(ref => {
        if (ref.targetDocument) {
          const targetNode = nodeMap.get(ref.targetDocument);
          if (targetNode) {
            links.push({
              source: sourceNode,
              target: targetNode,
              valid: ref.valid,
              type: ref.type
            });
          }
        }
      });
    }

    return links;
  }

  // Show tooltip
  showTooltip(event, text) {
    let tooltip = document.querySelector('.legal-git-reference-tooltip');

    if (!tooltip) {
      tooltip = document.createElement('div');
      tooltip.classList.add('legal-git-reference-tooltip');
      document.body.appendChild(tooltip);
    }

    tooltip.textContent = text;
    tooltip.style.left = event.pageX + 'px';
    tooltip.style.top = (event.pageY - 40) + 'px';
    tooltip.classList.add('visible');
  }

  // Hide tooltip
  hideTooltip() {
    const tooltip = document.querySelector('.legal-git-reference-tooltip');
    if (tooltip) {
      tooltip.classList.remove('visible');
    }
  }

  // Attach modal event listeners
  attachModalEventListeners() {
    // Close button
    document.querySelector('.legal-git-reference-close')?.addEventListener('click', () => {
      this.closeReferenceModal();
    });

    // Search filter
    document.querySelector('.legal-git-reference-filter')?.addEventListener('input', (e) => {
      this.filterReferences(e.target.value);
    });

    // Type filters
    document.querySelectorAll('.legal-git-reference-type-item').forEach(item => {
      item.addEventListener('click', () => {
        const type = item.dataset.type;
        this.filterByType(type);

        // Update active state
        document.querySelectorAll('.legal-git-reference-type-item').forEach(i => {
          i.classList.remove('active');
        });
        item.classList.add('active');
      });
    });

    // Reference cards
    document.addEventListener('click', (e) => {
      const card = e.target.closest('.legal-git-reference-card');
      if (card) {
        const referenceId = card.dataset.referenceId;
        this.handleReferenceCardClick(referenceId);
      }
    });

    // Action buttons
    document.getElementById('check-references')?.addEventListener('click', () => {
      this.checkAllReferences();
    });

    document.getElementById('export-references')?.addEventListener('click', () => {
      this.exportReferenceReport();
    });

    // Click outside to close
    document.querySelector('.legal-git-reference-container')?.addEventListener('click', (e) => {
      if (e.target.classList.contains('legal-git-reference-container')) {
        this.closeReferenceModal();
      }
    });
  }

  // Filter references by search text
  filterReferences(searchText) {
    const cards = document.querySelectorAll('.legal-git-reference-card');
    const searchLower = searchText.toLowerCase();

    cards.forEach(card => {
      const text = card.textContent.toLowerCase();
      if (text.includes(searchLower)) {
        card.style.display = 'block';
      } else {
        card.style.display = 'none';
      }
    });
  }

  // Filter by reference type
  filterByType(typeId) {
    const references = [];

    for (const [docId, docRefs] of this.documentReferences) {
      references.push(...docRefs.filter(r => r.type === typeId));
    }

    this.loadFilteredReferences(references);
  }

  // Load filtered references
  loadFilteredReferences(references) {
    const referenceList = document.getElementById('reference-list');
    if (!referenceList) return;

    let html = '';

    for (const reference of references) {
      const typeConfig = this.referenceTypes.get(reference.type);
      html += this.renderReferenceCard(reference, typeConfig);
    }

    referenceList.innerHTML = html || '<p style="text-align: center; color: #757575;">No references found</p>';
    this.updateReferenceStats(references);
  }

  // Handle reference card click
  handleReferenceCardClick(referenceId) {
    const reference = this.findReference(referenceId);
    if (!reference) return;

    // Navigate to reference in document
    window.dispatchEvent(new CustomEvent('navigateToReference', {
      detail: {
        documentId: reference.documentId,
        position: reference.position,
        text: reference.text
      }
    }));
  }

  // Find reference by ID
  findReference(referenceId) {
    for (const [docId, refs] of this.documentReferences) {
      const ref = refs.find(r => r.id === referenceId);
      if (ref) return ref;
    }
    return null;
  }

  // Check all references
  async checkAllReferences() {
    const button = document.getElementById('check-references');
    if (button) {
      button.textContent = 'Checking...';
      button.disabled = true;
    }

    let totalChecked = 0;
    let brokenFound = 0;

    for (const [docId, refs] of this.documentReferences) {
      for (const ref of refs) {
        const validation = await this.referenceTypes.get(ref.type).validator(ref);
        ref.valid = validation.valid;
        ref.targetDocument = validation.targetDocument;
        ref.validationMessage = validation.message;

        totalChecked++;
        if (!ref.valid) brokenFound++;
      }
    }

    // Save updated references
    await this.saveReferences();

    // Reload UI
    this.loadReferencesIntoModal();
    this.renderReferenceGraph();

    if (button) {
      button.textContent = 'Check All References';
      button.disabled = false;
    }

    // Show results
    this.showNotification(`Checked ${totalChecked} references. Found ${brokenFound} broken references.`);
  }

  // Export reference report
  exportReferenceReport() {
    const report = this.generateReferenceReport();

    const blob = new Blob([report], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = `reference-report-${new Date().toISOString().split('T')[0]}.md`;
    a.click();

    URL.revokeObjectURL(url);

    this.showNotification('Reference report exported successfully');
  }

  // Generate reference report
  generateReferenceReport() {
    let report = '# Document Reference Report\n\n';
    report += `Generated: ${new Date().toLocaleString()}\n\n`;

    // Summary statistics
    let totalRefs = 0;
    let brokenRefs = 0;
    const typeStats = new Map();

    for (const [docId, refs] of this.documentReferences) {
      totalRefs += refs.length;
      brokenRefs += refs.filter(r => !r.valid).length;

      refs.forEach(ref => {
        const count = typeStats.get(ref.type) || 0;
        typeStats.set(ref.type, count + 1);
      });
    }

    report += '## Summary\n\n';
    report += `- Total References: ${totalRefs}\n`;
    report += `- Valid References: ${totalRefs - brokenRefs}\n`;
    report += `- Broken References: ${brokenRefs}\n`;
    report += `- Documents Analyzed: ${this.documentReferences.size}\n\n`;

    report += '## Reference Types\n\n';
    for (const [typeId, count] of typeStats) {
      const typeConfig = this.referenceTypes.get(typeId);
      report += `- ${typeConfig.displayName}: ${count}\n`;
    }
    report += '\n';

    // Detailed references by document
    report += '## References by Document\n\n';

    for (const [docId, refs] of this.documentReferences) {
      report += `### ${this.getDocumentName(docId)}\n\n`;

      if (refs.length === 0) {
        report += 'No references found.\n\n';
        continue;
      }

      // Group by type
      const refsByType = new Map();
      refs.forEach(ref => {
        const list = refsByType.get(ref.type) || [];
        list.push(ref);
        refsByType.set(ref.type, list);
      });

      for (const [typeId, typeRefs] of refsByType) {
        const typeConfig = this.referenceTypes.get(typeId);
        report += `#### ${typeConfig.displayName}\n\n`;

        typeRefs.forEach(ref => {
          const status = ref.valid ? '✅' : '❌';
          report += `- ${status} "${ref.text}"`;

          if (ref.targetDocument) {
            report += ` → ${this.getDocumentName(ref.targetDocument)}`;
          }

          if (!ref.valid && ref.validationMessage) {
            report += `\n  - Issue: ${ref.validationMessage}`;
          }

          report += '\n';
        });

        report += '\n';
      }
    }

    // Broken references section
    if (brokenRefs > 0) {
      report += '## Broken References\n\n';

      for (const [docId, refs] of this.documentReferences) {
        const broken = refs.filter(r => !r.valid);
        if (broken.length === 0) continue;

        report += `### ${this.getDocumentName(docId)}\n\n`;

        broken.forEach(ref => {
          const typeConfig = this.referenceTypes.get(ref.type);
          report += `- **${typeConfig.displayName}**: "${ref.text}"\n`;
          report += `  - Issue: ${ref.validationMessage || 'Reference target not found'}\n`;
        });

        report += '\n';
      }
    }

    return report;
  }

  // Close reference modal
  closeReferenceModal() {
    const container = document.querySelector('.legal-git-reference-container');
    if (container) {
      container.remove();
    }
    this.referenceViewOpen = false;
  }

  // Show notification
  showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.style.cssText = `
      position: fixed;
      bottom: 20px;
      right: 20px;
      background: ${type === 'error' ? '#f44336' : '#1976d2'};
      color: white;
      padding: 16px 24px;
      border-radius: 8px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.2);
      font-family: 'Google Sans', Roboto, Arial, sans-serif;
      font-size: 14px;
      z-index: 28000;
      animation: slideIn 0.3s ease;
    `;

    notification.textContent = message;
    document.body.appendChild(notification);

    setTimeout(() => {
      notification.style.animation = 'slideOut 0.3s ease';
      setTimeout(() => notification.remove(), 300);
    }, 3000);
  }

  // Validation methods
  validateCaseCitation(reference) {
    // Mock validation - would check against legal databases
    return {
      valid: Math.random() > 0.2,
      targetDocument: null,
      message: reference.text.includes('U.S.') ? 'Valid federal case citation' : 'Citation format not recognized'
    };
  }

  validateStatute(reference) {
    // Mock validation
    return {
      valid: true,
      targetDocument: null,
      message: 'Federal statute reference'
    };
  }

  validateContractClause(reference) {
    // Check if clause exists in current document
    return {
      valid: Math.random() > 0.1,
      targetDocument: reference.documentId,
      message: 'Internal clause reference'
    };
  }

  validateExhibit(reference) {
    // Mock validation - would check exhibit attachments
    return {
      valid: Math.random() > 0.3,
      targetDocument: `exhibit_${reference.text.replace(/\s+/g, '_').toLowerCase()}`,
      message: reference.valid ? 'Exhibit found' : 'Exhibit not attached to document'
    };
  }

  validateInternalReference(reference) {
    return {
      valid: true,
      targetDocument: reference.documentId,
      message: 'Internal document reference'
    };
  }

  validateDocumentReference(reference) {
    // Mock validation - would check document repository
    return {
      valid: Math.random() > 0.25,
      targetDocument: `doc_${Date.now()}`,
      message: reference.valid ? 'Referenced document found in repository' : 'Referenced document not found'
    };
  }

  validateDefinition(reference) {
    return {
      valid: true,
      targetDocument: reference.documentId,
      message: 'Term definition'
    };
  }

  validatePartyReference(reference) {
    return {
      valid: true,
      targetDocument: reference.documentId,
      message: 'Party reference'
    };
  }

  // Helper methods
  generateReferenceId() {
    return `ref_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  extractReferenceMetadata(match, typeId) {
    const metadata = {};

    switch (typeId) {
      case 'case_citation':
        // Extract volume, reporter, page
        const citeParts = match[0].split(/\s+/);
        if (citeParts.length >= 3) {
          metadata.volume = citeParts[0];
          metadata.reporter = citeParts[1];
          metadata.page = citeParts[2];
        }
        break;

      case 'statute':
        // Extract title and section
        const statuteMatch = match[0].match(/(\d+)\s+U\.S\.C\.\s+§\s*(\d+)/);
        if (statuteMatch) {
          metadata.title = statuteMatch[1];
          metadata.section = statuteMatch[2];
        }
        break;

      case 'contract_clause':
        // Extract section number
        const clauseMatch = match[0].match(/(?:Section|Article|Clause)\s+([\d.]+)/i);
        if (clauseMatch) {
          metadata.number = clauseMatch[1];
        }
        break;

      case 'exhibit':
        // Extract exhibit identifier
        const exhibitMatch = match[0].match(/Exhibit\s+([A-Z]\d*)/);
        if (exhibitMatch) {
          metadata.identifier = exhibitMatch[1];
        }
        break;
    }

    return metadata;
  }

  async getDocumentContent(documentId) {
    // Mock implementation - would get actual document content
    return `
      This Agreement is entered into as of January 15, 2024 between Company A and Company B.

      Section 1.1 Definitions
      "Services" means the consulting services described in Exhibit A.

      Section 2.1 Services
      Company A shall provide the Services as set forth in Exhibit A attached hereto.

      Section 3.1 Payment
      As consideration for the Services, Company B shall pay the fees set forth in Section 4.2.

      Section 4.2 Fee Schedule
      The fees for Services shall be as described in Exhibit B.

      This Agreement is governed by the laws of the State of Delaware, without regard to its conflict of laws provisions.
      Reference is made to Smith v. Jones, 123 U.S. 456 (2020) for the applicable legal standard.

      See also 15 U.S.C. § 1234 for regulatory requirements.

      IN WITNESS WHEREOF, the parties have executed this Agreement dated February 1, 2024.
    `;
  }

  updateReferenceGraph(documentId, references) {
    // Update graph structure
    const edges = [];

    references.forEach(ref => {
      if (ref.targetDocument) {
        edges.push({
          source: documentId,
          target: ref.targetDocument,
          type: ref.type,
          valid: ref.valid
        });
      }
    });

    this.referenceGraph.set(documentId, edges);
  }

  async saveReferences() {
    // Convert Maps to objects for storage
    const referencesObj = {};
    for (const [key, value] of this.documentReferences) {
      referencesObj[key] = value;
    }

    const graphObj = {};
    for (const [key, value] of this.referenceGraph) {
      graphObj[key] = value;
    }

    await chrome.storage.local.set({
      documentReferences: referencesObj,
      referenceGraph: graphObj
    });
  }

  async checkBrokenReferences(documentId) {
    const references = this.documentReferences.get(documentId) || [];
    const broken = references.filter(r => !r.valid);

    if (broken.length > 0) {
      this.brokenReferences.set(documentId, broken);

      // Notify about broken references
      window.dispatchEvent(new CustomEvent('brokenReferencesFound', {
        detail: {
          documentId,
          count: broken.length,
          references: broken
        }
      }));
    }
  }

  // Public method to handle reference click in document
  handleReferenceClick(detail) {
    const { referenceText, position, documentId } = detail;

    // Find matching reference
    const references = this.documentReferences.get(documentId) || [];
    const reference = references.find(r => r.text === referenceText && r.position === position);

    if (reference && reference.targetDocument) {
      // Navigate to target document
      window.dispatchEvent(new CustomEvent('navigateToDocument', {
        detail: {
          documentId: reference.targetDocument,
          referenceId: reference.id
        }
      }));
    } else {
      this.showNotification('Reference target not found', 'error');
    }
  }

  // Show reference graph for specific document
  showReferenceGraph(documentId) {
    this.showReferenceModal({ documentId });

    // Focus on graph section
    setTimeout(() => {
      document.querySelector('.legal-git-reference-graph')?.scrollIntoView({ behavior: 'smooth' });
    }, 100);
  }
}
