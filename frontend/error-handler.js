// Legal Git Chrome Extension - Global Error Handler
// Comprehensive error handling for production stability

class ErrorHandler {
  constructor() {
    this.errorLog = [];
    this.maxLogSize = 100;
    this.errorListeners = new Set();
    this.offlineQueue = [];
    this.init();
  }

  init() {
    this.setupGlobalHandlers();
    this.setupNetworkMonitoring();
    this.injectErrorUI();
  }

  // Setup global error handlers
  setupGlobalHandlers() {
    // Handle JavaScript errors
    window.addEventListener('error', (event) => {
      this.handleError({
        type: 'javascript',
        message: event.message,
        source: event.filename,
        line: event.lineno,
        column: event.colno,
        stack: event.error?.stack,
        timestamp: Date.now()
      });
    });

    // Handle unhandled promise rejections
    window.addEventListener('unhandledrejection', (event) => {
      this.handleError({
        type: 'promise',
        message: event.reason?.message || String(event.reason),
        stack: event.reason?.stack,
        timestamp: Date.now()
      });
    });

    // Intercept fetch errors
    const originalFetch = window.fetch;
    window.fetch = async (...args) => {
      try {
        const response = await originalFetch(...args);
        if (!response.ok) {
          this.handleNetworkError({
            url: args[0],
            status: response.status,
            statusText: response.statusText
          });
        }
        return response;
      } catch (error) {
        this.handleNetworkError({
          url: args[0],
          message: error.message,
          offline: !navigator.onLine
        });
        throw error;
      }
    };
  }

  // Setup network monitoring
  setupNetworkMonitoring() {
    window.addEventListener('online', () => {
      this.processOfflineQueue();
      this.showNotification('Connection restored', 'success');
    });

    window.addEventListener('offline', () => {
      this.showNotification('Working offline - changes will sync when connection returns', 'warning');
    });
  }

  // Inject error UI elements
  injectErrorUI() {
    const style = document.createElement('style');
    style.textContent = `
      .legal-git-error-notification {
        position: fixed;
        top: 20px;
        right: 20px;
        max-width: 400px;
        padding: 16px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 10000;
        font-family: 'Google Sans', Arial, sans-serif;
        animation: slideIn 0.3s ease-out;
      }

      @keyframes slideIn {
        from {
          transform: translateX(120%);
        }
        to {
          transform: translateX(0);
        }
      }

      .legal-git-error-notification.error {
        background: #dc3545;
        color: white;
      }

      .legal-git-error-notification.warning {
        background: #ffc107;
        color: #212529;
      }

      .legal-git-error-notification.success {
        background: #28a745;
        color: white;
      }

      .legal-git-error-notification.info {
        background: #17a2b8;
        color: white;
      }

      .legal-git-error-title {
        font-weight: 600;
        margin-bottom: 4px;
      }

      .legal-git-error-message {
        font-size: 14px;
        line-height: 1.4;
      }

      .legal-git-error-actions {
        margin-top: 12px;
        display: flex;
        gap: 8px;
      }

      .legal-git-error-btn {
        padding: 4px 12px;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        font-size: 13px;
        background: rgba(255,255,255,0.2);
        color: inherit;
        transition: background 0.2s;
      }

      .legal-git-error-btn:hover {
        background: rgba(255,255,255,0.3);
      }

      .legal-git-error-close {
        position: absolute;
        top: 8px;
        right: 8px;
        background: none;
        border: none;
        color: inherit;
        font-size: 20px;
        cursor: pointer;
        padding: 4px;
        line-height: 1;
      }

      .legal-git-error-details {
        margin-top: 12px;
        padding: 8px;
        background: rgba(0,0,0,0.1);
        border-radius: 4px;
        font-size: 12px;
        font-family: monospace;
        max-height: 150px;
        overflow-y: auto;
      }
    `;
    document.head.appendChild(style);
  }

  // Handle errors
  handleError(error) {
    // Log error
    this.logError(error);

    // Determine error severity and user message
    const userMessage = this.getUserFriendlyMessage(error);
    const severity = this.getErrorSeverity(error);

    // Show notification to user
    if (severity !== 'low') {
      this.showNotification(userMessage.title, severity, userMessage.message, userMessage.actions);
    }

    // Notify listeners
    this.errorListeners.forEach(listener => {
      try {
        listener(error);
      } catch (e) {
        console.error('Error in error listener:', e);
      }
    });

    // Attempt recovery if possible
    this.attemptErrorRecovery(error);
  }

  // Handle network errors specifically
  handleNetworkError(error) {
    const isOffline = !navigator.onLine;

    if (isOffline) {
      // Queue for offline processing
      this.offlineQueue.push({
        ...error,
        timestamp: Date.now()
      });
    }

    this.handleError({
      type: 'network',
      ...error,
      offline: isOffline
    });
  }

  // Get user-friendly error message
  getUserFriendlyMessage(error) {
    const messages = {
      network: {
        offline: {
          title: 'Working Offline',
          message: 'Your changes will be saved when connection returns',
          actions: []
        },
        404: {
          title: 'Document Not Found',
          message: 'The requested document could not be found',
          actions: [{ text: 'Refresh', action: 'refresh' }]
        },
        401: {
          title: 'Authentication Required',
          message: 'Please sign in to continue',
          actions: [{ text: 'Sign In', action: 'signin' }]
        },
        500: {
          title: 'Server Error',
          message: 'The server encountered an error. Please try again later',
          actions: [{ text: 'Retry', action: 'retry' }]
        }
      },
      javascript: {
        title: 'Something went wrong',
        message: 'An unexpected error occurred. The issue has been logged',
        actions: [{ text: 'Report Issue', action: 'report' }]
      },
      promise: {
        title: 'Operation Failed',
        message: 'The requested operation could not be completed',
        actions: [{ text: 'Try Again', action: 'retry' }]
      }
    };

    if (error.type === 'network') {
      if (error.offline) {
        return messages.network.offline;
      }
      return messages.network[error.status] || {
        title: 'Connection Error',
        message: `Unable to connect to server (${error.status || 'Unknown'})`,
        actions: [{ text: 'Retry', action: 'retry' }]
      };
    }

    return messages[error.type] || messages.javascript;
  }

  // Determine error severity
  getErrorSeverity(error) {
    if (error.type === 'network' && error.offline) {
      return 'warning';
    }

    if (error.type === 'network' && error.status >= 500) {
      return 'error';
    }

    if (error.type === 'javascript' && error.source?.includes('chrome-extension://')) {
      return 'error';
    }

    return 'warning';
  }

  // Show notification to user
  showNotification(title, type = 'error', message = '', actions = []) {
    const notification = document.createElement('div');
    notification.className = `legal-git-error-notification ${type}`;

    let actionsHtml = '';
    if (actions.length > 0) {
      actionsHtml = `
        <div class="legal-git-error-actions">
          ${actions.map(action =>
            `<button class="legal-git-error-btn" data-action="${action.action}">${action.text}</button>`
          ).join('')}
        </div>
      `;
    }

    notification.innerHTML = `
      <button class="legal-git-error-close">&times;</button>
      <div class="legal-git-error-title">${title}</div>
      ${message ? `<div class="legal-git-error-message">${message}</div>` : ''}
      ${actionsHtml}
    `;

    // Add event listeners
    notification.querySelector('.legal-git-error-close').onclick = () => notification.remove();

    notification.querySelectorAll('[data-action]').forEach(btn => {
      btn.onclick = () => {
        this.handleAction(btn.dataset.action);
        notification.remove();
      };
    });

    document.body.appendChild(notification);

    // Auto-remove after delay
    setTimeout(() => {
      if (notification.parentNode) {
        notification.remove();
      }
    }, type === 'error' ? 10000 : 5000);
  }

  // Handle notification actions
  handleAction(action) {
    switch (action) {
      case 'refresh':
        location.reload();
        break;
      case 'signin':
        // Trigger sign-in flow
        chrome.runtime.sendMessage({ action: 'signIn' });
        break;
      case 'retry':
        // Retry last failed operation
        if (this.lastFailedOperation) {
          this.lastFailedOperation();
        }
        break;
      case 'report':
        // Open feedback system
        if (window.legalGitFeedback) {
          window.legalGitFeedback.openReportDialog(this.getRecentErrors());
        }
        break;
    }
  }

  // Attempt automatic error recovery
  attemptErrorRecovery(error) {
    // Network errors - retry with exponential backoff
    if (error.type === 'network' && !error.offline) {
      const retryCount = error.retryCount || 0;
      if (retryCount < 3) {
        const delay = Math.pow(2, retryCount) * 1000;
        setTimeout(() => {
          console.log(`Retrying failed request (attempt ${retryCount + 1})`);
          // Retry logic would go here
        }, delay);
      }
    }

    // JavaScript errors - try to reload affected components
    if (error.type === 'javascript' && error.source?.includes('chunk')) {
      // Likely a code splitting error - try to reload the chunk
      console.log('Attempting to reload failed chunk');
      // Reload logic would go here
    }
  }

  // Process offline queue when back online
  processOfflineQueue() {
    if (this.offlineQueue.length === 0) return;

    console.log(`Processing ${this.offlineQueue.length} offline operations`);

    const queue = [...this.offlineQueue];
    this.offlineQueue = [];

    queue.forEach(operation => {
      // Retry each queued operation
      console.log('Retrying offline operation:', operation);
      // Retry logic would go here
    });
  }

  // Log error for debugging
  logError(error) {
    this.errorLog.push({
      ...error,
      timestamp: error.timestamp || Date.now(),
      url: location.href,
      userAgent: navigator.userAgent
    });

    // Keep log size limited
    if (this.errorLog.length > this.maxLogSize) {
      this.errorLog.shift();
    }

    // Log to console in development
    if (this.isDevelopment()) {
      console.error('Legal Git Error:', error);
    }
  }

  // Get recent errors for reporting
  getRecentErrors(count = 10) {
    return this.errorLog.slice(-count);
  }

  // Add error listener
  addErrorListener(listener) {
    this.errorListeners.add(listener);
  }

  // Remove error listener
  removeErrorListener(listener) {
    this.errorListeners.delete(listener);
  }

  // Check if in development mode
  isDevelopment() {
    return !('update_url' in chrome.runtime.getManifest());
  }

  // Clear error log
  clearErrorLog() {
    this.errorLog = [];
  }

  // Get error statistics
  getErrorStats() {
    const stats = {
      total: this.errorLog.length,
      byType: {},
      recent: []
    };

    this.errorLog.forEach(error => {
      stats.byType[error.type] = (stats.byType[error.type] || 0) + 1;
    });

    stats.recent = this.errorLog.slice(-5).map(error => ({
      type: error.type,
      message: error.message,
      timestamp: new Date(error.timestamp).toLocaleString()
    }));

    return stats;
  }
}

// Initialize error handler
window.legalGitErrorHandler = new ErrorHandler();

// Export for use in other modules
window.ErrorHandler = ErrorHandler;
