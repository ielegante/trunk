// Enhanced Legal Git Content Script - Sprint 2 Integration

// Enhanced UI injection with Sprint 2 features
async function injectEnhancedLegalGitUI() {
  if (document.getElementById('legal-git-ui')) {
    document.getElementById('legal-git-ui').remove();
  }

  const uiContainer = document.createElement('div');
  uiContainer.id = 'legal-git-ui';

  // Get repository status
  const repositoryStatus = currentPage.repositoryId ?
    gitOpsManager.getRepositoryStatus(currentPage.repositoryId) : null;

  uiContainer.innerHTML = `
    <div id="legal-git-toolbar" style="
      position: fixed;
      top: 80px;
      right: 20px;
      z-index: 10000;
      background: white;
      border: 1px solid #dadce0;
      border-radius: 8px;
      padding: 12px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.1);
      font-family: 'Google Sans', Roboto, Arial, sans-serif;
      font-size: 14px;
      min-width: 220px;
      max-width: 280px;
      display: none;
    ">
      <div class="legal-git-header" style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid #f1f3f4;">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="#1a73e8">
          <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.03 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>
        </svg>
        <span style="font-weight: 500; color: #1a73e8; font-size: 14px;">Legal Git</span>
      </div>

      <div class="repository-status" style="margin-bottom: 12px;">
        <div style="font-size: 12px; color: #5f6368; margin-bottom: 4px;">Repository Status</div>
        <div id="legal-git-status" style="font-size: 12px; padding: 4px 8px; border-radius: 4px; text-align: center; ${repositoryStatus ? 'background: #e8f5e8; color: #137333;' : 'background: #fef7e0; color: #b8860b;'}">
          ${repositoryStatus ? 'Tracked' : 'Not tracked'}
        </div>
        ${repositoryStatus ? `
          <div style="font-size: 11px; color: #5f6368; margin-top: 4px; text-align: center;">
            🌿 <span id="current-branch-display">${repositoryStatus.currentBranch}</span>
          </div>
        ` : ''}
      </div>

      <div class="legal-git-actions" style="display: flex; flex-direction: column; gap: 6px;">
        ${!repositoryStatus ? `
          <button id="lg-start-tracking" class="legal-git-btn" style="
            background: #1a73e8;
            color: white;
            border: none;
            padding: 8px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            font-weight: 500;
            width: 100%;
          ">📁 Start Repository Tracking</button>
        ` : `
          <button id="lg-save-milestone" class="legal-git-btn legal-git-btn-secondary" style="
            background: #34a853;
            color: white;
            border: none;
            padding: 8px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            font-weight: 500;
            width: 100%;
          ">💾 Save Milestone</button>

          <button id="lg-manage-branches" class="legal-git-btn legal-git-btn-tertiary" style="
            background: #fbbc04;
            color: #1f1f1f;
            border: none;
            padding: 8px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            font-weight: 500;
            width: 100%;
          ">🌿 Manage Work Streams</button>

          <button id="lg-view-history" class="legal-git-btn" style="
            background: #9c27b0;
            color: white;
            border: none;
            padding: 8px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            font-weight: 500;
            width: 100%;
          ">📚 View History</button>
        `}
      </div>

      ${repositoryStatus ? `
        <div class="repository-info" style="
          margin-top: 12px;
          padding-top: 8px;
          border-top: 1px solid #f1f3f4;
          font-size: 11px;
          color: #5f6368;
        ">
          <div>📂 ${repositoryStatus.name}</div>
          <div>👥 ${repositoryStatus.permissions?.length || 0} collaborators</div>
          <div>🌿 ${repositoryStatus.branches?.length || 1} work streams</div>
        </div>
      ` : ''}
    </div>
  `;

  document.body.appendChild(uiContainer);

  // Show toolbar after a delay to ensure page is loaded
  setTimeout(() => {
    const toolbar = document.getElementById('legal-git-toolbar');
    if (toolbar && currentPage.type) {
      toolbar.style.display = 'block';
    }
  }, 1000);

  setupEnhancedUIEventListeners();
}

// Enhanced event listeners for Sprint 2 features
function setupEnhancedUIEventListeners() {
  // Start repository tracking
  document.getElementById('lg-start-tracking')?.addEventListener('click', () => {
    handleStartRepositoryTracking();
  });

  // Save milestone (commit)
  document.getElementById('lg-save-milestone')?.addEventListener('click', () => {
    handleSaveMilestone();
  });

  // Manage branches
  document.getElementById('lg-manage-branches')?.addEventListener('click', () => {
    handleManageBranches();
  });

  // View history
  document.getElementById('lg-view-history')?.addEventListener('click', () => {
    handleViewHistory();
  });
}

// Handle repository tracking initialization
async function handleStartRepositoryTracking() {
  if (!currentPage.repositoryId) {
    commitUIManager.showErrorMessage('Unable to determine folder for repository. Please ensure you are in a Google Drive folder.');
    return;
  }

  try {
    // Show loading state
    const startBtn = document.getElementById('lg-start-tracking');
    if (startBtn) {
      startBtn.disabled = true;
      startBtn.textContent = '🔄 Creating repository...';
    }

    const folderInfo = {
      folderId: currentPage.repositoryId,
      folderName: currentPage.folderName || currentPage.fileName || 'Unnamed Folder'
    };

    const repository = await gitOpsManager.createRepository(folderInfo);

    commitUIManager.showSuccessMessage(`Repository created successfully! Now tracking "${repository.name}"`);

    // Refresh UI to show tracked state
    await injectEnhancedLegalGitUI();

  } catch (error) {
    console.error('Repository creation failed:', error);
    commitUIManager.showErrorMessage(`Failed to create repository: ${error.message}`);

    // Reset button
    const startBtn = document.getElementById('lg-start-tracking');
    if (startBtn) {
      startBtn.disabled = false;
      startBtn.textContent = '📁 Start Repository Tracking';
    }
  }
}

// Handle milestone saving (commits)
async function handleSaveMilestone() {
  if (!currentPage.repositoryId) {
    commitUIManager.showErrorMessage('No repository found. Please start tracking first.');
    return;
  }

  const repository = gitOpsManager.getRepositoryStatus(currentPage.repositoryId);
  if (!repository) {
    commitUIManager.showErrorMessage('Repository not found. Please start tracking first.');
    return;
  }

  commitUIManager.showCommitModal(currentPage.repositoryId, repository.currentBranch);
}

// Handle branch management
async function handleManageBranches() {
  if (!currentPage.repositoryId) {
    commitUIManager.showErrorMessage('No repository found. Please start tracking first.');
    return;
  }

  commitUIManager.showBranchModal(currentPage.repositoryId);
}

// Handle history viewing
async function handleViewHistory() {
  if (!currentPage.repositoryId) {
    commitUIManager.showErrorMessage('No repository found. Please start tracking first.');
    return;
  }

  // For Sprint 2, show placeholder
  commitUIManager.showToast('History view coming in Sprint 3!', 'info');
}

// Listen for status updates
window.addEventListener('legalGitStatusUpdate', async (event) => {
  await injectEnhancedLegalGitUI();
});

// Enhanced update UI status
async function updateEnhancedUIStatus() {
  if (currentPage.repositoryId) {
    await injectEnhancedLegalGitUI();
  }
}

// Replace the original functions
if (typeof injectLegalGitUI !== 'undefined') {
  injectLegalGitUI = injectEnhancedLegalGitUI;
}

if (typeof setupUIEventListeners !== 'undefined') {
  setupUIEventListeners = setupEnhancedUIEventListeners;
}

if (typeof updateUIStatus !== 'undefined') {
  updateUIStatus = updateEnhancedUIStatus;
}
