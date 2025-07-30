// Legal Git Chrome Extension - Conflict Resolution Interface
// Handles merge conflicts and provides resolution UI for legal documents

class ConflictResolver {
  constructor(documentConverter, diffVisualizer) {
    this.documentConverter = documentConverter;
    this.diffVisualizer = diffVisualizer;
    this.activeConflicts = new Map();
    this.resolutionHistory = new Map();
    this.conflictViewOpen = false;
    this.init();
  }

  init() {
    this.setupConflictEventListeners();
    this.injectConflictStyles();
  }

  // Setup event listeners for conflict resolution
  setupConflictEventListeners() {
    window.addEventListener('mergeConflictDetected', (event) => {
      this.handleMergeConflict(event.detail);
    });

    window.addEventListener('legalGitShowConflictResolution', (event) => {
      this.showConflictResolutionModal(event.detail);
    });

    window.addEventListener('legalGitResolveConflict', (event) => {
      this.resolveConflict(event.detail);
    });
  }

  // Inject CSS styles for conflict resolution UI
  injectConflictStyles() {
    const styleId = 'legal-git-conflict-styles';
    if (document.getElementById(styleId)) return;

    const style = document.createElement('style');
    style.id = styleId;
    style.textContent = `
      .legal-git-conflict-container {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.8);
        z-index: 25000;
        display: flex;
        align-items: center;
        justify-content: center;
        font-family: 'Google Sans', Roboto, Arial, sans-serif;
      }

      .legal-git-conflict-modal {
        background: white;
        border-radius: 12px;
        box-shadow: 0 12px 40px rgba(0,0,0,0.4);
        width: 95vw;
        height: 90vh;
        max-width: 1400px;
        display: flex;
        flex-direction: column;
        overflow: hidden;
      }

      .legal-git-conflict-header {
        padding: 20px 24px;
        border-bottom: 2px solid #ea4335;
        background: linear-gradient(135deg, #fff5f5, #fef2f2);
        display: flex;
        justify-content: space-between;
        align-items: center;
      }

      .legal-git-conflict-title {
        font-size: 20px;
        font-weight: 600;
        color: #d93025;
        display: flex;
        align-items: center;
        gap: 12px;
      }

      .legal-git-conflict-close {
        background: none;
        border: none;
        font-size: 28px;
        cursor: pointer;
        color: #5f6368;
        padding: 8px;
        border-radius: 6px;
        transition: all 0.2s;
      }

      .legal-git-conflict-close:hover {
        background: #f1f3f4;
        transform: scale(1.1);
      }

      .legal-git-conflict-content {
        flex: 1;
        display: flex;
        overflow: hidden;
      }

      .legal-git-conflict-sidebar {
        width: 300px;
        background: #f8f9fa;
        border-right: 1px solid #e0e0e0;
        overflow-y: auto;
        padding: 20px;
      }

      .legal-git-conflict-main {
        flex: 1;
        overflow-y: auto;
        padding: 20px 24px;
      }

      .legal-git-conflict-summary {
        background: white;
        border: 1px solid #dadce0;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 20px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
      }

      .legal-git-conflict-summary h4 {
        margin: 0 0 12px 0;
        font-size: 16px;
        font-weight: 600;
        color: #1f1f1f;
        display: flex;
        align-items: center;
        gap: 8px;
      }

      .legal-git-conflict-stat {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 0;
        font-size: 14px;
        border-bottom: 1px solid #f0f0f0;
      }

      .legal-git-conflict-stat:last-child {
        border-bottom: none;
      }

      .legal-git-conflict-count {
        font-weight: 600;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 12px;
      }

      .legal-git-conflict-count.conflicts {
        background: #fce8e6;
        color: #d93025;
      }

      .legal-git-conflict-count.resolved {
        background: #e6f4ea;
        color: #1e8e3e;
      }

      .legal-git-conflict-count.pending {
        background: #fef7e0;
        color: #f29900;
      }

      .legal-git-conflict-list {
        background: white;
        border: 1px solid #dadce0;
        border-radius: 8px;
        overflow: hidden;
        margin-bottom: 20px;
      }

      .legal-git-conflict-item {
        padding: 16px;
        border-bottom: 1px solid #f0f0f0;
        cursor: pointer;
        transition: background 0.2s;
        display: flex;
        align-items: center;
        gap: 12px;
      }

      .legal-git-conflict-item:hover {
        background: #f8f9fa;
      }

      .legal-git-conflict-item.active {
        background: #e8f0fe;
        border-left: 4px solid #1a73e8;
      }

      .legal-git-conflict-item:last-child {
        border-bottom: none;
      }

      .legal-git-conflict-marker {
        width: 12px;
        height: 12px;
        border-radius: 50%;
        flex-shrink: 0;
      }

      .legal-git-conflict-marker.unresolved {
        background: #ea4335;
        box-shadow: 0 0 0 2px #fce8e6;
      }

      .legal-git-conflict-marker.resolved {
        background: #34a853;
        box-shadow: 0 0 0 2px #e6f4ea;
      }

      .legal-git-conflict-details {
        flex: 1;
        min-width: 0;
      }

      .legal-git-conflict-location {
        font-weight: 500;
        color: #1f1f1f;
        margin-bottom: 4px;
      }

      .legal-git-conflict-description {
        font-size: 13px;
        color: #5f6368;
        line-height: 1.4;
      }

      .legal-git-conflict-resolution-area {
        background: #fafafa;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        overflow: hidden;
        margin-bottom: 20px;
      }

      .legal-git-conflict-resolution-header {
        background: #f8f9fa;
        padding: 16px 20px;
        border-bottom: 1px solid #e0e0e0;
        display: flex;
        justify-content: space-between;
        align-items: center;
      }

      .legal-git-conflict-resolution-title {
        font-size: 16px;
        font-weight: 600;
        color: #1f1f1f;
      }

      .legal-git-conflict-actions {
        display: flex;
        gap: 8px;
      }

      .legal-git-conflict-btn {
        padding: 8px 16px;
        border: 1px solid #dadce0;
        border-radius: 4px;
        font-size: 13px;
        cursor: pointer;
        transition: all 0.2s;
        font-weight: 500;
      }

      .legal-git-conflict-btn.accept-current {
        background: #e8f0fe;
        color: #1a73e8;
        border-color: #1a73e8;
      }

      .legal-git-conflict-btn.accept-incoming {
        background: #e6f4ea;
        color: #1e8e3e;
        border-color: #34a853;
      }

      .legal-git-conflict-btn.manual-edit {
        background: #fef7e0;
        color: #f29900;
        border-color: #fbbc04;
      }

      .legal-git-conflict-btn:hover {
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
      }

      .legal-git-conflict-comparison {
        display: flex;
        height: 400px;
      }

      .legal-git-conflict-version {
        flex: 1;
        display: flex;
        flex-direction: column;
        border-right: 1px solid #e0e0e0;
      }

      .legal-git-conflict-version:last-child {
        border-right: none;
      }

      .legal-git-conflict-version-header {
        padding: 12px 16px;
        background: #f8f9fa;
        border-bottom: 1px solid #e0e0e0;
        font-weight: 500;
        display: flex;
        align-items: center;
        gap: 8px;
      }

      .legal-git-conflict-version-content {
        flex: 1;
        padding: 16px;
        overflow-y: auto;
        font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
        font-size: 13px;
        line-height: 1.5;
        white-space: pre-wrap;
      }

      .legal-git-conflict-version.current .legal-git-conflict-version-header {
        background: #e8f0fe;
        color: #1a73e8;
      }

      .legal-git-conflict-version.incoming .legal-git-conflict-version-header {
        background: #e6f4ea;
        color: #1e8e3e;
      }

      .legal-git-conflict-version.resolved .legal-git-conflict-version-header {
        background: #fef7e0;
        color: #f29900;
      }

      .legal-git-conflict-manual-editor {
        background: white;
        border: 1px solid #dadce0;
        border-radius: 8px;
        padding: 16px;
        margin-top: 16px;
        font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
        font-size: 13px;
        line-height: 1.5;
        min-height: 200px;
        resize: vertical;
        width: 100%;
      }

      .legal-git-conflict-progress {
        background: white;
        border: 1px solid #dadce0;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 20px;
      }

      .legal-git-conflict-progress-bar {
        height: 8px;
        background: #f0f0f0;
        border-radius: 4px;
        overflow: hidden;
        margin-bottom: 8px;
      }

      .legal-git-conflict-progress-fill {
        height: 100%;
        background: linear-gradient(90deg, #34a853, #1e8e3e);
        transition: width 0.3s ease;
      }

      .legal-git-conflict-progress-text {
        font-size: 13px;
        color: #5f6368;
        text-align: center;
      }

      .legal-git-conflict-footer {
        padding: 20px 24px;
        border-top: 1px solid #e0e0e0;
        background: #f8f9fa;
        display: flex;
        justify-content: space-between;
        align-items: center;
      }

      .legal-git-conflict-footer-actions {
        display: flex;
        gap: 12px;
      }

      .legal-git-conflict-footer-btn {
        padding: 10px 20px;
        border: none;
        border-radius: 6px;
        font-size: 14px;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s;
      }

      .legal-git-conflict-footer-btn.primary {
        background: #1a73e8;
        color: white;
      }

      .legal-git-conflict-footer-btn.secondary {
        background: #f8f9fa;
        color: #5f6368;
        border: 1px solid #dadce0;
      }

      .legal-git-conflict-footer-btn:hover {
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
      }

      .legal-git-conflict-footer-btn:disabled {
        opacity: 0.5;
        cursor: not-allowed;
        transform: none;
        box-shadow: none;
      }

      .legal-git-conflict-notification {
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

      .legal-git-conflict-notification.error {
        border-left: 4px solid #ea4335;
        background: #fce8e6;
      }

      .legal-git-conflict-notification.success {
        border-left: 4px solid #34a853;
        background: #e6f4ea;
      }

      .legal-git-conflict-notification.warning {
        border-left: 4px solid #fbbc04;
        background: #fef7e0;
      }

      @keyframes conflictPulse {
        0% { transform: scale(1); opacity: 1; }
        50% { transform: scale(1.05); opacity: 0.8; }
        100% { transform: scale(1); opacity: 1; }
      }

      .legal-git-conflict-pulse {
        animation: conflictPulse 2s infinite;
      }
    `;

    document.head.appendChild(style);
  }

  // Handle merge conflict detection
  handleMergeConflict(conflictData) {
    console.log('Merge conflict detected:', conflictData);

    // Store conflict data
    this.activeConflicts.set(conflictData.id, conflictData);

    // Show conflict notification
    this.showConflictNotification(conflictData);

    // Update UI indicators
    this.updateConflictIndicators(conflictData);
  }

  // Show conflict notification
  showConflictNotification(conflictData) {
    const notification = document.createElement('div');
    notification.className = 'legal-git-conflict-notification error';
    notification.innerHTML = `
      <div style="font-size: 24px;">⚠️</div>
      <div>
        <div style="font-weight: 600; margin-bottom: 4px;">Merge Conflict Detected</div>
        <div style="font-size: 13px; color: #5f6368;">
          ${conflictData.conflictCount} conflicts found in "${conflictData.documentTitle}"
        </div>
        <button onclick="this.parentElement.parentElement.remove(); window.conflictResolver.showConflictResolutionModal('${conflictData.id}');"
                style="margin-top: 8px; padding: 6px 12px; background: #ea4335; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 12px;">
          Resolve Conflicts
        </button>
      </div>
    `;

    document.body.appendChild(notification);

    // Auto-remove notification after 10 seconds
    setTimeout(() => {
      if (notification.parentNode) {
        notification.remove();
      }
    }, 10000);
  }

  // Show conflict resolution modal
  showConflictResolutionModal(conflictId) {
    if (this.conflictViewOpen) {
      this.closeConflictModal();
    }

    const conflictData = this.activeConflicts.get(conflictId);
    if (!conflictData) {
      console.error('Conflict data not found:', conflictId);
      return;
    }

    const modal = this.createConflictModal(conflictData);
    document.body.appendChild(modal);
    this.conflictViewOpen = true;
    this.currentConflictId = conflictId;

    // Initialize conflict resolution state
    this.initializeConflictResolution(conflictData);

    // Focus trap
    setTimeout(() => {
      const closeBtn = modal.querySelector('.legal-git-conflict-close');
      if (closeBtn) closeBtn.focus();
    }, 100);
  }

  // Create conflict resolution modal
  createConflictModal(conflictData) {
    const modal = document.createElement('div');
    modal.className = 'legal-git-conflict-container';
    modal.id = 'legal-git-conflict-modal';

    modal.innerHTML = `
      <div class="legal-git-conflict-modal">
        <div class="legal-git-conflict-header">
          <div class="legal-git-conflict-title">
            <span>⚠️</span>
            <span>Resolve Merge Conflicts - ${conflictData.documentTitle}</span>
          </div>
          <button class="legal-git-conflict-close" onclick="window.conflictResolver.closeConflictModal()">×</button>
        </div>

        <div class="legal-git-conflict-content">
          <div class="legal-git-conflict-sidebar">
            ${this.generateConflictSummary(conflictData)}
            ${this.generateConflictList(conflictData)}
            ${this.generateConflictProgress(conflictData)}
          </div>

          <div class="legal-git-conflict-main">
            <div class="legal-git-conflict-resolution-area">
              <div class="legal-git-conflict-resolution-header">
                <div class="legal-git-conflict-resolution-title">
                  Conflict Resolution
                </div>
                <div class="legal-git-conflict-actions">
                  <button class="legal-git-conflict-btn accept-current" onclick="window.conflictResolver.acceptCurrentVersion()">
                    Accept Current
                  </button>
                  <button class="legal-git-conflict-btn accept-incoming" onclick="window.conflictResolver.acceptIncomingVersion()">
                    Accept Incoming
                  </button>
                  <button class="legal-git-conflict-btn manual-edit" onclick="window.conflictResolver.enableManualEdit()">
                    Manual Edit
                  </button>
                </div>
              </div>

              <div class="legal-git-conflict-comparison" id="conflict-comparison">
                ${this.generateConflictComparison(conflictData)}
              </div>
            </div>
          </div>
        </div>

        <div class="legal-git-conflict-footer">
          <div style="font-size: 13px; color: #5f6368;">
            Resolve all conflicts to complete the merge
          </div>
          <div class="legal-git-conflict-footer-actions">
            <button class="legal-git-conflict-footer-btn secondary" onclick="window.conflictResolver.closeConflictModal()">
              Cancel
            </button>
            <button class="legal-git-conflict-footer-btn primary" id="complete-merge-btn" onclick="window.conflictResolver.completeMerge()" disabled>
              Complete Merge
            </button>
          </div>
        </div>
      </div>
    `;

    this.setupConflictModalEvents(modal, conflictData);
    return modal;
  }

  // Generate conflict summary
  generateConflictSummary(conflictData) {
    const totalConflicts = conflictData.conflicts.length;
    const resolvedConflicts = conflictData.conflicts.filter(c => c.resolved).length;
    const pendingConflicts = totalConflicts - resolvedConflicts;

    return `
      <div class="legal-git-conflict-summary">
        <h4>📊 Conflict Summary</h4>
        <div class="legal-git-conflict-stat">
          <span>Total Conflicts:</span>
          <span class="legal-git-conflict-count conflicts">${totalConflicts}</span>
        </div>
        <div class="legal-git-conflict-stat">
          <span>Resolved:</span>
          <span class="legal-git-conflict-count resolved">${resolvedConflicts}</span>
        </div>
        <div class="legal-git-conflict-stat">
          <span>Pending:</span>
          <span class="legal-git-conflict-count pending">${pendingConflicts}</span>
        </div>
      </div>
    `;
  }

  // Generate conflict list
  generateConflictList(conflictData) {
    let listHtml = `
      <div class="legal-git-conflict-summary">
        <h4>📝 Conflicts</h4>
        <div class="legal-git-conflict-list">
    `;

    conflictData.conflicts.forEach((conflict, index) => {
      const isActive = index === 0 ? 'active' : '';
      const markerClass = conflict.resolved ? 'resolved' : 'unresolved';

      listHtml += `
        <div class="legal-git-conflict-item ${isActive}" data-conflict-index="${index}" onclick="window.conflictResolver.selectConflict(${index})">
          <div class="legal-git-conflict-marker ${markerClass}"></div>
          <div class="legal-git-conflict-details">
            <div class="legal-git-conflict-location">${conflict.location}</div>
            <div class="legal-git-conflict-description">${conflict.description}</div>
          </div>
        </div>
      `;
    });

    listHtml += '</div></div>';
    return listHtml;
  }

  // Generate conflict progress
  generateConflictProgress(conflictData) {
    const totalConflicts = conflictData.conflicts.length;
    const resolvedConflicts = conflictData.conflicts.filter(c => c.resolved).length;
    const progressPercentage = totalConflicts > 0 ? (resolvedConflicts / totalConflicts) * 100 : 0;

    return `
      <div class="legal-git-conflict-progress">
        <div class="legal-git-conflict-progress-bar">
          <div class="legal-git-conflict-progress-fill" style="width: ${progressPercentage}%"></div>
        </div>
        <div class="legal-git-conflict-progress-text">
          ${resolvedConflicts} of ${totalConflicts} conflicts resolved
        </div>
      </div>
    `;
  }

  // Generate conflict comparison view
  generateConflictComparison(conflictData) {
    const currentConflict = conflictData.conflicts[0]; // Show first conflict initially

    return `
      <div class="legal-git-conflict-version current">
        <div class="legal-git-conflict-version-header">
          <span>📝</span>
          <span>Current Version (${conflictData.currentBranch})</span>
        </div>
        <div class="legal-git-conflict-version-content" id="current-version-content">
          ${this.escapeHtml(currentConflict.currentVersion)}
        </div>
      </div>

      <div class="legal-git-conflict-version incoming">
        <div class="legal-git-conflict-version-header">
          <span>📥</span>
          <span>Incoming Version (${conflictData.incomingBranch})</span>
        </div>
        <div class="legal-git-conflict-version-content" id="incoming-version-content">
          ${this.escapeHtml(currentConflict.incomingVersion)}
        </div>
      </div>

      <div class="legal-git-conflict-version resolved">
        <div class="legal-git-conflict-version-header">
          <span>✅</span>
          <span>Resolved Version</span>
        </div>
        <div class="legal-git-conflict-version-content" id="resolved-version-content">
          <textarea class="legal-git-conflict-manual-editor" id="manual-editor" placeholder="Edit the resolved version here..." disabled>
            ${this.escapeHtml(currentConflict.resolvedVersion || '')}
          </textarea>
        </div>
      </div>
    `;
  }

  // Initialize conflict resolution state
  initializeConflictResolution(conflictData) {
    this.currentConflictIndex = 0;
    this.conflictData = conflictData;
    this.updateConflictDisplay();
  }

  // Select a specific conflict
  selectConflict(index) {
    this.currentConflictIndex = index;
    this.updateConflictDisplay();

    // Update active state in sidebar
    const items = document.querySelectorAll('.legal-git-conflict-item');
    items.forEach(item => item.classList.remove('active'));
    items[index].classList.add('active');
  }

  // Update conflict display
  updateConflictDisplay() {
    const conflict = this.conflictData.conflicts[this.currentConflictIndex];
    if (!conflict) return;

    const currentContent = document.getElementById('current-version-content');
    const incomingContent = document.getElementById('incoming-version-content');
    const manualEditor = document.getElementById('manual-editor');

    if (currentContent) {
      currentContent.textContent = conflict.currentVersion;
    }
    if (incomingContent) {
      incomingContent.textContent = conflict.incomingVersion;
    }
    if (manualEditor) {
      manualEditor.value = conflict.resolvedVersion || '';
    }
  }

  // Accept current version
  acceptCurrentVersion() {
    const conflict = this.conflictData.conflicts[this.currentConflictIndex];
    conflict.resolvedVersion = conflict.currentVersion;
    conflict.resolved = true;
    conflict.resolutionMethod = 'current';

    this.updateConflictStatus();
    this.moveToNextConflict();
  }

  // Accept incoming version
  acceptIncomingVersion() {
    const conflict = this.conflictData.conflicts[this.currentConflictIndex];
    conflict.resolvedVersion = conflict.incomingVersion;
    conflict.resolved = true;
    conflict.resolutionMethod = 'incoming';

    this.updateConflictStatus();
    this.moveToNextConflict();
  }

  // Enable manual editing
  enableManualEdit() {
    const manualEditor = document.getElementById('manual-editor');
    if (manualEditor) {
      manualEditor.disabled = false;
      manualEditor.focus();

      // Save manual changes
      manualEditor.addEventListener('input', () => {
        const conflict = this.conflictData.conflicts[this.currentConflictIndex];
        conflict.resolvedVersion = manualEditor.value;
        conflict.resolved = manualEditor.value.trim() !== '';
        conflict.resolutionMethod = 'manual';

        this.updateConflictStatus();
      });
    }
  }

  // Move to next unresolved conflict
  moveToNextConflict() {
    const nextIndex = this.findNextUnresolvedConflict();
    if (nextIndex !== -1) {
      this.selectConflict(nextIndex);
    }
  }

  // Find next unresolved conflict
  findNextUnresolvedConflict() {
    for (let i = 0; i < this.conflictData.conflicts.length; i++) {
      if (!this.conflictData.conflicts[i].resolved) {
        return i;
      }
    }
    return -1;
  }

  // Update conflict status
  updateConflictStatus() {
    // Update progress bar
    const totalConflicts = this.conflictData.conflicts.length;
    const resolvedConflicts = this.conflictData.conflicts.filter(c => c.resolved).length;
    const progressPercentage = (resolvedConflicts / totalConflicts) * 100;

    const progressFill = document.querySelector('.legal-git-conflict-progress-fill');
    const progressText = document.querySelector('.legal-git-conflict-progress-text');

    if (progressFill) {
      progressFill.style.width = `${progressPercentage}%`;
    }
    if (progressText) {
      progressText.textContent = `${resolvedConflicts} of ${totalConflicts} conflicts resolved`;
    }

    // Update conflict markers
    const markers = document.querySelectorAll('.legal-git-conflict-marker');
    this.conflictData.conflicts.forEach((conflict, index) => {
      if (markers[index]) {
        markers[index].className = `legal-git-conflict-marker ${conflict.resolved ? 'resolved' : 'unresolved'}`;
      }
    });

    // Update summary
    const summaryStats = document.querySelectorAll('.legal-git-conflict-stat .legal-git-conflict-count');
    if (summaryStats.length >= 3) {
      summaryStats[1].textContent = resolvedConflicts;
      summaryStats[2].textContent = totalConflicts - resolvedConflicts;
    }

    // Enable/disable complete merge button
    const completeMergeBtn = document.getElementById('complete-merge-btn');
    if (completeMergeBtn) {
      completeMergeBtn.disabled = resolvedConflicts !== totalConflicts;
    }
  }

  // Complete merge after all conflicts resolved
  async completeMerge() {
    const allResolved = this.conflictData.conflicts.every(c => c.resolved);
    if (!allResolved) {
      alert('Please resolve all conflicts before completing the merge.');
      return;
    }

    try {
      // Show loading state
      const completeMergeBtn = document.getElementById('complete-merge-btn');
      if (completeMergeBtn) {
        completeMergeBtn.textContent = 'Completing...';
        completeMergeBtn.disabled = true;
      }

      // Simulate merge completion
      await this.performMerge();

      // Show success notification
      this.showSuccessNotification('Merge completed successfully!');

      // Close modal
      this.closeConflictModal();

      // Update UI
      this.updateUIAfterMerge();

    } catch (error) {
      console.error('Error completing merge:', error);
      alert('Failed to complete merge: ' + error.message);
    }
  }

  // Perform the actual merge
  async performMerge() {
    // Simulate API call to complete merge
    return new Promise((resolve) => {
      setTimeout(() => {
        console.log('Merge completed with resolutions:', this.conflictData.conflicts);
        resolve();
      }, 2000);
    });
  }

  // Show success notification
  showSuccessNotification(message) {
    const notification = document.createElement('div');
    notification.className = 'legal-git-conflict-notification success';
    notification.innerHTML = `
      <div style="font-size: 24px;">✅</div>
      <div>
        <div style="font-weight: 600; margin-bottom: 4px;">Success</div>
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

  // Update UI after merge completion
  updateUIAfterMerge() {
    // Remove conflict indicators
    const indicators = document.querySelectorAll('.legal-git-conflict-indicator');
    indicators.forEach(indicator => indicator.remove());

    // Update git status
    if (window.gitOpsManager) {
      window.gitOpsManager.refreshStatus();
    }

    // Clear active conflicts
    this.activeConflicts.delete(this.currentConflictId);
  }

  // Update conflict indicators in toolbar
  updateConflictIndicators(conflictData) {
    const toolbar = document.getElementById('legal-git-toolbar');
    if (!toolbar) return;

    // Remove existing indicators
    const existing = toolbar.querySelector('.legal-git-conflict-indicator');
    if (existing) existing.remove();

    const indicator = document.createElement('div');
    indicator.className = 'legal-git-conflict-indicator legal-git-conflict-pulse';
    indicator.style.cssText = `
      background: #ea4335;
      color: white;
      font-size: 11px;
      padding: 6px 10px;
      border-radius: 12px;
      margin-top: 8px;
      text-align: center;
      cursor: pointer;
      border: 1px solid #d93025;
      font-weight: 600;
    `;
    indicator.textContent = `⚠️ ${conflictData.conflictCount} conflicts`;
    indicator.title = 'Click to resolve conflicts';

    indicator.addEventListener('click', () => {
      this.showConflictResolutionModal(conflictData.id);
    });

    toolbar.appendChild(indicator);
  }

  // Setup conflict modal event listeners
  setupConflictModalEvents(modal, conflictData) {
    // Keyboard navigation
    modal.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        this.closeConflictModal();
      } else if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
        e.preventDefault();
        const direction = e.key === 'ArrowUp' ? -1 : 1;
        const newIndex = Math.max(0, Math.min(conflictData.conflicts.length - 1, this.currentConflictIndex + direction));
        this.selectConflict(newIndex);
      }
    });

    // Make globally available
    window.conflictResolver = this;
  }

  // Close conflict modal
  closeConflictModal() {
    const modal = document.getElementById('legal-git-conflict-modal');
    if (modal) {
      modal.remove();
      this.conflictViewOpen = false;
      this.currentConflictId = null;
    }
  }

  // Escape HTML for safe display
  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // Simulate conflict detection for testing
  simulateConflict(documentId) {
    const conflictData = {
      id: `conflict_${Date.now()}`,
      documentId: documentId,
      documentTitle: 'Legal Contract Draft',
      currentBranch: 'main',
      incomingBranch: 'feature/updates',
      conflictCount: 3,
      conflicts: [
        {
          id: 'conflict_1',
          location: 'Section 2: Terms and Conditions',
          description: 'Conflicting payment terms',
          currentVersion: 'Payment shall be made within 30 days of invoice date.',
          incomingVersion: 'Payment shall be made within 45 days of invoice date.',
          resolvedVersion: null,
          resolved: false,
          resolutionMethod: null
        },
        {
          id: 'conflict_2',
          location: 'Section 4: Liability',
          description: 'Different liability limitations',
          currentVersion: 'Liability shall not exceed $10,000.',
          incomingVersion: 'Liability shall not exceed $25,000.',
          resolvedVersion: null,
          resolved: false,
          resolutionMethod: null
        },
        {
          id: 'conflict_3',
          location: 'Section 6: Termination',
          description: 'Termination notice period',
          currentVersion: 'Either party may terminate with 30 days notice.',
          incomingVersion: 'Either party may terminate with 60 days notice.',
          resolvedVersion: null,
          resolved: false,
          resolutionMethod: null
        }
      ]
    };

    this.handleMergeConflict(conflictData);
  }
}

// Export for use in other scripts
window.ConflictResolver = ConflictResolver;
