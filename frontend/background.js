// Legal Git Chrome Extension - Background Service Worker

// Initialize extension
chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === 'install') {
    console.log('Legal Git extension installed');
    setupContextMenus();
  }
});

// Set up context menus for Google Drive
function setupContextMenus() {
  chrome.contextMenus.create({
    id: 'start-version-tracking',
    title: 'Start Version Tracking',
    contexts: ['page'],
    documentUrlPatterns: ['https://drive.google.com/*']
  });

  chrome.contextMenus.create({
    id: 'save-milestone',
    title: 'Save Milestone',
    contexts: ['page'],
    documentUrlPatterns: ['https://drive.google.com/*', 'https://docs.google.com/*']
  });

  chrome.contextMenus.create({
    id: 'view-history',
    title: 'View Document History',
    contexts: ['page'],
    documentUrlPatterns: ['https://drive.google.com/*', 'https://docs.google.com/*']
  });
}

// Handle context menu clicks
chrome.contextMenus.onClicked.addListener((info, tab) => {
  switch (info.menuItemId) {
    case 'start-version-tracking':
      handleStartTracking(tab);
      break;
    case 'save-milestone':
      handleSaveMilestone(tab);
      break;
    case 'view-history':
      handleViewHistory(tab);
      break;
  }
});

// Handle starting version tracking for a document/folder
async function handleStartTracking(tab) {
  try {
    await chrome.tabs.sendMessage(tab.id, {
      action: 'startTracking',
      url: tab.url
    });
  } catch (error) {
    console.error('Error starting tracking:', error);
  }
}

// Handle saving a milestone/commit
async function handleSaveMilestone(tab) {
  try {
    await chrome.tabs.sendMessage(tab.id, {
      action: 'saveMilestone',
      url: tab.url
    });
  } catch (error) {
    console.error('Error saving milestone:', error);
  }
}

// Handle viewing document history
async function handleViewHistory(tab) {
  try {
    await chrome.tabs.sendMessage(tab.id, {
      action: 'viewHistory',
      url: tab.url
    });
  } catch (error) {
    console.error('Error viewing history:', error);
  }
}

// Handle messages from content scripts
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  switch (message.action) {
    case 'getStoredData':
      chrome.storage.local.get(message.key, (result) => {
        sendResponse(result);
      });
      return true; // Keep message channel open for async response

    case 'setStoredData':
      chrome.storage.local.set({ [message.key]: message.data }, () => {
        sendResponse({ success: true });
      });
      return true;

    case 'gitOperation':
      handleGitOperation(message, sendResponse);
      return true;
  }
});

// Handle git operations (placeholder for git server communication)
async function handleGitOperation(message, sendResponse) {
  try {
    // TODO: Implement actual git server communication
    console.log('Git operation:', message.operation, message.data);

    // Placeholder response
    sendResponse({
      success: true,
      data: { message: `${message.operation} completed successfully` }
    });
  } catch (error) {
    console.error('Git operation failed:', error);
    sendResponse({
      success: false,
      error: error.message
    });
  }
}
