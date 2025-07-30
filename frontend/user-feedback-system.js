// Legal Git Chrome Extension - User Feedback System
// Collects user feedback for continuous improvement

class UserFeedbackSystem {
  constructor() {
    this.feedbackEndpoint = '/api/feedback'; // Will use local server
    this.isOpen = false;
    this.feedbackData = {};
    this.init();
  }

  init() {
    this.injectFeedbackUI();
    this.setupEventListeners();
    this.setupFeedbackWidget();
  }

  // Inject feedback UI styles and elements
  injectFeedbackUI() {
    const style = document.createElement('style');
    style.textContent = `
      .legal-git-feedback-widget {
        position: fixed;
        bottom: 20px;
        right: 20px;
        z-index: 9998;
      }

      .legal-git-feedback-button {
        background: #1a73e8;
        color: white;
        border: none;
        padding: 12px 20px;
        border-radius: 24px;
        cursor: pointer;
        font-size: 14px;
        font-weight: 600;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        display: flex;
        align-items: center;
        gap: 8px;
        transition: transform 0.2s, box-shadow 0.2s;
      }

      .legal-git-feedback-button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(0,0,0,0.2);
      }

      .legal-git-feedback-dialog {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0,0,0,0.5);
        z-index: 9999;
        display: none;
        align-items: center;
        justify-content: center;
      }

      .legal-git-feedback-dialog.active {
        display: flex;
      }

      .legal-git-feedback-content {
        background: white;
        border-radius: 8px;
        width: 90%;
        max-width: 500px;
        max-height: 90vh;
        overflow-y: auto;
        box-shadow: 0 8px 32px rgba(0,0,0,0.2);
      }

      .legal-git-feedback-header {
        padding: 20px;
        border-bottom: 1px solid #e0e0e0;
      }

      .legal-git-feedback-header h3 {
        margin: 0;
        font-size: 20px;
        color: #202124;
      }

      .legal-git-feedback-body {
        padding: 20px;
      }

      .legal-git-feedback-type {
        display: flex;
        gap: 12px;
        margin-bottom: 20px;
      }

      .legal-git-feedback-type-btn {
        flex: 1;
        padding: 12px;
        border: 2px solid #e0e0e0;
        background: white;
        border-radius: 8px;
        cursor: pointer;
        text-align: center;
        transition: all 0.2s;
      }

      .legal-git-feedback-type-btn:hover {
        border-color: #1a73e8;
      }

      .legal-git-feedback-type-btn.active {
        background: #e8f0fe;
        border-color: #1a73e8;
        color: #1a73e8;
      }

      .legal-git-feedback-type-icon {
        font-size: 24px;
        margin-bottom: 4px;
      }

      .legal-git-feedback-type-label {
        font-size: 13px;
        font-weight: 600;
      }

      .legal-git-feedback-form {
        display: flex;
        flex-direction: column;
        gap: 16px;
      }

      .legal-git-feedback-field {
        display: flex;
        flex-direction: column;
        gap: 4px;
      }

      .legal-git-feedback-label {
        font-size: 14px;
        font-weight: 600;
        color: #5f6368;
      }

      .legal-git-feedback-input,
      .legal-git-feedback-textarea {
        padding: 8px 12px;
        border: 1px solid #dadce0;
        border-radius: 4px;
        font-size: 14px;
        font-family: inherit;
      }

      .legal-git-feedback-textarea {
        min-height: 100px;
        resize: vertical;
      }

      .legal-git-feedback-rating {
        display: flex;
        gap: 8px;
      }

      .legal-git-feedback-star {
        font-size: 24px;
        color: #dadce0;
        cursor: pointer;
        transition: color 0.2s;
      }

      .legal-git-feedback-star:hover,
      .legal-git-feedback-star.active {
        color: #fbbc04;
      }

      .legal-git-feedback-footer {
        padding: 16px 20px;
        border-top: 1px solid #e0e0e0;
        display: flex;
        justify-content: space-between;
        align-items: center;
      }

      .legal-git-feedback-actions {
        display: flex;
        gap: 8px;
      }

      .legal-git-feedback-btn {
        padding: 8px 16px;
        border: none;
        border-radius: 4px;
        font-size: 14px;
        font-weight: 600;
        cursor: pointer;
        transition: background 0.2s;
      }

      .legal-git-feedback-btn.primary {
        background: #1a73e8;
        color: white;
      }

      .legal-git-feedback-btn.primary:hover {
        background: #1557b0;
      }

      .legal-git-feedback-btn.secondary {
        background: #f8f9fa;
        color: #5f6368;
      }

      .legal-git-feedback-btn.secondary:hover {
        background: #e8eaed;
      }

      .legal-git-feedback-screenshot {
        margin-top: 12px;
        position: relative;
      }

      .legal-git-feedback-screenshot img {
        max-width: 100%;
        border: 1px solid #dadce0;
        border-radius: 4px;
      }

      .legal-git-feedback-success {
        text-align: center;
        padding: 40px 20px;
      }

      .legal-git-feedback-success-icon {
        font-size: 48px;
        color: #34a853;
        margin-bottom: 16px;
      }

      .legal-git-feedback-success-message {
        font-size: 16px;
        color: #202124;
        margin-bottom: 8px;
      }

      .legal-git-feedback-success-sub {
        font-size: 14px;
        color: #5f6368;
      }
    `;
    document.head.appendChild(style);
  }

  // Setup feedback widget
  setupFeedbackWidget() {
    const widget = document.createElement('div');
    widget.className = 'legal-git-feedback-widget';
    widget.innerHTML = `
      <button class="legal-git-feedback-button">
        <span>💬</span>
        <span>Feedback</span>
      </button>
    `;
    document.body.appendChild(widget);

    // Create dialog
    const dialog = document.createElement('div');
    dialog.className = 'legal-git-feedback-dialog';
    dialog.innerHTML = `
      <div class="legal-git-feedback-content">
        <div class="legal-git-feedback-header">
          <h3>Send Feedback</h3>
        </div>
        <div class="legal-git-feedback-body"></div>
        <div class="legal-git-feedback-footer"></div>
      </div>
    `;
    document.body.appendChild(dialog);

    this.widget = widget;
    this.dialog = dialog;
  }

  // Setup event listeners
  setupEventListeners() {
    // Open feedback on widget click
    document.addEventListener('click', (e) => {
      if (e.target.closest('.legal-git-feedback-button')) {
        this.openFeedbackDialog();
      }
    });

    // Close on background click
    this.dialog?.addEventListener('click', (e) => {
      if (e.target === this.dialog) {
        this.closeFeedbackDialog();
      }
    });

    // Close on escape
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this.isOpen) {
        this.closeFeedbackDialog();
      }
    });
  }

  // Open feedback dialog
  openFeedbackDialog(prefillType = null) {
    this.isOpen = true;
    this.dialog.classList.add('active');
    this.feedbackData = { type: prefillType };
    this.renderFeedbackForm();
  }

  // Close feedback dialog
  closeFeedbackDialog() {
    this.isOpen = false;
    this.dialog.classList.remove('active');
    this.feedbackData = {};
  }

  // Render feedback form
  renderFeedbackForm() {
    const body = this.dialog.querySelector('.legal-git-feedback-body');
    const footer = this.dialog.querySelector('.legal-git-feedback-footer');

    body.innerHTML = `
      <div class="legal-git-feedback-type">
        <button class="legal-git-feedback-type-btn" data-type="bug">
          <div class="legal-git-feedback-type-icon">🐛</div>
          <div class="legal-git-feedback-type-label">Bug Report</div>
        </button>
        <button class="legal-git-feedback-type-btn" data-type="feature">
          <div class="legal-git-feedback-type-icon">💡</div>
          <div class="legal-git-feedback-type-label">Feature Request</div>
        </button>
        <button class="legal-git-feedback-type-btn" data-type="improvement">
          <div class="legal-git-feedback-type-icon">⚡</div>
          <div class="legal-git-feedback-type-label">Improvement</div>
        </button>
      </div>

      <form class="legal-git-feedback-form">
        <div class="legal-git-feedback-field">
          <label class="legal-git-feedback-label">How would you rate your experience?</label>
          <div class="legal-git-feedback-rating">
            ${[1,2,3,4,5].map(i =>
              `<span class="legal-git-feedback-star" data-rating="${i}">★</span>`
            ).join('')}
          </div>
        </div>

        <div class="legal-git-feedback-field">
          <label class="legal-git-feedback-label" for="feedback-title">Title</label>
          <input type="text" id="feedback-title" class="legal-git-feedback-input"
                 placeholder="Brief summary of your feedback" required>
        </div>

        <div class="legal-git-feedback-field">
          <label class="legal-git-feedback-label" for="feedback-description">Description</label>
          <textarea id="feedback-description" class="legal-git-feedback-textarea"
                    placeholder="Please provide details..." required></textarea>
        </div>

        <div class="legal-git-feedback-field">
          <label class="legal-git-feedback-label">
            <input type="checkbox" id="feedback-screenshot"> Include screenshot
          </label>
          <div class="legal-git-feedback-screenshot" style="display: none;">
            <img id="feedback-screenshot-img" alt="Screenshot">
          </div>
        </div>
      </form>
    `;

    footer.innerHTML = `
      <div class="legal-git-feedback-info">
        <small style="color: #5f6368;">Your feedback helps us improve</small>
      </div>
      <div class="legal-git-feedback-actions">
        <button class="legal-git-feedback-btn secondary" onclick="window.legalGitFeedback.closeFeedbackDialog()">Cancel</button>
        <button class="legal-git-feedback-btn primary" onclick="window.legalGitFeedback.submitFeedback()">Send Feedback</button>
      </div>
    `;

    // Add event listeners
    this.setupFormListeners();

    // Pre-select type if provided
    if (this.feedbackData.type) {
      const typeBtn = body.querySelector(`[data-type="${this.feedbackData.type}"]`);
      if (typeBtn) {
        typeBtn.classList.add('active');
      }
    }
  }

  // Setup form event listeners
  setupFormListeners() {
    // Feedback type selection
    this.dialog.querySelectorAll('.legal-git-feedback-type-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        this.dialog.querySelectorAll('.legal-git-feedback-type-btn').forEach(b =>
          b.classList.remove('active')
        );
        btn.classList.add('active');
        this.feedbackData.type = btn.dataset.type;
      });
    });

    // Rating selection
    this.dialog.querySelectorAll('.legal-git-feedback-star').forEach(star => {
      star.addEventListener('click', () => {
        const rating = parseInt(star.dataset.rating);
        this.feedbackData.rating = rating;
        this.updateRatingDisplay(rating);
      });
    });

    // Screenshot checkbox
    const screenshotCheckbox = this.dialog.querySelector('#feedback-screenshot');
    screenshotCheckbox?.addEventListener('change', async (e) => {
      if (e.target.checked) {
        await this.captureScreenshot();
      } else {
        this.dialog.querySelector('.legal-git-feedback-screenshot').style.display = 'none';
        delete this.feedbackData.screenshot;
      }
    });
  }

  // Update rating display
  updateRatingDisplay(rating) {
    this.dialog.querySelectorAll('.legal-git-feedback-star').forEach((star, index) => {
      if (index < rating) {
        star.classList.add('active');
      } else {
        star.classList.remove('active');
      }
    });
  }

  // Capture screenshot
  async captureScreenshot() {
    try {
      // Request screenshot from background script
      const response = await chrome.runtime.sendMessage({ action: 'captureScreenshot' });

      if (response && response.dataUrl) {
        this.feedbackData.screenshot = response.dataUrl;
        const screenshotDiv = this.dialog.querySelector('.legal-git-feedback-screenshot');
        const screenshotImg = this.dialog.querySelector('#feedback-screenshot-img');

        screenshotImg.src = response.dataUrl;
        screenshotDiv.style.display = 'block';
      }
    } catch (error) {
      console.error('Failed to capture screenshot:', error);
    }
  }

  // Submit feedback
  async submitFeedback() {
    // Gather form data
    const title = this.dialog.querySelector('#feedback-title').value;
    const description = this.dialog.querySelector('#feedback-description').value;

    if (!title || !description || !this.feedbackData.type) {
      alert('Please fill in all required fields and select a feedback type');
      return;
    }

    // Prepare feedback data
    const feedback = {
      type: this.feedbackData.type,
      rating: this.feedbackData.rating || 0,
      title: title,
      description: description,
      screenshot: this.feedbackData.screenshot,
      timestamp: Date.now(),
      url: location.href,
      userAgent: navigator.userAgent,
      extensionVersion: chrome.runtime.getManifest().version
    };

    try {
      // Send feedback to local server
      await this.sendFeedback(feedback);
      this.showSuccessMessage();
    } catch (error) {
      console.error('Failed to send feedback:', error);
      alert('Failed to send feedback. Please try again later.');
    }
  }

  // Send feedback to server
  async sendFeedback(feedback) {
    // For now, store locally and log
    const feedbackHistory = await this.getFeedbackHistory();
    feedbackHistory.push(feedback);

    await chrome.storage.local.set({ feedbackHistory: feedbackHistory });

    console.log('Feedback submitted:', feedback);

    // In production, send to server
    // await fetch(this.feedbackEndpoint, {
    //   method: 'POST',
    //   headers: { 'Content-Type': 'application/json' },
    //   body: JSON.stringify(feedback)
    // });
  }

  // Get feedback history
  async getFeedbackHistory() {
    const result = await chrome.storage.local.get(['feedbackHistory']);
    return result.feedbackHistory || [];
  }

  // Show success message
  showSuccessMessage() {
    const body = this.dialog.querySelector('.legal-git-feedback-body');
    const footer = this.dialog.querySelector('.legal-git-feedback-footer');

    body.innerHTML = `
      <div class="legal-git-feedback-success">
        <div class="legal-git-feedback-success-icon">✅</div>
        <div class="legal-git-feedback-success-message">Thank you for your feedback!</div>
        <div class="legal-git-feedback-success-sub">Your input helps us improve Trunk for everyone.</div>
      </div>
    `;

    footer.innerHTML = `
      <div class="legal-git-feedback-actions" style="width: 100%; justify-content: center;">
        <button class="legal-git-feedback-btn primary" onclick="window.legalGitFeedback.closeFeedbackDialog()">Close</button>
      </div>
    `;

    // Auto-close after 3 seconds
    setTimeout(() => {
      this.closeFeedbackDialog();
    }, 3000);
  }

  // Open report dialog with error context
  openReportDialog(errors = []) {
    this.openFeedbackDialog('bug');

    // Pre-fill with error information
    setTimeout(() => {
      const descriptionField = this.dialog.querySelector('#feedback-description');
      if (descriptionField && errors.length > 0) {
        const errorSummary = errors.map(e =>
          `${e.type}: ${e.message} (${new Date(e.timestamp).toLocaleString()})`
        ).join('\n');

        descriptionField.value = `Encountered errors:\n\n${errorSummary}\n\nAdditional context:\n`;
      }
    }, 100);
  }
}

// Initialize feedback system
window.legalGitFeedback = new UserFeedbackSystem();

// Export for use in other modules
window.UserFeedbackSystem = UserFeedbackSystem;
