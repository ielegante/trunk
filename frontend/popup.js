// Legal Git Chrome Extension - Popup Script

document.addEventListener('DOMContentLoaded', async () => {
  await initializePopup();
  setupEventListeners();
});

async function initializePopup() {
  await updateServerStatus();
  await updatePageStatus();
  await updateDocumentStatus();
  updateButtonStates();
}

function setupEventListeners() {
  document.getElementById('configure-server').addEventListener('click', configureServer);
  document.getElementById('start-tracking').addEventListener('click', startTracking);
  document.getElementById('save-milestone').addEventListener('click', saveMilestone);
  document.getElementById('view-history').addEventListener('click', viewHistory);
  document.getElementById('options-link').addEventListener('click', openOptions);
}

async function updateServerStatus() {
  try {
    const result = await chrome.storage.local.get(['gitServerConfig']);
    const serverStatus = document.getElementById('server-status');

    if (result.gitServerConfig && result.gitServerConfig.url) {
      serverStatus.textContent = `Connected to ${result.gitServerConfig.url}`;
      serverStatus.className = 'status-value status-connected';
    } else {
      serverStatus.textContent = 'Not configured';
      serverStatus.className = 'status-value status-disconnected';
    }
  } catch (error) {
    console.error('Error checking server status:', error);
  }
}

async function updatePageStatus() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const pageStatus = document.getElementById('page-status');

    if (tab && tab.url) {
      if (tab.url.includes('drive.google.com')) {
        pageStatus.textContent = 'Google Drive';
      } else if (tab.url.includes('docs.google.com')) {
        pageStatus.textContent = 'Google Docs';
      } else {
        pageStatus.textContent = 'Not supported';
      }
    } else {
      pageStatus.textContent = 'Unknown';
    }
  } catch (error) {
    console.error('Error checking page status:', error);
  }
}

async function updateDocumentStatus() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const documentStatus = document.getElementById('document-status');

    if (tab && (tab.url.includes('drive.google.com') || tab.url.includes('docs.google.com'))) {
      // TODO: Check if current document is tracked
      // For now, default to not tracked
      documentStatus.textContent = 'Not tracked';
    } else {
      documentStatus.textContent = 'No document';
    }
  } catch (error) {
    console.error('Error checking document status:', error);
  }
}

function updateButtonStates() {
  const serverStatus = document.getElementById('server-status');
  const pageStatus = document.getElementById('page-status');
  const documentStatus = document.getElementById('document-status');

  const isServerConfigured = serverStatus.classList.contains('status-connected');
  const isOnSupportedPage = pageStatus.textContent === 'Google Drive' || pageStatus.textContent === 'Google Docs';
  const isDocumentTracked = documentStatus.textContent !== 'Not tracked' && documentStatus.textContent !== 'No document';

  // Start tracking button - enabled if server configured and on supported page
  const startButton = document.getElementById('start-tracking');
  startButton.disabled = !isServerConfigured || !isOnSupportedPage || isDocumentTracked;

  // Milestone and history buttons - enabled if document is tracked
  const milestoneButton = document.getElementById('save-milestone');
  const historyButton = document.getElementById('view-history');
  milestoneButton.disabled = !isDocumentTracked;
  historyButton.disabled = !isDocumentTracked;
}

async function configureServer() {
  const serverUrl = prompt('Enter Git Server URL:', 'http://localhost:8080');
  const username = prompt('Enter username:');
  const token = prompt('Enter access token or password:');

  if (serverUrl && username && token) {
    const config = {
      url: serverUrl,
      username: username,
      token: token,
      configured: true
    };

    try {
      await chrome.storage.local.set({ gitServerConfig: config });
      await updateServerStatus();
      updateButtonStates();
      alert('Git server configuration saved successfully!');
    } catch (error) {
      console.error('Error saving server config:', error);
      alert('Failed to save configuration: ' + error.message);
    }
  }
}

async function startTracking() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    if (tab) {
      await chrome.tabs.sendMessage(tab.id, { action: 'startTracking' });
      setTimeout(async () => {
        await updateDocumentStatus();
        updateButtonStates();
      }, 1000);
    }
  } catch (error) {
    console.error('Error starting tracking:', error);
    alert('Failed to start tracking: ' + error.message);
  }
}

async function saveMilestone() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    if (tab) {
      await chrome.tabs.sendMessage(tab.id, { action: 'saveMilestone' });
    }
  } catch (error) {
    console.error('Error saving milestone:', error);
    alert('Failed to save milestone: ' + error.message);
  }
}

async function viewHistory() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    if (tab) {
      await chrome.tabs.sendMessage(tab.id, { action: 'viewHistory' });
    }
  } catch (error) {
    console.error('Error viewing history:', error);
    alert('Failed to view history: ' + error.message);
  }
}

function openOptions() {
  chrome.tabs.create({ url: chrome.runtime.getURL('options.html') });
}
