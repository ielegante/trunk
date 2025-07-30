// Legal Git Chrome Extension - Diff Visualization and Change Tracking UI
// Handles visual diff display and change tracking interface

class DiffVisualizer {
  constructor(documentConverter) {
    this.documentConverter = documentConverter;
    this.activeDiffs = new Map();
    this.changeHighlights = new Map();
    this.diffViewOpen = false;
    this.init();
  }

  init() {
    this.setupChangeEventListeners();
    this.injectDiffStyles();
  }

  // Setup event listeners for document changes
  setupChangeEventListeners() {
    window.addEventListener('documentContentChanged', (event) => {
      this.handleDocumentChange(event.detail);
    });

    window.addEventListener('legalGitShowDiff', (event) => {
      this.showDiffModal(event.detail.documentId, event.detail.changes);
    });
  }

  // Inject CSS styles for diff visualization
  injectDiffStyles() {
    const styleId = 'legal-git-diff-styles';
    if (document.getElementById(styleId)) return;

    const style = document.createElement('style');
    style.id = styleId;
    style.textContent = `
      .legal-git-diff-container {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.7);
        z-index: 20000;
        display: flex;
        align-items: center;
        justify-content: center;
        font-family: 'Google Sans', Roboto, Arial, sans-serif;
      }

      .legal-git-diff-modal {
        background: white;
        border-radius: 8px;
        box-shadow: 0 8px 30px rgba(0,0,0,0.3);
        width: 90vw;
        height: 80vh;
        max-width: 1200px;
        display: flex;
        flex-direction: column;
        overflow: hidden;
      }

      .legal-git-diff-header {
        padding: 16px 20px;
        border-bottom: 1px solid #e0e0e0;
        background: #f8f9fa;
        display: flex;
        justify-content: space-between;
        align-items: center;
      }

      .legal-git-diff-title {
        font-size: 18px;
        font-weight: 500;
        color: #1f1f1f;
      }

      .legal-git-diff-close {
        background: none;
        border: none;
        font-size: 24px;
        cursor: pointer;
        color: #5f6368;
        padding: 4px;
        border-radius: 4px;
        transition: background 0.2s;
      }

      .legal-git-diff-close:hover {
        background: #f1f3f4;
      }

      .legal-git-diff-content {
        flex: 1;
        display: flex;
        overflow: hidden;
      }

      .legal-git-diff-sidebar {
        width: 250px;
        background: #f8f9fa;
        border-right: 1px solid #e0e0e0;
        overflow-y: auto;
        padding: 16px;
      }

      .legal-git-diff-main {
        flex: 1;
        overflow-y: auto;
        padding: 16px 20px;
      }

      .legal-git-change-summary {
        background: white;
        border: 1px solid #dadce0;
        border-radius: 6px;
        padding: 12px;
        margin-bottom: 16px;
      }

      .legal-git-change-summary h4 {
        margin: 0 0 8px 0;
        font-size: 14px;
        font-weight: 500;
        color: #1f1f1f;
      }

      .legal-git-change-stat {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 4px 0;
        font-size: 13px;
      }

      .legal-git-change-count {
        font-weight: 500;
      }

      .legal-git-change-count.additions {
        color: #28a745;
      }

      .legal-git-change-count.deletions {
        color: #dc3545;
      }

      .legal-git-change-count.modifications {
        color: #ffc107;
      }

      .legal-git-diff-view {
        background: #fafafa;
        border: 1px solid #e0e0e0;
        border-radius: 6px;
        overflow: hidden;
      }

      .legal-git-diff-line {
        display: flex;
        font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
        font-size: 13px;
        line-height: 1.4;
        border-bottom: 1px solid #f0f0f0;
      }

      .legal-git-diff-line:last-child {
        border-bottom: none;
      }

      .legal-git-line-number {
        width: 60px;
        padding: 6px 8px;
        background: #f5f5f5;
        color: #666;
        text-align: right;
        border-right: 1px solid #e0e0e0;
        user-select: none;
      }

      .legal-git-line-content {
        flex: 1;
        padding: 6px 12px;
        white-space: pre-wrap;
        word-break: break-word;
      }

      .legal-git-diff-line.addition {
        background-color: #e6ffed;
      }

      .legal-git-diff-line.addition .legal-git-line-number {
        background-color: #cdffd8;
        color: #28a745;
      }

      .legal-git-diff-line.deletion {
        background-color: #ffeef0;
      }

      .legal-git-diff-line.deletion .legal-git-line-number {
        background-color: #ffc1cc;
        color: #dc3545;
      }

      .legal-git-diff-line.modification {
        background-color: #fff3cd;
      }

      .legal-git-diff-line.modification .legal-git-line-number {
        background-color: #ffe69c;
        color: #856404;
      }

      .legal-git-diff-navigation {
        padding: 12px;
        background: white;
        border-bottom: 1px solid #e0e0e0;
        display: flex;
        gap: 8px;
        align-items: center;
      }

      .legal-git-diff-nav-btn {
        padding: 6px 12px;
        background: #f8f9fa;
        border: 1px solid #dadce0;
        border-radius: 4px;
        font-size: 12px;
        cursor: pointer;
        transition: background 0.2s;
      }

      .legal-git-diff-nav-btn:hover {
        background: #e9ecef;
      }

      .legal-git-diff-nav-btn.active {
        background: #1a73e8;
        color: white;
        border-color: #1a73e8;
      }

      .legal-git-inline-change {
        position: relative;
        display: inline;
      }

      .legal-git-inline-change.addition {
        background-color: rgba(40, 167, 69, 0.2);
        border-bottom: 2px solid #28a745;
      }

      .legal-git-inline-change.deletion {
        background-color: rgba(220, 53, 69, 0.2);
        text-decoration: line-through;
        border-bottom: 2px solid #dc3545;
      }

      .legal-git-inline-change.modification {
        background-color: rgba(255, 193, 7, 0.2);
        border-bottom: 2px solid #ffc107;
      }

      .legal-git-change-tooltip {
        position: absolute;
        bottom: 100%;
        left: 50%;
        transform: translateX(-50%);
        background: #333;
        color: white;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 11px;
        white-space: nowrap;
        z-index: 1000;
        opacity: 0;
        pointer-events: none;
        transition: opacity 0.2s;
      }

      .legal-git-inline-change:hover .legal-git-change-tooltip {
        opacity: 1;
      }
    `;

    document.head.appendChild(style);
  }

  // Handle document change events
  handleDocumentChange(changeData) {
    const { documentId, content, changes } = changeData;

    // Store the changes for later visualization
    this.activeDiffs.set(documentId, changes);

    // Show inline change indicators if enabled
    if (this.shouldShowInlineChanges()) {
      this.showInlineChanges(changes);
    }

    // Update change tracking UI
    this.updateChangeTrackingUI(documentId, changes);
  }

  // Check if inline changes should be shown
  shouldShowInlineChanges() {
    // For now, only show in Google Docs
    return window.location.hostname === 'docs.google.com';
  }

  // Show diff modal for document changes
  showDiffModal(documentId, changes) {
    if (this.diffViewOpen) {
      this.closeDiffModal();
    }

    const modal = this.createDiffModal(documentId, changes);
    document.body.appendChild(modal);
    this.diffViewOpen = true;

    // Focus trap and keyboard handling
    setTimeout(() => {
      const closeBtn = modal.querySelector('.legal-git-diff-close');
      if (closeBtn) closeBtn.focus();
    }, 100);
  }

  // Create diff modal HTML
  createDiffModal(documentId, changes) {
    const modal = document.createElement('div');
    modal.className = 'legal-git-diff-container';
    modal.id = 'legal-git-diff-modal';

    const cachedDoc = this.documentConverter.getCachedContent(documentId);
    const documentTitle = cachedDoc?.content?.title || 'Document';

    modal.innerHTML = `
      <div class="legal-git-diff-modal">
        <div class="legal-git-diff-header">
          <div class="legal-git-diff-title">
            📊 Document Changes - ${documentTitle}
          </div>
          <button class="legal-git-diff-close" onclick="this.closest('.legal-git-diff-container').remove(); window.diffVisualizer.diffViewOpen = false;">×</button>
        </div>

        <div class="legal-git-diff-content">
          <div class="legal-git-diff-sidebar">
            ${this.generateChangeSummary(changes)}
            ${this.generateNavigationControls(changes)}
          </div>

          <div class="legal-git-diff-main">
            <div class="legal-git-diff-navigation">
              <button class="legal-git-diff-nav-btn active" data-view="unified">Unified View</button>
              <button class="legal-git-diff-nav-btn" data-view="split">Split View</button>
              <button class="legal-git-diff-nav-btn" data-view="inline">Inline Changes</button>
            </div>

            <div class="legal-git-diff-view" id="diff-view-container">
              ${this.generateUnifiedDiff(changes)}
            </div>
          </div>
        </div>
      </div>
    `;

    this.setupDiffModalEvents(modal, changes);
    return modal;
  }

  // Generate change summary sidebar
  generateChangeSummary(changes) {
    const stats = this.calculateChangeStats(changes);

    return `
      <div class="legal-git-change-summary">
        <h4>📈 Change Summary</h4>
        <div class="legal-git-change-stat">
          <span>Additions:</span>
          <span class="legal-git-change-count additions">+${stats.additions}</span>
        </div>
        <div class="legal-git-change-stat">
          <span>Deletions:</span>
          <span class="legal-git-change-count deletions">-${stats.deletions}</span>
        </div>
        <div class="legal-git-change-stat">
          <span>Modifications:</span>
          <span class="legal-git-change-count modifications">${stats.modifications}</span>
        </div>
        <div class="legal-git-change-stat">
          <span>Total Changes:</span>
          <span class="legal-git-change-count">${stats.total}</span>
        </div>
      </div>
    `;
  }

  // Calculate change statistics
  calculateChangeStats(changes) {
    let additions = 0;
    let deletions = 0;
    let modifications = 0;

    if (changes.textDiff) {
      changes.textDiff.forEach(diff => {
        switch (diff.type) {
          case 'add':
            additions++;
            break;
          case 'delete':
            deletions++;
            break;
          case 'modify':
            modifications++;
            break;
        }
      });
    }

    return {
      additions,
      deletions,
      modifications,
      total: additions + deletions + modifications
    };
  }

  // Generate navigation controls
  generateNavigationControls(changes) {
    const hasTextChanges = changes.textDiff && changes.textDiff.length > 0;
    const hasCommentChanges = changes.comments && (changes.comments.added.length > 0 || changes.comments.removed.length > 0);

    return `
      <div class="legal-git-change-summary">
        <h4>🧭 Navigation</h4>
        ${hasTextChanges ? '<div class="legal-git-change-stat"><span>📝 Text Changes</span><button class="legal-git-diff-nav-btn" onclick="window.diffVisualizer.scrollToSection(\'text\')">View</button></div>' : ''}
        ${hasCommentChanges ? '<div class="legal-git-change-stat"><span>💬 Comments</span><button class="legal-git-diff-nav-btn" onclick="window.diffVisualizer.scrollToSection(\'comments\')">View</button></div>' : ''}
        ${changes.title ? '<div class="legal-git-change-stat"><span>📋 Title Changed</span><button class="legal-git-diff-nav-btn" onclick="window.diffVisualizer.scrollToSection(\'title\')">View</button></div>' : ''}
      </div>
    `;
  }

  // Generate unified diff view
  generateUnifiedDiff(changes) {
    let diffHtml = '';

    // Title changes
    if (changes.title) {
      diffHtml += '<div class="legal-git-diff-section" id="title-section">';
      diffHtml += '<h4>📋 Title Changes</h4>';
      diffHtml += '<div class="legal-git-diff-line modification">';
      diffHtml += '<div class="legal-git-line-number">T</div>';
      diffHtml += '<div class="legal-git-line-content">Title changed</div>';
      diffHtml += '</div></div>';
    }

    // Text changes
    if (changes.textDiff && changes.textDiff.length > 0) {
      diffHtml += '<div class="legal-git-diff-section" id="text-section">';
      diffHtml += '<h4>📝 Text Changes</h4>';

      changes.textDiff.forEach((diff, index) => {
        const lineClass = diff.type === 'add' ? 'addition' :
                         diff.type === 'delete' ? 'deletion' : 'modification';

        diffHtml += `<div class="legal-git-diff-line ${lineClass}">`;
        diffHtml += `<div class="legal-git-line-number">${diff.lineNumber}</div>`;

        if (diff.type === 'modify') {
          diffHtml += `<div class="legal-git-line-content">`;
          diffHtml += `<div style="color: #dc3545; text-decoration: line-through;">${this.escapeHtml(diff.old)}</div>`;
          diffHtml += `<div style="color: #28a745;">${this.escapeHtml(diff.new)}</div>`;
          diffHtml += `</div>`;
        } else if (diff.type === 'add') {
          diffHtml += `<div class="legal-git-line-content">${this.escapeHtml(diff.new)}</div>`;
        } else {
          diffHtml += `<div class="legal-git-line-content">${this.escapeHtml(diff.old)}</div>`;
        }

        diffHtml += '</div>';
      });

      diffHtml += '</div>';
    }

    // Comment changes
    if (changes.comments && (changes.comments.added.length > 0 || changes.comments.removed.length > 0)) {
      diffHtml += '<div class="legal-git-diff-section" id="comments-section">';
      diffHtml += '<h4>💬 Comment Changes</h4>';

      changes.comments.added.forEach(comment => {
        diffHtml += '<div class="legal-git-diff-line addition">';
        diffHtml += '<div class="legal-git-line-number">+C</div>';
        diffHtml += `<div class="legal-git-line-content">Added: ${this.escapeHtml(comment.text)}</div>`;
        diffHtml += '</div>';
      });

      changes.comments.removed.forEach(comment => {
        diffHtml += '<div class="legal-git-diff-line deletion">';
        diffHtml += '<div class="legal-git-line-number">-C</div>';
        diffHtml += `<div class="legal-git-line-content">Removed: ${this.escapeHtml(comment.text)}</div>`;
        diffHtml += '</div>';
      });

      diffHtml += '</div>';
    }

    if (!diffHtml) {
      diffHtml = '<div style="text-align: center; padding: 40px; color: #666;">No changes detected</div>';
    }

    return diffHtml;
  }

  // Setup diff modal event listeners
  setupDiffModalEvents(modal, changes) {
    // View switching
    const navButtons = modal.querySelectorAll('.legal-git-diff-nav-btn[data-view]');
    navButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        const view = btn.dataset.view;
        this.switchDiffView(modal, view, changes);

        // Update active state
        navButtons.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
      });
    });

    // Keyboard navigation
    modal.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        this.closeDiffModal();
      }
    });
  }

  // Switch diff view mode
  switchDiffView(modal, viewType, changes) {
    const container = modal.querySelector('#diff-view-container');

    switch (viewType) {
      case 'unified':
        container.innerHTML = this.generateUnifiedDiff(changes);
        break;
      case 'split':
        container.innerHTML = this.generateSplitDiff(changes);
        break;
      case 'inline':
        container.innerHTML = this.generateInlineDiff(changes);
        break;
    }
  }

  // Generate split diff view with side-by-side comparison
  generateSplitDiff(changes) {
    const splitDiffHtml = `
      <div class="legal-git-split-diff" style="display: flex; height: 100%; min-height: 400px;">
        <div class="legal-git-split-before" style="flex: 1; border-right: 1px solid #e0e0e0; display: flex; flex-direction: column;">
          <div class="legal-git-split-header" style="
            background: #f8f9fa;
            padding: 12px;
            border-bottom: 1px solid #e0e0e0;
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 8px;
          ">
            <span style="color: #dc3545;">📝</span>
            <span>Before Changes</span>
            <span style="font-size: 12px; color: #666; font-weight: normal;">(Previous Version)</span>
          </div>
          <div class="legal-git-split-content" style="flex: 1; overflow-y: auto;">
            ${this.generateBeforeContent(changes)}
          </div>
        </div>

        <div class="legal-git-split-after" style="flex: 1; display: flex; flex-direction: column;">
          <div class="legal-git-split-header" style="
            background: #f8f9fa;
            padding: 12px;
            border-bottom: 1px solid #e0e0e0;
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 8px;
          ">
            <span style="color: #28a745;">📝</span>
            <span>After Changes</span>
            <span style="font-size: 12px; color: #666; font-weight: normal;">(Current Version)</span>
          </div>
          <div class="legal-git-split-content" style="flex: 1; overflow-y: auto;">
            ${this.generateAfterContent(changes)}
          </div>
        </div>
      </div>
    `;

    return splitDiffHtml;
  }

  // Generate before content for split view
  generateBeforeContent(changes) {
    let beforeHtml = '';

    if (changes.textDiff && changes.textDiff.length > 0) {
      beforeHtml += '<div class="legal-git-split-section">';

      changes.textDiff.forEach(diff => {
        if (diff.type === 'delete' || diff.type === 'modify') {
          beforeHtml += `
            <div class="legal-git-split-line" style="
              padding: 8px 12px;
              margin-bottom: 2px;
              background: #ffeef0;
              border-left: 4px solid #dc3545;
              font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
              font-size: 13px;
              line-height: 1.4;
            ">
              <div style="display: flex; align-items: flex-start; gap: 8px;">
                <span style="color: #dc3545; font-weight: bold; min-width: 30px;">${diff.lineNumber}</span>
                <span style="flex: 1; white-space: pre-wrap;">${this.escapeHtml(diff.old)}</span>
              </div>
            </div>
          `;
        } else if (diff.type === 'add') {
          // Show empty placeholder for added lines
          beforeHtml += `
            <div class="legal-git-split-line" style="
              padding: 8px 12px;
              margin-bottom: 2px;
              background: #f8f9fa;
              border-left: 4px solid #e0e0e0;
              font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
              font-size: 13px;
              line-height: 1.4;
              opacity: 0.5;
            ">
              <div style="display: flex; align-items: flex-start; gap: 8px;">
                <span style="color: #999; font-weight: bold; min-width: 30px;">-</span>
                <span style="flex: 1; color: #999; font-style: italic;">(line added)</span>
              </div>
            </div>
          `;
        }
      });

      beforeHtml += '</div>';
    }

    if (!beforeHtml) {
      beforeHtml = '<div style="padding: 40px; text-align: center; color: #666;">No previous content available</div>';
    }

    return beforeHtml;
  }

  // Generate after content for split view
  generateAfterContent(changes) {
    let afterHtml = '';

    if (changes.textDiff && changes.textDiff.length > 0) {
      afterHtml += '<div class="legal-git-split-section">';

      changes.textDiff.forEach(diff => {
        if (diff.type === 'add' || diff.type === 'modify') {
          afterHtml += `
            <div class="legal-git-split-line" style="
              padding: 8px 12px;
              margin-bottom: 2px;
              background: #e6ffed;
              border-left: 4px solid #28a745;
              font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
              font-size: 13px;
              line-height: 1.4;
            ">
              <div style="display: flex; align-items: flex-start; gap: 8px;">
                <span style="color: #28a745; font-weight: bold; min-width: 30px;">${diff.lineNumber}</span>
                <span style="flex: 1; white-space: pre-wrap;">${this.escapeHtml(diff.new)}</span>
              </div>
            </div>
          `;
        } else if (diff.type === 'delete') {
          // Show empty placeholder for deleted lines
          afterHtml += `
            <div class="legal-git-split-line" style="
              padding: 8px 12px;
              margin-bottom: 2px;
              background: #f8f9fa;
              border-left: 4px solid #e0e0e0;
              font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
              font-size: 13px;
              line-height: 1.4;
              opacity: 0.5;
            ">
              <div style="display: flex; align-items: flex-start; gap: 8px;">
                <span style="color: #999; font-weight: bold; min-width: 30px;">-</span>
                <span style="flex: 1; color: #999; font-style: italic;">(line deleted)</span>
              </div>
            </div>
          `;
        }
      });

      afterHtml += '</div>';
    }

    if (!afterHtml) {
      afterHtml = '<div style="padding: 40px; text-align: center; color: #666;">No current content available</div>';
    }

    return afterHtml;
  }

  // Generate inline diff view
  generateInlineDiff(changes) {
    return `
      <div style="padding: 16px;">
        <p style="color: #666; margin-bottom: 16px;">
          Inline changes are shown directly in the document with highlighting.
          Close this dialog to see inline changes in the document.
        </p>
        <button onclick="window.diffVisualizer.closeDiffModal(); window.diffVisualizer.showInlineChanges(${JSON.stringify(changes).replace(/"/g, '&quot;')});"
                style="padding: 8px 16px; background: #1a73e8; color: white; border: none; border-radius: 4px; cursor: pointer;">
          Show Inline Changes
        </button>
      </div>
    `;
  }

  // Show inline changes in the document
  showInlineChanges(changes) {
    // This would highlight changes directly in the Google Docs interface
    console.log('Showing inline changes:', changes);

    // For now, show a notification
    this.showChangeNotification(changes);
  }

  // Show change notification
  showChangeNotification(changes) {
    const stats = this.calculateChangeStats(changes);
    const message = `Document updated: ${stats.total} changes detected (${stats.additions} additions, ${stats.deletions} deletions, ${stats.modifications} modifications)`;

    // Use the existing toast system from commit-ui.js if available
    if (window.commitUIManager) {
      window.commitUIManager.showToast(message, 'info');
    } else {
      console.log(message);
    }
  }

  // Update change tracking UI
  updateChangeTrackingUI(documentId, changes) {
    // Update toolbar with change indicator
    const toolbar = document.getElementById('legal-git-toolbar');
    if (toolbar) {
      this.addChangeIndicatorToToolbar(toolbar, changes);
    }
  }

  // Add change indicator to toolbar
  addChangeIndicatorToToolbar(toolbar, changes) {
    // Remove existing indicator
    const existing = toolbar.querySelector('.legal-git-change-indicator');
    if (existing) existing.remove();

    const stats = this.calculateChangeStats(changes);
    if (stats.total === 0) return;

    const indicator = document.createElement('div');
    indicator.className = 'legal-git-change-indicator';
    indicator.style.cssText = `
      background: #ffc107;
      color: #856404;
      font-size: 11px;
      padding: 4px 8px;
      border-radius: 12px;
      margin-top: 8px;
      text-align: center;
      cursor: pointer;
      border: 1px solid #ffeaa7;
    `;
    indicator.textContent = `${stats.total} unsaved changes`;
    indicator.title = 'Click to view changes';

    indicator.addEventListener('click', () => {
      window.dispatchEvent(new CustomEvent('legalGitShowDiff', {
        detail: {
          documentId: this.documentConverter.getDocumentIdFromUrl(),
          changes: changes
        }
      }));
    });

    toolbar.appendChild(indicator);
  }

  // Scroll to specific section in diff view
  scrollToSection(sectionType) {
    const section = document.getElementById(`${sectionType}-section`);
    if (section) {
      section.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }

  // Close diff modal
  closeDiffModal() {
    const modal = document.getElementById('legal-git-diff-modal');
    if (modal) {
      modal.remove();
      this.diffViewOpen = false;
    }
  }

  // Escape HTML for safe display
  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // Get diff data for a document
  getDiffData(documentId) {
    return this.activeDiffs.get(documentId);
  }

  // Clear change highlights
  clearChangeHighlights(documentId) {
    this.changeHighlights.delete(documentId);
    const indicators = document.querySelectorAll('.legal-git-change-indicator');
    indicators.forEach(indicator => indicator.remove());
  }
}

// Export for use in other scripts
window.DiffVisualizer = DiffVisualizer;
