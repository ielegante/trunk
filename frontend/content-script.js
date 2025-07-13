// Legal Git Chrome Extension - Content Script for Google Drive Integration

console.log('Legal Git content script loaded');

// Initialize Git Operations and Commit UI managers
let gitOpsManager = null;
let commitUIManager = null;

// Track current page state
let currentPage = {
  type: null, // 'drive' or 'docs'
  fileId: null,
  fileName: null,
  folderId: null,
  folderName: null,
  repositoryId: null
};

// Initialize when page loads
document.addEventListener('DOMContentLoaded', initializeLegalGit);
window.addEventListener('load', initializeLegalGit);

// Handle dynamic page changes in Google Drive/Docs
let lastUrl = location.href;
new MutationObserver(() => {
  const currentUrl = location.href;
  if (currentUrl !== lastUrl) {
    lastUrl = currentUrl;
    setTimeout(initializeLegalGit, 1000); // Delay to let page content load
  }
}).observe(document, { subtree: true, childList: true });

async function initializeLegalGit() {
  // Initialize managers
  if (!gitOpsManager) {
    gitOpsManager = new GitOperationsManager();
    await gitOpsManager.init();
  }

  if (!commitUIManager) {
    commitUIManager = new CommitUIManager(gitOpsManager);
  }

  detectPageType();
  await injectLegalGitUI();
  setupFileDetection();
}

// Detect if we're on Google Drive or Google Docs
function detectPageType() {
  const hostname = window.location.hostname;
  const pathname = window.location.pathname;

  if (hostname === 'drive.google.com') {
    currentPage.type = 'drive';
    extractDriveFileInfo();
  } else if (hostname === 'docs.google.com') {
    currentPage.type = 'docs';
    extractDocsFileInfo();
  }

  console.log('Page detected:', currentPage);
}

// Extract file information from Google Drive URL and page
function extractDriveFileInfo() {
  const urlParams = new URLSearchParams(window.location.search);
  const pathParts = window.location.pathname.split('/');

  // Try to get file ID from URL
  if (pathParts.includes('file') && pathParts.includes('d')) {
    const fileIndex = pathParts.indexOf('d') + 1;
    currentPage.fileId = pathParts[fileIndex];
  }

  // Try to get folder ID (for repository creation)
  if (pathParts.includes('folders')) {
    const folderIndex = pathParts.indexOf('folders') + 1;
    currentPage.folderId = pathParts[folderIndex];
  }

  // Try to get file/folder name from page title or selected item
  setTimeout(() => {
    const titleElement = document.querySelector('[data-tooltip="Rename"]') ||
                        document.querySelector('.p1sYSb') ||
                        document.querySelector('[data-target="doc-title"]') ||
                        document.querySelector('[data-tooltip*="folder"]');
    if (titleElement) {
      const name = titleElement.textContent?.trim();
      if (currentPage.folderId) {
        currentPage.folderName = name;
        currentPage.repositoryId = currentPage.folderId;
      } else {
        currentPage.fileName = name;
        // For files, use parent folder as repository if available
        currentPage.repositoryId = currentPage.folderId || 'root';
      }
    }
  }, 500);
}

// Extract file information from Google Docs
function extractDocsFileInfo() {
  const pathParts = window.location.pathname.split('/');

  // Extract file ID from URL pattern: /document/d/{fileId}/edit
  if (pathParts.includes('d')) {
    const fileIndex = pathParts.indexOf('d') + 1;
    currentPage.fileId = pathParts[fileIndex];
  }

  // Get document title
  setTimeout(() => {
    const titleElement = document.querySelector('.docs-title-input') ||
                        document.querySelector('[data-tooltip="Rename"]');
    if (titleElement) {
      currentPage.fileName = titleElement.textContent?.trim() || titleElement.value?.trim();
    }
  }, 500);
}

// Inject Legal Git UI elements
function injectLegalGitUI() {
  if (document.getElementById('legal-git-ui')) return; // Already injected

  const uiContainer = document.createElement('div');
  uiContainer.id = 'legal-git-ui';
  uiContainer.innerHTML = `
    <div id="legal-git-toolbar" style="
      position: fixed;
      top: 80px;
      right: 20px;
      z-index: 10000;
      background: white;
      border: 1px solid #dadce0;
      border-radius: 8px;
      padding: 8px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.1);
      font-family: 'Google Sans', Roboto, Arial, sans-serif;
      font-size: 14px;
      display: none;
    ">
      <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="#1a73e8">
          <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.03 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>
        </svg>
        <span style="font-weight: 500; color: #1a73e8;">Legal Git</span>
      </div>
      <div id="legal-git-status" style="margin-bottom: 8px; font-size: 12px; color: #5f6368;">
        Not tracked
      </div>
      <div style="display: flex; flex-direction: column; gap: 4px;">
        <button id="lg-start-tracking" style="
          background: #1a73e8;
          color: white;
          border: none;
          padding: 6px 12px;
          border-radius: 4px;
          cursor: pointer;
          font-size: 12px;
        ">Start Tracking</button>
        <button id="lg-save-milestone" style="
          background: #34a853;
          color: white;
          border: none;
          padding: 6px 12px;
          border-radius: 4px;
          cursor: pointer;
          font-size: 12px;
          display: none;
        ">Save Milestone</button>
        <button id="lg-view-history" style="
          background: #fbbc04;
          color: #1f1f1f;
          border: none;
          padding: 6px 12px;
          border-radius: 4px;
          cursor: pointer;
          font-size: 12px;
          display: none;
        ">View History</button>
      </div>
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

  setupUIEventListeners();
}

// Set up event listeners for UI elements
function setupUIEventListeners() {
  document.getElementById('lg-start-tracking')?.addEventListener('click', () => {
    handleStartTracking();
  });

  document.getElementById('lg-save-milestone')?.addEventListener('click', () => {
    handleSaveMilestone();
  });

  document.getElementById('lg-view-history')?.addEventListener('click', () => {
    handleViewHistory();
  });
}

// Set up file detection and monitoring
function setupFileDetection() {
  if (currentPage.type === 'drive') {
    observeDriveChanges();
  } else if (currentPage.type === 'docs') {
    observeDocsChanges();
  }
}

// Monitor changes in Google Drive interface
function observeDriveChanges() {
  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      if (mutation.type === 'childList') {
        // Check for file selection changes
        updateFileSelection();
      }
    });
  });

  observer.observe(document.body, {
    childList: true,
    subtree: true
  });
}

// Monitor changes in Google Docs
function observeDocsChanges() {
  // Monitor document title changes
  const titleObserver = new MutationObserver(() => {
    extractDocsFileInfo();
  });

  const titleElement = document.querySelector('.docs-title-input');
  if (titleElement) {
    titleObserver.observe(titleElement, {
      attributes: true,
      attributeFilter: ['value']
    });
  }
}

// Update file selection in Drive
function updateFileSelection() {
  setTimeout(() => {
    extractDriveFileInfo();
    updateUIStatus();
  }, 100);
}

// Update UI status based on current file
function updateUIStatus() {
  const statusElement = document.getElementById('legal-git-status');
  const startButton = document.getElementById('lg-start-tracking');
  const milestoneButton = document.getElementById('lg-save-milestone');
  const historyButton = document.getElementById('lg-view-history');

  if (!statusElement) return;

  if (currentPage.fileId) {
    // TODO: Check if file is tracked in git
    statusElement.textContent = 'Ready to track';
    if (startButton) startButton.style.display = 'block';
  } else {
    statusElement.textContent = 'No file selected';
    if (startButton) startButton.style.display = 'none';
    if (milestoneButton) milestoneButton.style.display = 'none';
    if (historyButton) historyButton.style.display = 'none';
  }
}

// Handle messages from background script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  switch (message.action) {
    case 'startTracking':
      handleStartTracking();
      break;
    case 'saveMilestone':
      handleSaveMilestone();
      break;
    case 'viewHistory':
      handleViewHistory();
      break;
  }
  sendResponse({ success: true });
});

// Handle starting version tracking
async function handleStartTracking() {
  if (!currentPage.fileId) {
    alert('No file selected. Please select a file to start tracking.');
    return;
  }

  console.log('Starting tracking for:', currentPage);

  try {
    const response = await chrome.runtime.sendMessage({
      action: 'gitOperation',
      operation: 'initRepository',
      data: {
        fileId: currentPage.fileId,
        fileName: currentPage.fileName,
        pageType: currentPage.type
      }
    });

    if (response.success) {
      updateTrackingStatus(true);
      alert('Version tracking started successfully!');
    } else {
      throw new Error(response.error);
    }
  } catch (error) {
    console.error('Error starting tracking:', error);
    alert('Failed to start tracking: ' + error.message);
  }
}

// Handle saving a milestone
async function handleSaveMilestone() {
  const commitMessage = prompt('Enter a description for this milestone:');
  if (!commitMessage) return;

  console.log('Saving milestone:', commitMessage);

  try {
    const response = await chrome.runtime.sendMessage({
      action: 'gitOperation',
      operation: 'commit',
      data: {
        fileId: currentPage.fileId,
        fileName: currentPage.fileName,
        message: commitMessage,
        pageType: currentPage.type
      }
    });

    if (response.success) {
      alert('Milestone saved successfully!');
    } else {
      throw new Error(response.error);
    }
  } catch (error) {
    console.error('Error saving milestone:', error);
    alert('Failed to save milestone: ' + error.message);
  }
}

// Handle viewing history
async function handleViewHistory() {
  console.log('Viewing history for:', currentPage);

  try {
    const response = await chrome.runtime.sendMessage({
      action: 'gitOperation',
      operation: 'getHistory',
      data: {
        fileId: currentPage.fileId,
        fileName: currentPage.fileName
      }
    });

    if (response.success) {
      showHistoryModal(response.data);
    } else {
      throw new Error(response.error);
    }
  } catch (error) {
    console.error('Error viewing history:', error);
    alert('Failed to load history: ' + error.message);
  }
}

// Update tracking status in UI
function updateTrackingStatus(isTracked) {
  const statusElement = document.getElementById('legal-git-status');
  const startButton = document.getElementById('lg-start-tracking');
  const milestoneButton = document.getElementById('lg-save-milestone');
  const historyButton = document.getElementById('lg-view-history');

  if (isTracked) {
    if (statusElement) statusElement.textContent = 'Tracked';
    if (startButton) startButton.style.display = 'none';
    if (milestoneButton) milestoneButton.style.display = 'block';
    if (historyButton) historyButton.style.display = 'block';
  } else {
    if (statusElement) statusElement.textContent = 'Not tracked';
    if (startButton) startButton.style.display = 'block';
    if (milestoneButton) milestoneButton.style.display = 'none';
    if (historyButton) historyButton.style.display = 'none';
  }
}

// Show history modal (placeholder)
function showHistoryModal(historyData) {
  alert('History view coming soon!\n\nHistory data: ' + JSON.stringify(historyData, null, 2));
}
