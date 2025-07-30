// Legal Git Chrome Extension - Document Locking System
// Implements "Reserved Editing" for conflict-free collaboration

class DocumentLockingSystem {
  constructor(gitOpsManager) {
    this.gitOpsManager = gitOpsManager;
    this.activeLocks = new Map(); // documentId -> lock info
    this.lockCheckInterval = 30000; // 30 seconds
    this.lockTimeout = 3600000; // 1 hour default
    this.init();
  }

  init() {
    this.setupEventListeners();
    this.injectLockingUI();
    this.startLockMonitoring();
    this.loadActiveLocks();
  }

  // Load active locks from storage
  async loadActiveLocks() {
    try {
      const result = await chrome.storage.local.get(['documentLocks']);
      if (result.documentLocks) {
        this.activeLocks = new Map(Object.entries(result.documentLocks));
        this.refreshLockUI();
      }
    } catch (error) {
      console.error('Failed to load active locks:', error);
    }
  }

  // Save locks to storage
  async saveLocks() {
    try {
      const lockObject = Object.fromEntries(this.activeLocks);
      await chrome.storage.local.set({ documentLocks: lockObject });
    } catch (error) {
      console.error('Failed to save locks:', error);
    }
  }

  // Setup event listeners for lock operations
  setupEventListeners() {
    // Lock document button
    document.addEventListener('click', (event) => {
      if (event.target.matches('.legal-git-lock-btn')) {
        event.preventDefault();
        const documentId = event.target.dataset.documentId;
        this.requestDocumentLock(documentId);
      }
    });

    // Unlock document button
    document.addEventListener('click', (event) => {
      if (event.target.matches('.legal-git-unlock-btn')) {
        event.preventDefault();
        const documentId = event.target.dataset.documentId;
        this.releaseDocumentLock(documentId);
      }
    });

    // Admin override button
    document.addEventListener('click', (event) => {
      if (event.target.matches('.legal-git-override-btn')) {
        event.preventDefault();
        const documentId = event.target.dataset.documentId;
        this.showOverrideDialog(documentId);
      }
    });

    // Lock info button
    document.addEventListener('click', (event) => {
      if (event.target.matches('.legal-git-lock-info')) {
        event.preventDefault();
        const documentId = event.target.dataset.documentId;
        this.showLockInfo(documentId);
      }
    });

    // Window beforeunload to release locks
    window.addEventListener('beforeunload', () => {
      this.releaseAllUserLocks();
    });
  }

  // Inject locking UI into Google Drive interface
  injectLockingUI() {
    const style = document.createElement('style');
    style.textContent = `
      .legal-git-lock-container {
        display: flex;
        align-items: center;
        gap: 8px;
        margin: 4px 0;
        padding: 8px 12px;
        background: #f8f9fa;
        border-radius: 6px;
        border-left: 4px solid #28a745;
        font-family: 'Google Sans', sans-serif;
        font-size: 13px;
      }

      .legal-git-lock-container.locked {
        border-left-color: #dc3545;
        background: #fff5f5;
      }

      .legal-git-lock-icon {
        width: 16px;
        height: 16px;
        fill: #28a745;
      }

      .legal-git-lock-container.locked .legal-git-lock-icon {
        fill: #dc3545;
      }

      .legal-git-lock-btn {
        background: #28a745;
        color: white;
        border: none;
        padding: 4px 12px;
        border-radius: 4px;
        font-size: 12px;
        cursor: pointer;
        transition: background 0.2s;
      }

      .legal-git-lock-btn:hover {
        background: #218838;
      }

      .legal-git-unlock-btn {
        background: #dc3545;
        color: white;
        border: none;
        padding: 4px 12px;
        border-radius: 4px;
        font-size: 12px;
        cursor: pointer;
        transition: background 0.2s;
      }

      .legal-git-unlock-btn:hover {
        background: #c82333;
      }

      .legal-git-override-btn {
        background: #ffc107;
        color: #212529;
        border: none;
        padding: 4px 12px;
        border-radius: 4px;
        font-size: 12px;
        cursor: pointer;
        transition: background 0.2s;
      }

      .legal-git-override-btn:hover {
        background: #e0a800;
      }

      .legal-git-lock-info {
        color: #6c757d;
        text-decoration: none;
        cursor: pointer;
      }

      .legal-git-lock-info:hover {
        color: #495057;
        text-decoration: underline;
      }

      .legal-git-lock-status {
        flex: 1;
        color: #495057;
      }

      .legal-git-lock-user {
        font-weight: 600;
        color: #dc3545;
      }

      .legal-git-lock-time {
        font-size: 11px;
        color: #6c757d;
      }

      .legal-git-lock-dialog {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.5);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10000;
        font-family: 'Google Sans', sans-serif;
      }

      .legal-git-lock-dialog-content {
        background: white;
        padding: 24px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        max-width: 500px;
        width: 90%;
      }

      .legal-git-lock-dialog h3 {
        margin: 0 0 16px 0;
        color: #333;
        font-size: 18px;
      }

      .legal-git-lock-dialog p {
        margin: 8px 0;
        color: #666;
        line-height: 1.4;
      }

      .legal-git-lock-dialog-buttons {
        display: flex;
        gap: 12px;
        justify-content: flex-end;
        margin-top: 20px;
      }

      .legal-git-dialog-btn {
        padding: 8px 16px;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        font-size: 14px;
        transition: background 0.2s;
      }

      .legal-git-dialog-btn.primary {
        background: #1a73e8;
        color: white;
      }

      .legal-git-dialog-btn.primary:hover {
        background: #1557b0;
      }

      .legal-git-dialog-btn.secondary {
        background: #f8f9fa;
        color: #3c4043;
        border: 1px solid #dadce0;
      }

      .legal-git-dialog-btn.secondary:hover {
        background: #f1f3f4;
      }

      .legal-git-dialog-btn.danger {
        background: #dc3545;
        color: white;
      }

      .legal-git-dialog-btn.danger:hover {
        background: #c82333;
      }
    `;
    document.head.appendChild(style);
  }

  // Start monitoring locks for expiration and updates
  startLockMonitoring() {
    setInterval(() => {
      this.checkLockExpiration();
      this.refreshLockUI();
    }, this.lockCheckInterval);
  }

  // Check for expired locks
  checkLockExpiration() {
    const now = Date.now();
    const expiredLocks = [];

    for (const [documentId, lock] of this.activeLocks) {
      if (now > lock.expiresAt) {
        expiredLocks.push(documentId);
      }
    }

    // Remove expired locks
    expiredLocks.forEach(documentId => {
      this.activeLocks.delete(documentId);
      this.notifyLockExpired(documentId);
    });

    if (expiredLocks.length > 0) {
      this.saveLocks();
      this.refreshLockUI();
    }
  }

  // Request lock on a document
  async requestDocumentLock(documentId) {
    try {
      // Check if already locked
      const existingLock = this.activeLocks.get(documentId);
      if (existingLock) {
        this.showLockedDocumentDialog(documentId, existingLock);
        return;
      }

      // Get current user info
      const userInfo = await this.getCurrentUser();
      if (!userInfo) {
        this.showError('Unable to identify current user. Please ensure you are signed into Google Drive.');
        return;
      }

      // Create lock
      const lock = {
        documentId: documentId,
        userId: userInfo.id,
        userEmail: userInfo.email,
        userName: userInfo.name,
        lockedAt: Date.now(),
        expiresAt: Date.now() + this.lockTimeout,
        reason: 'Document editing',
        type: 'user'
      };

      // TODO: Call backend API to create lock
      // For now, simulate the lock creation
      const lockCreated = await this.simulateLockCreation(lock);

      if (lockCreated.success) {
        this.activeLocks.set(documentId, lock);
        await this.saveLocks();
        this.refreshLockUI();
        this.showLockSuccessMessage(documentId);
      } else {
        this.showError(lockCreated.error || 'Failed to lock document');
      }

    } catch (error) {
      console.error('Error requesting document lock:', error);
      this.showError('Failed to lock document: ' + error.message);
    }
  }

  // Release lock on a document
  async releaseDocumentLock(documentId) {
    try {
      const lock = this.activeLocks.get(documentId);
      if (!lock) {
        this.showError('No active lock found for this document');
        return;
      }

      // Check if user owns the lock
      const userInfo = await this.getCurrentUser();
      if (lock.userId !== userInfo.id) {
        this.showError('You can only release locks you created');
        return;
      }

      // TODO: Call backend API to release lock
      const lockReleased = await this.simulateLockRelease(documentId);

      if (lockReleased.success) {
        this.activeLocks.delete(documentId);
        await this.saveLocks();
        this.refreshLockUI();
        this.showLockReleaseMessage(documentId);
      } else {
        this.showError(lockReleased.error || 'Failed to release document lock');
      }

    } catch (error) {
      console.error('Error releasing document lock:', error);
      this.showError('Failed to release lock: ' + error.message);
    }
  }

  // Show dialog for locked document
  showLockedDocumentDialog(documentId, lock) {
    const timeRemaining = this.formatTimeRemaining(lock.expiresAt - Date.now());
    const isOwnLock = this.isUserLock(lock);

    const dialog = document.createElement('div');
    dialog.className = 'legal-git-lock-dialog';
    dialog.innerHTML = `
      <div class="legal-git-lock-dialog-content">
        <h3>🔒 Document Reserved for Editing</h3>
        <p><strong>Locked by:</strong> ${lock.userName} (${lock.userEmail})</p>
        <p><strong>Locked since:</strong> ${new Date(lock.lockedAt).toLocaleString()}</p>
        <p><strong>Time remaining:</strong> ${timeRemaining}</p>
        <p><strong>Reason:</strong> ${lock.reason}</p>

        ${isOwnLock ? '<p><em>This is your lock. You can continue editing or release it.</em></p>' :
          '<p><em>Please wait for the lock to be released or contact the editor if urgent.</em></p>'}

        <div class="legal-git-lock-dialog-buttons">
          ${isOwnLock ? '<button class="legal-git-dialog-btn danger" onclick="this.closest(\'.legal-git-lock-dialog\').remove(); window.legalGitDocumentLocking.releaseDocumentLock(\'' + documentId + '\')">Release Lock</button>' : ''}
          ${this.isAdmin() ? '<button class="legal-git-dialog-btn primary" onclick="this.closest(\'.legal-git-lock-dialog\').remove(); window.legalGitDocumentLocking.showOverrideDialog(\'' + documentId + '\')">Admin Override</button>' : ''}
          <button class="legal-git-dialog-btn secondary" onclick="this.closest('.legal-git-lock-dialog').remove()">Close</button>
        </div>
      </div>
    `;

    document.body.appendChild(dialog);

    // Auto-remove dialog after 10 seconds
    setTimeout(() => {
      if (dialog.parentNode) {
        dialog.remove();
      }
    }, 10000);
  }

  // Show admin override dialog
  showOverrideDialog(documentId) {
    const lock = this.activeLocks.get(documentId);
    if (!lock) return;

    const dialog = document.createElement('div');
    dialog.className = 'legal-git-lock-dialog';
    dialog.innerHTML = `
      <div class="legal-git-lock-dialog-content">
        <h3>⚠️ Admin Override</h3>
        <p>You are about to override a document lock. This should only be done in urgent situations.</p>
        <p><strong>Current lock holder:</strong> ${lock.userName} (${lock.userEmail})</p>
        <p><strong>Lock reason:</strong> ${lock.reason}</p>

        <div style="margin: 16px 0;">
          <label for="override-reason" style="display: block; margin-bottom: 4px; font-weight: 600;">Override reason:</label>
          <input type="text" id="override-reason" placeholder="Explain why this override is necessary"
                 style="width: 100%; padding: 8px; border: 1px solid #dadce0; border-radius: 4px;">
        </div>

        <div class="legal-git-lock-dialog-buttons">
          <button class="legal-git-dialog-btn danger" onclick="window.legalGitDocumentLocking.executeOverride('${documentId}', document.getElementById('override-reason').value); this.closest('.legal-git-lock-dialog').remove();">Override Lock</button>
          <button class="legal-git-dialog-btn secondary" onclick="this.closest('.legal-git-lock-dialog').remove()">Cancel</button>
        </div>
      </div>
    `;

    document.body.appendChild(dialog);
  }

  // Execute admin override
  async executeOverride(documentId, reason) {
    if (!reason.trim()) {
      this.showError('Override reason is required');
      return;
    }

    try {
      const userInfo = await this.getCurrentUser();

      // TODO: Call backend API for admin override
      const overrideResult = await this.simulateAdminOverride(documentId, reason);

      if (overrideResult.success) {
        const oldLock = this.activeLocks.get(documentId);

        // Create new lock for admin
        const newLock = {
          documentId: documentId,
          userId: userInfo.id,
          userEmail: userInfo.email,
          userName: userInfo.name,
          lockedAt: Date.now(),
          expiresAt: Date.now() + this.lockTimeout,
          reason: `Admin override: ${reason}`,
          type: 'admin_override',
          previousLock: oldLock
        };

        this.activeLocks.set(documentId, newLock);
        await this.saveLocks();
        this.refreshLockUI();

        // Notify previous lock holder
        this.notifyLockOverride(oldLock, reason);
        this.showSuccess('Document lock overridden successfully');
      } else {
        this.showError(overrideResult.error || 'Failed to override lock');
      }

    } catch (error) {
      console.error('Error executing admin override:', error);
      this.showError('Failed to override lock: ' + error.message);
    }
  }

  // Show lock information
  showLockInfo(documentId) {
    const lock = this.activeLocks.get(documentId);
    if (!lock) {
      this.showError('No lock information available');
      return;
    }

    const timeRemaining = this.formatTimeRemaining(lock.expiresAt - Date.now());
    const lockDuration = this.formatDuration(Date.now() - lock.lockedAt);

    const dialog = document.createElement('div');
    dialog.className = 'legal-git-lock-dialog';
    dialog.innerHTML = `
      <div class="legal-git-lock-dialog-content">
        <h3>📋 Lock Information</h3>
        <p><strong>Document:</strong> ${this.getDocumentTitle(documentId)}</p>
        <p><strong>Locked by:</strong> ${lock.userName} (${lock.userEmail})</p>
        <p><strong>Lock type:</strong> ${lock.type === 'admin_override' ? 'Admin Override' : 'User Lock'}</p>
        <p><strong>Locked since:</strong> ${new Date(lock.lockedAt).toLocaleString()}</p>
        <p><strong>Duration:</strong> ${lockDuration}</p>
        <p><strong>Time remaining:</strong> ${timeRemaining}</p>
        <p><strong>Reason:</strong> ${lock.reason}</p>

        ${lock.previousLock ? `
          <div style="margin-top: 16px; padding: 12px; background: #f8f9fa; border-radius: 4px;">
            <strong>Previous lock:</strong><br>
            ${lock.previousLock.userName} (${lock.previousLock.userEmail})<br>
            <em>${lock.previousLock.reason}</em>
          </div>
        ` : ''}

        <div class="legal-git-lock-dialog-buttons">
          <button class="legal-git-dialog-btn secondary" onclick="this.closest('.legal-git-lock-dialog').remove()">Close</button>
        </div>
      </div>
    `;

    document.body.appendChild(dialog);
  }

  // Refresh lock UI in the interface
  refreshLockUI() {
    // Find all tracked documents and update their lock status
    const documentElements = document.querySelectorAll('[data-document-id]');

    documentElements.forEach(element => {
      const documentId = element.dataset.documentId;
      this.updateDocumentLockUI(documentId, element);
    });
  }

  // Update lock UI for a specific document
  updateDocumentLockUI(documentId, container) {
    if (!container) return;

    // Remove existing lock UI
    const existingLockUI = container.querySelector('.legal-git-lock-container');
    if (existingLockUI) {
      existingLockUI.remove();
    }

    const lock = this.activeLocks.get(documentId);
    const isLocked = !!lock;
    const isOwnLock = lock ? this.isUserLock(lock) : false;

    const lockContainer = document.createElement('div');
    lockContainer.className = `legal-git-lock-container ${isLocked ? 'locked' : ''}`;

    if (isLocked) {
      const timeRemaining = this.formatTimeRemaining(lock.expiresAt - Date.now());
      lockContainer.innerHTML = `
        <svg class="legal-git-lock-icon" viewBox="0 0 24 24">
          <path d="M18,8A2,2 0 0,1 20,10V20A2,2 0 0,1 18,22H6A2,2 0 0,1 4,20V10A2,2 0 0,1 6,8H7V6A5,5 0 0,1 12,1A5,5 0 0,1 17,6V8H18M12,3A3,3 0 0,0 9,6V8H15V6A3,3 0 0,0 12,3Z"/>
        </svg>
        <div class="legal-git-lock-status">
          <div>Reserved by <span class="legal-git-lock-user">${isOwnLock ? 'You' : lock.userName}</span></div>
          <div class="legal-git-lock-time">${timeRemaining} remaining</div>
        </div>
        ${isOwnLock ? `<button class="legal-git-unlock-btn" data-document-id="${documentId}">Release</button>` : ''}
        ${this.isAdmin() ? `<button class="legal-git-override-btn" data-document-id="${documentId}">Override</button>` : ''}
        <a class="legal-git-lock-info" data-document-id="${documentId}">Info</a>
      `;
    } else {
      lockContainer.innerHTML = `
        <svg class="legal-git-lock-icon" viewBox="0 0 24 24">
          <path d="M18,8A2,2 0 0,1 20,10V20A2,2 0 0,1 18,22H6A2,2 0 0,1 4,20V10C4,8.89 4.9,8 6,8H7V6A5,5 0 0,1 12,1A5,5 0 0,1 17,6V8H18M12,3A3,3 0 0,0 9,6V8H15V6A3,3 0 0,0 12,3M12,17A2,2 0 0,1 10,15A2,2 0 0,1 12,13A2,2 0 0,1 14,15A2,2 0 0,1 12,17Z"/>
        </svg>
        <div class="legal-git-lock-status">Document available for editing</div>
        <button class="legal-git-lock-btn" data-document-id="${documentId}">Reserve</button>
      `;
    }

    container.appendChild(lockContainer);
  }

  // Utility functions

  async getCurrentUser() {
    // Simulate getting current user from Google Drive API
    return {
      id: 'user_' + Date.now(),
      email: 'user@example.com',
      name: 'Current User'
    };
  }

  isUserLock(lock) {
    // For now, simulate by checking if lock was created recently
    return Date.now() - lock.lockedAt < 60000; // Last minute
  }

  isAdmin() {
    // Simulate admin check - in production, this would check user permissions
    return true;
  }

  getDocumentTitle(documentId) {
    const element = document.querySelector(`[data-document-id="${documentId}"]`);
    return element ? element.textContent.trim() : 'Unknown Document';
  }

  formatTimeRemaining(milliseconds) {
    if (milliseconds <= 0) return 'Expired';

    const minutes = Math.floor(milliseconds / 60000);
    if (minutes < 60) return `${minutes}m`;

    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;
    return `${hours}h ${remainingMinutes}m`;
  }

  formatDuration(milliseconds) {
    const minutes = Math.floor(milliseconds / 60000);
    if (minutes < 60) return `${minutes} minutes`;

    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;
    return `${hours} hours ${remainingMinutes} minutes`;
  }

  // Notification functions
  notifyLockExpired(documentId) {
    console.log(`Lock expired for document ${documentId}`);
    // TODO: Show notification to user
  }

  notifyLockOverride(oldLock, reason) {
    console.log(`Lock overridden for ${oldLock.userEmail}: ${reason}`);
    // TODO: Send notification to previous lock holder
  }

  showLockSuccessMessage(documentId) {
    this.showSuccess('Document reserved for editing');
  }

  showLockReleaseMessage(documentId) {
    this.showSuccess('Document lock released');
  }

  showSuccess(message) {
    // TODO: Implement toast notification
    console.log('Success:', message);
  }

  showError(message) {
    // TODO: Implement error notification
    console.error('Error:', message);
    alert('Error: ' + message);
  }

  // Release all locks held by current user (on page unload)
  async releaseAllUserLocks() {
    const userInfo = await this.getCurrentUser();
    const userLocks = Array.from(this.activeLocks.entries())
      .filter(([_, lock]) => lock.userId === userInfo.id);

    for (const [documentId, _] of userLocks) {
      await this.releaseDocumentLock(documentId);
    }
  }

  // Simulation methods (replace with actual API calls)
  async simulateLockCreation(lock) {
    // Simulate API call delay
    await new Promise(resolve => setTimeout(resolve, 500));
    return { success: true };
  }

  async simulateLockRelease(documentId) {
    await new Promise(resolve => setTimeout(resolve, 300));
    return { success: true };
  }

  async simulateAdminOverride(documentId, reason) {
    await new Promise(resolve => setTimeout(resolve, 400));
    return { success: true };
  }
}

// Initialize document locking system
window.legalGitDocumentLocking = new DocumentLockingSystem(window.GitOperationsManager);
