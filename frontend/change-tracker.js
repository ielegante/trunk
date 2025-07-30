// Legal Git Chrome Extension - Change Tracking UI Components
// Handles change tracking interface, history view, and document status

class ChangeTracker {
  constructor(documentConverter, diffVisualizer) {
    this.documentConverter = documentConverter;
    this.diffVisualizer = diffVisualizer;
    this.changeHistory = new Map();
    this.trackingEnabled = false;
    this.currentDocumentId = null;
    this.init();
  }

  async init() {
    await this.loadChangeHistory();
    this.setupEventListeners();
    this.detectCurrentDocument();
  }

  async loadChangeHistory() {
    try {
      const result = await chrome.storage.local.get(['changeHistory']);
      if (result.changeHistory) {
        this.changeHistory = new Map(Object.entries(result.changeHistory));
      }
    } catch (error) {
      console.error('Failed to load change history:', error);
    }
  }

  async saveChangeHistory() {
    try {
      const historyObject = Object.fromEntries(this.changeHistory);
      await chrome.storage.local.set({ changeHistory: historyObject });
    } catch (error) {
      console.error('Failed to save change history:', error);
    }
  }

  setupEventListeners() {
    // Listen for document changes
    window.addEventListener('documentContentChanged', (event) => {
      this.handleDocumentChange(event.detail);
    });

    // Listen for tracking toggle
    window.addEventListener('legalGitToggleTracking', (event) => {
      this.toggleTracking(event.detail.enabled);
    });

    // Listen for history view requests
    window.addEventListener('legalGitShowHistory', (event) => {
      this.showHistoryModal(event.detail.documentId);
    });
  }

  detectCurrentDocument() {
    if (window.location.hostname === 'docs.google.com') {
      this.currentDocumentId = this.extractDocumentIdFromUrl();
      if (this.currentDocumentId) {
        this.enableTracking();
      }
    }
  }

  extractDocumentIdFromUrl() {
    const pathParts = window.location.pathname.split('/');
    const docIndex = pathParts.indexOf('d');
    return docIndex !== -1 ? pathParts[docIndex + 1] : null;
  }

  enableTracking() {
    this.trackingEnabled = true;
    console.log('Change tracking enabled for document:', this.currentDocumentId);
  }

  disableTracking() {
    this.trackingEnabled = false;
    console.log('Change tracking disabled');
  }

  toggleTracking(enabled) {
    if (enabled) {
      this.enableTracking();
    } else {
      this.disableTracking();
    }
  }

  handleDocumentChange(changeData) {
    if (!this.trackingEnabled) return;

    const { documentId, content, changes } = changeData;

    // Record the change in history
    this.recordChange(documentId, content, changes);

    // Update UI indicators
    this.updateChangeIndicators(documentId, changes);

    // Show real-time notifications if enabled
    this.showChangeNotification(changes);
  }

  recordChange(documentId, content, changes) {
    if (!this.changeHistory.has(documentId)) {
      this.changeHistory.set(documentId, []);
    }

    const history = this.changeHistory.get(documentId);
    const changeRecord = {
      id: Date.now().toString(),
      timestamp: new Date().toISOString(),
      content: content,
      changes: changes,
      summary: this.generateChangeSummary(changes)
    };

    history.push(changeRecord);

    // Keep only last 100 changes per document
    if (history.length > 100) {
      history.shift();
    }

    this.changeHistory.set(documentId, history);
    this.saveChangeHistory();
  }

  generateChangeSummary(changes) {
    const stats = this.calculateChangeStats(changes);
    let summary = '';

    if (changes.title) {
      summary += 'Title changed. ';
    }

    if (stats.additions > 0) {
      summary += `+${stats.additions} additions. `;
    }

    if (stats.deletions > 0) {
      summary += `-${stats.deletions} deletions. `;
    }

    if (stats.modifications > 0) {
      summary += `${stats.modifications} modifications. `;
    }

    if (changes.comments && (changes.comments.added.length > 0 || changes.comments.removed.length > 0)) {
      summary += `${changes.comments.added.length} comments added, ${changes.comments.removed.length} removed. `;
    }

    return summary.trim() || 'Minor changes';
  }

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

    return { additions, deletions, modifications };
  }

  updateChangeIndicators(documentId, changes) {
    // Update toolbar indicator
    this.updateToolbarIndicator(changes);

    // Update document title if tracking is visible
    this.updateDocumentTitle(changes);
  }

  updateToolbarIndicator(changes) {
    const toolbar = document.getElementById('legal-git-toolbar');
    if (!toolbar) return;

    // Remove existing indicator
    const existing = toolbar.querySelector('.legal-git-change-indicator');
    if (existing) existing.remove();

    const stats = this.calculateChangeStats(changes);
    if (stats.additions + stats.deletions + stats.modifications === 0) return;

    const indicator = document.createElement('div');
    indicator.className = 'legal-git-change-indicator';
    indicator.innerHTML = `
      <div style="
        background: linear-gradient(135deg, #ffc107 0%, #ffca28 100%);
        color: #856404;
        font-size: 11px;
        padding: 6px 10px;
        border-radius: 16px;
        margin: 8px 0;
        text-align: center;
        cursor: pointer;
        border: 1px solid #ffeaa7;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        transition: all 0.2s ease;
      " onmouseover="this.style.transform='scale(1.05)'" onmouseout="this.style.transform='scale(1)'">
        <div style="font-weight: 500; margin-bottom: 2px;">📝 ${stats.additions + stats.deletions + stats.modifications} Changes</div>
        <div style="font-size: 10px; opacity: 0.8;">Click to view diff</div>
      </div>
    `;

    indicator.addEventListener('click', () => {
      this.diffVisualizer.showDiffModal(this.currentDocumentId, changes);
    });

    toolbar.appendChild(indicator);
  }

  updateDocumentTitle(changes) {
    if (changes.title) {
      // Could add a visual indicator that the title has changed
      console.log('Document title changed');
    }
  }

  showChangeNotification(changes) {
    const stats = this.calculateChangeStats(changes);
    const totalChanges = stats.additions + stats.deletions + stats.modifications;

    if (totalChanges === 0) return;

    const message = `Document updated: ${totalChanges} changes detected`;

    // Use existing toast system if available
    if (window.commitUIManager) {
      window.commitUIManager.showToast(message, 'info');
    }
  }

  showHistoryModal(documentId) {
    const modal = this.createHistoryModal(documentId);
    document.body.appendChild(modal);
  }

  createHistoryModal(documentId) {
    const modal = document.createElement('div');
    modal.className = 'legal-git-modal';
    modal.id = 'change-history-modal';

    const history = this.changeHistory.get(documentId) || [];
    const cachedDoc = this.documentConverter.getCachedContent(documentId);
    const documentTitle = cachedDoc?.content?.title || 'Document';

    modal.innerHTML = `
      <div class="legal-git-modal-content" style="max-width: 800px; height: 600px;">
        <div class="legal-git-modal-header">
          <h3 class="legal-git-modal-title">📚 Document History - ${documentTitle}</h3>
          <button class="legal-git-modal-close" onclick="this.closest('.legal-git-modal').remove()">×</button>
        </div>

        <div class="change-history-content" style="padding: 20px; overflow-y: auto; height: calc(100% - 80px);">
          ${this.generateHistoryView(history)}
        </div>
      </div>
    `;

    this.setupHistoryModalEvents(modal, documentId);
    return modal;
  }

  generateHistoryView(history) {
    if (history.length === 0) {
      return `
        <div style="text-align: center; padding: 40px; color: #666;">
          <div style="font-size: 48px; margin-bottom: 16px;">📝</div>
          <div style="font-size: 18px; margin-bottom: 8px;">No changes recorded yet</div>
          <div style="font-size: 14px;">Changes will appear here as you edit the document</div>
        </div>
      `;
    }

    // Sort by timestamp (newest first)
    const sortedHistory = [...history].sort((a, b) =>
      new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    );

    let historyHtml = '<div class="change-history-timeline">';

    sortedHistory.forEach((change, index) => {
      const timeAgo = this.formatTimeAgo(change.timestamp);
      const stats = this.calculateChangeStats(change.changes);

      historyHtml += `
        <div class="change-history-item" style="
          border-left: 3px solid #1a73e8;
          padding-left: 16px;
          margin-bottom: 20px;
          position: relative;
        ">
          <div class="change-history-dot" style="
            position: absolute;
            left: -7px;
            top: 8px;
            width: 12px;
            height: 12px;
            background: #1a73e8;
            border-radius: 50%;
            border: 2px solid white;
            box-shadow: 0 0 0 2px #1a73e8;
          "></div>

          <div class="change-history-header" style="
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
          ">
            <div style="font-weight: 500; color: #1f1f1f;">
              ${change.summary}
            </div>
            <div style="font-size: 12px; color: #5f6368;">
              ${timeAgo}
            </div>
          </div>

          <div class="change-history-stats" style="
            display: flex;
            gap: 16px;
            font-size: 12px;
            margin-bottom: 8px;
          ">
            ${stats.additions > 0 ? `<span style="color: #28a745;">+${stats.additions} additions</span>` : ''}
            ${stats.deletions > 0 ? `<span style="color: #dc3545;">-${stats.deletions} deletions</span>` : ''}
            ${stats.modifications > 0 ? `<span style="color: #ffc107;">${stats.modifications} modifications</span>` : ''}
          </div>

          <div class="change-history-actions" style="
            display: flex;
            gap: 8px;
            margin-top: 8px;
          ">
            <button onclick="window.changeTracker.showChangeDetails('${change.id}')" style="
              padding: 4px 8px;
              background: #f8f9fa;
              border: 1px solid #dadce0;
              border-radius: 4px;
              font-size: 11px;
              cursor: pointer;
            ">View Details</button>
            <button onclick="window.changeTracker.showDiffFromHistory('${change.id}')" style="
              padding: 4px 8px;
              background: #e3f2fd;
              border: 1px solid #2196f3;
              border-radius: 4px;
              font-size: 11px;
              cursor: pointer;
              color: #1976d2;
            ">Show Diff</button>
          </div>
        </div>
      `;
    });

    historyHtml += '</div>';
    return historyHtml;
  }

  formatTimeAgo(timestamp) {
    const now = new Date();
    const changeTime = new Date(timestamp);
    const diffMs = now.getTime() - changeTime.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;

    return changeTime.toLocaleDateString();
  }

  setupHistoryModalEvents(modal, documentId) {
    // Keyboard navigation
    modal.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        modal.remove();
      }
    });
  }

  showChangeDetails(changeId) {
    const change = this.findChangeById(changeId);
    if (!change) return;

    const detailModal = document.createElement('div');
    detailModal.className = 'legal-git-modal';
    detailModal.innerHTML = `
      <div class="legal-git-modal-content" style="max-width: 600px;">
        <div class="legal-git-modal-header">
          <h3 class="legal-git-modal-title">📋 Change Details</h3>
          <button class="legal-git-modal-close" onclick="this.closest('.legal-git-modal').remove()">×</button>
        </div>

        <div style="padding: 20px;">
          <div style="margin-bottom: 16px;">
            <strong>Timestamp:</strong> ${new Date(change.timestamp).toLocaleString()}
          </div>
          <div style="margin-bottom: 16px;">
            <strong>Summary:</strong> ${change.summary}
          </div>
          <div style="margin-bottom: 16px;">
            <strong>Changes:</strong>
            <pre style="background: #f8f9fa; padding: 12px; border-radius: 4px; margin-top: 8px; overflow-x: auto;">${JSON.stringify(change.changes, null, 2)}</pre>
          </div>
        </div>
      </div>
    `;

    document.body.appendChild(detailModal);
  }

  showDiffFromHistory(changeId) {
    const change = this.findChangeById(changeId);
    if (!change) return;

    this.diffVisualizer.showDiffModal(this.currentDocumentId, change.changes);
  }

  findChangeById(changeId) {
    for (const [documentId, history] of this.changeHistory.entries()) {
      const change = history.find(c => c.id === changeId);
      if (change) return change;
    }
    return null;
  }

  getChangeHistory(documentId) {
    return this.changeHistory.get(documentId) || [];
  }

  clearHistory(documentId) {
    this.changeHistory.delete(documentId);
    this.saveChangeHistory();
  }

  exportHistory(documentId) {
    const history = this.getChangeHistory(documentId);
    const exportData = {
      documentId: documentId,
      exportedAt: new Date().toISOString(),
      changes: history
    };

    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `document-history-${documentId}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  // Add change tracking controls to toolbar
  addTrackingControls() {
    const toolbar = document.getElementById('legal-git-toolbar');
    if (!toolbar) return;

    const existing = toolbar.querySelector('.legal-git-tracking-controls');
    if (existing) return;

    const controls = document.createElement('div');
    controls.className = 'legal-git-tracking-controls';
    controls.innerHTML = `
      <div style="
        margin-top: 8px;
        padding-top: 8px;
        border-top: 1px solid #f1f3f4;
      ">
        <div style="font-size: 11px; color: #5f6368; margin-bottom: 4px;">Change Tracking</div>
        <div style="display: flex; gap: 4px;">
          <button id="lg-toggle-tracking" style="
            flex: 1;
            padding: 4px 8px;
            background: ${this.trackingEnabled ? '#e8f5e8' : '#f8f9fa'};
            color: ${this.trackingEnabled ? '#137333' : '#5f6368'};
            border: 1px solid ${this.trackingEnabled ? '#c8e6c9' : '#dadce0'};
            border-radius: 4px;
            font-size: 10px;
            cursor: pointer;
          ">${this.trackingEnabled ? '🟢 ON' : '⚫ OFF'}</button>
          <button id="lg-show-history" style="
            flex: 1;
            padding: 4px 8px;
            background: #f8f9fa;
            color: #5f6368;
            border: 1px solid #dadce0;
            border-radius: 4px;
            font-size: 10px;
            cursor: pointer;
          ">📚 History</button>
        </div>
      </div>
    `;

    toolbar.appendChild(controls);

    // Add event listeners
    controls.querySelector('#lg-toggle-tracking').addEventListener('click', () => {
      this.toggleTracking(!this.trackingEnabled);
      this.updateTrackingControls();
    });

    controls.querySelector('#lg-show-history').addEventListener('click', () => {
      this.showHistoryModal(this.currentDocumentId);
    });
  }

  updateTrackingControls() {
    const toggleBtn = document.getElementById('lg-toggle-tracking');
    if (toggleBtn) {
      toggleBtn.textContent = this.trackingEnabled ? '🟢 ON' : '⚫ OFF';
      toggleBtn.style.background = this.trackingEnabled ? '#e8f5e8' : '#f8f9fa';
      toggleBtn.style.color = this.trackingEnabled ? '#137333' : '#5f6368';
      toggleBtn.style.borderColor = this.trackingEnabled ? '#c8e6c9' : '#dadce0';
    }
  }
}

// Export for use in other scripts
window.ChangeTracker = ChangeTracker;
