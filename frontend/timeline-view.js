// Legal Git Chrome Extension - Timeline View for Document History
// Provides chronological visualization of document changes and version history

class TimelineView {
  constructor(documentConverter, changeTracker) {
    this.documentConverter = documentConverter;
    this.changeTracker = changeTracker;
    this.timelineData = new Map();
    this.timelineViewOpen = false;
    this.currentDocumentId = null;
    this.init();
  }

  init() {
    this.setupTimelineEventListeners();
    this.injectTimelineStyles();
  }

  // Setup event listeners for timeline view
  setupTimelineEventListeners() {
    window.addEventListener('legalGitShowTimeline', (event) => {
      this.showTimelineModal(event.detail.documentId);
    });

    window.addEventListener('documentHistoryUpdated', (event) => {
      this.updateTimelineData(event.detail);
    });

    window.addEventListener('legalGitCompareVersions', (event) => {
      this.compareVersions(event.detail.version1, event.detail.version2);
    });
  }

  // Inject CSS styles for timeline view
  injectTimelineStyles() {
    const styleId = 'legal-git-timeline-styles';
    if (document.getElementById(styleId)) return;

    const style = document.createElement('style');
    style.id = styleId;
    style.textContent = `
      .legal-git-timeline-container {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.75);
        z-index: 22000;
        display: flex;
        align-items: center;
        justify-content: center;
        font-family: 'Google Sans', Roboto, Arial, sans-serif;
      }

      .legal-git-timeline-modal {
        background: white;
        border-radius: 12px;
        box-shadow: 0 12px 40px rgba(0,0,0,0.4);
        width: 95vw;
        height: 90vh;
        max-width: 1600px;
        display: flex;
        flex-direction: column;
        overflow: hidden;
      }

      .legal-git-timeline-header {
        padding: 20px 24px;
        border-bottom: 1px solid #e0e0e0;
        background: linear-gradient(135deg, #f8f9fa, #e8f0fe);
        display: flex;
        justify-content: space-between;
        align-items: center;
      }

      .legal-git-timeline-title {
        font-size: 20px;
        font-weight: 600;
        color: #1a73e8;
        display: flex;
        align-items: center;
        gap: 12px;
      }

      .legal-git-timeline-close {
        background: none;
        border: none;
        font-size: 28px;
        cursor: pointer;
        color: #5f6368;
        padding: 8px;
        border-radius: 6px;
        transition: all 0.2s;
      }

      .legal-git-timeline-close:hover {
        background: #f1f3f4;
        transform: scale(1.1);
      }

      .legal-git-timeline-content {
        flex: 1;
        display: flex;
        overflow: hidden;
      }

      .legal-git-timeline-sidebar {
        width: 320px;
        background: #f8f9fa;
        border-right: 1px solid #e0e0e0;
        overflow-y: auto;
        padding: 20px;
      }

      .legal-git-timeline-main {
        flex: 1;
        overflow-y: auto;
        padding: 20px 24px;
      }

      .legal-git-timeline-filters {
        background: white;
        border: 1px solid #dadce0;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 20px;
      }

      .legal-git-timeline-filters h4 {
        margin: 0 0 12px 0;
        font-size: 14px;
        font-weight: 600;
        color: #1f1f1f;
      }

      .legal-git-timeline-filter-group {
        margin-bottom: 16px;
      }

      .legal-git-timeline-filter-group:last-child {
        margin-bottom: 0;
      }

      .legal-git-timeline-filter-label {
        display: block;
        font-size: 12px;
        color: #5f6368;
        margin-bottom: 6px;
        font-weight: 500;
      }

      .legal-git-timeline-filter-select {
        width: 100%;
        padding: 8px 12px;
        border: 1px solid #dadce0;
        border-radius: 4px;
        font-size: 13px;
        background: white;
      }

      .legal-git-timeline-stats {
        background: white;
        border: 1px solid #dadce0;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 20px;
      }

      .legal-git-timeline-stats h4 {
        margin: 0 0 12px 0;
        font-size: 14px;
        font-weight: 600;
        color: #1f1f1f;
      }

      .legal-git-timeline-stat {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 6px 0;
        font-size: 13px;
        border-bottom: 1px solid #f0f0f0;
      }

      .legal-git-timeline-stat:last-child {
        border-bottom: none;
      }

      .legal-git-timeline-stat-value {
        font-weight: 600;
        color: #1a73e8;
      }

      .legal-git-timeline-view {
        background: white;
        border: 1px solid #dadce0;
        border-radius: 8px;
        overflow: hidden;
        position: relative;
      }

      .legal-git-timeline-controls {
        padding: 16px 20px;
        border-bottom: 1px solid #e0e0e0;
        background: #f8f9fa;
        display: flex;
        justify-content: space-between;
        align-items: center;
      }

      .legal-git-timeline-controls-left {
        display: flex;
        gap: 12px;
        align-items: center;
      }

      .legal-git-timeline-controls-right {
        display: flex;
        gap: 8px;
        align-items: center;
      }

      .legal-git-timeline-control-btn {
        padding: 6px 12px;
        background: white;
        border: 1px solid #dadce0;
        border-radius: 4px;
        font-size: 12px;
        cursor: pointer;
        transition: all 0.2s;
        font-weight: 500;
      }

      .legal-git-timeline-control-btn:hover {
        background: #f1f3f4;
      }

      .legal-git-timeline-control-btn.active {
        background: #1a73e8;
        color: white;
        border-color: #1a73e8;
      }

      .legal-git-timeline-viewport {
        height: 500px;
        overflow-y: auto;
        position: relative;
      }

      .legal-git-timeline-track {
        position: relative;
        padding: 20px;
        min-height: 100%;
      }

      .legal-git-timeline-line {
        position: absolute;
        left: 50%;
        top: 0;
        bottom: 0;
        width: 4px;
        background: linear-gradient(to bottom, #1a73e8, #4285f4);
        transform: translateX(-50%);
        border-radius: 2px;
      }

      .legal-git-timeline-event {
        position: relative;
        margin-bottom: 32px;
        display: flex;
        align-items: flex-start;
        gap: 16px;
      }

      .legal-git-timeline-event.left {
        flex-direction: row;
        text-align: right;
      }

      .legal-git-timeline-event.right {
        flex-direction: row-reverse;
        text-align: left;
      }

      .legal-git-timeline-event-marker {
        position: absolute;
        left: 50%;
        transform: translateX(-50%);
        width: 16px;
        height: 16px;
        border-radius: 50%;
        background: white;
        border: 3px solid #1a73e8;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        z-index: 10;
      }

      .legal-git-timeline-event-marker.major {
        width: 20px;
        height: 20px;
        border-color: #34a853;
        background: #34a853;
      }

      .legal-git-timeline-event-marker.minor {
        width: 12px;
        height: 12px;
        border-color: #fbbc04;
        background: #fbbc04;
      }

      .legal-git-timeline-event-content {
        flex: 1;
        max-width: 45%;
        background: white;
        border: 1px solid #dadce0;
        border-radius: 8px;
        padding: 16px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        transition: all 0.2s;
        cursor: pointer;
      }

      .legal-git-timeline-event-content:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 16px rgba(0,0,0,0.1);
      }

      .legal-git-timeline-event-content.selected {
        border-color: #1a73e8;
        background: #e8f0fe;
      }

      .legal-git-timeline-event-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 8px;
      }

      .legal-git-timeline-event-title {
        font-size: 14px;
        font-weight: 600;
        color: #1f1f1f;
        line-height: 1.4;
      }

      .legal-git-timeline-event-time {
        font-size: 11px;
        color: #5f6368;
        font-weight: 500;
        white-space: nowrap;
        margin-left: 8px;
      }

      .legal-git-timeline-event-details {
        font-size: 13px;
        color: #5f6368;
        line-height: 1.4;
        margin-bottom: 8px;
      }

      .legal-git-timeline-event-meta {
        display: flex;
        gap: 8px;
        font-size: 11px;
        color: #5f6368;
      }

      .legal-git-timeline-event-tag {
        background: #f1f3f4;
        padding: 2px 6px;
        border-radius: 3px;
        font-weight: 500;
      }

      .legal-git-timeline-event-tag.commit {
        background: #e8f0fe;
        color: #1a73e8;
      }

      .legal-git-timeline-event-tag.branch {
        background: #e6f4ea;
        color: #1e8e3e;
      }

      .legal-git-timeline-event-tag.merge {
        background: #fef7e0;
        color: #f29900;
      }

      .legal-git-timeline-event-tag.conflict {
        background: #fce8e6;
        color: #d93025;
      }

      .legal-git-timeline-event-actions {
        display: flex;
        gap: 6px;
        margin-top: 8px;
      }

      .legal-git-timeline-event-btn {
        padding: 4px 8px;
        background: #f8f9fa;
        border: 1px solid #dadce0;
        border-radius: 3px;
        font-size: 11px;
        cursor: pointer;
        transition: all 0.2s;
      }

      .legal-git-timeline-event-btn:hover {
        background: #e9ecef;
      }

      .legal-git-timeline-comparison {
        background: white;
        border: 1px solid #dadce0;
        border-radius: 8px;
        margin-top: 20px;
        overflow: hidden;
      }

      .legal-git-timeline-comparison-header {
        padding: 16px 20px;
        background: #f8f9fa;
        border-bottom: 1px solid #e0e0e0;
        display: flex;
        justify-content: space-between;
        align-items: center;
      }

      .legal-git-timeline-comparison-title {
        font-size: 16px;
        font-weight: 600;
        color: #1f1f1f;
      }

      .legal-git-timeline-comparison-content {
        padding: 20px;
        max-height: 400px;
        overflow-y: auto;
      }

      .legal-git-timeline-version-selector {
        display: flex;
        gap: 12px;
        align-items: center;
        margin-bottom: 16px;
      }

      .legal-git-timeline-version-select {
        padding: 8px 12px;
        border: 1px solid #dadce0;
        border-radius: 4px;
        font-size: 13px;
        background: white;
      }

      .legal-git-timeline-zoom-controls {
        display: flex;
        gap: 4px;
        align-items: center;
      }

      .legal-git-timeline-zoom-btn {
        width: 28px;
        height: 28px;
        border: 1px solid #dadce0;
        border-radius: 4px;
        background: white;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 14px;
        transition: all 0.2s;
      }

      .legal-git-timeline-zoom-btn:hover {
        background: #f1f3f4;
      }

      .legal-git-timeline-loading {
        display: flex;
        align-items: center;
        justify-content: center;
        height: 200px;
        color: #5f6368;
      }

      .legal-git-timeline-empty {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        height: 300px;
        color: #5f6368;
      }

      .legal-git-timeline-empty-icon {
        font-size: 48px;
        margin-bottom: 16px;
        opacity: 0.5;
      }

      @keyframes timelineSlideIn {
        from { opacity: 0; transform: translateX(-20px); }
        to { opacity: 1; transform: translateX(0); }
      }

      .legal-git-timeline-event-content {
        animation: timelineSlideIn 0.3s ease-out;
      }

      @keyframes timelinePulse {
        0%, 100% { transform: translateX(-50%) scale(1); }
        50% { transform: translateX(-50%) scale(1.2); }
      }

      .legal-git-timeline-event-marker.active {
        animation: timelinePulse 2s infinite;
      }
    `;

    document.head.appendChild(style);
  }

  // Show timeline modal
  showTimelineModal(documentId) {
    if (this.timelineViewOpen) {
      this.closeTimelineModal();
    }

    this.currentDocumentId = documentId;
    const modal = this.createTimelineModal(documentId);
    document.body.appendChild(modal);
    this.timelineViewOpen = true;

    // Load timeline data
    this.loadTimelineData(documentId);

    // Focus trap
    setTimeout(() => {
      const closeBtn = modal.querySelector('.legal-git-timeline-close');
      if (closeBtn) closeBtn.focus();
    }, 100);
  }

  // Create timeline modal
  createTimelineModal(documentId) {
    const modal = document.createElement('div');
    modal.className = 'legal-git-timeline-container';
    modal.id = 'legal-git-timeline-modal';

    const documentTitle = this.getDocumentTitle(documentId);

    modal.innerHTML = `
      <div class="legal-git-timeline-modal">
        <div class="legal-git-timeline-header">
          <div class="legal-git-timeline-title">
            <span>📅</span>
            <span>Document Timeline - ${documentTitle}</span>
          </div>
          <button class="legal-git-timeline-close" onclick="window.timelineView.closeTimelineModal()">×</button>
        </div>

        <div class="legal-git-timeline-content">
          <div class="legal-git-timeline-sidebar">
            ${this.generateTimelineFilters()}
            ${this.generateTimelineStats()}
          </div>

          <div class="legal-git-timeline-main">
            <div class="legal-git-timeline-view">
              <div class="legal-git-timeline-controls">
                <div class="legal-git-timeline-controls-left">
                  <button class="legal-git-timeline-control-btn active" data-view="chronological">
                    Chronological
                  </button>
                  <button class="legal-git-timeline-control-btn" data-view="branched">
                    Branched
                  </button>
                  <button class="legal-git-timeline-control-btn" data-view="activity">
                    Activity
                  </button>
                </div>
                <div class="legal-git-timeline-controls-right">
                  <div class="legal-git-timeline-zoom-controls">
                    <button class="legal-git-timeline-zoom-btn" onclick="window.timelineView.zoomOut()">-</button>
                    <span style="padding: 0 8px; font-size: 12px; color: #5f6368;">100%</span>
                    <button class="legal-git-timeline-zoom-btn" onclick="window.timelineView.zoomIn()">+</button>
                  </div>
                </div>
              </div>

              <div class="legal-git-timeline-viewport">
                <div class="legal-git-timeline-loading">
                  <div>Loading timeline...</div>
                </div>
              </div>
            </div>

            <div class="legal-git-timeline-comparison" id="timeline-comparison" style="display: none;">
              <div class="legal-git-timeline-comparison-header">
                <div class="legal-git-timeline-comparison-title">Version Comparison</div>
                <button onclick="document.getElementById('timeline-comparison').style.display = 'none';"
                        style="background: none; border: none; font-size: 20px; cursor: pointer;">×</button>
              </div>
              <div class="legal-git-timeline-comparison-content">
                <div class="legal-git-timeline-version-selector">
                  <span>Compare:</span>
                  <select class="legal-git-timeline-version-select" id="version-select-1">
                    <option>Select version...</option>
                  </select>
                  <span>with:</span>
                  <select class="legal-git-timeline-version-select" id="version-select-2">
                    <option>Select version...</option>
                  </select>
                  <button class="legal-git-timeline-control-btn" onclick="window.timelineView.performComparison()">
                    Compare
                  </button>
                </div>
                <div id="comparison-result"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;

    this.setupTimelineModalEvents(modal);
    return modal;
  }

  // Generate timeline filters
  generateTimelineFilters() {
    return `
      <div class="legal-git-timeline-filters">
        <h4>🔍 Filters</h4>
        <div class="legal-git-timeline-filter-group">
          <label class="legal-git-timeline-filter-label">Time Range</label>
          <select class="legal-git-timeline-filter-select" id="time-range-filter">
            <option value="all">All Time</option>
            <option value="today">Today</option>
            <option value="week">This Week</option>
            <option value="month">This Month</option>
            <option value="quarter">This Quarter</option>
          </select>
        </div>
        <div class="legal-git-timeline-filter-group">
          <label class="legal-git-timeline-filter-label">Event Type</label>
          <select class="legal-git-timeline-filter-select" id="event-type-filter">
            <option value="all">All Events</option>
            <option value="commits">Commits Only</option>
            <option value="branches">Branches Only</option>
            <option value="merges">Merges Only</option>
            <option value="conflicts">Conflicts Only</option>
          </select>
        </div>
        <div class="legal-git-timeline-filter-group">
          <label class="legal-git-timeline-filter-label">Author</label>
          <select class="legal-git-timeline-filter-select" id="author-filter">
            <option value="all">All Authors</option>
          </select>
        </div>
      </div>
    `;
  }

  // Generate timeline statistics
  generateTimelineStats() {
    return `
      <div class="legal-git-timeline-stats">
        <h4>📊 Statistics</h4>
        <div class="legal-git-timeline-stat">
          <span>Total Events:</span>
          <span class="legal-git-timeline-stat-value" id="total-events">0</span>
        </div>
        <div class="legal-git-timeline-stat">
          <span>Commits:</span>
          <span class="legal-git-timeline-stat-value" id="total-commits">0</span>
        </div>
        <div class="legal-git-timeline-stat">
          <span>Branches:</span>
          <span class="legal-git-timeline-stat-value" id="total-branches">0</span>
        </div>
        <div class="legal-git-timeline-stat">
          <span>Merges:</span>
          <span class="legal-git-timeline-stat-value" id="total-merges">0</span>
        </div>
        <div class="legal-git-timeline-stat">
          <span>Contributors:</span>
          <span class="legal-git-timeline-stat-value" id="total-contributors">0</span>
        </div>
      </div>
    `;
  }

  // Load timeline data
  async loadTimelineData(documentId) {
    try {
      // Simulate loading timeline data
      const timelineData = await this.fetchTimelineData(documentId);
      this.timelineData.set(documentId, timelineData);

      // Render timeline
      this.renderTimeline(timelineData);

      // Update statistics
      this.updateTimelineStats(timelineData);

    } catch (error) {
      console.error('Error loading timeline data:', error);
      this.showTimelineError('Failed to load timeline data');
    }
  }

  // Fetch timeline data (simulate API call)
  async fetchTimelineData(documentId) {
    return new Promise((resolve) => {
      setTimeout(() => {
        const sampleData = {
          events: [
            {
              id: 'event_1',
              type: 'commit',
              timestamp: Date.now() - 86400000, // 1 day ago
              author: 'User 1',
              title: 'Initial legal document draft',
              description: 'Created initial structure for legal contract',
              commitHash: 'abc123',
              branch: 'main',
              changes: { additions: 145, deletions: 0, modifications: 0 }
            },
            {
              id: 'event_2',
              type: 'branch',
              timestamp: Date.now() - 43200000, // 12 hours ago
              author: 'User 2',
              title: 'Created review branch',
              description: 'Created branch for legal review process',
              branch: 'review/legal-terms',
              parentBranch: 'main'
            },
            {
              id: 'event_3',
              type: 'commit',
              timestamp: Date.now() - 21600000, // 6 hours ago
              author: 'User 2',
              title: 'Updated payment terms',
              description: 'Modified payment schedule and terms',
              commitHash: 'def456',
              branch: 'review/legal-terms',
              changes: { additions: 12, deletions: 8, modifications: 15 }
            },
            {
              id: 'event_4',
              type: 'merge',
              timestamp: Date.now() - 10800000, // 3 hours ago
              author: 'User 1',
              title: 'Merged legal review updates',
              description: 'Merged reviewed changes back to main',
              commitHash: 'ghi789',
              branch: 'main',
              sourceBranch: 'review/legal-terms',
              changes: { additions: 12, deletions: 8, modifications: 15 }
            },
            {
              id: 'event_5',
              type: 'commit',
              timestamp: Date.now() - 3600000, // 1 hour ago
              author: 'User 3',
              title: 'Added liability clauses',
              description: 'Added comprehensive liability and insurance clauses',
              commitHash: 'jkl012',
              branch: 'main',
              changes: { additions: 28, deletions: 0, modifications: 5 }
            }
          ],
          branches: ['main', 'review/legal-terms'],
          authors: ['User 1', 'User 2', 'User 3'],
          stats: {
            totalEvents: 5,
            totalCommits: 3,
            totalBranches: 2,
            totalMerges: 1,
            totalContributors: 3
          }
        };
        resolve(sampleData);
      }, 1000);
    });
  }

  // Render timeline
  renderTimeline(timelineData) {
    const viewport = document.querySelector('.legal-git-timeline-viewport');
    if (!viewport) return;

    // Clear loading state
    viewport.innerHTML = `
      <div class="legal-git-timeline-track">
        <div class="legal-git-timeline-line"></div>
        <div id="timeline-events"></div>
      </div>
    `;

    const eventsContainer = document.getElementById('timeline-events');
    if (!eventsContainer) return;

    // Sort events by timestamp (newest first)
    const sortedEvents = [...timelineData.events].sort((a, b) => b.timestamp - a.timestamp);

    // Render events
    sortedEvents.forEach((event, index) => {
      const eventElement = this.createTimelineEvent(event, index);
      eventsContainer.appendChild(eventElement);
    });

    // Populate version selectors
    this.populateVersionSelectors(timelineData);
  }

  // Create timeline event element
  createTimelineEvent(event, index) {
    const eventDiv = document.createElement('div');
    eventDiv.className = `legal-git-timeline-event ${index % 2 === 0 ? 'right' : 'left'}`;
    eventDiv.dataset.eventId = event.id;

    const markerClass = this.getEventMarkerClass(event.type);
    const tagClass = this.getEventTagClass(event.type);
    const timeAgo = this.formatTimeAgo(event.timestamp);

    eventDiv.innerHTML = `
      <div class="legal-git-timeline-event-marker ${markerClass}"></div>
      <div class="legal-git-timeline-event-content" onclick="window.timelineView.selectEvent('${event.id}')">
        <div class="legal-git-timeline-event-header">
          <div class="legal-git-timeline-event-title">${event.title}</div>
          <div class="legal-git-timeline-event-time">${timeAgo}</div>
        </div>
        <div class="legal-git-timeline-event-details">${event.description}</div>
        <div class="legal-git-timeline-event-meta">
          <span class="legal-git-timeline-event-tag ${tagClass}">${event.type}</span>
          <span class="legal-git-timeline-event-tag">by ${event.author}</span>
          <span class="legal-git-timeline-event-tag">branch: ${event.branch}</span>
        </div>
        <div class="legal-git-timeline-event-actions">
          <button class="legal-git-timeline-event-btn" onclick="event.stopPropagation(); window.timelineView.viewEventDetails('${event.id}')">
            View Details
          </button>
          ${event.type === 'commit' ? `
            <button class="legal-git-timeline-event-btn" onclick="event.stopPropagation(); window.timelineView.viewCommitDiff('${event.id}')">
              View Diff
            </button>
          ` : ''}
          <button class="legal-git-timeline-event-btn" onclick="event.stopPropagation(); window.timelineView.compareToVersion('${event.id}')">
            Compare
          </button>
        </div>
      </div>
    `;

    return eventDiv;
  }

  // Get event marker class
  getEventMarkerClass(eventType) {
    switch (eventType) {
      case 'merge':
        return 'major';
      case 'branch':
        return 'minor';
      case 'commit':
      default:
        return '';
    }
  }

  // Get event tag class
  getEventTagClass(eventType) {
    return eventType;
  }

  // Format time ago
  formatTimeAgo(timestamp) {
    const now = Date.now();
    const diffMs = now - timestamp;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 60) {
      return `${diffMins}m ago`;
    } else if (diffHours < 24) {
      return `${diffHours}h ago`;
    } else {
      return `${diffDays}d ago`;
    }
  }

  // Update timeline statistics
  updateTimelineStats(timelineData) {
    const stats = timelineData.stats;

    document.getElementById('total-events').textContent = stats.totalEvents;
    document.getElementById('total-commits').textContent = stats.totalCommits;
    document.getElementById('total-branches').textContent = stats.totalBranches;
    document.getElementById('total-merges').textContent = stats.totalMerges;
    document.getElementById('total-contributors').textContent = stats.totalContributors;

    // Populate author filter
    const authorFilter = document.getElementById('author-filter');
    if (authorFilter) {
      // Clear existing options except first
      while (authorFilter.children.length > 1) {
        authorFilter.removeChild(authorFilter.lastChild);
      }

      timelineData.authors.forEach(author => {
        const option = document.createElement('option');
        option.value = author;
        option.textContent = author;
        authorFilter.appendChild(option);
      });
    }
  }

  // Populate version selectors
  populateVersionSelectors(timelineData) {
    const selector1 = document.getElementById('version-select-1');
    const selector2 = document.getElementById('version-select-2');

    if (selector1 && selector2) {
      const commits = timelineData.events.filter(e => e.type === 'commit');

      [selector1, selector2].forEach(selector => {
        // Clear existing options except first
        while (selector.children.length > 1) {
          selector.removeChild(selector.lastChild);
        }

        commits.forEach(commit => {
          const option = document.createElement('option');
          option.value = commit.id;
          option.textContent = `${commit.title} (${this.formatTimeAgo(commit.timestamp)})`;
          selector.appendChild(option);
        });
      });
    }
  }

  // Select event
  selectEvent(eventId) {
    // Remove previous selection
    document.querySelectorAll('.legal-git-timeline-event-content.selected').forEach(el => {
      el.classList.remove('selected');
    });

    // Add selection to clicked event
    const eventElement = document.querySelector(`[data-event-id="${eventId}"] .legal-git-timeline-event-content`);
    if (eventElement) {
      eventElement.classList.add('selected');
    }

    // Update marker animation
    document.querySelectorAll('.legal-git-timeline-event-marker.active').forEach(marker => {
      marker.classList.remove('active');
    });

    const marker = document.querySelector(`[data-event-id="${eventId}"] .legal-git-timeline-event-marker`);
    if (marker) {
      marker.classList.add('active');
    }
  }

  // View event details
  viewEventDetails(eventId) {
    const timelineData = this.timelineData.get(this.currentDocumentId);
    if (!timelineData) return;

    const event = timelineData.events.find(e => e.id === eventId);
    if (!event) return;

    // Show detailed information
    alert(`Event Details:\n\nTitle: ${event.title}\nDescription: ${event.description}\nAuthor: ${event.author}\nBranch: ${event.branch}\nTime: ${new Date(event.timestamp).toLocaleString()}`);
  }

  // View commit diff
  viewCommitDiff(eventId) {
    const timelineData = this.timelineData.get(this.currentDocumentId);
    if (!timelineData) return;

    const event = timelineData.events.find(e => e.id === eventId);
    if (!event || event.type !== 'commit') return;

    // Show diff using existing diff visualizer
    if (window.diffVisualizer) {
      const mockDiff = {
        textDiff: [
          {
            type: 'add',
            lineNumber: 1,
            new: 'This is a new line added in the commit'
          },
          {
            type: 'modify',
            lineNumber: 2,
            old: 'Old version of this line',
            new: 'New version of this line'
          }
        ]
      };

      window.diffVisualizer.showDiffModal(this.currentDocumentId, mockDiff);
    }
  }

  // Compare to version
  compareToVersion(eventId) {
    const comparison = document.getElementById('timeline-comparison');
    if (comparison) {
      comparison.style.display = 'block';

      // Pre-select this version
      const selector1 = document.getElementById('version-select-1');
      if (selector1) {
        selector1.value = eventId;
      }
    }
  }

  // Perform comparison
  performComparison() {
    const selector1 = document.getElementById('version-select-1');
    const selector2 = document.getElementById('version-select-2');

    if (!selector1 || !selector2) return;

    const version1 = selector1.value;
    const version2 = selector2.value;

    if (version1 === 'Select version...' || version2 === 'Select version...') {
      alert('Please select two versions to compare');
      return;
    }

    if (version1 === version2) {
      alert('Please select different versions to compare');
      return;
    }

    // Show comparison result
    const resultDiv = document.getElementById('comparison-result');
    if (resultDiv) {
      resultDiv.innerHTML = `
        <div style="padding: 20px; border: 1px solid #dadce0; border-radius: 8px; background: #f8f9fa;">
          <h4>Comparison Result</h4>
          <p>Comparing versions ${version1} and ${version2}...</p>
          <p style="color: #5f6368;">This would show the detailed diff between the selected versions.</p>
        </div>
      `;
    }
  }

  // Zoom in
  zoomIn() {
    // Implement zoom functionality
    console.log('Zooming in...');
  }

  // Zoom out
  zoomOut() {
    // Implement zoom functionality
    console.log('Zooming out...');
  }

  // Show timeline error
  showTimelineError(message) {
    const viewport = document.querySelector('.legal-git-timeline-viewport');
    if (viewport) {
      viewport.innerHTML = `
        <div class="legal-git-timeline-empty">
          <div class="legal-git-timeline-empty-icon">⚠️</div>
          <div>Error: ${message}</div>
        </div>
      `;
    }
  }

  // Get document title
  getDocumentTitle(documentId) {
    // Try to get from cached content
    if (this.documentConverter) {
      const cached = this.documentConverter.getCachedContent(documentId);
      if (cached?.content?.title) {
        return cached.content.title;
      }
    }

    return 'Document';
  }

  // Update timeline data
  updateTimelineData(data) {
    if (data.documentId && this.timelineData.has(data.documentId)) {
      const timelineData = this.timelineData.get(data.documentId);

      // Add new event
      timelineData.events.push(data.event);

      // Update stats
      timelineData.stats.totalEvents++;
      if (data.event.type === 'commit') {
        timelineData.stats.totalCommits++;
      }

      // Re-render if this timeline is currently open
      if (this.timelineViewOpen && this.currentDocumentId === data.documentId) {
        this.renderTimeline(timelineData);
        this.updateTimelineStats(timelineData);
      }
    }
  }

  // Setup timeline modal events
  setupTimelineModalEvents(modal) {
    // View switching
    const viewButtons = modal.querySelectorAll('[data-view]');
    viewButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        viewButtons.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        const view = btn.dataset.view;
        this.switchTimelineView(view);
      });
    });

    // Filter changes
    const filters = modal.querySelectorAll('.legal-git-timeline-filter-select');
    filters.forEach(filter => {
      filter.addEventListener('change', () => {
        this.applyTimelineFilters();
      });
    });

    // Keyboard navigation
    modal.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        this.closeTimelineModal();
      }
    });

    // Make globally available
    window.timelineView = this;
  }

  // Switch timeline view
  switchTimelineView(view) {
    console.log(`Switching to ${view} view`);
    // Implement different view modes
  }

  // Apply timeline filters
  applyTimelineFilters() {
    const timeRange = document.getElementById('time-range-filter')?.value;
    const eventType = document.getElementById('event-type-filter')?.value;
    const author = document.getElementById('author-filter')?.value;

    console.log('Applying filters:', { timeRange, eventType, author });

    // Re-render timeline with filters
    if (this.currentDocumentId) {
      const timelineData = this.timelineData.get(this.currentDocumentId);
      if (timelineData) {
        this.renderTimeline(timelineData);
      }
    }
  }

  // Close timeline modal
  closeTimelineModal() {
    const modal = document.getElementById('legal-git-timeline-modal');
    if (modal) {
      modal.remove();
      this.timelineViewOpen = false;
      this.currentDocumentId = null;
    }
  }
}

// Export for use in other scripts
window.TimelineView = TimelineView;
