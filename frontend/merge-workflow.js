// Legal Git Chrome Extension - Merge Workflow for Parallel Branches
// Handles branch merging, conflict detection, and merge UI workflow

class MergeWorkflow {
  constructor(gitOpsManager, conflictResolver, timelineView) {
    this.gitOpsManager = gitOpsManager;
    this.conflictResolver = conflictResolver;
    this.timelineView = timelineView;
    this.activeMerges = new Map();
    this.mergeViewOpen = false;
    this.currentMergeId = null;
    this.init();
  }

  init() {
    this.setupMergeEventListeners();
    this.injectMergeStyles();
  }

  // Setup event listeners for merge workflow
  setupMergeEventListeners() {
    window.addEventListener('legalGitInitiateMerge', (event) => {
      this.initiateMerge(event.detail);
    });

    window.addEventListener('legalGitShowMergeWorkflow', (event) => {
      this.showMergeWorkflowModal(event.detail);
    });

    window.addEventListener('branchMergeRequested', (event) => {
      this.handleMergeRequest(event.detail);
    });
  }

  // Inject CSS styles for merge workflow
  injectMergeStyles() {
    const styleId = 'legal-git-merge-styles';
    if (document.getElementById(styleId)) return;

    const style = document.createElement('style');
    style.id = styleId;
    style.textContent = `
      .legal-git-merge-container {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.8);
        z-index: 23000;
        display: flex;
        align-items: center;
        justify-content: center;
        font-family: 'Google Sans', Roboto, Arial, sans-serif;
      }

      .legal-git-merge-modal {
        background: white;
        border-radius: 12px;
        box-shadow: 0 12px 40px rgba(0,0,0,0.4);
        width: 95vw;
        height: 90vh;
        max-width: 1500px;
        display: flex;
        flex-direction: column;
        overflow: hidden;
      }

      .legal-git-merge-header {
        padding: 20px 24px;
        border-bottom: 1px solid #e0e0e0;
        background: linear-gradient(135deg, #e8f0fe, #f8f9fa);
        display: flex;
        justify-content: space-between;
        align-items: center;
      }

      .legal-git-merge-title {
        font-size: 20px;
        font-weight: 600;
        color: #1a73e8;
        display: flex;
        align-items: center;
        gap: 12px;
      }

      .legal-git-merge-close {
        background: none;
        border: none;
        font-size: 28px;
        cursor: pointer;
        color: #5f6368;
        padding: 8px;
        border-radius: 6px;
        transition: all 0.2s;
      }

      .legal-git-merge-close:hover {
        background: #f1f3f4;
        transform: scale(1.1);
      }

      .legal-git-merge-content {
        flex: 1;
        display: flex;
        overflow: hidden;
      }

      .legal-git-merge-sidebar {
        width: 350px;
        background: #f8f9fa;
        border-right: 1px solid #e0e0e0;
        overflow-y: auto;
        padding: 20px;
      }

      .legal-git-merge-main {
        flex: 1;
        overflow-y: auto;
        padding: 20px 24px;
      }

      .legal-git-merge-step {
        background: white;
        border: 1px solid #dadce0;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 16px;
      }

      .legal-git-merge-step.active {
        border-color: #1a73e8;
        background: #e8f0fe;
      }

      .legal-git-merge-step.completed {
        border-color: #34a853;
        background: #e6f4ea;
      }

      .legal-git-merge-step.error {
        border-color: #ea4335;
        background: #fce8e6;
      }

      .legal-git-merge-step-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
      }

      .legal-git-merge-step-title {
        font-size: 14px;
        font-weight: 600;
        color: #1f1f1f;
        display: flex;
        align-items: center;
        gap: 8px;
      }

      .legal-git-merge-step-status {
        font-size: 12px;
        padding: 2px 8px;
        border-radius: 12px;
        font-weight: 500;
      }

      .legal-git-merge-step-status.pending {
        background: #fef7e0;
        color: #f29900;
      }

      .legal-git-merge-step-status.active {
        background: #e8f0fe;
        color: #1a73e8;
      }

      .legal-git-merge-step-status.completed {
        background: #e6f4ea;
        color: #1e8e3e;
      }

      .legal-git-merge-step-status.error {
        background: #fce8e6;
        color: #d93025;
      }

      .legal-git-merge-step-description {
        font-size: 13px;
        color: #5f6368;
        line-height: 1.4;
      }

      .legal-git-merge-branches {
        background: white;
        border: 1px solid #dadce0;
        border-radius: 8px;
        overflow: hidden;
        margin-bottom: 20px;
      }

      .legal-git-merge-branches-header {
        padding: 16px 20px;
        background: #f8f9fa;
        border-bottom: 1px solid #e0e0e0;
        font-weight: 600;
        color: #1f1f1f;
      }

      .legal-git-merge-branch-comparison {
        display: flex;
        padding: 20px;
        gap: 20px;
      }

      .legal-git-merge-branch {
        flex: 1;
        text-align: center;
      }

      .legal-git-merge-branch-icon {
        width: 60px;
        height: 60px;
        border-radius: 50%;
        margin: 0 auto 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 24px;
        color: white;
        font-weight: 600;
      }

      .legal-git-merge-branch-icon.source {
        background: linear-gradient(135deg, #1a73e8, #4285f4);
      }

      .legal-git-merge-branch-icon.target {
        background: linear-gradient(135deg, #34a853, #0f9d58);
      }

      .legal-git-merge-branch-name {
        font-size: 16px;
        font-weight: 600;
        color: #1f1f1f;
        margin-bottom: 4px;
      }

      .legal-git-merge-branch-info {
        font-size: 13px;
        color: #5f6368;
        line-height: 1.4;
      }

      .legal-git-merge-arrow {
        align-self: center;
        font-size: 32px;
        color: #5f6368;
        margin: 0 20px;
      }

      .legal-git-merge-preview {
        background: #fafafa;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        margin-bottom: 20px;
        overflow: hidden;
      }

      .legal-git-merge-preview-header {
        padding: 16px 20px;
        background: #f8f9fa;
        border-bottom: 1px solid #e0e0e0;
        display: flex;
        justify-content: space-between;
        align-items: center;
      }

      .legal-git-merge-preview-title {
        font-size: 16px;
        font-weight: 600;
        color: #1f1f1f;
      }

      .legal-git-merge-preview-content {
        padding: 20px;
        max-height: 300px;
        overflow-y: auto;
      }

      .legal-git-merge-change-summary {
        display: flex;
        gap: 16px;
        margin-bottom: 16px;
      }

      .legal-git-merge-change-stat {
        flex: 1;
        text-align: center;
        padding: 12px;
        background: white;
        border: 1px solid #dadce0;
        border-radius: 6px;
      }

      .legal-git-merge-change-stat-value {
        font-size: 20px;
        font-weight: 600;
        margin-bottom: 4px;
      }

      .legal-git-merge-change-stat-value.additions {
        color: #34a853;
      }

      .legal-git-merge-change-stat-value.deletions {
        color: #ea4335;
      }

      .legal-git-merge-change-stat-value.modifications {
        color: #fbbc04;
      }

      .legal-git-merge-change-stat-label {
        font-size: 12px;
        color: #5f6368;
        font-weight: 500;
      }

      .legal-git-merge-controls {
        background: white;
        border: 1px solid #dadce0;
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 20px;
      }

      .legal-git-merge-controls-header {
        font-size: 16px;
        font-weight: 600;
        color: #1f1f1f;
        margin-bottom: 16px;
      }

      .legal-git-merge-control-group {
        margin-bottom: 16px;
      }

      .legal-git-merge-control-group:last-child {
        margin-bottom: 0;
      }

      .legal-git-merge-control-label {
        display: block;
        font-size: 13px;
        font-weight: 500;
        color: #5f6368;
        margin-bottom: 6px;
      }

      .legal-git-merge-control-options {
        display: flex;
        gap: 12px;
      }

      .legal-git-merge-control-option {
        flex: 1;
        padding: 12px;
        border: 2px solid #dadce0;
        border-radius: 6px;
        cursor: pointer;
        transition: all 0.2s;
        text-align: center;
      }

      .legal-git-merge-control-option:hover {
        border-color: #1a73e8;
        background: #e8f0fe;
      }

      .legal-git-merge-control-option.selected {
        border-color: #1a73e8;
        background: #e8f0fe;
      }

      .legal-git-merge-control-option-title {
        font-size: 13px;
        font-weight: 600;
        color: #1f1f1f;
        margin-bottom: 4px;
      }

      .legal-git-merge-control-option-description {
        font-size: 11px;
        color: #5f6368;
        line-height: 1.3;
      }

      .legal-git-merge-progress {
        background: white;
        border: 1px solid #dadce0;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 20px;
      }

      .legal-git-merge-progress-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;
      }

      .legal-git-merge-progress-title {
        font-size: 14px;
        font-weight: 600;
        color: #1f1f1f;
      }

      .legal-git-merge-progress-percentage {
        font-size: 12px;
        color: #5f6368;
        font-weight: 500;
      }

      .legal-git-merge-progress-bar {
        height: 8px;
        background: #f0f0f0;
        border-radius: 4px;
        overflow: hidden;
        margin-bottom: 8px;
      }

      .legal-git-merge-progress-fill {
        height: 100%;
        background: linear-gradient(90deg, #1a73e8, #4285f4);
        transition: width 0.3s ease;
      }

      .legal-git-merge-progress-steps {
        display: flex;
        justify-content: space-between;
        font-size: 11px;
        color: #5f6368;
      }

      .legal-git-merge-progress-step {
        display: flex;
        align-items: center;
        gap: 4px;
      }

      .legal-git-merge-progress-step.completed {
        color: #1e8e3e;
      }

      .legal-git-merge-progress-step.active {
        color: #1a73e8;
        font-weight: 600;
      }

      .legal-git-merge-footer {
        padding: 20px 24px;
        border-top: 1px solid #e0e0e0;
        background: #f8f9fa;
        display: flex;
        justify-content: space-between;
        align-items: center;
      }

      .legal-git-merge-footer-info {
        font-size: 13px;
        color: #5f6368;
      }

      .legal-git-merge-footer-actions {
        display: flex;
        gap: 12px;
      }

      .legal-git-merge-footer-btn {
        padding: 10px 20px;
        border: none;
        border-radius: 6px;
        font-size: 14px;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s;
      }

      .legal-git-merge-footer-btn.primary {
        background: #1a73e8;
        color: white;
      }

      .legal-git-merge-footer-btn.secondary {
        background: #f8f9fa;
        color: #5f6368;
        border: 1px solid #dadce0;
      }

      .legal-git-merge-footer-btn:hover {
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
      }

      .legal-git-merge-footer-btn:disabled {
        opacity: 0.5;
        cursor: not-allowed;
        transform: none;
        box-shadow: none;
      }

      .legal-git-merge-notification {
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

      .legal-git-merge-notification.success {
        border-left: 4px solid #34a853;
        background: #e6f4ea;
      }

      .legal-git-merge-notification.error {
        border-left: 4px solid #ea4335;
        background: #fce8e6;
      }

      .legal-git-merge-notification.info {
        border-left: 4px solid #1a73e8;
        background: #e8f0fe;
      }

      @keyframes mergeProgress {
        0% { width: 0%; }
        100% { width: 100%; }
      }

      .legal-git-merge-progress-fill.animate {
        animation: mergeProgress 2s ease-in-out;
      }

      @keyframes mergePulse {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.05); }
      }

      .legal-git-merge-step.active .legal-git-merge-step-title {
        animation: mergePulse 2s infinite;
      }
    `;

    document.head.appendChild(style);
  }

  // Initiate merge process
  async initiateMerge(mergeData) {
    const { sourceBranch, targetBranch, documentId } = mergeData;

    console.log('Initiating merge:', mergeData);

    try {
      // Pre-merge validation
      const validation = await this.validateMerge(sourceBranch, targetBranch, documentId);

      if (!validation.canMerge) {
        throw new Error(validation.reason);
      }

      // Create merge workflow
      const mergeId = `merge_${Date.now()}`;
      const mergeWorkflow = {
        id: mergeId,
        sourceBranch,
        targetBranch,
        documentId,
        status: 'preparing',
        conflicts: [],
        steps: [
          { id: 'prepare', title: 'Prepare Merge', status: 'active' },
          { id: 'analyze', title: 'Analyze Changes', status: 'pending' },
          { id: 'conflicts', title: 'Resolve Conflicts', status: 'pending' },
          { id: 'merge', title: 'Complete Merge', status: 'pending' }
        ],
        createdAt: Date.now()
      };

      this.activeMerges.set(mergeId, mergeWorkflow);

      // Show merge workflow modal
      this.showMergeWorkflowModal(mergeId);

      // Start merge process
      await this.executeMergeWorkflow(mergeId);

    } catch (error) {
      console.error('Error initiating merge:', error);
      this.showMergeNotification('Error: ' + error.message, 'error');
    }
  }

  // Validate merge compatibility
  async validateMerge(sourceBranch, targetBranch, documentId) {
    // Simulate validation logic
    return new Promise((resolve) => {
      setTimeout(() => {
        // In real implementation, this would check:
        // - Branch existence
        // - Permissions
        // - Conflicts
        // - Document state

        resolve({
          canMerge: true,
          reason: null,
          conflictCount: 0
        });
      }, 500);
    });
  }

  // Execute merge workflow
  async executeMergeWorkflow(mergeId) {
    const mergeWorkflow = this.activeMerges.get(mergeId);
    if (!mergeWorkflow) return;

    try {
      // Step 1: Prepare merge
      await this.executeMergeStep(mergeId, 'prepare');

      // Step 2: Analyze changes
      await this.executeMergeStep(mergeId, 'analyze');

      // Step 3: Check for conflicts
      const conflicts = await this.checkForConflicts(mergeId);

      if (conflicts.length > 0) {
        mergeWorkflow.conflicts = conflicts;
        await this.executeMergeStep(mergeId, 'conflicts');

        // Show conflict resolution
        this.showConflictResolution(mergeId);
      } else {
        // No conflicts, proceed to merge
        await this.executeMergeStep(mergeId, 'merge');
        this.completeMerge(mergeId);
      }

    } catch (error) {
      console.error('Error executing merge workflow:', error);
      this.updateMergeStep(mergeId, 'error', error.message);
    }
  }

  // Execute individual merge step
  async executeMergeStep(mergeId, stepId) {
    const mergeWorkflow = this.activeMerges.get(mergeId);
    if (!mergeWorkflow) return;

    // Update step status
    this.updateMergeStep(mergeId, stepId, 'active');

    // Simulate step execution
    await new Promise(resolve => setTimeout(resolve, 2000));

    // Complete step
    this.updateMergeStep(mergeId, stepId, 'completed');

    // Update progress
    this.updateMergeProgress(mergeId);
  }

  // Check for merge conflicts
  async checkForConflicts(mergeId) {
    const mergeWorkflow = this.activeMerges.get(mergeId);
    if (!mergeWorkflow) return [];

    // Simulate conflict detection
    return new Promise((resolve) => {
      setTimeout(() => {
        // In real implementation, this would analyze actual document changes
        const hasConflicts = Math.random() > 0.7; // 30% chance of conflicts

        if (hasConflicts) {
          const conflicts = [
            {
              id: 'conflict_1',
              location: 'Section 2: Payment Terms',
              description: 'Conflicting payment schedules',
              currentVersion: 'Payment due within 30 days',
              incomingVersion: 'Payment due within 45 days'
            },
            {
              id: 'conflict_2',
              location: 'Section 5: Liability',
              description: 'Different liability limits',
              currentVersion: 'Liability capped at $10,000',
              incomingVersion: 'Liability capped at $25,000'
            }
          ];
          resolve(conflicts);
        } else {
          resolve([]);
        }
      }, 1000);
    });
  }

  // Show merge workflow modal
  showMergeWorkflowModal(mergeId) {
    if (this.mergeViewOpen) {
      this.closeMergeModal();
    }

    const mergeWorkflow = this.activeMerges.get(mergeId);
    if (!mergeWorkflow) return;

    const modal = this.createMergeModal(mergeWorkflow);
    document.body.appendChild(modal);
    this.mergeViewOpen = true;
    this.currentMergeId = mergeId;

    // Focus trap
    setTimeout(() => {
      const closeBtn = modal.querySelector('.legal-git-merge-close');
      if (closeBtn) closeBtn.focus();
    }, 100);
  }

  // Create merge modal
  createMergeModal(mergeWorkflow) {
    const modal = document.createElement('div');
    modal.className = 'legal-git-merge-container';
    modal.id = 'legal-git-merge-modal';

    modal.innerHTML = `
      <div class="legal-git-merge-modal">
        <div class="legal-git-merge-header">
          <div class="legal-git-merge-title">
            <span>🔀</span>
            <span>Merge Workflow - ${mergeWorkflow.sourceBranch} → ${mergeWorkflow.targetBranch}</span>
          </div>
          <button class="legal-git-merge-close" onclick="window.mergeWorkflow.closeMergeModal()">×</button>
        </div>

        <div class="legal-git-merge-content">
          <div class="legal-git-merge-sidebar">
            ${this.generateMergeSteps(mergeWorkflow)}
            ${this.generateMergeProgress(mergeWorkflow)}
          </div>

          <div class="legal-git-merge-main">
            ${this.generateBranchComparison(mergeWorkflow)}
            ${this.generateMergePreview(mergeWorkflow)}
            ${this.generateMergeControls(mergeWorkflow)}
          </div>
        </div>

        <div class="legal-git-merge-footer">
          <div class="legal-git-merge-footer-info">
            Merge started ${this.formatTimeAgo(mergeWorkflow.createdAt)}
          </div>
          <div class="legal-git-merge-footer-actions">
            <button class="legal-git-merge-footer-btn secondary" onclick="window.mergeWorkflow.cancelMerge()">
              Cancel
            </button>
            <button class="legal-git-merge-footer-btn primary" id="proceed-merge-btn" onclick="window.mergeWorkflow.proceedMerge()" disabled>
              Proceed
            </button>
          </div>
        </div>
      </div>
    `;

    this.setupMergeModalEvents(modal, mergeWorkflow);
    return modal;
  }

  // Generate merge steps
  generateMergeSteps(mergeWorkflow) {
    let stepsHtml = `
      <div class="legal-git-merge-steps">
        <h4 style="margin: 0 0 16px 0; font-size: 14px; font-weight: 600; color: #1f1f1f;">
          📋 Merge Steps
        </h4>
    `;

    mergeWorkflow.steps.forEach((step, index) => {
      const stepClass = step.status === 'active' ? 'active' :
                       step.status === 'completed' ? 'completed' :
                       step.status === 'error' ? 'error' : '';

      stepsHtml += `
        <div class="legal-git-merge-step ${stepClass}" data-step-id="${step.id}">
          <div class="legal-git-merge-step-header">
            <div class="legal-git-merge-step-title">
              ${this.getStepIcon(step.status)}
              <span>${step.title}</span>
            </div>
            <div class="legal-git-merge-step-status ${step.status}">
              ${step.status}
            </div>
          </div>
          <div class="legal-git-merge-step-description">
            ${this.getStepDescription(step.id)}
          </div>
        </div>
      `;
    });

    stepsHtml += '</div>';
    return stepsHtml;
  }

  // Generate merge progress
  generateMergeProgress(mergeWorkflow) {
    const completedSteps = mergeWorkflow.steps.filter(s => s.status === 'completed').length;
    const totalSteps = mergeWorkflow.steps.length;
    const progressPercentage = (completedSteps / totalSteps) * 100;

    return `
      <div class="legal-git-merge-progress">
        <div class="legal-git-merge-progress-header">
          <div class="legal-git-merge-progress-title">Overall Progress</div>
          <div class="legal-git-merge-progress-percentage">${Math.round(progressPercentage)}%</div>
        </div>
        <div class="legal-git-merge-progress-bar">
          <div class="legal-git-merge-progress-fill" style="width: ${progressPercentage}%"></div>
        </div>
        <div class="legal-git-merge-progress-steps">
          <div class="legal-git-merge-progress-step ${completedSteps >= 1 ? 'completed' : completedSteps === 0 ? 'active' : ''}">
            ${completedSteps >= 1 ? '✓' : '1'} Prepare
          </div>
          <div class="legal-git-merge-progress-step ${completedSteps >= 2 ? 'completed' : completedSteps === 1 ? 'active' : ''}">
            ${completedSteps >= 2 ? '✓' : '2'} Analyze
          </div>
          <div class="legal-git-merge-progress-step ${completedSteps >= 3 ? 'completed' : completedSteps === 2 ? 'active' : ''}">
            ${completedSteps >= 3 ? '✓' : '3'} Conflicts
          </div>
          <div class="legal-git-merge-progress-step ${completedSteps >= 4 ? 'completed' : completedSteps === 3 ? 'active' : ''}">
            ${completedSteps >= 4 ? '✓' : '4'} Merge
          </div>
        </div>
      </div>
    `;
  }

  // Generate branch comparison
  generateBranchComparison(mergeWorkflow) {
    return `
      <div class="legal-git-merge-branches">
        <div class="legal-git-merge-branches-header">
          Branch Comparison
        </div>
        <div class="legal-git-merge-branch-comparison">
          <div class="legal-git-merge-branch">
            <div class="legal-git-merge-branch-icon source">
              ${mergeWorkflow.sourceBranch.substring(0, 2).toUpperCase()}
            </div>
            <div class="legal-git-merge-branch-name">${mergeWorkflow.sourceBranch}</div>
            <div class="legal-git-merge-branch-info">
              Source Branch<br>
              5 commits ahead<br>
              Last updated 2h ago
            </div>
          </div>

          <div class="legal-git-merge-arrow">→</div>

          <div class="legal-git-merge-branch">
            <div class="legal-git-merge-branch-icon target">
              ${mergeWorkflow.targetBranch.substring(0, 2).toUpperCase()}
            </div>
            <div class="legal-git-merge-branch-name">${mergeWorkflow.targetBranch}</div>
            <div class="legal-git-merge-branch-info">
              Target Branch<br>
              3 commits ahead<br>
              Last updated 4h ago
            </div>
          </div>
        </div>
      </div>
    `;
  }

  // Generate merge preview
  generateMergePreview(mergeWorkflow) {
    return `
      <div class="legal-git-merge-preview">
        <div class="legal-git-merge-preview-header">
          <div class="legal-git-merge-preview-title">Merge Preview</div>
          <button class="legal-git-merge-control-btn" onclick="window.mergeWorkflow.refreshPreview()">
            Refresh
          </button>
        </div>
        <div class="legal-git-merge-preview-content">
          <div class="legal-git-merge-change-summary">
            <div class="legal-git-merge-change-stat">
              <div class="legal-git-merge-change-stat-value additions">+15</div>
              <div class="legal-git-merge-change-stat-label">Additions</div>
            </div>
            <div class="legal-git-merge-change-stat">
              <div class="legal-git-merge-change-stat-value deletions">-8</div>
              <div class="legal-git-merge-change-stat-label">Deletions</div>
            </div>
            <div class="legal-git-merge-change-stat">
              <div class="legal-git-merge-change-stat-value modifications">12</div>
              <div class="legal-git-merge-change-stat-label">Modifications</div>
            </div>
          </div>

          <div style="font-size: 13px; color: #5f6368; line-height: 1.4;">
            This merge will combine changes from <strong>${mergeWorkflow.sourceBranch}</strong> into <strong>${mergeWorkflow.targetBranch}</strong>.
            ${mergeWorkflow.conflicts.length > 0 ?
              `<br><br><strong style="color: #ea4335;">${mergeWorkflow.conflicts.length} conflicts detected</strong> that need resolution.` :
              '<br><br>No conflicts detected. Merge can proceed automatically.'
            }
          </div>
        </div>
      </div>
    `;
  }

  // Generate merge controls
  generateMergeControls(mergeWorkflow) {
    return `
      <div class="legal-git-merge-controls">
        <div class="legal-git-merge-controls-header">Merge Strategy</div>

        <div class="legal-git-merge-control-group">
          <label class="legal-git-merge-control-label">Choose merge strategy:</label>
          <div class="legal-git-merge-control-options">
            <div class="legal-git-merge-control-option selected" data-strategy="merge">
              <div class="legal-git-merge-control-option-title">Merge Commit</div>
              <div class="legal-git-merge-control-option-description">
                Creates a merge commit preserving branch history
              </div>
            </div>
            <div class="legal-git-merge-control-option" data-strategy="squash">
              <div class="legal-git-merge-control-option-title">Squash & Merge</div>
              <div class="legal-git-merge-control-option-description">
                Combines all commits into a single commit
              </div>
            </div>
            <div class="legal-git-merge-control-option" data-strategy="rebase">
              <div class="legal-git-merge-control-option-title">Rebase & Merge</div>
              <div class="legal-git-merge-control-option-description">
                Replays commits on top of target branch
              </div>
            </div>
          </div>
        </div>

        <div class="legal-git-merge-control-group">
          <label class="legal-git-merge-control-label">Post-merge actions:</label>
          <div style="display: flex; flex-direction: column; gap: 8px;">
            <label style="display: flex; align-items: center; gap: 8px; font-size: 13px;">
              <input type="checkbox" checked> Delete source branch after merge
            </label>
            <label style="display: flex; align-items: center; gap: 8px; font-size: 13px;">
              <input type="checkbox" checked> Update document timeline
            </label>
            <label style="display: flex; align-items: center; gap: 8px; font-size: 13px;">
              <input type="checkbox"> Send merge notification
            </label>
          </div>
        </div>
      </div>
    `;
  }

  // Get step icon
  getStepIcon(status) {
    switch (status) {
      case 'completed':
        return '✅';
      case 'active':
        return '🔄';
      case 'error':
        return '❌';
      default:
        return '⏳';
    }
  }

  // Get step description
  getStepDescription(stepId) {
    const descriptions = {
      prepare: 'Preparing branches and validating merge requirements',
      analyze: 'Analyzing document changes and identifying modifications',
      conflicts: 'Checking for conflicts and preparing resolution interface',
      merge: 'Executing final merge and updating document history'
    };
    return descriptions[stepId] || 'Processing step...';
  }

  // Update merge step
  updateMergeStep(mergeId, stepId, status, message = null) {
    const mergeWorkflow = this.activeMerges.get(mergeId);
    if (!mergeWorkflow) return;

    // Update step status
    const step = mergeWorkflow.steps.find(s => s.id === stepId);
    if (step) {
      step.status = status;
      if (message) step.message = message;
    }

    // Update UI if modal is open
    if (this.mergeViewOpen && this.currentMergeId === mergeId) {
      this.refreshMergeModal();
    }
  }

  // Update merge progress
  updateMergeProgress(mergeId) {
    const mergeWorkflow = this.activeMerges.get(mergeId);
    if (!mergeWorkflow) return;

    const completedSteps = mergeWorkflow.steps.filter(s => s.status === 'completed').length;
    const totalSteps = mergeWorkflow.steps.length;
    const progressPercentage = (completedSteps / totalSteps) * 100;

    // Update progress bar
    const progressFill = document.querySelector('.legal-git-merge-progress-fill');
    if (progressFill) {
      progressFill.style.width = `${progressPercentage}%`;
    }

    // Update step indicators
    const progressSteps = document.querySelectorAll('.legal-git-merge-progress-step');
    progressSteps.forEach((stepEl, index) => {
      if (index < completedSteps) {
        stepEl.className = 'legal-git-merge-progress-step completed';
        stepEl.innerHTML = `✓ ${stepEl.textContent.split(' ')[1]}`;
      } else if (index === completedSteps) {
        stepEl.className = 'legal-git-merge-progress-step active';
      }
    });
  }

  // Show conflict resolution
  showConflictResolution(mergeId) {
    const mergeWorkflow = this.activeMerges.get(mergeId);
    if (!mergeWorkflow || !this.conflictResolver) return;

    // Create conflict data for resolver
    const conflictData = {
      id: `merge_conflict_${mergeId}`,
      documentId: mergeWorkflow.documentId,
      documentTitle: 'Legal Document',
      currentBranch: mergeWorkflow.targetBranch,
      incomingBranch: mergeWorkflow.sourceBranch,
      conflictCount: mergeWorkflow.conflicts.length,
      conflicts: mergeWorkflow.conflicts.map(conflict => ({
        ...conflict,
        resolved: false,
        resolutionMethod: null
      }))
    };

    // Show conflict resolution modal
    this.conflictResolver.handleMergeConflict(conflictData);
  }

  // Complete merge
  async completeMerge(mergeId) {
    const mergeWorkflow = this.activeMerges.get(mergeId);
    if (!mergeWorkflow) return;

    try {
      // Simulate merge completion
      await new Promise(resolve => setTimeout(resolve, 1000));

      // Update status
      mergeWorkflow.status = 'completed';

      // Show success notification
      this.showMergeNotification('Merge completed successfully!', 'success');

      // Update timeline
      if (this.timelineView) {
        this.timelineView.updateTimelineData({
          documentId: mergeWorkflow.documentId,
          event: {
            id: `merge_${Date.now()}`,
            type: 'merge',
            timestamp: Date.now(),
            author: 'Current User',
            title: `Merged ${mergeWorkflow.sourceBranch} into ${mergeWorkflow.targetBranch}`,
            description: 'Branch merge completed successfully',
            branch: mergeWorkflow.targetBranch,
            sourceBranch: mergeWorkflow.sourceBranch
          }
        });
      }

      // Close modal
      setTimeout(() => {
        this.closeMergeModal();
      }, 2000);

    } catch (error) {
      console.error('Error completing merge:', error);
      this.showMergeNotification('Error completing merge: ' + error.message, 'error');
    }
  }

  // Refresh merge modal
  refreshMergeModal() {
    if (!this.mergeViewOpen || !this.currentMergeId) return;

    const mergeWorkflow = this.activeMerges.get(this.currentMergeId);
    if (!mergeWorkflow) return;

    const modal = document.getElementById('legal-git-merge-modal');
    if (modal) {
      const sidebar = modal.querySelector('.legal-git-merge-sidebar');
      if (sidebar) {
        sidebar.innerHTML = this.generateMergeSteps(mergeWorkflow) + this.generateMergeProgress(mergeWorkflow);
      }
    }
  }

  // Show merge notification
  showMergeNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `legal-git-merge-notification ${type}`;
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

  // Handle merge request
  handleMergeRequest(requestData) {
    const { sourceBranch, targetBranch, documentId } = requestData;

    // Initiate merge workflow
    this.initiateMerge({
      sourceBranch,
      targetBranch,
      documentId
    });
  }

  // Cancel merge
  cancelMerge() {
    if (this.currentMergeId) {
      this.activeMerges.delete(this.currentMergeId);
      this.showMergeNotification('Merge cancelled', 'info');
      this.closeMergeModal();
    }
  }

  // Proceed with merge
  proceedMerge() {
    if (this.currentMergeId) {
      const mergeWorkflow = this.activeMerges.get(this.currentMergeId);
      if (mergeWorkflow && mergeWorkflow.conflicts.length === 0) {
        this.completeMerge(this.currentMergeId);
      } else {
        this.showMergeNotification('Please resolve all conflicts before proceeding', 'error');
      }
    }
  }

  // Refresh preview
  refreshPreview() {
    this.showMergeNotification('Preview refreshed', 'info');
  }

  // Format time ago
  formatTimeAgo(timestamp) {
    const now = Date.now();
    const diffMs = now - timestamp;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);

    if (diffMins < 60) {
      return `${diffMins} minutes ago`;
    } else {
      return `${diffHours} hours ago`;
    }
  }

  // Setup merge modal events
  setupMergeModalEvents(modal, mergeWorkflow) {
    // Strategy selection
    const strategyOptions = modal.querySelectorAll('[data-strategy]');
    strategyOptions.forEach(option => {
      option.addEventListener('click', () => {
        strategyOptions.forEach(opt => opt.classList.remove('selected'));
        option.classList.add('selected');
      });
    });

    // Keyboard navigation
    modal.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        this.closeMergeModal();
      }
    });

    // Make globally available
    window.mergeWorkflow = this;
  }

  // Close merge modal
  closeMergeModal() {
    const modal = document.getElementById('legal-git-merge-modal');
    if (modal) {
      modal.remove();
      this.mergeViewOpen = false;
      this.currentMergeId = null;
    }
  }

  // Simulate merge for testing
  simulateMerge() {
    this.initiateMerge({
      sourceBranch: 'feature/payment-terms',
      targetBranch: 'main',
      documentId: 'doc_123'
    });
  }
}

// Export for use in other scripts
window.MergeWorkflow = MergeWorkflow;
