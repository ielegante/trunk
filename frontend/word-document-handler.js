// Legal Git Chrome Extension - Word Document UI Handler
// Handles Word document detection, UI integration, and format processing

class WordDocumentHandler {
  constructor(documentConverter, gitOpsManager) {
    this.documentConverter = documentConverter;
    this.gitOpsManager = gitOpsManager;
    this.wordDocuments = new Map();
    this.activeWordDoc = null;
    this.wordUIInjected = false;
    this.supportedFormats = ['docx', 'doc', 'rtf', 'odt', 'txt', 'md'];
    this.init();
  }

  init() {
    this.setupWordEventListeners();
    this.injectWordStyles();
    this.detectWordDocuments();
  }

  // Setup event listeners for Word document handling
  setupWordEventListeners() {
    // Listen for Word document events
    window.addEventListener('wordDocumentDetected', (event) => {
      this.handleWordDocumentDetected(event.detail);
    });

    window.addEventListener('wordDocumentOpened', (event) => {
      this.handleWordDocumentOpened(event.detail);
    });

    window.addEventListener('legalGitShowFormatSelector', (event) => {
      this.showFormatSelectionModal(event.detail);
    });

    // Monitor for Office 365 Word online
    if (window.location.hostname.includes('office.com') ||
        window.location.hostname.includes('microsoft.com')) {
      this.setupOfficeIntegration();
    }

    // Monitor for Google Docs with Word import
    if (window.location.hostname === 'docs.google.com') {
      this.setupGoogleDocsWordIntegration();
    }
  }

  // Inject CSS styles for Word document UI
  injectWordStyles() {
    const styleId = 'legal-git-word-styles';
    if (document.getElementById(styleId)) return;

    const style = document.createElement('style');
    style.id = styleId;
    style.textContent = `
      .legal-git-word-container {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.85);
        z-index: 24000;
        display: flex;
        align-items: center;
        justify-content: center;
        font-family: 'Segoe UI', 'Google Sans', Roboto, Arial, sans-serif;
      }

      .legal-git-word-modal {
        background: white;
        border-radius: 12px;
        box-shadow: 0 12px 40px rgba(0,0,0,0.4);
        width: 90vw;
        height: 85vh;
        max-width: 1400px;
        display: flex;
        flex-direction: column;
        overflow: hidden;
      }

      .legal-git-word-header {
        padding: 20px 24px;
        border-bottom: 2px solid #0078d4;
        background: linear-gradient(135deg, #f3f9ff, #e1f5fe);
        display: flex;
        justify-content: space-between;
        align-items: center;
      }

      .legal-git-word-title {
        font-size: 20px;
        font-weight: 600;
        color: #0078d4;
        display: flex;
        align-items: center;
        gap: 12px;
      }

      .legal-git-word-close {
        background: none;
        border: none;
        font-size: 28px;
        cursor: pointer;
        color: #5f6368;
        padding: 8px;
        border-radius: 6px;
        transition: all 0.2s;
      }

      .legal-git-word-close:hover {
        background: #f1f3f4;
        transform: scale(1.1);
      }

      .legal-git-word-content {
        flex: 1;
        display: flex;
        overflow: hidden;
      }

      .legal-git-word-sidebar {
        width: 320px;
        background: #f8f9fa;
        border-right: 1px solid #e0e0e0;
        overflow-y: auto;
        padding: 20px;
      }

      .legal-git-word-main {
        flex: 1;
        overflow-y: auto;
        padding: 20px 24px;
      }

      .legal-git-word-format-selector {
        background: white;
        border: 1px solid #dadce0;
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 20px;
      }

      .legal-git-word-format-selector h4 {
        margin: 0 0 16px 0;
        font-size: 16px;
        font-weight: 600;
        color: #1f1f1f;
        display: flex;
        align-items: center;
        gap: 8px;
      }

      .legal-git-word-format-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 12px;
        margin-bottom: 20px;
      }

      .legal-git-word-format-option {
        border: 2px solid #dadce0;
        border-radius: 8px;
        padding: 16px;
        cursor: pointer;
        transition: all 0.2s;
        text-align: center;
        background: white;
      }

      .legal-git-word-format-option:hover {
        border-color: #0078d4;
        background: #f3f9ff;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
      }

      .legal-git-word-format-option.selected {
        border-color: #0078d4;
        background: #e1f5fe;
      }

      .legal-git-word-format-icon {
        font-size: 32px;
        margin-bottom: 8px;
        display: block;
      }

      .legal-git-word-format-name {
        font-size: 14px;
        font-weight: 600;
        color: #1f1f1f;
        margin-bottom: 4px;
      }

      .legal-git-word-format-description {
        font-size: 12px;
        color: #5f6368;
        line-height: 1.3;
      }

      .legal-git-word-document-info {
        background: white;
        border: 1px solid #dadce0;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 20px;
      }

      .legal-git-word-document-info h4 {
        margin: 0 0 12px 0;
        font-size: 14px;
        font-weight: 600;
        color: #1f1f1f;
      }

      .legal-git-word-info-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 6px 0;
        font-size: 13px;
        border-bottom: 1px solid #f0f0f0;
      }

      .legal-git-word-info-item:last-child {
        border-bottom: none;
      }

      .legal-git-word-info-label {
        color: #5f6368;
      }

      .legal-git-word-info-value {
        font-weight: 500;
        color: #1f1f1f;
      }

      .legal-git-word-conversion-preview {
        background: #fafafa;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        overflow: hidden;
        margin-bottom: 20px;
      }

      .legal-git-word-conversion-header {
        padding: 16px 20px;
        background: #f8f9fa;
        border-bottom: 1px solid #e0e0e0;
        display: flex;
        justify-content: space-between;
        align-items: center;
      }

      .legal-git-word-conversion-title {
        font-size: 16px;
        font-weight: 600;
        color: #1f1f1f;
      }

      .legal-git-word-conversion-content {
        padding: 20px;
        max-height: 300px;
        overflow-y: auto;
      }

      .legal-git-word-preview-tabs {
        display: flex;
        gap: 8px;
        margin-bottom: 16px;
      }

      .legal-git-word-preview-tab {
        padding: 8px 16px;
        background: #f8f9fa;
        border: 1px solid #dadce0;
        border-radius: 4px;
        font-size: 13px;
        cursor: pointer;
        transition: all 0.2s;
      }

      .legal-git-word-preview-tab.active {
        background: #0078d4;
        color: white;
        border-color: #0078d4;
      }

      .legal-git-word-preview-content {
        background: white;
        border: 1px solid #dadce0;
        border-radius: 4px;
        padding: 16px;
        font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
        font-size: 12px;
        line-height: 1.4;
        white-space: pre-wrap;
        max-height: 200px;
        overflow-y: auto;
      }

      .legal-git-word-settings {
        background: white;
        border: 1px solid #dadce0;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 20px;
      }

      .legal-git-word-settings h4 {
        margin: 0 0 16px 0;
        font-size: 14px;
        font-weight: 600;
        color: #1f1f1f;
      }

      .legal-git-word-setting-group {
        margin-bottom: 16px;
      }

      .legal-git-word-setting-group:last-child {
        margin-bottom: 0;
      }

      .legal-git-word-setting-label {
        display: block;
        font-size: 13px;
        font-weight: 500;
        color: #5f6368;
        margin-bottom: 6px;
      }

      .legal-git-word-setting-control {
        width: 100%;
        padding: 8px 12px;
        border: 1px solid #dadce0;
        border-radius: 4px;
        font-size: 13px;
        background: white;
      }

      .legal-git-word-setting-checkbox {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 13px;
        color: #1f1f1f;
      }

      .legal-git-word-toolbar {
        position: fixed;
        top: 100px;
        right: 20px;
        z-index: 15000;
        background: white;
        border: 2px solid #0078d4;
        border-radius: 8px;
        padding: 12px;
        box-shadow: 0 4px 16px rgba(0,0,0,0.1);
        font-family: 'Segoe UI', 'Google Sans', Roboto, Arial, sans-serif;
        font-size: 14px;
        display: none;
      }

      .legal-git-word-toolbar.visible {
        display: block;
      }

      .legal-git-word-toolbar-header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 12px;
        padding-bottom: 8px;
        border-bottom: 1px solid #e0e0e0;
      }

      .legal-git-word-toolbar-title {
        font-weight: 600;
        color: #0078d4;
      }

      .legal-git-word-toolbar-actions {
        display: flex;
        flex-direction: column;
        gap: 6px;
      }

      .legal-git-word-toolbar-btn {
        padding: 8px 12px;
        background: #0078d4;
        color: white;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        font-size: 12px;
        font-weight: 500;
        transition: all 0.2s;
        text-align: left;
      }

      .legal-git-word-toolbar-btn:hover {
        background: #106ebe;
        transform: translateY(-1px);
      }

      .legal-git-word-toolbar-btn.secondary {
        background: #f8f9fa;
        color: #5f6368;
        border: 1px solid #dadce0;
      }

      .legal-git-word-toolbar-btn.secondary:hover {
        background: #e9ecef;
      }

      .legal-git-word-status {
        font-size: 11px;
        color: #5f6368;
        margin-top: 8px;
        padding-top: 8px;
        border-top: 1px solid #e0e0e0;
      }

      .legal-git-word-notification {
        position: fixed;
        top: 20px;
        right: 20px;
        background: white;
        border: 1px solid #dadce0;
        border-radius: 8px;
        padding: 16px;
        box-shadow: 0 4px 16px rgba(0,0,0,0.1);
        z-index: 30000;
        max-width: 400px;
        display: flex;
        align-items: center;
        gap: 12px;
      }

      .legal-git-word-notification.success {
        border-left: 4px solid #107c10;
        background: #f3fffa;
      }

      .legal-git-word-notification.error {
        border-left: 4px solid #d13438;
        background: #fdf6f6;
      }

      .legal-git-word-notification.info {
        border-left: 4px solid #0078d4;
        background: #f3f9ff;
      }

      .legal-git-word-footer {
        padding: 20px 24px;
        border-top: 1px solid #e0e0e0;
        background: #f8f9fa;
        display: flex;
        justify-content: space-between;
        align-items: center;
      }

      .legal-git-word-footer-info {
        font-size: 13px;
        color: #5f6368;
      }

      .legal-git-word-footer-actions {
        display: flex;
        gap: 12px;
      }

      .legal-git-word-footer-btn {
        padding: 10px 20px;
        border: none;
        border-radius: 6px;
        font-size: 14px;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s;
      }

      .legal-git-word-footer-btn.primary {
        background: #0078d4;
        color: white;
      }

      .legal-git-word-footer-btn.secondary {
        background: #f8f9fa;
        color: #5f6368;
        border: 1px solid #dadce0;
      }

      .legal-git-word-footer-btn:hover {
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
      }

      .legal-git-word-footer-btn:disabled {
        opacity: 0.5;
        cursor: not-allowed;
        transform: none;
        box-shadow: none;
      }

      @keyframes wordDocPulse {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.05); }
      }

      .legal-git-word-detected {
        animation: wordDocPulse 2s infinite;
      }

      .legal-git-word-format-option.converting {
        opacity: 0.7;
        pointer-events: none;
      }

      .legal-git-word-format-option.converting::after {
        content: '⏳';
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        font-size: 24px;
      }
    `;

    document.head.appendChild(style);
  }

  // Detect Word documents on the page
  detectWordDocuments() {
    const currentUrl = window.location.href;

    // Office 365 Word Online detection
    if (currentUrl.includes('office.com') && currentUrl.includes('word')) {
      this.handleOfficeWordDetection();
    }

    // Google Docs with Word import detection
    if (currentUrl.includes('docs.google.com')) {
      this.handleGoogleDocsWordDetection();
    }

    // Local file detection (if accessible)
    this.handleLocalWordFileDetection();

    // Monitor for dynamic Word document loading
    this.setupWordDocumentMonitoring();
  }

  // Handle Office 365 Word Online detection
  handleOfficeWordDetection() {
    console.log('Office 365 Word document detected');

    const wordDoc = {
      id: this.generateDocumentId(),
      type: 'office365',
      url: window.location.href,
      title: this.extractOfficeWordTitle(),
      format: 'docx',
      detected: Date.now()
    };

    this.wordDocuments.set(wordDoc.id, wordDoc);
    this.activeWordDoc = wordDoc.id;

    // Inject Word-specific UI
    this.injectWordUI(wordDoc);

    // Dispatch detection event
    window.dispatchEvent(new CustomEvent('wordDocumentDetected', {
      detail: wordDoc
    }));
  }

  // Handle Google Docs with Word import
  handleGoogleDocsWordDetection() {
    // Check for Word import indicators
    const importIndicators = [
      '[data-tooltip*="docx"]',
      '[data-tooltip*="Word"]',
      '.docs-upload-dialog',
      '.docs-import-dialog'
    ];

    importIndicators.forEach(selector => {
      const element = document.querySelector(selector);
      if (element) {
        console.log('Google Docs Word import detected');
        this.handleWordImportToGoogleDocs();
      }
    });
  }

  // Handle local Word file detection
  handleLocalWordFileDetection() {
    // Check for file input elements that might handle Word files
    const fileInputs = document.querySelectorAll('input[type="file"]');

    fileInputs.forEach(input => {
      if (input.accept && (input.accept.includes('.docx') || input.accept.includes('.doc'))) {
        this.setupFileInputMonitoring(input);
      }
    });
  }

  // Setup Word document monitoring
  setupWordDocumentMonitoring() {
    // Monitor for title changes in Office 365
    if (window.location.hostname.includes('office.com')) {
      const titleObserver = new MutationObserver(() => {
        this.updateOfficeWordTitle();
      });

      const titleElement = document.querySelector('[data-automation-id="DocumentTitleTextBox"]') ||
                          document.querySelector('.od-DocumentTitle-title');

      if (titleElement) {
        titleObserver.observe(titleElement, {
          attributes: true,
          childList: true,
          subtree: true
        });
      }
    }

    // Monitor for content changes
    this.setupWordContentMonitoring();
  }

  // Setup Office 365 integration
  setupOfficeIntegration() {
    console.log('Setting up Office 365 integration');

    // Wait for Office to load
    setTimeout(() => {
      this.detectWordDocuments();
    }, 2000);

    // Monitor for Office app changes
    const officeObserver = new MutationObserver(() => {
      if (this.isOfficeWordPage()) {
        this.handleOfficeWordDetection();
      }
    });

    officeObserver.observe(document.body, {
      childList: true,
      subtree: true
    });
  }

  // Setup Google Docs Word integration
  setupGoogleDocsWordIntegration() {
    console.log('Setting up Google Docs Word integration');

    // Monitor for Word import dialogs
    const importObserver = new MutationObserver((mutations) => {
      mutations.forEach(mutation => {
        mutation.addedNodes.forEach(node => {
          if (node.nodeType === 1) { // Element node
            if (node.querySelector && (
                node.querySelector('[data-tooltip*="docx"]') ||
                node.querySelector('[data-tooltip*="Word"]')
            )) {
              this.handleWordImportToGoogleDocs();
            }
          }
        });
      });
    });

    importObserver.observe(document.body, {
      childList: true,
      subtree: true
    });
  }

  // Inject Word-specific UI
  injectWordUI(wordDoc) {
    if (this.wordUIInjected) return;

    const toolbar = document.createElement('div');
    toolbar.className = 'legal-git-word-toolbar visible';
    toolbar.id = 'legal-git-word-toolbar';

    toolbar.innerHTML = `
      <div class="legal-git-word-toolbar-header">
        <span>📝</span>
        <span class="legal-git-word-toolbar-title">Legal Git for Word</span>
      </div>

      <div class="legal-git-word-toolbar-actions">
        <button class="legal-git-word-toolbar-btn" onclick="window.wordDocumentHandler.showFormatSelectionModal('${wordDoc.id}')">
          Convert Format
        </button>
        <button class="legal-git-word-toolbar-btn" onclick="window.wordDocumentHandler.startWordTracking('${wordDoc.id}')">
          Start Tracking
        </button>
        <button class="legal-git-word-toolbar-btn secondary" onclick="window.wordDocumentHandler.exportWordDocument('${wordDoc.id}')">
          Export Document
        </button>
        <button class="legal-git-word-toolbar-btn secondary" onclick="window.wordDocumentHandler.showWordSettings('${wordDoc.id}')">
          Settings
        </button>
      </div>

      <div class="legal-git-word-status">
        Document: ${wordDoc.title}
        <br>Format: ${wordDoc.format.toUpperCase()}
      </div>
    `;

    document.body.appendChild(toolbar);
    this.wordUIInjected = true;

    // Make globally available
    window.wordDocumentHandler = this;
  }

  // Show format selection modal
  showFormatSelectionModal(wordDocId) {
    const wordDoc = this.wordDocuments.get(wordDocId);
    if (!wordDoc) return;

    const modal = this.createFormatSelectionModal(wordDoc);
    document.body.appendChild(modal);
  }

  // Create format selection modal
  createFormatSelectionModal(wordDoc) {
    const modal = document.createElement('div');
    modal.className = 'legal-git-word-container';
    modal.id = 'legal-git-word-format-modal';

    modal.innerHTML = `
      <div class="legal-git-word-modal">
        <div class="legal-git-word-header">
          <div class="legal-git-word-title">
            <span>📝</span>
            <span>Format Selection - ${wordDoc.title}</span>
          </div>
          <button class="legal-git-word-close" onclick="this.closest('.legal-git-word-container').remove()">×</button>
        </div>

        <div class="legal-git-word-content">
          <div class="legal-git-word-sidebar">
            ${this.generateWordDocumentInfo(wordDoc)}
            ${this.generateConversionSettings()}
          </div>

          <div class="legal-git-word-main">
            ${this.generateFormatSelector()}
            ${this.generateConversionPreview(wordDoc)}
          </div>
        </div>

        <div class="legal-git-word-footer">
          <div class="legal-git-word-footer-info">
            Select target format for version control integration
          </div>
          <div class="legal-git-word-footer-actions">
            <button class="legal-git-word-footer-btn secondary" onclick="this.closest('.legal-git-word-container').remove()">
              Cancel
            </button>
            <button class="legal-git-word-footer-btn primary" onclick="window.wordDocumentHandler.performFormatConversion('${wordDoc.id}')">
              Convert & Track
            </button>
          </div>
        </div>
      </div>
    `;

    this.setupFormatModalEvents(modal, wordDoc);
    return modal;
  }

  // Generate format selector
  generateFormatSelector() {
    return `
      <div class="legal-git-word-format-selector">
        <h4>🔄 Select Target Format</h4>
        <div class="legal-git-word-format-grid">
          ${this.supportedFormats.map(format => `
            <div class="legal-git-word-format-option" data-format="${format}" onclick="window.wordDocumentHandler.selectFormat('${format}')">
              <span class="legal-git-word-format-icon">${this.getFormatIcon(format)}</span>
              <div class="legal-git-word-format-name">${format.toUpperCase()}</div>
              <div class="legal-git-word-format-description">${this.getFormatDescription(format)}</div>
            </div>
          `).join('')}
        </div>
      </div>
    `;
  }

  // Generate document info
  generateWordDocumentInfo(wordDoc) {
    return `
      <div class="legal-git-word-document-info">
        <h4>📄 Document Information</h4>
        <div class="legal-git-word-info-item">
          <span class="legal-git-word-info-label">Title:</span>
          <span class="legal-git-word-info-value">${wordDoc.title}</span>
        </div>
        <div class="legal-git-word-info-item">
          <span class="legal-git-word-info-label">Current Format:</span>
          <span class="legal-git-word-info-value">${wordDoc.format.toUpperCase()}</span>
        </div>
        <div class="legal-git-word-info-item">
          <span class="legal-git-word-info-label">Source:</span>
          <span class="legal-git-word-info-value">${wordDoc.type}</span>
        </div>
        <div class="legal-git-word-info-item">
          <span class="legal-git-word-info-label">Detected:</span>
          <span class="legal-git-word-info-value">${this.formatTimeAgo(wordDoc.detected)}</span>
        </div>
      </div>
    `;
  }

  // Generate conversion settings
  generateConversionSettings() {
    return `
      <div class="legal-git-word-settings">
        <h4>⚙️ Conversion Settings</h4>
        <div class="legal-git-word-setting-group">
          <label class="legal-git-word-setting-label">Preserve Formatting</label>
          <label class="legal-git-word-setting-checkbox">
            <input type="checkbox" checked> Maintain styles and formatting
          </label>
        </div>
        <div class="legal-git-word-setting-group">
          <label class="legal-git-word-setting-label">Include Comments</label>
          <label class="legal-git-word-setting-checkbox">
            <input type="checkbox" checked> Convert comments to annotations
          </label>
        </div>
        <div class="legal-git-word-setting-group">
          <label class="legal-git-word-setting-label">Track Changes</label>
          <label class="legal-git-word-setting-checkbox">
            <input type="checkbox" checked> Preserve revision history
          </label>
        </div>
        <div class="legal-git-word-setting-group">
          <label class="legal-git-word-setting-label">Legal Metadata</label>
          <label class="legal-git-word-setting-checkbox">
            <input type="checkbox" checked> Extract legal document metadata
          </label>
        </div>
      </div>
    `;
  }

  // Generate conversion preview
  generateConversionPreview(wordDoc) {
    return `
      <div class="legal-git-word-conversion-preview">
        <div class="legal-git-word-conversion-header">
          <div class="legal-git-word-conversion-title">Conversion Preview</div>
          <button class="legal-git-word-footer-btn secondary" onclick="window.wordDocumentHandler.refreshPreview('${wordDoc.id}')">
            Refresh
          </button>
        </div>
        <div class="legal-git-word-conversion-content">
          <div class="legal-git-word-preview-tabs">
            <div class="legal-git-word-preview-tab active" data-tab="original">Original</div>
            <div class="legal-git-word-preview-tab" data-tab="converted">Converted</div>
            <div class="legal-git-word-preview-tab" data-tab="metadata">Metadata</div>
          </div>
          <div class="legal-git-word-preview-content" id="preview-content">
            ${this.generatePreviewContent('original', wordDoc)}
          </div>
        </div>
      </div>
    `;
  }

  // Generate preview content
  generatePreviewContent(tab, wordDoc) {
    switch (tab) {
      case 'original':
        return `Document Title: ${wordDoc.title}\nFormat: ${wordDoc.format}\nSource: ${wordDoc.type}\n\nOriginal document content will be displayed here...`;
      case 'converted':
        return `# ${wordDoc.title}\n\nConverted document content will be displayed here...\n\n## Section 1\nContent with preserved formatting...\n\n## Section 2\nMore content...`;
      case 'metadata':
        return `Document Metadata:\n- Title: ${wordDoc.title}\n- Author: [Extracted from document]\n- Created: [Document creation date]\n- Modified: [Last modification date]\n- Version: [Document version]\n- Legal Document Type: [Auto-detected]`;
      default:
        return 'Select a tab to view content...';
    }
  }

  // Get format icon
  getFormatIcon(format) {
    const icons = {
      'docx': '📄',
      'doc': '📝',
      'rtf': '📋',
      'odt': '📊',
      'txt': '📃',
      'md': '📑'
    };
    return icons[format] || '📄';
  }

  // Get format description
  getFormatDescription(format) {
    const descriptions = {
      'docx': 'Modern Word format with full feature support',
      'doc': 'Legacy Word format for compatibility',
      'rtf': 'Rich Text Format for cross-platform use',
      'odt': 'Open Document Text for open standards',
      'txt': 'Plain text for simple version tracking',
      'md': 'Markdown for developer-friendly format'
    };
    return descriptions[format] || 'Document format';
  }

  // Select format
  selectFormat(format) {
    // Remove previous selection
    document.querySelectorAll('.legal-git-word-format-option.selected').forEach(el => {
      el.classList.remove('selected');
    });

    // Add selection to clicked format
    const formatOption = document.querySelector(`[data-format="${format}"]`);
    if (formatOption) {
      formatOption.classList.add('selected');
    }

    // Update preview
    this.updateFormatPreview(format);
  }

  // Update format preview
  updateFormatPreview(format) {
    const previewContent = document.getElementById('preview-content');
    if (previewContent) {
      previewContent.textContent = `Converting to ${format.toUpperCase()}...\n\nPreview will show converted content in ${format} format.`;
    }
  }

  // Perform format conversion
  async performFormatConversion(wordDocId) {
    const wordDoc = this.wordDocuments.get(wordDocId);
    if (!wordDoc) return;

    const selectedFormat = document.querySelector('.legal-git-word-format-option.selected');
    if (!selectedFormat) {
      this.showWordNotification('Please select a target format', 'error');
      return;
    }

    const targetFormat = selectedFormat.dataset.format;

    try {
      // Show loading state
      selectedFormat.classList.add('converting');

      // Simulate conversion process
      await this.convertWordDocument(wordDoc, targetFormat);

      // Show success notification
      this.showWordNotification(`Document converted to ${targetFormat.toUpperCase()} successfully!`, 'success');

      // Close modal
      const modal = document.getElementById('legal-git-word-format-modal');
      if (modal) modal.remove();

      // Start tracking the converted document
      this.startWordTracking(wordDocId);

    } catch (error) {
      console.error('Error converting document:', error);
      this.showWordNotification('Error converting document: ' + error.message, 'error');
      selectedFormat.classList.remove('converting');
    }
  }

  // Convert Word document
  async convertWordDocument(wordDoc, targetFormat) {
    // Simulate document conversion
    return new Promise((resolve, reject) => {
      setTimeout(() => {
        // In real implementation, this would:
        // 1. Extract content from Word document
        // 2. Convert to target format
        // 3. Preserve formatting and metadata
        // 4. Handle legal document specifics

        console.log(`Converting ${wordDoc.title} from ${wordDoc.format} to ${targetFormat}`);

        // Update document record
        wordDoc.convertedFormat = targetFormat;
        wordDoc.conversionDate = Date.now();

        resolve({
          originalFormat: wordDoc.format,
          targetFormat: targetFormat,
          content: `Converted content in ${targetFormat} format`,
          metadata: {
            title: wordDoc.title,
            author: 'Document Author',
            convertedBy: 'Legal Git',
            conversionDate: new Date().toISOString()
          }
        });
      }, 2000);
    });
  }

  // Start Word tracking
  async startWordTracking(wordDocId) {
    const wordDoc = this.wordDocuments.get(wordDocId);
    if (!wordDoc) return;

    try {
      console.log('Starting Word document tracking:', wordDoc);

      // Initialize git tracking for Word document
      if (this.gitOpsManager) {
        await this.gitOpsManager.initRepository({
          fileId: wordDocId,
          fileName: wordDoc.title,
          pageType: 'word',
          format: wordDoc.convertedFormat || wordDoc.format
        });
      }

      // Show success notification
      this.showWordNotification('Word document tracking started successfully!', 'success');

      // Update toolbar status
      this.updateWordToolbarStatus(wordDocId, 'tracked');

    } catch (error) {
      console.error('Error starting Word tracking:', error);
      this.showWordNotification('Error starting tracking: ' + error.message, 'error');
    }
  }

  // Export Word document
  exportWordDocument(wordDocId) {
    const wordDoc = this.wordDocuments.get(wordDocId);
    if (!wordDoc) return;

    this.showWordNotification('Exporting Word document...', 'info');

    // Simulate export process
    setTimeout(() => {
      this.showWordNotification('Document exported successfully!', 'success');
    }, 1000);
  }

  // Show Word settings
  showWordSettings(wordDocId) {
    this.showWordNotification('Word settings panel opening...', 'info');
  }

  // Refresh preview
  refreshPreview(wordDocId) {
    const previewContent = document.getElementById('preview-content');
    if (previewContent) {
      previewContent.textContent = 'Refreshing preview...';

      setTimeout(() => {
        const activeTab = document.querySelector('.legal-git-word-preview-tab.active');
        if (activeTab) {
          const wordDoc = this.wordDocuments.get(wordDocId);
          previewContent.textContent = this.generatePreviewContent(activeTab.dataset.tab, wordDoc);
        }
      }, 500);
    }
  }

  // Setup format modal events
  setupFormatModalEvents(modal, wordDoc) {
    // Tab switching
    const tabs = modal.querySelectorAll('.legal-git-word-preview-tab');
    tabs.forEach(tab => {
      tab.addEventListener('click', () => {
        tabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');

        const previewContent = modal.querySelector('#preview-content');
        if (previewContent) {
          previewContent.textContent = this.generatePreviewContent(tab.dataset.tab, wordDoc);
        }
      });
    });

    // Keyboard navigation
    modal.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        modal.remove();
      }
    });
  }

  // Update Word toolbar status
  updateWordToolbarStatus(wordDocId, status) {
    const statusElement = document.querySelector('.legal-git-word-status');
    if (statusElement) {
      const wordDoc = this.wordDocuments.get(wordDocId);
      statusElement.innerHTML = `
        Document: ${wordDoc.title}
        <br>Format: ${(wordDoc.convertedFormat || wordDoc.format).toUpperCase()}
        <br>Status: ${status}
      `;
    }
  }

  // Show Word notification
  showWordNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `legal-git-word-notification ${type}`;
    notification.innerHTML = `
      <div style="font-size: 24px;">
        ${type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️'}
      </div>
      <div>
        <div style="font-weight: 600; margin-bottom: 4px;">
          ${type === 'success' ? 'Success' : type === 'error' ? 'Error' : 'Info'}
        </div>
        <div style="font-size: 13px; color: #5f6368;">${message}</div>
      </div>
    `;

    document.body.appendChild(notification);

    setTimeout(() => {
      if (notification.parentNode) {
        notification.remove();
      }
    }, 5000);
  }

  // Helper methods
  generateDocumentId() {
    return `word_doc_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  extractOfficeWordTitle() {
    const titleElement = document.querySelector('[data-automation-id="DocumentTitleTextBox"]') ||
                        document.querySelector('.od-DocumentTitle-title') ||
                        document.querySelector('title');

    return titleElement ? titleElement.textContent || titleElement.value || 'Untitled Document' : 'Word Document';
  }

  updateOfficeWordTitle() {
    if (this.activeWordDoc) {
      const wordDoc = this.wordDocuments.get(this.activeWordDoc);
      if (wordDoc) {
        wordDoc.title = this.extractOfficeWordTitle();
        this.updateWordToolbarStatus(this.activeWordDoc, 'updated');
      }
    }
  }

  isOfficeWordPage() {
    return window.location.href.includes('office.com') &&
           (window.location.href.includes('word') || document.querySelector('[data-automation-id="DocumentTitleTextBox"]'));
  }

  handleWordImportToGoogleDocs() {
    console.log('Word import to Google Docs detected');

    // Create a special Word document entry for imported docs
    const wordDoc = {
      id: this.generateDocumentId(),
      type: 'google_docs_import',
      url: window.location.href,
      title: 'Imported Word Document',
      format: 'docx',
      detected: Date.now()
    };

    this.wordDocuments.set(wordDoc.id, wordDoc);
    this.showWordNotification('Word document import detected. Click to enable tracking.', 'info');
  }

  setupFileInputMonitoring(input) {
    input.addEventListener('change', (event) => {
      const files = event.target.files;
      for (let file of files) {
        if (this.isWordFile(file)) {
          this.handleLocalWordFile(file);
        }
      }
    });
  }

  setupWordContentMonitoring() {
    // Monitor for content changes in Word documents
    if (this.activeWordDoc) {
      const contentObserver = new MutationObserver(() => {
        this.handleWordContentChange();
      });

      // Office 365 content area
      const contentArea = document.querySelector('[data-automation-id="contentHost"]') ||
                         document.querySelector('.docs-texteventtarget-iframe');

      if (contentArea) {
        contentObserver.observe(contentArea, {
          childList: true,
          subtree: true,
          characterData: true
        });
      }
    }
  }

  handleWordContentChange() {
    if (this.activeWordDoc) {
      console.log('Word document content changed');
      // This could trigger change tracking similar to Google Docs
    }
  }

  isWordFile(file) {
    const wordExtensions = ['doc', 'docx', 'rtf'];
    const extension = file.name.split('.').pop().toLowerCase();
    return wordExtensions.includes(extension);
  }

  handleLocalWordFile(file) {
    console.log('Local Word file detected:', file.name);

    const wordDoc = {
      id: this.generateDocumentId(),
      type: 'local_file',
      file: file,
      title: file.name,
      format: file.name.split('.').pop().toLowerCase(),
      detected: Date.now()
    };

    this.wordDocuments.set(wordDoc.id, wordDoc);
    this.showWordNotification(`Word file detected: ${file.name}`, 'info');
  }

  handleWordDocumentDetected(wordDoc) {
    console.log('Word document detected event:', wordDoc);
    this.injectWordUI(wordDoc);
  }

  handleWordDocumentOpened(wordDoc) {
    console.log('Word document opened event:', wordDoc);
    this.activeWordDoc = wordDoc.id;
    this.setupWordContentMonitoring();
  }

  formatTimeAgo(timestamp) {
    const now = Date.now();
    const diffMs = now - timestamp;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);

    if (diffMins < 60) {
      return `${diffMins}m ago`;
    } else {
      return `${diffHours}h ago`;
    }
  }
}

// Export for use in other scripts
window.WordDocumentHandler = WordDocumentHandler;
