// Legal Git Chrome Extension - Advanced Diff Visualizer
// Enhanced diff visualization with legal document formatting support

class AdvancedDiffVisualizer {
  constructor() {
    this.currentView = 'side-by-side';
    this.isOpen = false;
    this.currentDiff = null;
    this.init();
  }

  init() {
    this.injectStyles();
    this.setupEventListeners();
  }

  // Inject CSS styles for diff visualization
  injectStyles() {
    const style = document.createElement('style');
    style.textContent = `
      .legal-git-diff-container {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.8);
        z-index: 9999;
        display: none;
      }

      .legal-git-diff-container.active {
        display: flex;
        align-items: center;
        justify-content: center;
      }

      .legal-git-diff-modal {
        background: white;
        width: 90vw;
        height: 90vh;
        max-width: 1400px;
        border-radius: 8px;
        display: flex;
        flex-direction: column;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
      }

      .legal-git-diff-header {
        padding: 16px 20px;
        border-bottom: 1px solid #e0e0e0;
        display: flex;
        align-items: center;
        gap: 16px;
      }

      .legal-git-diff-title {
        font-size: 18px;
        font-weight: 600;
        flex: 1;
      }

      .legal-git-diff-controls {
        display: flex;
        gap: 8px;
      }

      .legal-git-diff-btn {
        padding: 6px 12px;
        border: 1px solid #dadce0;
        background: white;
        border-radius: 4px;
        cursor: pointer;
        font-size: 13px;
        transition: all 0.2s;
      }

      .legal-git-diff-btn:hover {
        background: #f8f9fa;
      }

      .legal-git-diff-btn.active {
        background: #1a73e8;
        color: white;
        border-color: #1a73e8;
      }

      .legal-git-diff-content {
        flex: 1;
        overflow: auto;
        padding: 20px;
      }

      .legal-git-diff-side-by-side {
        display: flex;
        gap: 20px;
        height: 100%;
      }

      .legal-git-diff-side {
        flex: 1;
        border: 1px solid #e0e0e0;
        border-radius: 4px;
        overflow: auto;
        padding: 16px;
      }

      .legal-git-diff-side h4 {
        margin: 0 0 16px 0;
        padding-bottom: 8px;
        border-bottom: 2px solid #1a73e8;
      }

      .legal-git-diff-unified {
        font-family: 'Monaco', 'Consolas', monospace;
        font-size: 13px;
        line-height: 1.5;
      }

      .legal-git-diff-line {
        padding: 2px 8px;
        white-space: pre-wrap;
        word-wrap: break-word;
      }

      .legal-git-diff-line.added {
        background: #dff0d8;
        color: #3c763d;
      }

      .legal-git-diff-line.removed {
        background: #f2dede;
        color: #a94442;
      }

      .legal-git-diff-line.context {
        color: #666;
      }

      .legal-git-diff-line-number {
        display: inline-block;
        width: 50px;
        color: #999;
        text-align: right;
        padding-right: 10px;
        user-select: none;
      }

      .legal-git-diff-redline {
        font-family: 'Times New Roman', serif;
        font-size: 14px;
        line-height: 2;
      }

      .legal-git-diff-redline del {
        color: #d9534f;
        text-decoration: line-through;
        background: #ffe6e6;
      }

      .legal-git-diff-redline ins {
        color: #5cb85c;
        text-decoration: underline;
        background: #e6ffe6;
      }

      .legal-git-diff-stats {
        padding: 12px;
        background: #f8f9fa;
        border-radius: 4px;
        margin-bottom: 16px;
        display: flex;
        gap: 20px;
        font-size: 14px;
      }

      .legal-git-diff-stat {
        display: flex;
        align-items: center;
        gap: 6px;
      }

      .legal-git-diff-stat-added {
        color: #28a745;
      }

      .legal-git-diff-stat-removed {
        color: #dc3545;
      }

      .legal-git-diff-footer {
        padding: 16px 20px;
        border-top: 1px solid #e0e0e0;
        display: flex;
        justify-content: space-between;
        align-items: center;
      }

      .legal-git-diff-export {
        display: flex;
        gap: 8px;
      }

      .legal-git-diff-close-btn {
        background: #dc3545;
        color: white;
        border: none;
        padding: 8px 16px;
        border-radius: 4px;
        cursor: pointer;
        font-size: 14px;
      }

      .legal-git-diff-close-btn:hover {
        background: #c82333;
      }

      .legal-git-diff-highlight {
        background: #fffacd;
        padding: 2px 4px;
        border-radius: 2px;
      }
    `;
    document.head.appendChild(style);

    // Create diff container
    const container = document.createElement('div');
    container.className = 'legal-git-diff-container';
    container.innerHTML = `
      <div class="legal-git-diff-modal">
        <div class="legal-git-diff-header">
          <h3 class="legal-git-diff-title">Document Comparison</h3>
          <div class="legal-git-diff-controls">
            <button class="legal-git-diff-btn active" data-view="side-by-side">Side by Side</button>
            <button class="legal-git-diff-btn" data-view="unified">Unified</button>
            <button class="legal-git-diff-btn" data-view="redline">Legal Redline</button>
          </div>
        </div>
        <div class="legal-git-diff-content"></div>
        <div class="legal-git-diff-footer">
          <div class="legal-git-diff-export">
            <button class="legal-git-diff-btn" data-export="pdf">Export as PDF</button>
            <button class="legal-git-diff-btn" data-export="docx">Export as Word</button>
          </div>
          <button class="legal-git-diff-close-btn">Close</button>
        </div>
      </div>
    `;
    document.body.appendChild(container);
    this.container = container;
  }

  // Setup event listeners
  setupEventListeners() {
    // View mode buttons
    this.container.addEventListener('click', (e) => {
      if (e.target.matches('[data-view]')) {
        this.currentView = e.target.dataset.view;
        this.updateViewButtons();
        this.renderDiff();
      }

      if (e.target.matches('[data-export]')) {
        this.exportDiff(e.target.dataset.export);
      }

      if (e.target.matches('.legal-git-diff-close-btn')) {
        this.close();
      }
    });

    // Close on escape
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this.isOpen) {
        this.close();
      }
    });

    // Close on background click
    this.container.addEventListener('click', (e) => {
      if (e.target === this.container) {
        this.close();
      }
    });
  }

  // Show diff visualization
  show(oldContent, newContent, metadata = {}) {
    this.currentDiff = {
      old: oldContent,
      new: newContent,
      metadata: metadata
    };

    this.container.classList.add('active');
    this.isOpen = true;

    // Update title
    const title = this.container.querySelector('.legal-git-diff-title');
    title.textContent = metadata.title || 'Document Comparison';

    this.renderDiff();
  }

  // Close diff visualization
  close() {
    this.container.classList.remove('active');
    this.isOpen = false;
    this.currentDiff = null;
  }

  // Update view buttons
  updateViewButtons() {
    const buttons = this.container.querySelectorAll('[data-view]');
    buttons.forEach(btn => {
      if (btn.dataset.view === this.currentView) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });
  }

  // Render diff based on current view
  renderDiff() {
    if (!this.currentDiff) return;

    const content = this.container.querySelector('.legal-git-diff-content');
    content.innerHTML = '';

    // Add statistics
    const stats = this.calculateStats();
    content.appendChild(this.createStatsElement(stats));

    // Render based on view mode
    switch (this.currentView) {
      case 'side-by-side':
        content.appendChild(this.renderSideBySide());
        break;
      case 'unified':
        content.appendChild(this.renderUnified());
        break;
      case 'redline':
        content.appendChild(this.renderRedline());
        break;
    }
  }

  // Calculate diff statistics
  calculateStats() {
    const oldLines = this.currentDiff.old.split('\n');
    const newLines = this.currentDiff.new.split('\n');

    // Simple stats calculation
    const added = Math.max(0, newLines.length - oldLines.length);
    const removed = Math.max(0, oldLines.length - newLines.length);
    const modified = Math.min(oldLines.length, newLines.length);

    return {
      added: added,
      removed: removed,
      modified: modified,
      total: Math.max(oldLines.length, newLines.length)
    };
  }

  // Create statistics element
  createStatsElement(stats) {
    const statsEl = document.createElement('div');
    statsEl.className = 'legal-git-diff-stats';
    statsEl.innerHTML = `
      <div class="legal-git-diff-stat">
        <span>Total Lines:</span>
        <strong>${stats.total}</strong>
      </div>
      <div class="legal-git-diff-stat legal-git-diff-stat-added">
        <span>+</span>
        <strong>${stats.added}</strong>
        <span>additions</span>
      </div>
      <div class="legal-git-diff-stat legal-git-diff-stat-removed">
        <span>-</span>
        <strong>${stats.removed}</strong>
        <span>deletions</span>
      </div>
      <div class="legal-git-diff-stat">
        <span>~</span>
        <strong>${stats.modified}</strong>
        <span>modifications</span>
      </div>
    `;
    return statsEl;
  }

  // Render side-by-side view
  renderSideBySide() {
    const container = document.createElement('div');
    container.className = 'legal-git-diff-side-by-side';

    // Old version
    const oldSide = document.createElement('div');
    oldSide.className = 'legal-git-diff-side';
    oldSide.innerHTML = `
      <h4>Previous Version</h4>
      <div class="legal-git-diff-content-text">${this.escapeHtml(this.currentDiff.old)}</div>
    `;

    // New version
    const newSide = document.createElement('div');
    newSide.className = 'legal-git-diff-side';
    newSide.innerHTML = `
      <h4>Current Version</h4>
      <div class="legal-git-diff-content-text">${this.highlightChanges(this.currentDiff.new, this.currentDiff.old)}</div>
    `;

    container.appendChild(oldSide);
    container.appendChild(newSide);
    return container;
  }

  // Render unified diff view
  renderUnified() {
    const container = document.createElement('div');
    container.className = 'legal-git-diff-unified';

    const oldLines = this.currentDiff.old.split('\n');
    const newLines = this.currentDiff.new.split('\n');

    // Simple diff algorithm
    const diff = this.computeSimpleDiff(oldLines, newLines);

    diff.forEach(change => {
      const line = document.createElement('div');
      line.className = `legal-git-diff-line ${change.type}`;

      const lineNumber = document.createElement('span');
      lineNumber.className = 'legal-git-diff-line-number';
      lineNumber.textContent = change.lineNumber || '';

      line.appendChild(lineNumber);
      line.appendChild(document.createTextNode(change.content));
      container.appendChild(line);
    });

    return container;
  }

  // Render legal redline view
  renderRedline() {
    const container = document.createElement('div');
    container.className = 'legal-git-diff-redline';

    // Create redline markup
    const oldWords = this.currentDiff.old.split(/\s+/);
    const newWords = this.currentDiff.new.split(/\s+/);

    let html = '';
    let i = 0, j = 0;

    while (i < oldWords.length || j < newWords.length) {
      if (i >= oldWords.length) {
        // Remaining new words
        html += `<ins>${newWords.slice(j).join(' ')}</ins> `;
        break;
      } else if (j >= newWords.length) {
        // Remaining old words
        html += `<del>${oldWords.slice(i).join(' ')}</del> `;
        break;
      } else if (oldWords[i] === newWords[j]) {
        // Unchanged word
        html += oldWords[i] + ' ';
        i++;
        j++;
      } else {
        // Changed section
        html += `<del>${oldWords[i]}</del> <ins>${newWords[j]}</ins> `;
        i++;
        j++;
      }
    }

    container.innerHTML = html;
    return container;
  }

  // Compute simple diff
  computeSimpleDiff(oldLines, newLines) {
    const diff = [];
    const maxLines = Math.max(oldLines.length, newLines.length);

    for (let i = 0; i < maxLines; i++) {
      if (i >= oldLines.length) {
        diff.push({
          type: 'added',
          content: '+ ' + newLines[i],
          lineNumber: i + 1
        });
      } else if (i >= newLines.length) {
        diff.push({
          type: 'removed',
          content: '- ' + oldLines[i],
          lineNumber: i + 1
        });
      } else if (oldLines[i] !== newLines[i]) {
        diff.push({
          type: 'removed',
          content: '- ' + oldLines[i],
          lineNumber: i + 1
        });
        diff.push({
          type: 'added',
          content: '+ ' + newLines[i],
          lineNumber: i + 1
        });
      } else {
        diff.push({
          type: 'context',
          content: '  ' + oldLines[i],
          lineNumber: i + 1
        });
      }
    }

    return diff;
  }

  // Highlight changes in text
  highlightChanges(newText, oldText) {
    // Simple highlighting - in production, use a proper diff algorithm
    const words = newText.split(/\s+/);
    const oldWords = oldText.split(/\s+/);

    return words.map(word => {
      if (!oldWords.includes(word)) {
        return `<span class="legal-git-diff-highlight">${this.escapeHtml(word)}</span>`;
      }
      return this.escapeHtml(word);
    }).join(' ');
  }

  // Export diff
  async exportDiff(format) {
    console.log(`Exporting diff as ${format}`);

    // Create export content based on format
    let content = '';
    const title = this.currentDiff.metadata.title || 'Document Comparison';

    switch (format) {
      case 'pdf':
        // In production, use a PDF library
        content = `${title}\n\n${this.createExportContent()}`;
        this.downloadFile(content, `${title}.txt`, 'text/plain');
        break;

      case 'docx':
        // In production, use a DOCX library
        content = `${title}\n\n${this.createExportContent()}`;
        this.downloadFile(content, `${title}.txt`, 'text/plain');
        break;
    }
  }

  // Create export content
  createExportContent() {
    if (this.currentView === 'redline') {
      return `LEGAL REDLINE VIEW\n\nOld Version:\n${this.currentDiff.old}\n\nNew Version:\n${this.currentDiff.new}`;
    } else {
      return `DOCUMENT COMPARISON\n\nOld Version:\n${this.currentDiff.old}\n\nNew Version:\n${this.currentDiff.new}`;
    }
  }

  // Download file
  downloadFile(content, filename, type) {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  // Escape HTML
  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
}

// Initialize advanced diff visualizer
window.legalGitAdvancedDiff = new AdvancedDiffVisualizer();
