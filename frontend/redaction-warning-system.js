// Legal Git Chrome Extension - Redaction Warning System
// Handles detection and warnings for sensitive information in legal documents

class RedactionWarningSystem {
  constructor(documentConverter, changeTracker) {
    this.documentConverter = documentConverter;
    this.changeTracker = changeTracker;
    this.sensitivePatterns = new Map();
    this.redactionWarnings = new Map();
    this.warningCategories = new Map();
    this.warningHistory = new Map();
    this.autoRedactionEnabled = false;
    this.warningLevel = 'medium'; // low, medium, high
    this.init();
  }

  init() {
    this.setupSensitivePatterns();
    this.setupWarningCategories();
    this.setupRedactionEventListeners();
    this.injectRedactionStyles();
  }

  // Setup sensitive information patterns
  setupSensitivePatterns() {
    // Social Security Numbers
    this.sensitivePatterns.set('ssn', {
      pattern: /\b\d{3}-\d{2}-\d{4}\b|\b\d{9}\b/g,
      category: 'pii',
      severity: 'high',
      description: 'Social Security Number',
      suggestion: 'Replace with XXX-XX-XXXX or [SSN REDACTED]',
      color: '#d32f2f'
    });

    // Credit Card Numbers
    this.sensitivePatterns.set('credit_card', {
      pattern: /\b(?:\d{4}[-\s]?){3}\d{4}\b/g,
      category: 'financial',
      severity: 'high',
      description: 'Credit Card Number',
      suggestion: 'Replace with XXXX-XXXX-XXXX-XXXX or [CARD REDACTED]',
      color: '#d32f2f'
    });

    // Phone Numbers
    this.sensitivePatterns.set('phone', {
      pattern: /\b\d{3}[-.]?\d{3}[-.]?\d{4}\b|\(\d{3}\)\s?\d{3}[-.]?\d{4}/g,
      category: 'pii',
      severity: 'medium',
      description: 'Phone Number',
      suggestion: 'Replace with XXX-XXX-XXXX or [PHONE REDACTED]',
      color: '#f57c00'
    });

    // Email Addresses
    this.sensitivePatterns.set('email', {
      pattern: /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/g,
      category: 'pii',
      severity: 'medium',
      description: 'Email Address',
      suggestion: 'Replace with [EMAIL REDACTED] or use initials',
      color: '#f57c00'
    });

    // Bank Account Numbers
    this.sensitivePatterns.set('bank_account', {
      pattern: /\b\d{8,17}\b/g,
      category: 'financial',
      severity: 'high',
      description: 'Potential Bank Account Number',
      suggestion: 'Replace with [ACCOUNT REDACTED]',
      color: '#d32f2f'
    });

    // Addresses
    this.sensitivePatterns.set('address', {
      pattern: /\b\d+\s+[A-Za-z\s]+(Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd|Circle|Cir|Court|Ct)\b/gi,
      category: 'pii',
      severity: 'medium',
      description: 'Street Address',
      suggestion: 'Replace with [ADDRESS REDACTED] or use city/state only',
      color: '#f57c00'
    });

    // Driver's License Numbers
    this.sensitivePatterns.set('drivers_license', {
      pattern: /\b[A-Z]\d{7,8}\b|\b\d{8,9}\b/g,
      category: 'pii',
      severity: 'high',
      description: 'Potential Driver\'s License Number',
      suggestion: 'Replace with [LICENSE REDACTED]',
      color: '#d32f2f'
    });

    // Legal Case Numbers
    this.sensitivePatterns.set('case_number', {
      pattern: /\b\d{2}-[A-Z]{2}-\d{6}\b|\bCase\s+No\.?\s*\d+[-\w]*\b/gi,
      category: 'legal',
      severity: 'medium',
      description: 'Case Number',
      suggestion: 'Consider if case number should be public',
      color: '#f57c00'
    });

    // Attorney-Client Privileged Communications
    this.sensitivePatterns.set('attorney_client', {
      pattern: /attorney[- ]client\s+privilege|privileged\s+communication|confidential\s+legal/gi,
      category: 'legal',
      severity: 'high',
      description: 'Attorney-Client Privileged Content',
      suggestion: 'Ensure privilege is protected in shared documents',
      color: '#d32f2f'
    });

    // Medical Information
    this.sensitivePatterns.set('medical', {
      pattern: /medical\s+records?|health\s+information|diagnosis|prescription|HIPAA/gi,
      category: 'medical',
      severity: 'high',
      description: 'Medical Information',
      suggestion: 'Ensure HIPAA compliance for medical data',
      color: '#d32f2f'
    });

    // Financial Information
    this.sensitivePatterns.set('financial_terms', {
      pattern: /\$[\d,]+(?:\.\d{2})?|\b\d+\s+dollars?\b|salary|income|revenue|profit/gi,
      category: 'financial',
      severity: 'low',
      description: 'Financial Information',
      suggestion: 'Consider if financial details should be disclosed',
      color: '#2e7d32'
    });
  }

  // Setup warning categories
  setupWarningCategories() {
    this.warningCategories.set('pii', {
      name: 'Personal Information',
      icon: '👤',
      color: '#f57c00',
      description: 'Information that can identify individuals'
    });

    this.warningCategories.set('financial', {
      name: 'Financial Data',
      icon: '💳',
      color: '#d32f2f',
      description: 'Financial account numbers and monetary information'
    });

    this.warningCategories.set('legal', {
      name: 'Legal Content',
      icon: '⚖️',
      color: '#f57c00',
      description: 'Privileged or sensitive legal information'
    });

    this.warningCategories.set('medical', {
      name: 'Medical Information',
      icon: '🏥',
      color: '#d32f2f',
      description: 'Protected health information (PHI)'
    });
  }

  // Setup event listeners for redaction warnings
  setupRedactionEventListeners() {
    window.addEventListener('documentContentChanged', (event) => {
      this.scanForSensitiveInformation(event.detail);
    });

    window.addEventListener('legalGitShowRedactionWarnings', (event) => {
      this.showRedactionWarningsModal(event.detail);
    });

    window.addEventListener('redactionRequested', (event) => {
      this.performRedaction(event.detail);
    });

    // Monitor document changes for real-time scanning
    this.setupDocumentMonitoring();
  }

  // Inject CSS styles for redaction warnings
  injectRedactionStyles() {
    const styleId = 'legal-git-redaction-styles';
    if (document.getElementById(styleId)) return;

    const style = document.createElement('style');
    style.id = styleId;
    style.textContent = `
      .legal-git-redaction-container {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.85);
        z-index: 28000;
        display: flex;
        align-items: center;
        justify-content: center;
        font-family: 'Google Sans', Roboto, Arial, sans-serif;
      }

      .legal-git-redaction-modal {
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

      .legal-git-redaction-header {
        padding: 20px 24px;
        border-bottom: 2px solid #ff5722;
        background: linear-gradient(135deg, #fff3e0, #ffe0b2);
        display: flex;
        justify-content: space-between;
        align-items: center;
      }

      .legal-git-redaction-title {
        font-size: 20px;
        font-weight: 600;
        color: #ff5722;
        display: flex;
        align-items: center;
        gap: 12px;
      }

      .legal-git-redaction-close {
        background: none;
        border: none;
        font-size: 28px;
        cursor: pointer;
        color: #5f6368;
        padding: 8px;
        border-radius: 6px;
        transition: all 0.2s;
      }

      .legal-git-redaction-close:hover {
        background: #f1f3f4;
        transform: scale(1.1);
      }

      .legal-git-redaction-content {
        flex: 1;
        display: flex;
        overflow: hidden;
      }

      .legal-git-redaction-sidebar {
        width: 320px;
        background: #f8f9fa;
        border-right: 1px solid #e0e0e0;
        overflow-y: auto;
        padding: 20px;
      }

      .legal-git-redaction-main {
        flex: 1;
        overflow-y: auto;
        padding: 20px 24px;
      }

      .legal-git-warning-summary {
        background: white;
        border: 1px solid #dadce0;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 16px;
      }

      .legal-git-warning-summary.high {
        border-left: 4px solid #d32f2f;
        background: #ffebee;
      }

      .legal-git-warning-summary.medium {
        border-left: 4px solid #f57c00;
        background: #fff8e1;
      }

      .legal-git-warning-summary.low {
        border-left: 4px solid #2e7d32;
        background: #e8f5e8;
      }

      .legal-git-warning-summary h4 {
        margin: 0 0 12px 0;
        font-size: 14px;
        font-weight: 600;
        color: #1f1f1f;
        display: flex;
        align-items: center;
        gap: 8px;
      }

      .legal-git-warning-count {
        background: #ff5722;
        color: white;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 600;
      }

      .legal-git-warning-stat {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 6px 0;
        font-size: 13px;
        border-bottom: 1px solid #f0f0f0;
      }

      .legal-git-warning-stat:last-child {
        border-bottom: none;
      }

      .legal-git-warning-stat-label {
        color: #5f6368;
      }

      .legal-git-warning-stat-value {
        font-weight: 600;
      }

      .legal-git-warning-stat-value.high {
        color: #d32f2f;
      }

      .legal-git-warning-stat-value.medium {
        color: #f57c00;
      }

      .legal-git-warning-stat-value.low {
        color: #2e7d32;
      }

      .legal-git-warning-list {
        background: white;
        border: 1px solid #dadce0;
        border-radius: 8px;
        overflow: hidden;
      }

      .legal-git-warning-item {
        padding: 16px;
        border-bottom: 1px solid #f0f0f0;
        transition: background 0.2s;
        cursor: pointer;
      }

      .legal-git-warning-item:hover {
        background: #f8f9fa;
      }

      .legal-git-warning-item:last-child {
        border-bottom: none;
      }

      .legal-git-warning-item.high {
        border-left: 4px solid #d32f2f;
      }

      .legal-git-warning-item.medium {
        border-left: 4px solid #f57c00;
      }

      .legal-git-warning-item.low {
        border-left: 4px solid #2e7d32;
      }

      .legal-git-warning-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 8px;
      }

      .legal-git-warning-type {
        font-size: 14px;
        font-weight: 600;
        color: #1f1f1f;
        display: flex;
        align-items: center;
        gap: 6px;
      }

      .legal-git-warning-severity {
        font-size: 11px;
        padding: 2px 6px;
        border-radius: 10px;
        font-weight: 600;
        text-transform: uppercase;
      }

      .legal-git-warning-severity.high {
        background: #ffcdd2;
        color: #d32f2f;
      }

      .legal-git-warning-severity.medium {
        background: #ffe0b2;
        color: #f57c00;
      }

      .legal-git-warning-severity.low {
        background: #c8e6c9;
        color: #2e7d32;
      }

      .legal-git-warning-content {
        font-size: 13px;
        color: #5f6368;
        margin-bottom: 8px;
        font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
        background: #f8f9fa;
        padding: 8px;
        border-radius: 4px;
        word-break: break-all;
      }

      .legal-git-warning-suggestion {
        font-size: 12px;
        color: #1f1f1f;
        margin-bottom: 12px;
        line-height: 1.4;
      }

      .legal-git-warning-actions {
        display: flex;
        gap: 8px;
      }

      .legal-git-warning-btn {
        padding: 6px 12px;
        border: 1px solid #dadce0;
        border-radius: 4px;
        font-size: 11px;
        cursor: pointer;
        transition: all 0.2s;
        font-weight: 500;
      }

      .legal-git-warning-btn.redact {
        background: #d32f2f;
        color: white;
        border-color: #d32f2f;
      }

      .legal-git-warning-btn.redact:hover {
        background: #c62828;
      }

      .legal-git-warning-btn.ignore {
        background: #f8f9fa;
        color: #5f6368;
      }

      .legal-git-warning-btn.ignore:hover {
        background: #e9ecef;
      }

      .legal-git-warning-btn.highlight {
        background: #fff3e0;
        color: #ff5722;
        border-color: #ff5722;
      }

      .legal-git-warning-btn.highlight:hover {
        background: #ffe0b2;
      }

      .legal-git-redaction-settings {
        background: white;
        border: 1px solid #dadce0;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 16px;
      }

      .legal-git-redaction-settings h4 {
        margin: 0 0 12px 0;
        font-size: 14px;
        font-weight: 600;
        color: #1f1f1f;
      }

      .legal-git-setting-option {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 6px 0;
        font-size: 13px;
      }

      .legal-git-sensitivity-slider {
        width: 100%;
        margin: 8px 0;
      }

      .legal-git-redaction-preview {
        background: #f8f9fa;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        overflow: hidden;
        margin-bottom: 20px;
      }

      .legal-git-redaction-preview-header {
        padding: 16px 20px;
        background: #f8f9fa;
        border-bottom: 1px solid #e0e0e0;
        display: flex;
        justify-content: space-between;
        align-items: center;
      }

      .legal-git-redaction-preview-title {
        font-size: 16px;
        font-weight: 600;
        color: #1f1f1f;
      }

      .legal-git-redaction-preview-content {
        padding: 20px;
        max-height: 300px;
        overflow-y: auto;
        font-family: 'Times New Roman', serif;
        line-height: 1.6;
      }

      .legal-git-sensitive-highlight {
        background: rgba(255, 87, 34, 0.2);
        border-bottom: 2px solid #ff5722;
        padding: 2px 4px;
        border-radius: 2px;
        position: relative;
        cursor: pointer;
      }

      .legal-git-sensitive-highlight.high {
        background: rgba(211, 47, 47, 0.3);
        border-bottom-color: #d32f2f;
      }

      .legal-git-sensitive-highlight.medium {
        background: rgba(245, 124, 0, 0.2);
        border-bottom-color: #f57c00;
      }

      .legal-git-sensitive-highlight.low {
        background: rgba(46, 125, 50, 0.2);
        border-bottom-color: #2e7d32;
      }

      .legal-git-sensitive-tooltip {
        position: absolute;
        bottom: 100%;
        left: 50%;
        transform: translateX(-50%);
        background: #333;
        color: white;
        padding: 6px 8px;
        border-radius: 4px;
        font-size: 11px;
        white-space: nowrap;
        z-index: 1000;
        opacity: 0;
        pointer-events: none;
        transition: opacity 0.2s;
      }

      .legal-git-sensitive-highlight:hover .legal-git-sensitive-tooltip {
        opacity: 1;
      }

      .legal-git-redacted-text {
        background: #000;
        color: transparent;
        user-select: none;
        padding: 2px 4px;
        border-radius: 2px;
        position: relative;
      }

      .legal-git-redacted-text::after {
        content: '[REDACTED]';
        color: #666;
        font-size: 10px;
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
      }

      .legal-git-warning-notification {
        position: fixed;
        top: 20px;
        right: 20px;
        background: white;
        border: 1px solid #dadce0;
        border-left: 4px solid #ff5722;
        border-radius: 8px;
        padding: 16px;
        box-shadow: 0 4px 16px rgba(0,0,0,0.1);
        z-index: 30000;
        max-width: 400px;
        animation: warningSlideIn 0.3s ease-out;
      }

      @keyframes warningSlideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
      }

      .legal-git-warning-notification-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
      }

      .legal-git-warning-notification-title {
        font-weight: 600;
        color: #ff5722;
        font-size: 14px;
      }

      .legal-git-warning-notification-close {
        background: none;
        border: none;
        font-size: 16px;
        cursor: pointer;
        color: #5f6368;
        padding: 2px;
      }

      .legal-git-warning-notification-content {
        font-size: 13px;
        color: #5f6368;
        line-height: 1.4;
        margin-bottom: 12px;
      }

      .legal-git-warning-notification-actions {
        display: flex;
        gap: 8px;
      }

      .legal-git-warning-notification-btn {
        padding: 6px 12px;
        border: 1px solid #dadce0;
        border-radius: 4px;
        font-size: 11px;
        cursor: pointer;
        transition: all 0.2s;
        font-weight: 500;
      }

      .legal-git-warning-notification-btn.primary {
        background: #ff5722;
        color: white;
        border-color: #ff5722;
      }

      .legal-git-warning-notification-btn.secondary {
        background: white;
        color: #5f6368;
      }

      .legal-git-footer {
        padding: 20px 24px;
        border-top: 1px solid #e0e0e0;
        background: #f8f9fa;
        display: flex;
        justify-content: space-between;
        align-items: center;
      }

      .legal-git-footer-info {
        font-size: 13px;
        color: #5f6368;
      }

      .legal-git-footer-actions {
        display: flex;
        gap: 12px;
      }

      .legal-git-footer-btn {
        padding: 10px 20px;
        border: none;
        border-radius: 6px;
        font-size: 14px;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s;
      }

      .legal-git-footer-btn.primary {
        background: #ff5722;
        color: white;
      }

      .legal-git-footer-btn.secondary {
        background: #f8f9fa;
        color: #5f6368;
        border: 1px solid #dadce0;
      }

      .legal-git-footer-btn:hover {
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
      }

      .legal-git-footer-btn:disabled {
        opacity: 0.5;
        cursor: not-allowed;
        transform: none;
        box-shadow: none;
      }
    `;

    document.head.appendChild(style);
  }

  // Setup document monitoring for real-time scanning
  setupDocumentMonitoring() {
    // Monitor for document changes in Google Docs
    if (window.location.hostname === 'docs.google.com') {
      this.setupGoogleDocsMonitoring();
    }

    // Monitor for document changes in Office 365
    if (window.location.hostname.includes('office.com')) {
      this.setupOfficeMonitoring();
    }
  }

  // Setup Google Docs monitoring
  setupGoogleDocsMonitoring() {
    const docsContentArea = document.querySelector('.docs-texteventtarget-iframe') ||
                           document.querySelector('[role="textbox"]');

    if (docsContentArea) {
      const observer = new MutationObserver(() => {
        this.debouncedScan();
      });

      observer.observe(docsContentArea, {
        childList: true,
        subtree: true,
        characterData: true
      });
    }
  }

  // Setup Office 365 monitoring
  setupOfficeMonitoring() {
    const officeContentArea = document.querySelector('[data-automation-id="contentHost"]') ||
                             document.querySelector('.Canvas');

    if (officeContentArea) {
      const observer = new MutationObserver(() => {
        this.debouncedScan();
      });

      observer.observe(officeContentArea, {
        childList: true,
        subtree: true,
        characterData: true
      });
    }
  }

  // Debounced scan to prevent excessive scanning
  debouncedScan = this.debounce(() => {
    this.scanCurrentDocument();
  }, 2000);

  // Scan for sensitive information in document
  scanForSensitiveInformation(documentData) {
    const { documentId, content } = documentData;

    if (!content || !content.body) return;

    const textContent = this.extractTextContent(content.body);
    const warnings = this.detectSensitivePatterns(textContent, documentId);

    if (warnings.length > 0) {
      this.redactionWarnings.set(documentId, warnings);
      this.showWarningNotification(warnings.length, documentId);
    }
  }

  // Scan current document for sensitive information
  scanCurrentDocument() {
    const documentContent = this.extractCurrentDocumentContent();
    if (!documentContent) return;

    const documentId = this.getCurrentDocumentId();
    const warnings = this.detectSensitivePatterns(documentContent, documentId);

    if (warnings.length > 0) {
      this.redactionWarnings.set(documentId, warnings);
      this.updateRedactionIndicators(warnings);
    }
  }

  // Extract current document content
  extractCurrentDocumentContent() {
    let content = '';

    // Google Docs
    if (window.location.hostname === 'docs.google.com') {
      const docsContent = document.querySelector('.docs-texteventtarget-iframe');
      if (docsContent) {
        content = docsContent.textContent || '';
      }
    }

    // Office 365
    if (window.location.hostname.includes('office.com')) {
      const officeContent = document.querySelector('[data-automation-id="contentHost"]');
      if (officeContent) {
        content = officeContent.textContent || '';
      }
    }

    return content;
  }

  // Get current document ID
  getCurrentDocumentId() {
    // Google Docs
    if (window.location.hostname === 'docs.google.com') {
      const pathParts = window.location.pathname.split('/');
      const docIndex = pathParts.indexOf('d') + 1;
      return pathParts[docIndex] || 'current_doc';
    }

    // Office 365
    if (window.location.hostname.includes('office.com')) {
      return window.location.pathname.split('/').pop() || 'current_doc';
    }

    return 'current_doc';
  }

  // Extract text content from document body
  extractTextContent(body) {
    if (typeof body === 'string') {
      return body;
    }

    if (body && body.content) {
      return body.content;
    }

    return '';
  }

  // Detect sensitive patterns in text
  detectSensitivePatterns(text, documentId) {
    const warnings = [];

    this.sensitivePatterns.forEach((patternInfo, patternKey) => {
      const matches = text.match(patternInfo.pattern);

      if (matches) {
        matches.forEach((match, index) => {
          const warning = {
            id: `${patternKey}_${documentId}_${index}`,
            type: patternKey,
            content: match,
            position: text.indexOf(match),
            severity: patternInfo.severity,
            category: patternInfo.category,
            description: patternInfo.description,
            suggestion: patternInfo.suggestion,
            color: patternInfo.color,
            documentId: documentId,
            detected: Date.now(),
            status: 'pending' // pending, ignored, redacted
          };
          warnings.push(warning);
        });
      }
    });

    return warnings;
  }

  // Show warning notification
  showWarningNotification(warningCount, documentId) {
    // Don't show notifications for low-level warnings if setting is configured
    const severeCounts = this.getSevereWarningCounts(documentId);
    if (severeCounts.high === 0 && severeCounts.medium === 0 && this.warningLevel === 'high') {
      return;
    }

    const notification = document.createElement('div');
    notification.className = 'legal-git-warning-notification';
    notification.innerHTML = `
      <div class="legal-git-warning-notification-header">
        <div class="legal-git-warning-notification-title">
          ⚠️ Sensitive Information Detected
        </div>
        <button class="legal-git-warning-notification-close" onclick="this.parentElement.parentElement.remove()">×</button>
      </div>
      <div class="legal-git-warning-notification-content">
        Found ${warningCount} potential sensitive information instances that may need redaction before sharing.
      </div>
      <div class="legal-git-warning-notification-actions">
        <button class="legal-git-warning-notification-btn primary" onclick="window.redactionWarningSystem.showRedactionWarningsModal('${documentId}'); this.parentElement.parentElement.parentElement.remove();">
          Review Warnings
        </button>
        <button class="legal-git-warning-notification-btn secondary" onclick="this.parentElement.parentElement.remove();">
          Dismiss
        </button>
      </div>
    `;

    document.body.appendChild(notification);

    // Auto-remove after 10 seconds
    setTimeout(() => {
      if (notification.parentNode) {
        notification.remove();
      }
    }, 10000);
  }

  // Get severe warning counts
  getSevereWarningCounts(documentId) {
    const warnings = this.redactionWarnings.get(documentId) || [];
    return {
      high: warnings.filter(w => w.severity === 'high').length,
      medium: warnings.filter(w => w.severity === 'medium').length,
      low: warnings.filter(w => w.severity === 'low').length
    };
  }

  // Show redaction warnings modal
  showRedactionWarningsModal(documentId) {
    const warnings = this.redactionWarnings.get(documentId) || [];
    if (warnings.length === 0) {
      this.showRedactionNotification('No warnings found for this document.', 'info');
      return;
    }

    const modal = this.createRedactionWarningsModal(documentId, warnings);
    document.body.appendChild(modal);
  }

  // Create redaction warnings modal
  createRedactionWarningsModal(documentId, warnings) {
    const modal = document.createElement('div');
    modal.className = 'legal-git-redaction-container';
    modal.id = 'legal-git-redaction-warnings';

    const severityCounts = this.getSevereWarningCounts(documentId);

    modal.innerHTML = `
      <div class="legal-git-redaction-modal">
        <div class="legal-git-redaction-header">
          <div class="legal-git-redaction-title">
            <span>🔍</span>
            <span>Redaction Warnings</span>
            <span class="legal-git-warning-count">${warnings.length}</span>
          </div>
          <button class="legal-git-redaction-close" onclick="this.closest('.legal-git-redaction-container').remove()">×</button>
        </div>

        <div class="legal-git-redaction-content">
          <div class="legal-git-redaction-sidebar">
            ${this.generateWarningSummary(severityCounts)}
            ${this.generateRedactionSettings()}
          </div>

          <div class="legal-git-redaction-main">
            ${this.generateRedactionPreview(documentId, warnings)}
            ${this.generateWarningsList(warnings)}
          </div>
        </div>

        <div class="legal-git-footer">
          <div class="legal-git-footer-info">
            Review and handle ${warnings.length} potential sensitive information instances
          </div>
          <div class="legal-git-footer-actions">
            <button class="legal-git-footer-btn secondary" onclick="window.redactionWarningSystem.redactAll('${documentId}')">
              Redact All High Risk
            </button>
            <button class="legal-git-footer-btn primary" onclick="window.redactionWarningSystem.generateRedactionReport('${documentId}')">
              Generate Report
            </button>
          </div>
        </div>
      </div>
    `;

    this.setupRedactionModalEvents(modal, documentId);
    return modal;
  }

  // Generate warning summary
  generateWarningSummary(severityCounts) {
    const total = severityCounts.high + severityCounts.medium + severityCounts.low;
    const severityClass = severityCounts.high > 0 ? 'high' :
                         severityCounts.medium > 0 ? 'medium' : 'low';

    return `
      <div class="legal-git-warning-summary ${severityClass}">
        <h4>⚠️ Warning Summary</h4>
        <div class="legal-git-warning-stat">
          <span class="legal-git-warning-stat-label">Total Warnings:</span>
          <span class="legal-git-warning-stat-value">${total}</span>
        </div>
        <div class="legal-git-warning-stat">
          <span class="legal-git-warning-stat-label">High Risk:</span>
          <span class="legal-git-warning-stat-value high">${severityCounts.high}</span>
        </div>
        <div class="legal-git-warning-stat">
          <span class="legal-git-warning-stat-label">Medium Risk:</span>
          <span class="legal-git-warning-stat-value medium">${severityCounts.medium}</span>
        </div>
        <div class="legal-git-warning-stat">
          <span class="legal-git-warning-stat-label">Low Risk:</span>
          <span class="legal-git-warning-stat-value low">${severityCounts.low}</span>
        </div>
      </div>
    `;
  }

  // Generate redaction settings
  generateRedactionSettings() {
    return `
      <div class="legal-git-redaction-settings">
        <h4>⚙️ Settings</h4>
        <div class="legal-git-setting-option">
          <input type="checkbox" id="auto-redaction" ${this.autoRedactionEnabled ? 'checked' : ''}>
          <label for="auto-redaction">Auto-redact high risk items</label>
        </div>
        <div class="legal-git-setting-option">
          <input type="checkbox" id="real-time-scan" checked>
          <label for="real-time-scan">Real-time scanning</label>
        </div>
        <div class="legal-git-setting-option">
          <label>Warning Sensitivity:</label>
          <select class="legal-git-filter-select" onchange="window.redactionWarningSystem.updateSensitivity(this.value)">
            <option value="low" ${this.warningLevel === 'low' ? 'selected' : ''}>Low</option>
            <option value="medium" ${this.warningLevel === 'medium' ? 'selected' : ''}>Medium</option>
            <option value="high" ${this.warningLevel === 'high' ? 'selected' : ''}>High</option>
          </select>
        </div>
      </div>
    `;
  }

  // Generate redaction preview
  generateRedactionPreview(documentId, warnings) {
    const documentContent = this.extractCurrentDocumentContent();
    const highlightedContent = this.highlightSensitiveContent(documentContent, warnings);

    return `
      <div class="legal-git-redaction-preview">
        <div class="legal-git-redaction-preview-header">
          <div class="legal-git-redaction-preview-title">Document Preview with Highlights</div>
          <button class="legal-git-footer-btn secondary" onclick="window.redactionWarningSystem.refreshPreview('${documentId}')">
            Refresh
          </button>
        </div>
        <div class="legal-git-redaction-preview-content">
          ${highlightedContent}
        </div>
      </div>
    `;
  }

  // Generate warnings list
  generateWarningsList(warnings) {
    return `
      <div class="legal-git-warning-list">
        ${warnings.map(warning => `
          <div class="legal-git-warning-item ${warning.severity}" data-warning-id="${warning.id}">
            <div class="legal-git-warning-header">
              <div class="legal-git-warning-type">
                ${this.warningCategories.get(warning.category)?.icon || '⚠️'} ${warning.description}
              </div>
              <div class="legal-git-warning-severity ${warning.severity}">${warning.severity}</div>
            </div>
            <div class="legal-git-warning-content">${this.escapeHtml(warning.content)}</div>
            <div class="legal-git-warning-suggestion">${warning.suggestion}</div>
            <div class="legal-git-warning-actions">
              <button class="legal-git-warning-btn redact" onclick="window.redactionWarningSystem.redactWarning('${warning.id}')">
                Redact
              </button>
              <button class="legal-git-warning-btn highlight" onclick="window.redactionWarningSystem.highlightWarning('${warning.id}')">
                Highlight
              </button>
              <button class="legal-git-warning-btn ignore" onclick="window.redactionWarningSystem.ignoreWarning('${warning.id}')">
                Ignore
              </button>
            </div>
          </div>
        `).join('')}
      </div>
    `;
  }

  // Highlight sensitive content in text
  highlightSensitiveContent(text, warnings) {
    let highlightedText = this.escapeHtml(text);

    // Sort warnings by position (descending) to avoid position shifts
    const sortedWarnings = warnings.sort((a, b) => b.position - a.position);

    sortedWarnings.forEach(warning => {
      const escapedContent = this.escapeHtml(warning.content);
      const highlightHtml = `
        <span class="legal-git-sensitive-highlight ${warning.severity}" data-warning-id="${warning.id}">
          ${escapedContent}
          <span class="legal-git-sensitive-tooltip">${warning.description} (${warning.severity})</span>
        </span>
      `;

      highlightedText = highlightedText.replace(escapedContent, highlightHtml);
    });

    return highlightedText;
  }

  // Redact specific warning
  redactWarning(warningId) {
    console.log('Redacting warning:', warningId);

    // Find the warning
    let targetWarning = null;
    this.redactionWarnings.forEach(warnings => {
      const warning = warnings.find(w => w.id === warningId);
      if (warning) {
        targetWarning = warning;
        warning.status = 'redacted';
      }
    });

    if (targetWarning) {
      // Update UI to show redacted content
      const warningElement = document.querySelector(`[data-warning-id="${warningId}"]`);
      if (warningElement) {
        warningElement.style.opacity = '0.5';
        warningElement.querySelector('.legal-git-warning-btn.redact').textContent = 'Redacted';
        warningElement.querySelector('.legal-git-warning-btn.redact').disabled = true;
      }

      this.showRedactionNotification(`Redacted: ${targetWarning.description}`, 'success');
    }
  }

  // Highlight specific warning
  highlightWarning(warningId) {
    console.log('Highlighting warning:', warningId);

    const highlightElement = document.querySelector(`[data-warning-id="${warningId}"]`);
    if (highlightElement) {
      highlightElement.style.backgroundColor = '#ffeb3b';
      setTimeout(() => {
        highlightElement.style.backgroundColor = '';
      }, 2000);
    }
  }

  // Ignore specific warning
  ignoreWarning(warningId) {
    console.log('Ignoring warning:', warningId);

    // Find and update the warning
    this.redactionWarnings.forEach(warnings => {
      const warning = warnings.find(w => w.id === warningId);
      if (warning) {
        warning.status = 'ignored';
      }
    });

    // Update UI
    const warningElement = document.querySelector(`[data-warning-id="${warningId}"]`);
    if (warningElement) {
      warningElement.style.opacity = '0.3';
      warningElement.querySelector('.legal-git-warning-btn.ignore').textContent = 'Ignored';
    }

    this.showRedactionNotification('Warning ignored', 'info');
  }

  // Redact all high-risk warnings
  redactAll(documentId) {
    const warnings = this.redactionWarnings.get(documentId) || [];
    const highRiskWarnings = warnings.filter(w => w.severity === 'high' && w.status === 'pending');

    console.log(`Redacting ${highRiskWarnings.length} high-risk warnings`);

    highRiskWarnings.forEach(warning => {
      this.redactWarning(warning.id);
    });

    this.showRedactionNotification(`Redacted ${highRiskWarnings.length} high-risk items`, 'success');
  }

  // Generate redaction report
  generateRedactionReport(documentId) {
    const warnings = this.redactionWarnings.get(documentId) || [];

    const report = {
      documentId: documentId,
      scanDate: new Date().toISOString(),
      totalWarnings: warnings.length,
      severityBreakdown: this.getSevereWarningCounts(documentId),
      redactedCount: warnings.filter(w => w.status === 'redacted').length,
      ignoredCount: warnings.filter(w => w.status === 'ignored').length,
      warnings: warnings.map(w => ({
        type: w.description,
        severity: w.severity,
        status: w.status,
        suggestion: w.suggestion
      }))
    };

    // Create downloadable report
    const reportJson = JSON.stringify(report, null, 2);
    const blob = new Blob([reportJson], { type: 'application/json' });
    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = `redaction_report_${documentId}_${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    this.showRedactionNotification('Redaction report generated and downloaded', 'success');
  }

  // Update redaction indicators in document
  updateRedactionIndicators(warnings) {
    // Add redaction indicator to toolbar if warnings exist
    const toolbar = document.getElementById('legal-git-toolbar') ||
                   document.getElementById('legal-git-word-toolbar');

    if (toolbar && warnings.length > 0) {
      this.addRedactionIndicatorToToolbar(toolbar, warnings);
    }
  }

  // Add redaction indicator to toolbar
  addRedactionIndicatorToToolbar(toolbar, warnings) {
    // Remove existing indicator
    const existing = toolbar.querySelector('.legal-git-redaction-indicator');
    if (existing) existing.remove();

    const highRiskCount = warnings.filter(w => w.severity === 'high').length;
    if (highRiskCount === 0 && this.warningLevel === 'high') return;

    const indicator = document.createElement('div');
    indicator.className = 'legal-git-redaction-indicator';
    indicator.style.cssText = `
      background: #ff5722;
      color: white;
      font-size: 11px;
      padding: 4px 8px;
      border-radius: 12px;
      margin-top: 8px;
      text-align: center;
      cursor: pointer;
      border: 1px solid #d84315;
      animation: pulse 2s infinite;
    `;
    indicator.textContent = `⚠️ ${warnings.length} warnings`;
    indicator.title = 'Click to review redaction warnings';

    indicator.addEventListener('click', () => {
      this.showRedactionWarningsModal(this.getCurrentDocumentId());
    });

    toolbar.appendChild(indicator);
  }

  // Update sensitivity level
  updateSensitivity(level) {
    this.warningLevel = level;
    console.log('Warning sensitivity updated to:', level);
  }

  // Refresh preview
  refreshPreview(documentId) {
    console.log('Refreshing redaction preview for:', documentId);
    // Re-scan document and update preview
    this.scanCurrentDocument();
  }

  // Show redaction notification
  showRedactionNotification(message, type = 'info') {
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

  // Setup redaction modal events
  setupRedactionModalEvents(modal, documentId) {
    // Auto-redaction toggle
    const autoRedactionCheckbox = modal.querySelector('#auto-redaction');
    if (autoRedactionCheckbox) {
      autoRedactionCheckbox.addEventListener('change', (e) => {
        this.autoRedactionEnabled = e.target.checked;
        console.log('Auto-redaction:', this.autoRedactionEnabled);
      });
    }

    // Keyboard navigation
    modal.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        modal.remove();
      }
    });

    // Make globally available
    window.redactionWarningSystem = this;
  }

  // Utility methods
  debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  }

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
}

// Export for use in other scripts
window.RedactionWarningSystem = RedactionWarningSystem;
