// Legal Git Chrome Extension - Bulk Operations Interface
// Enables batch operations on multiple documents for small law firms

class BulkOperationsInterface {
  constructor(gitOpsManager) {
    this.gitOpsManager = gitOpsManager;
    this.selectedDocuments = new Set();
    this.isProcessing = false;
    this.init();
  }

  init() {
    this.injectBulkUI();
    this.setupEventListeners();
  }

  // Inject bulk operations UI elements
  injectBulkUI() {
    const style = document.createElement('style');
    style.textContent = `
      .legal-git-bulk-container {
        position: sticky;
        top: 60px;
        background: white;
        border: 1px solid #dadce0;
        border-radius: 8px;
        padding: 12px 16px;
        margin: 16px;
        display: none;
        align-items: center;
        gap: 16px;
        z-index: 100;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
      }

      .legal-git-bulk-container.active {
        display: flex;
      }

      .legal-git-bulk-checkbox {
        width: 18px;
        height: 18px;
        cursor: pointer;
        margin-right: 8px;
      }

      .legal-git-bulk-selected {
        font-weight: 600;
        color: #1a73e8;
      }

      .legal-git-bulk-actions {
        display: flex;
        gap: 8px;
        margin-left: auto;
      }

      .legal-git-bulk-btn {
        background: #1a73e8;
        color: white;
        border: none;
        padding: 6px 16px;
        border-radius: 4px;
        cursor: pointer;
        font-size: 13px;
        transition: background 0.2s;
      }

      .legal-git-bulk-btn:hover {
        background: #1557b0;
      }

      .legal-git-bulk-btn:disabled {
        background: #ccc;
        cursor: not-allowed;
      }

      .legal-git-bulk-progress {
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: white;
        padding: 24px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        min-width: 400px;
        z-index: 10000;
      }

      .legal-git-bulk-progress-bar {
        width: 100%;
        height: 8px;
        background: #e0e0e0;
        border-radius: 4px;
        overflow: hidden;
        margin: 16px 0;
      }

      .legal-git-bulk-progress-fill {
        height: 100%;
        background: #1a73e8;
        transition: width 0.3s;
      }

      .legal-git-bulk-status {
        font-size: 14px;
        color: #5f6368;
        text-align: center;
      }
    `;
    document.head.appendChild(style);

    // Create bulk operations container
    const container = document.createElement('div');
    container.className = 'legal-git-bulk-container';
    container.innerHTML = `
      <div class="legal-git-bulk-info">
        <span class="legal-git-bulk-selected">0 documents selected</span>
      </div>
      <div class="legal-git-bulk-actions">
        <button class="legal-git-bulk-btn" data-action="track">Start Tracking</button>
        <button class="legal-git-bulk-btn" data-action="commit">Bulk Commit</button>
        <button class="legal-git-bulk-btn" data-action="convert">Convert Format</button>
      </div>
    `;

    const mainContent = document.querySelector('[role="main"]') || document.body;
    mainContent.insertBefore(container, mainContent.firstChild);
    this.bulkContainer = container;
  }

  // Setup event listeners
  setupEventListeners() {
    // Add checkboxes to document items
    this.addCheckboxes();

    // Handle checkbox changes
    document.addEventListener('change', (e) => {
      if (e.target.classList.contains('legal-git-bulk-checkbox')) {
        const docId = e.target.dataset.documentId;
        if (e.target.checked) {
          this.selectedDocuments.add(docId);
        } else {
          this.selectedDocuments.delete(docId);
        }
        this.updateUI();
      }
    });

    // Handle bulk action buttons
    document.addEventListener('click', (e) => {
      if (e.target.matches('.legal-git-bulk-btn')) {
        const action = e.target.dataset.action;
        this.performBulkAction(action);
      }
    });

    // Re-add checkboxes when content updates
    const observer = new MutationObserver(() => {
      this.addCheckboxes();
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  // Add checkboxes to document items
  addCheckboxes() {
    const documentItems = document.querySelectorAll('[data-id]:not(.legal-git-bulk-enhanced)');

    documentItems.forEach(item => {
      const docId = item.dataset.id;
      if (!docId) return;

      item.classList.add('legal-git-bulk-enhanced');

      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.className = 'legal-git-bulk-checkbox';
      checkbox.dataset.documentId = docId;
      checkbox.checked = this.selectedDocuments.has(docId);

      item.insertBefore(checkbox, item.firstChild);
    });
  }

  // Update UI based on selection
  updateUI() {
    const count = this.selectedDocuments.size;
    const selectedText = this.bulkContainer.querySelector('.legal-git-bulk-selected');
    selectedText.textContent = `${count} document${count !== 1 ? 's' : ''} selected`;

    if (count > 0) {
      this.bulkContainer.classList.add('active');
    } else {
      this.bulkContainer.classList.remove('active');
    }

    // Enable/disable buttons
    const buttons = this.bulkContainer.querySelectorAll('.legal-git-bulk-btn');
    buttons.forEach(btn => {
      btn.disabled = count === 0 || this.isProcessing;
    });
  }

  // Perform bulk action
  async performBulkAction(action) {
    if (this.selectedDocuments.size === 0 || this.isProcessing) return;

    this.isProcessing = true;
    const documents = Array.from(this.selectedDocuments);

    // Show progress dialog
    const progressDialog = this.showProgressDialog(action, documents.length);

    try {
      let processed = 0;
      const errors = [];

      for (const docId of documents) {
        try {
          await this.processDocument(action, docId);
          processed++;
        } catch (error) {
          console.error(`Error processing ${docId}:`, error);
          errors.push({ docId, error: error.message });
        }

        // Update progress
        const progress = (processed / documents.length) * 100;
        this.updateProgress(progressDialog, progress, `${processed}/${documents.length} documents processed`);
      }

      // Show completion
      this.showCompletion(progressDialog, processed, errors);

    } catch (error) {
      console.error('Bulk operation failed:', error);
      alert(`Bulk operation failed: ${error.message}`);
    } finally {
      this.isProcessing = false;
      this.updateUI();
    }
  }

  // Process individual document
  async processDocument(action, docId) {
    // Simulate API call delay
    await new Promise(resolve => setTimeout(resolve, 500));

    switch (action) {
      case 'track':
        // Start tracking for document
        const folderInfo = {
          folderId: docId,
          folderName: this.getDocumentName(docId)
        };
        await this.gitOpsManager.createRepository(folderInfo);
        break;

      case 'commit':
        // Commit changes for document
        const commitData = {
          type: 'fix',
          description: 'Bulk update',
          files: [docId]
        };
        await this.gitOpsManager.createCommit(docId, commitData);
        break;

      case 'convert':
        // Convert document format
        console.log(`Converting document ${docId}`);
        // Actual conversion would happen here
        break;

      default:
        throw new Error(`Unknown action: ${action}`);
    }
  }

  // Show progress dialog
  showProgressDialog(action, total) {
    const dialog = document.createElement('div');
    dialog.className = 'legal-git-bulk-progress';
    dialog.innerHTML = `
      <h3>Bulk ${action.charAt(0).toUpperCase() + action.slice(1)} Operation</h3>
      <div class="legal-git-bulk-progress-bar">
        <div class="legal-git-bulk-progress-fill" style="width: 0%"></div>
      </div>
      <div class="legal-git-bulk-status">Initializing...</div>
    `;
    document.body.appendChild(dialog);
    return dialog;
  }

  // Update progress
  updateProgress(dialog, percentage, status) {
    const progressFill = dialog.querySelector('.legal-git-bulk-progress-fill');
    const statusText = dialog.querySelector('.legal-git-bulk-status');

    progressFill.style.width = `${percentage}%`;
    statusText.textContent = status;
  }

  // Show completion message
  showCompletion(dialog, processed, errors) {
    const statusText = dialog.querySelector('.legal-git-bulk-status');

    if (errors.length === 0) {
      statusText.textContent = `✅ Successfully processed ${processed} documents`;
    } else {
      statusText.textContent = `⚠️ Processed ${processed} documents with ${errors.length} errors`;
    }

    // Add close button
    const closeBtn = document.createElement('button');
    closeBtn.className = 'legal-git-bulk-btn';
    closeBtn.textContent = 'Close';
    closeBtn.style.marginTop = '16px';
    closeBtn.onclick = () => {
      dialog.remove();
      this.selectedDocuments.clear();
      this.updateUI();
      // Uncheck all checkboxes
      document.querySelectorAll('.legal-git-bulk-checkbox').forEach(cb => cb.checked = false);
    };
    dialog.appendChild(closeBtn);
  }

  // Get document name
  getDocumentName(docId) {
    const element = document.querySelector(`[data-id="${docId}"]`);
    return element ? element.textContent.trim() : 'Unknown Document';
  }
}

// Initialize bulk operations
if (window.GitOperationsManager) {
  window.legalGitBulkOperations = new BulkOperationsInterface(window.GitOperationsManager);
}
