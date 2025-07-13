// Legal Git Chrome Extension - Commit UI Components
// Handles commit interface, legal conventional commits, and branch management

class CommitUIManager {
  constructor(gitOpsManager) {
    this.gitOps = gitOpsManager;
    this.legalCommitTypes = {
      'feat': {
        label: 'Feature',
        description: 'New clauses/sections',
        icon: '✨',
        color: '#28a745'
      },
      'fix': {
        label: 'Fix',
        description: 'Corrections/changes',
        icon: '🔧',
        color: '#dc3545'
      },
      'review': {
        label: 'Review',
        description: 'Incorporate feedback',
        icon: '👀',
        color: '#17a2b8'
      },
      'draft': {
        label: 'Draft',
        description: 'Work in progress',
        icon: '📝',
        color: '#ffc107'
      },
      'final': {
        label: 'Final',
        description: 'Ready for signature',
        icon: '✅',
        color: '#6610f2'
      },
      'docs': {
        label: 'Docs',
        description: 'Administrative updates',
        icon: '📚',
        color: '#6f42c1'
      },
      'redact': {
        label: 'Redact',
        description: 'Remove confidential info',
        icon: '🔒',
        color: '#e83e8c'
      },
      'merge': {
        label: 'Merge',
        description: 'Combine multiple versions',
        icon: '🔀',
        color: '#20c997'
      },
      'revert': {
        label: 'Revert',
        description: 'Undo changes',
        icon: '↩️',
        color: '#fd7e14'
      },
      'comment': {
        label: 'Comment',
        description: 'Add internal notes/questions',
        icon: '💬',
        color: '#6c757d'
      },
      'cite': {
        label: 'Cite',
        description: 'Add legal citations/references',
        icon: '📖',
        color: '#495057'
      },
      'format': {
        label: 'Format',
        description: 'Styling/layout changes only',
        icon: '🎨',
        color: '#007bff'
      }
    };
  }

  // Show commit modal dialog
  showCommitModal(repositoryId, currentBranch) {
    const modal = this.createCommitModal(repositoryId, currentBranch);
    document.body.appendChild(modal);

    // Focus on commit type selector
    setTimeout(() => {
      const typeSelect = modal.querySelector('#commit-type-select');
      if (typeSelect) typeSelect.focus();
    }, 100);
  }

  // Create commit modal HTML
  createCommitModal(repositoryId, currentBranch) {
    const modal = document.createElement('div');
    modal.className = 'legal-git-modal';
    modal.id = 'commit-modal';

    modal.innerHTML = `
      <div class="legal-git-modal-content" style="max-width: 600px;">
        <div class="legal-git-modal-header">
          <h3 class="legal-git-modal-title">Save Milestone (Commit)</h3>
          <button class="legal-git-modal-close" onclick="this.closest('.legal-git-modal').remove()">×</button>
        </div>

        <div class="commit-form">
          <div class="form-group" style="margin-bottom: 16px;">
            <label for="commit-type-select" style="display: block; margin-bottom: 4px; font-weight: 500;">
              Commit Type <span style="color: #dc3545;">*</span>
            </label>
            <select id="commit-type-select" style="
              width: 100%;
              padding: 8px 12px;
              border: 1px solid #dadce0;
              border-radius: 4px;
              font-size: 14px;
              background: white;
            ">
              <option value="">Select commit type...</option>
              ${this.generateCommitTypeOptions()}
            </select>
          </div>

          <div class="form-group" style="margin-bottom: 16px;">
            <label for="commit-description" style="display: block; margin-bottom: 4px; font-weight: 500;">
              Description <span style="color: #dc3545;">*</span>
              <span style="font-size: 12px; color: #5f6368;">(max 50 characters)</span>
            </label>
            <input
              type="text"
              id="commit-description"
              placeholder="Brief description of changes..."
              maxlength="50"
              style="
                width: 100%;
                padding: 8px 12px;
                border: 1px solid #dadce0;
                border-radius: 4px;
                font-size: 14px;
              "
            />
            <div style="font-size: 12px; color: #5f6368; margin-top: 4px; text-align: right;">
              <span id="char-count">0</span>/50
            </div>
          </div>

          <div class="form-group" style="margin-bottom: 16px;">
            <label for="commit-branch" style="display: block; margin-bottom: 4px; font-weight: 500;">
              Branch
            </label>
            <div style="display: flex; gap: 8px; align-items: center;">
              <select id="commit-branch" style="
                flex: 1;
                padding: 8px 12px;
                border: 1px solid #dadce0;
                border-radius: 4px;
                font-size: 14px;
                background: white;
              ">
                <option value="${currentBranch}" selected>${currentBranch}</option>
              </select>
              <button id="new-branch-btn" type="button" style="
                padding: 8px 12px;
                background: #f8f9fa;
                border: 1px solid #dadce0;
                border-radius: 4px;
                font-size: 12px;
                cursor: pointer;
              ">New Branch</button>
            </div>
          </div>

          <div id="new-branch-group" style="display: none; margin-bottom: 16px;">
            <label for="new-branch-name" style="display: block; margin-bottom: 4px; font-weight: 500;">
              New Branch Name
            </label>
            <input
              type="text"
              id="new-branch-name"
              placeholder="feature/new-clause"
              style="
                width: 100%;
                padding: 8px 12px;
                border: 1px solid #dadce0;
                border-radius: 4px;
                font-size: 14px;
              "
            />
          </div>

          <div class="commit-preview" style="
            background: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 4px;
            padding: 12px;
            margin-bottom: 16px;
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            font-size: 13px;
          ">
            <div style="color: #6c757d; margin-bottom: 4px;">Commit Message Preview:</div>
            <div id="commit-preview-text" style="color: #495057;">
              Select type and enter description
            </div>
          </div>

          <div class="modal-actions" style="display: flex; gap: 8px; justify-content: flex-end;">
            <button
              class="btn-cancel"
              onclick="this.closest('.legal-git-modal').remove()"
              style="
                padding: 8px 16px;
                background: #f8f9fa;
                border: 1px solid #dadce0;
                border-radius: 4px;
                cursor: pointer;
              "
            >Cancel</button>
            <button
              id="commit-save-btn"
              disabled
              style="
                padding: 8px 16px;
                background: #28a745;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
              "
            >Save Milestone</button>
          </div>
        </div>
      </div>
    `;

    this.setupCommitModalEvents(modal, repositoryId);
    return modal;
  }

  // Generate commit type dropdown options
  generateCommitTypeOptions() {
    return Object.entries(this.legalCommitTypes)
      .map(([type, config]) => `
        <option value="${type}">
          ${config.icon} ${config.label} - ${config.description}
        </option>
      `).join('');
  }

  // Setup commit modal event listeners
  setupCommitModalEvents(modal, repositoryId) {
    const typeSelect = modal.querySelector('#commit-type-select');
    const descriptionInput = modal.querySelector('#commit-description');
    const charCount = modal.querySelector('#char-count');
    const previewText = modal.querySelector('#commit-preview-text');
    const saveBtn = modal.querySelector('#commit-save-btn');
    const newBranchBtn = modal.querySelector('#new-branch-btn');
    const newBranchGroup = modal.querySelector('#new-branch-group');
    const branchSelect = modal.querySelector('#commit-branch');

    // Update preview and validation
    const updatePreview = () => {
      const type = typeSelect.value;
      const description = descriptionInput.value.trim();

      if (type && description) {
        previewText.textContent = `${type}: ${description}`;
        previewText.style.color = this.legalCommitTypes[type].color;
        saveBtn.disabled = false;
        saveBtn.style.opacity = '1';
      } else {
        previewText.textContent = 'Select type and enter description';
        previewText.style.color = '#6c757d';
        saveBtn.disabled = true;
        saveBtn.style.opacity = '0.6';
      }
    };

    // Character count update
    descriptionInput.addEventListener('input', () => {
      charCount.textContent = descriptionInput.value.length;
      updatePreview();
    });

    typeSelect.addEventListener('change', updatePreview);

    // New branch toggle
    newBranchBtn.addEventListener('click', () => {
      const isVisible = newBranchGroup.style.display !== 'none';
      newBranchGroup.style.display = isVisible ? 'none' : 'block';
      newBranchBtn.textContent = isVisible ? 'New Branch' : 'Cancel';

      if (!isVisible) {
        modal.querySelector('#new-branch-name').focus();
      }
    });

    // Save commit
    saveBtn.addEventListener('click', async () => {
      await this.handleCommitSave(modal, repositoryId);
    });

    // Load existing branches
    this.loadBranches(repositoryId, branchSelect);
  }

  // Load branches for repository
  async loadBranches(repositoryId, branchSelect) {
    const repository = this.gitOps.getRepositoryStatus(repositoryId);
    if (repository && repository.branches) {
      // Clear existing options except current
      const currentOption = branchSelect.querySelector('option[selected]');
      branchSelect.innerHTML = '';

      // Add all branches
      repository.branches.forEach(branch => {
        const option = document.createElement('option');
        option.value = branch;
        option.textContent = branch;
        if (branch === repository.currentBranch) {
          option.selected = true;
        }
        branchSelect.appendChild(option);
      });
    }
  }

  // Handle commit save
  async handleCommitSave(modal, repositoryId) {
    const typeSelect = modal.querySelector('#commit-type-select');
    const descriptionInput = modal.querySelector('#commit-description');
    const branchSelect = modal.querySelector('#commit-branch');
    const newBranchInput = modal.querySelector('#new-branch-name');
    const saveBtn = modal.querySelector('#commit-save-btn');

    try {
      saveBtn.disabled = true;
      saveBtn.textContent = 'Saving...';

      const commitData = {
        type: typeSelect.value,
        description: descriptionInput.value.trim(),
        branch: branchSelect.value,
        author: 'Current User' // TODO: Get from auth
      };

      // Create new branch if specified
      if (newBranchInput.value.trim()) {
        const newBranchName = newBranchInput.value.trim();
        await this.gitOps.createBranch(repositoryId, newBranchName, branchSelect.value);
        commitData.branch = this.gitOps.sanitizeBranchName(newBranchName);
      }

      // Create the commit
      const result = await this.gitOps.createCommit(repositoryId, commitData);

      // Show success message
      this.showSuccessMessage(`Milestone saved successfully! Commit: ${result.commitId}`);

      // Close modal
      modal.remove();

      // Update UI to reflect changes
      this.updateToolbarStatus(repositoryId);

    } catch (error) {
      console.error('Commit failed:', error);
      this.showErrorMessage(`Failed to save milestone: ${error.message}`);

      saveBtn.disabled = false;
      saveBtn.textContent = 'Save Milestone';
    }
  }

  // Show branch management modal
  showBranchModal(repositoryId) {
    const repository = this.gitOps.getRepositoryStatus(repositoryId);
    if (!repository) {
      this.showErrorMessage('Repository not found');
      return;
    }

    const modal = this.createBranchModal(repositoryId, repository);
    document.body.appendChild(modal);
  }

  // Create branch management modal
  createBranchModal(repositoryId, repository) {
    const modal = document.createElement('div');
    modal.className = 'legal-git-modal';
    modal.id = 'branch-modal';

    modal.innerHTML = `
      <div class="legal-git-modal-content" style="max-width: 500px;">
        <div class="legal-git-modal-header">
          <h3 class="legal-git-modal-title">Manage Work Streams (Branches)</h3>
          <button class="legal-git-modal-close" onclick="this.closest('.legal-git-modal').remove()">×</button>
        </div>

        <div class="branch-management">
          <div class="current-branch" style="
            background: #e3f2fd;
            border: 1px solid #2196f3;
            border-radius: 4px;
            padding: 12px;
            margin-bottom: 16px;
          ">
            <div style="font-weight: 500; color: #1976d2; margin-bottom: 4px;">
              🌿 Current Work Stream
            </div>
            <div style="font-size: 18px; color: #0d47a1;">
              ${repository.currentBranch}
            </div>
          </div>

          <div class="branch-list" style="margin-bottom: 16px;">
            <div style="font-weight: 500; margin-bottom: 8px; color: #1f1f1f;">
              All Work Streams:
            </div>
            <div id="branch-list-container">
              ${this.generateBranchList(repository)}
            </div>
          </div>

          <div class="new-branch-section" style="
            border-top: 1px solid #e0e0e0;
            padding-top: 16px;
          ">
            <div style="font-weight: 500; margin-bottom: 8px;">
              Create New Work Stream:
            </div>
            <div style="display: flex; gap: 8px;">
              <input
                type="text"
                id="new-branch-input"
                placeholder="client-review, internal-draft, etc."
                style="
                  flex: 1;
                  padding: 8px 12px;
                  border: 1px solid #dadce0;
                  border-radius: 4px;
                  font-size: 14px;
                "
              />
              <button id="create-branch-btn" style="
                padding: 8px 16px;
                background: #28a745;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                white-space: nowrap;
              ">Create</button>
            </div>
            <div style="font-size: 12px; color: #5f6368; margin-top: 4px;">
              Use descriptive names like "client-review" or "internal-draft"
            </div>
          </div>
        </div>
      </div>
    `;

    this.setupBranchModalEvents(modal, repositoryId);
    return modal;
  }

  // Generate branch list HTML
  generateBranchList(repository) {
    return repository.branches.map(branch => {
      const isCurrent = branch === repository.currentBranch;
      return `
        <div class="branch-item" style="
          display: flex;
          justify-content: between;
          align-items: center;
          padding: 8px 12px;
          border: 1px solid ${isCurrent ? '#2196f3' : '#e0e0e0'};
          border-radius: 4px;
          margin-bottom: 4px;
          background: ${isCurrent ? '#f3f8ff' : 'white'};
        ">
          <span style="flex: 1; font-weight: ${isCurrent ? '500' : '400'};">
            ${isCurrent ? '🌿 ' : ''}${branch}
          </span>
          ${!isCurrent ? `
            <button
              class="switch-branch-btn"
              data-branch="${branch}"
              style="
                padding: 4px 8px;
                background: #f8f9fa;
                border: 1px solid #dadce0;
                border-radius: 3px;
                font-size: 12px;
                cursor: pointer;
              "
            >Switch</button>
          ` : ''}
        </div>
      `;
    }).join('');
  }

  // Setup branch modal events
  setupBranchModalEvents(modal, repositoryId) {
    const createBtn = modal.querySelector('#create-branch-btn');
    const newBranchInput = modal.querySelector('#new-branch-input');

    // Create new branch
    createBtn.addEventListener('click', async () => {
      const branchName = newBranchInput.value.trim();
      if (!branchName) return;

      try {
        createBtn.disabled = true;
        createBtn.textContent = 'Creating...';

        await this.gitOps.createBranch(repositoryId, branchName);

        this.showSuccessMessage(`Work stream "${branchName}" created and switched to.`);
        modal.remove();
        this.updateToolbarStatus(repositoryId);

      } catch (error) {
        this.showErrorMessage(`Failed to create branch: ${error.message}`);
        createBtn.disabled = false;
        createBtn.textContent = 'Create';
      }
    });

    // Switch branch buttons
    modal.addEventListener('click', async (e) => {
      if (e.target.classList.contains('switch-branch-btn')) {
        const branchName = e.target.dataset.branch;

        try {
          e.target.disabled = true;
          e.target.textContent = 'Switching...';

          await this.gitOps.switchBranch(repositoryId, branchName);

          this.showSuccessMessage(`Switched to work stream "${branchName}".`);
          modal.remove();
          this.updateToolbarStatus(repositoryId);

        } catch (error) {
          this.showErrorMessage(`Failed to switch branch: ${error.message}`);
          e.target.disabled = false;
          e.target.textContent = 'Switch';
        }
      }
    });

    // Enter key to create branch
    newBranchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        createBtn.click();
      }
    });
  }

  // Update toolbar status after git operations
  updateToolbarStatus(repositoryId) {
    const repository = this.gitOps.getRepositoryStatus(repositoryId);
    const statusElement = document.getElementById('legal-git-status');
    const branchElement = document.getElementById('current-branch-display');

    if (statusElement && repository) {
      statusElement.textContent = `Tracked (${repository.currentBranch})`;
      statusElement.style.color = '#137333';
    }

    if (branchElement && repository) {
      branchElement.textContent = repository.currentBranch;
    }

    // Trigger UI update event
    window.dispatchEvent(new CustomEvent('legalGitStatusUpdate', {
      detail: { repositoryId, repository }
    }));
  }

  // Show success message
  showSuccessMessage(message) {
    this.showToast(message, 'success');
  }

  // Show error message
  showErrorMessage(message) {
    this.showToast(message, 'error');
  }

  // Show toast notification
  showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      z-index: 20001;
      padding: 12px 16px;
      border-radius: 4px;
      color: white;
      font-family: 'Google Sans', sans-serif;
      font-size: 14px;
      max-width: 300px;
      word-wrap: break-word;
      background: ${type === 'success' ? '#28a745' : type === 'error' ? '#dc3545' : '#17a2b8'};
      box-shadow: 0 2px 10px rgba(0,0,0,0.2);
      transform: translateX(100%);
      transition: transform 0.3s ease;
    `;

    toast.textContent = message;
    document.body.appendChild(toast);

    // Animate in
    setTimeout(() => {
      toast.style.transform = 'translateX(0)';
    }, 10);

    // Auto remove
    setTimeout(() => {
      toast.style.transform = 'translateX(100%)';
      setTimeout(() => {
        if (toast.parentNode) {
          toast.parentNode.removeChild(toast);
        }
      }, 300);
    }, 3000);
  }
}

// Export for use in other scripts
window.CommitUIManager = CommitUIManager;
