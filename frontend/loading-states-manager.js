// Legal Git Chrome Extension - Loading States Manager
// Manages loading indicators and progress feedback throughout the extension

class LoadingStatesManager {
  constructor() {
    this.activeLoaders = new Map();
    this.globalLoaderId = 'legal-git-global-loader';
    this.init();
  }

  init() {
    this.injectLoadingStyles();
    this.createGlobalLoader();
    this.interceptFetchRequests();
  }

  // Inject loading styles
  injectLoadingStyles() {
    const style = document.createElement('style');
    style.textContent = `
      /* Global loader */
      .legal-git-global-loader {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: #e0e0e0;
        z-index: 10001;
        opacity: 0;
        transition: opacity 0.3s;
      }

      .legal-git-global-loader.active {
        opacity: 1;
      }

      .legal-git-global-loader-bar {
        height: 100%;
        background: #1a73e8;
        width: 0;
        transition: width 0.3s ease;
        box-shadow: 0 0 10px rgba(26, 115, 232, 0.5);
      }

      .legal-git-global-loader-bar.indeterminate {
        width: 30%;
        animation: indeterminateLoader 1.5s infinite;
      }

      @keyframes indeterminateLoader {
        0% { transform: translateX(-100%); }
        100% { transform: translateX(400%); }
      }

      /* Inline loader */
      .legal-git-inline-loader {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        color: #5f6368;
        font-size: 14px;
      }

      .legal-git-spinner {
        width: 16px;
        height: 16px;
        border: 2px solid #e0e0e0;
        border-top-color: #1a73e8;
        border-radius: 50%;
        animation: spin 0.8s linear infinite;
      }

      @keyframes spin {
        to { transform: rotate(360deg); }
      }

      /* Button loader */
      .legal-git-btn-loading {
        position: relative;
        color: transparent !important;
        pointer-events: none;
      }

      .legal-git-btn-loading::after {
        content: '';
        position: absolute;
        width: 16px;
        height: 16px;
        top: 50%;
        left: 50%;
        margin-left: -8px;
        margin-top: -8px;
        border: 2px solid #ffffff;
        border-radius: 50%;
        border-top-color: transparent;
        animation: spin 0.8s linear infinite;
      }

      /* Skeleton loader */
      .legal-git-skeleton {
        background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
        background-size: 200% 100%;
        animation: loading 1.5s infinite;
        border-radius: 4px;
      }

      @keyframes loading {
        0% { background-position: 200% 0; }
        100% { background-position: -200% 0; }
      }

      .legal-git-skeleton-text {
        height: 12px;
        margin: 8px 0;
        border-radius: 4px;
      }

      .legal-git-skeleton-title {
        height: 20px;
        width: 60%;
        margin: 12px 0;
        border-radius: 4px;
      }

      .legal-git-skeleton-button {
        height: 36px;
        width: 120px;
        border-radius: 4px;
      }

      .legal-git-skeleton-card {
        padding: 16px;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        margin: 8px 0;
      }

      /* Loading overlay */
      .legal-git-loading-overlay {
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(255, 255, 255, 0.8);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 1000;
      }

      .legal-git-loading-content {
        text-align: center;
      }

      .legal-git-loading-spinner {
        width: 40px;
        height: 40px;
        border: 3px solid #e0e0e0;
        border-top-color: #1a73e8;
        border-radius: 50%;
        animation: spin 0.8s linear infinite;
        margin: 0 auto 16px;
      }

      .legal-git-loading-text {
        color: #5f6368;
        font-size: 14px;
      }

      .legal-git-loading-progress {
        margin-top: 12px;
        font-size: 12px;
        color: #9aa0a6;
      }

      /* Toast notifications */
      .legal-git-toast {
        position: fixed;
        bottom: 20px;
        left: 50%;
        transform: translateX(-50%);
        background: #323232;
        color: white;
        padding: 12px 24px;
        border-radius: 4px;
        font-size: 14px;
        z-index: 10002;
        opacity: 0;
        transition: opacity 0.3s, transform 0.3s;
      }

      .legal-git-toast.show {
        opacity: 1;
        transform: translateX(-50%) translateY(0);
      }

      /* Shimmer effect */
      .legal-git-shimmer {
        position: relative;
        overflow: hidden;
      }

      .legal-git-shimmer::after {
        content: '';
        position: absolute;
        top: 0;
        right: 0;
        bottom: 0;
        left: 0;
        transform: translateX(-100%);
        background: linear-gradient(
          90deg,
          rgba(255, 255, 255, 0) 0,
          rgba(255, 255, 255, 0.2) 20%,
          rgba(255, 255, 255, 0.5) 60%,
          rgba(255, 255, 255, 0)
        );
        animation: shimmer 2s infinite;
      }

      @keyframes shimmer {
        100% { transform: translateX(100%); }
      }
    `;
    document.head.appendChild(style);
  }

  // Create global loader element
  createGlobalLoader() {
    const loader = document.createElement('div');
    loader.id = this.globalLoaderId;
    loader.className = 'legal-git-global-loader';
    loader.innerHTML = '<div class="legal-git-global-loader-bar"></div>';
    document.body.appendChild(loader);
  }

  // Intercept fetch requests to show loading states
  interceptFetchRequests() {
    const originalFetch = window.fetch;
    const manager = this;

    window.fetch = function(...args) {
      const loadingId = manager.startLoading();

      return originalFetch.apply(this, args)
        .then(response => {
          manager.stopLoading(loadingId);
          return response;
        })
        .catch(error => {
          manager.stopLoading(loadingId);
          throw error;
        });
    };
  }

  // Start loading with optional message
  startLoading(message = null, options = {}) {
    const loadingId = `loading-${Date.now()}-${Math.random()}`;

    this.activeLoaders.set(loadingId, {
      message,
      startTime: Date.now(),
      options
    });

    // Show appropriate loader based on options
    if (options.type === 'inline') {
      return this.createInlineLoader(loadingId, message);
    } else if (options.type === 'button') {
      return this.setButtonLoading(options.element, true);
    } else if (options.type === 'overlay') {
      return this.createOverlayLoader(loadingId, message, options.container);
    } else {
      // Default to global loader
      this.showGlobalLoader();
    }

    return loadingId;
  }

  // Stop loading
  stopLoading(loadingId) {
    const loader = this.activeLoaders.get(loadingId);
    if (!loader) return;

    this.activeLoaders.delete(loadingId);

    // Remove inline loader if exists
    const inlineLoader = document.getElementById(loadingId);
    if (inlineLoader) {
      inlineLoader.remove();
    }

    // Hide global loader if no active loaders
    if (this.activeLoaders.size === 0) {
      this.hideGlobalLoader();
    }
  }

  // Show global loader
  showGlobalLoader(progress = null) {
    const loader = document.getElementById(this.globalLoaderId);
    const bar = loader.querySelector('.legal-git-global-loader-bar');

    loader.classList.add('active');

    if (progress !== null) {
      bar.classList.remove('indeterminate');
      bar.style.width = `${progress}%`;
    } else {
      bar.classList.add('indeterminate');
    }
  }

  // Hide global loader
  hideGlobalLoader() {
    const loader = document.getElementById(this.globalLoaderId);
    loader.classList.remove('active');
  }

  // Create inline loader
  createInlineLoader(id, message) {
    const loader = document.createElement('div');
    loader.id = id;
    loader.className = 'legal-git-inline-loader';
    loader.innerHTML = `
      <div class="legal-git-spinner"></div>
      ${message ? `<span>${message}</span>` : ''}
    `;
    return loader;
  }

  // Set button loading state
  setButtonLoading(button, isLoading) {
    if (!button) return;

    if (isLoading) {
      button.classList.add('legal-git-btn-loading');
      button.disabled = true;
      button.dataset.originalText = button.textContent;
    } else {
      button.classList.remove('legal-git-btn-loading');
      button.disabled = false;
      if (button.dataset.originalText) {
        button.textContent = button.dataset.originalText;
      }
    }
  }

  // Create overlay loader
  createOverlayLoader(id, message, container) {
    const overlay = document.createElement('div');
    overlay.id = id;
    overlay.className = 'legal-git-loading-overlay';
    overlay.innerHTML = `
      <div class="legal-git-loading-content">
        <div class="legal-git-loading-spinner"></div>
        ${message ? `<div class="legal-git-loading-text">${message}</div>` : ''}
        <div class="legal-git-loading-progress"></div>
      </div>
    `;

    const targetContainer = container || document.body;
    targetContainer.style.position = 'relative';
    targetContainer.appendChild(overlay);

    return overlay;
  }

  // Update loading progress
  updateLoadingProgress(loadingId, progress, message = null) {
    const loader = this.activeLoaders.get(loadingId);
    if (!loader) return;

    // Update overlay progress if exists
    const overlay = document.getElementById(loadingId);
    if (overlay) {
      const progressEl = overlay.querySelector('.legal-git-loading-progress');
      if (progressEl) {
        progressEl.textContent = message || `${Math.round(progress)}% complete`;
      }
    }

    // Update global loader progress
    if (this.activeLoaders.size === 1) {
      this.showGlobalLoader(progress);
    }
  }

  // Create skeleton loader
  createSkeleton(type = 'text', count = 3) {
    const container = document.createElement('div');

    switch (type) {
      case 'text':
        for (let i = 0; i < count; i++) {
          const skeleton = document.createElement('div');
          skeleton.className = 'legal-git-skeleton legal-git-skeleton-text';
          container.appendChild(skeleton);
        }
        break;

      case 'card':
        const card = document.createElement('div');
        card.className = 'legal-git-skeleton-card';
        card.innerHTML = `
          <div class="legal-git-skeleton legal-git-skeleton-title"></div>
          <div class="legal-git-skeleton legal-git-skeleton-text"></div>
          <div class="legal-git-skeleton legal-git-skeleton-text"></div>
          <div class="legal-git-skeleton legal-git-skeleton-button"></div>
        `;
        container.appendChild(card);
        break;

      case 'list':
        for (let i = 0; i < count; i++) {
          const item = document.createElement('div');
          item.style.display = 'flex';
          item.style.gap = '12px';
          item.style.marginBottom = '12px';
          item.innerHTML = `
            <div class="legal-git-skeleton" style="width: 40px; height: 40px; border-radius: 50%;"></div>
            <div style="flex: 1;">
              <div class="legal-git-skeleton legal-git-skeleton-text" style="width: 60%;"></div>
              <div class="legal-git-skeleton legal-git-skeleton-text" style="width: 40%;"></div>
            </div>
          `;
          container.appendChild(item);
        }
        break;
    }

    return container;
  }

  // Show toast notification
  showToast(message, duration = 3000) {
    const toast = document.createElement('div');
    toast.className = 'legal-git-toast';
    toast.textContent = message;
    document.body.appendChild(toast);

    // Trigger animation
    setTimeout(() => toast.classList.add('show'), 10);

    // Remove after duration
    setTimeout(() => {
      toast.classList.remove('show');
      setTimeout(() => toast.remove(), 300);
    }, duration);
  }

  // Add shimmer effect to element
  addShimmer(element) {
    element.classList.add('legal-git-shimmer');
  }

  // Remove shimmer effect
  removeShimmer(element) {
    element.classList.remove('legal-git-shimmer');
  }

  // Helper to wrap async operations with loading state
  async withLoading(asyncFn, message = 'Loading...', options = {}) {
    const loadingId = this.startLoading(message, options);

    try {
      const result = await asyncFn();
      this.stopLoading(loadingId);
      return result;
    } catch (error) {
      this.stopLoading(loadingId);
      throw error;
    }
  }

  // Get loading statistics
  getStats() {
    const stats = {
      activeLoaders: this.activeLoaders.size,
      averageLoadTime: 0
    };

    if (this.activeLoaders.size > 0) {
      const totalTime = Array.from(this.activeLoaders.values())
        .reduce((sum, loader) => sum + (Date.now() - loader.startTime), 0);
      stats.averageLoadTime = Math.round(totalTime / this.activeLoaders.size);
    }

    return stats;
  }
}

// Initialize loading states manager
window.legalGitLoading = new LoadingStatesManager();

// Export for use in other modules
window.LoadingStatesManager = LoadingStatesManager;
