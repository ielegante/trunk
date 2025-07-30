// Legal Git Chrome Extension - Template Gallery Interface
// Handles template browsing, preview, fork/clone workflows, and template management

class TemplateGallery {
  constructor(gitOpsManager, wordDocumentHandler) {
    this.gitOpsManager = gitOpsManager;
    this.wordDocumentHandler = wordDocumentHandler;
    this.templates = new Map();
    this.categories = new Map();
    this.favoriteTemplates = new Set();
    this.templateHistory = new Map();
    this.galleryViewOpen = false;
    this.selectedTemplate = null;
    this.init();
  }

  init() {
    this.setupTemplateEventListeners();
    this.injectTemplateStyles();
    this.loadTemplateData();
  }

  // Setup event listeners for template gallery
  setupTemplateEventListeners() {
    window.addEventListener('legalGitShowTemplateGallery', (event) => {
      this.showTemplateGallery(event.detail);
    });

    window.addEventListener('templatePreviewRequested', (event) => {
      this.showTemplatePreview(event.detail.templateId);
    });

    window.addEventListener('templateForkRequested', (event) => {
      this.forkTemplate(event.detail.templateId);
    });

    window.addEventListener('templateCloneRequested', (event) => {
      this.cloneTemplate(event.detail.templateId);
    });
  }

  // Inject CSS styles for template gallery
  injectTemplateStyles() {
    const styleId = 'legal-git-template-styles';
    if (document.getElementById(styleId)) return;

    const style = document.createElement('style');
    style.id = styleId;
    style.textContent = `
      .legal-git-template-container {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.85);
        z-index: 26000;
        display: flex;
        align-items: center;
        justify-content: center;
        font-family: 'Google Sans', Roboto, Arial, sans-serif;
      }

      .legal-git-template-modal {
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

      .legal-git-template-header {
        padding: 20px 24px;
        border-bottom: 2px solid #673ab7;
        background: linear-gradient(135deg, #f3e5f5, #e1bee7);
        display: flex;
        justify-content: space-between;
        align-items: center;
      }

      .legal-git-template-title {
        font-size: 20px;
        font-weight: 600;
        color: #673ab7;
        display: flex;
        align-items: center;
        gap: 12px;
      }

      .legal-git-template-close {
        background: none;
        border: none;
        font-size: 28px;
        cursor: pointer;
        color: #5f6368;
        padding: 8px;
        border-radius: 6px;
        transition: all 0.2s;
      }

      .legal-git-template-close:hover {
        background: #f1f3f4;
        transform: scale(1.1);
      }

      .legal-git-template-content {
        flex: 1;
        display: flex;
        overflow: hidden;
      }

      .legal-git-template-sidebar {
        width: 280px;
        background: #f8f9fa;
        border-right: 1px solid #e0e0e0;
        overflow-y: auto;
        padding: 20px;
      }

      .legal-git-template-main {
        flex: 1;
        overflow-y: auto;
        padding: 20px 24px;
      }

      .legal-git-template-search {
        background: white;
        border: 1px solid #dadce0;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 20px;
      }

      .legal-git-template-search h4 {
        margin: 0 0 12px 0;
        font-size: 14px;
        font-weight: 600;
        color: #1f1f1f;
      }

      .legal-git-search-input {
        width: 100%;
        padding: 10px 12px;
        border: 1px solid #dadce0;
        border-radius: 6px;
        font-size: 14px;
        margin-bottom: 12px;
      }

      .legal-git-search-filters {
        display: flex;
        flex-direction: column;
        gap: 8px;
      }

      .legal-git-filter-select {
        padding: 8px 12px;
        border: 1px solid #dadce0;
        border-radius: 4px;
        font-size: 13px;
        background: white;
      }

      .legal-git-template-categories {
        background: white;
        border: 1px solid #dadce0;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 20px;
      }

      .legal-git-template-categories h4 {
        margin: 0 0 12px 0;
        font-size: 14px;
        font-weight: 600;
        color: #1f1f1f;
      }

      .legal-git-category-list {
        display: flex;
        flex-direction: column;
        gap: 6px;
      }

      .legal-git-category-item {
        padding: 8px 12px;
        background: #f8f9fa;
        border: 1px solid transparent;
        border-radius: 4px;
        cursor: pointer;
        transition: all 0.2s;
        font-size: 13px;
        display: flex;
        justify-content: space-between;
        align-items: center;
      }

      .legal-git-category-item:hover {
        background: #e9ecef;
        border-color: #673ab7;
      }

      .legal-git-category-item.active {
        background: #e8eaf6;
        border-color: #673ab7;
        color: #673ab7;
        font-weight: 500;
      }

      .legal-git-category-count {
        font-size: 11px;
        background: #673ab7;
        color: white;
        padding: 2px 6px;
        border-radius: 10px;
      }

      .legal-git-template-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
        gap: 20px;
        margin-bottom: 20px;
      }

      .legal-git-template-card {
        background: white;
        border: 1px solid #dadce0;
        border-radius: 8px;
        overflow: hidden;
        transition: all 0.2s;
        cursor: pointer;
      }

      .legal-git-template-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 16px rgba(0,0,0,0.1);
        border-color: #673ab7;
      }

      .legal-git-template-thumbnail {
        height: 180px;
        background: linear-gradient(135deg, #f3e5f5, #e1bee7);
        position: relative;
        display: flex;
        align-items: center;
        justify-content: center;
        overflow: hidden;
      }

      .legal-git-template-icon {
        font-size: 48px;
        color: #673ab7;
        opacity: 0.8;
      }

      .legal-git-template-preview-btn {
        position: absolute;
        top: 8px;
        right: 8px;
        background: rgba(255, 255, 255, 0.9);
        border: none;
        border-radius: 50%;
        width: 32px;
        height: 32px;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        transition: all 0.2s;
        opacity: 0;
      }

      .legal-git-template-card:hover .legal-git-template-preview-btn {
        opacity: 1;
      }

      .legal-git-template-preview-btn:hover {
        background: white;
        transform: scale(1.1);
      }

      .legal-git-template-info {
        padding: 16px;
      }

      .legal-git-template-name {
        font-size: 16px;
        font-weight: 600;
        color: #1f1f1f;
        margin-bottom: 6px;
        line-height: 1.3;
      }

      .legal-git-template-description {
        font-size: 13px;
        color: #5f6368;
        line-height: 1.4;
        margin-bottom: 12px;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
      }

      .legal-git-template-meta {
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 12px;
        color: #5f6368;
        margin-bottom: 12px;
      }

      .legal-git-template-tags {
        display: flex;
        gap: 4px;
        flex-wrap: wrap;
        margin-bottom: 12px;
      }

      .legal-git-template-tag {
        background: #e8eaf6;
        color: #673ab7;
        padding: 2px 6px;
        border-radius: 10px;
        font-size: 11px;
        font-weight: 500;
      }

      .legal-git-template-actions {
        display: flex;
        gap: 8px;
      }

      .legal-git-template-btn {
        flex: 1;
        padding: 8px 12px;
        border: 1px solid #dadce0;
        border-radius: 4px;
        font-size: 12px;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s;
        text-align: center;
      }

      .legal-git-template-btn.primary {
        background: #673ab7;
        color: white;
        border-color: #673ab7;
      }

      .legal-git-template-btn.primary:hover {
        background: #5e35b1;
      }

      .legal-git-template-btn.secondary {
        background: white;
        color: #673ab7;
        border-color: #673ab7;
      }

      .legal-git-template-btn.secondary:hover {
        background: #f3e5f5;
      }

      .legal-git-template-preview {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.9);
        z-index: 27000;
        display: flex;
        align-items: center;
        justify-content: center;
        opacity: 0;
        visibility: hidden;
        transition: all 0.3s;
      }

      .legal-git-template-preview.active {
        opacity: 1;
        visibility: visible;
      }

      .legal-git-template-preview-modal {
        background: white;
        border-radius: 12px;
        width: 90vw;
        height: 85vh;
        max-width: 1400px;
        display: flex;
        flex-direction: column;
        overflow: hidden;
        transform: scale(0.9);
        transition: transform 0.3s;
      }

      .legal-git-template-preview.active .legal-git-template-preview-modal {
        transform: scale(1);
      }

      .legal-git-template-preview-header {
        padding: 20px 24px;
        border-bottom: 1px solid #e0e0e0;
        background: #f8f9fa;
        display: flex;
        justify-content: space-between;
        align-items: center;
      }

      .legal-git-template-preview-title {
        font-size: 18px;
        font-weight: 600;
        color: #1f1f1f;
      }

      .legal-git-template-preview-close {
        background: none;
        border: none;
        font-size: 24px;
        cursor: pointer;
        color: #5f6368;
        padding: 4px;
        border-radius: 4px;
        transition: background 0.2s;
      }

      .legal-git-template-preview-close:hover {
        background: #f1f3f4;
      }

      .legal-git-template-preview-content {
        flex: 1;
        display: flex;
        overflow: hidden;
      }

      .legal-git-template-preview-sidebar {
        width: 300px;
        background: #f8f9fa;
        border-right: 1px solid #e0e0e0;
        overflow-y: auto;
        padding: 20px;
      }

      .legal-git-template-preview-main {
        flex: 1;
        overflow-y: auto;
        padding: 20px;
        background: white;
      }

      .legal-git-template-document {
        background: white;
        border: 1px solid #dadce0;
        border-radius: 8px;
        padding: 40px;
        font-family: 'Times New Roman', serif;
        line-height: 1.6;
        max-width: 100%;
        margin: 0 auto;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
      }

      .legal-git-template-stats {
        background: white;
        border: 1px solid #dadce0;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 16px;
      }

      .legal-git-template-stats h4 {
        margin: 0 0 12px 0;
        font-size: 14px;
        font-weight: 600;
        color: #1f1f1f;
      }

      .legal-git-stat-item {
        display: flex;
        justify-content: space-between;
        padding: 4px 0;
        font-size: 13px;
        border-bottom: 1px solid #f0f0f0;
      }

      .legal-git-stat-item:last-child {
        border-bottom: none;
      }

      .legal-git-stat-label {
        color: #5f6368;
      }

      .legal-git-stat-value {
        font-weight: 500;
        color: #1f1f1f;
      }

      .legal-git-template-workflow {
        background: white;
        border: 1px solid #dadce0;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 16px;
      }

      .legal-git-template-workflow h4 {
        margin: 0 0 12px 0;
        font-size: 14px;
        font-weight: 600;
        color: #1f1f1f;
      }

      .legal-git-workflow-option {
        padding: 12px;
        border: 2px solid #dadce0;
        border-radius: 6px;
        margin-bottom: 8px;
        cursor: pointer;
        transition: all 0.2s;
      }

      .legal-git-workflow-option:hover {
        border-color: #673ab7;
        background: #f3e5f5;
      }

      .legal-git-workflow-option.selected {
        border-color: #673ab7;
        background: #e8eaf6;
      }

      .legal-git-workflow-title {
        font-size: 13px;
        font-weight: 600;
        color: #1f1f1f;
        margin-bottom: 4px;
      }

      .legal-git-workflow-description {
        font-size: 11px;
        color: #5f6368;
        line-height: 1.3;
      }

      .legal-git-template-footer {
        padding: 20px 24px;
        border-top: 1px solid #e0e0e0;
        background: #f8f9fa;
        display: flex;
        justify-content: space-between;
        align-items: center;
      }

      .legal-git-template-footer-info {
        font-size: 13px;
        color: #5f6368;
      }

      .legal-git-template-footer-actions {
        display: flex;
        gap: 12px;
      }

      .legal-git-template-footer-btn {
        padding: 10px 20px;
        border: none;
        border-radius: 6px;
        font-size: 14px;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s;
      }

      .legal-git-template-footer-btn.primary {
        background: #673ab7;
        color: white;
      }

      .legal-git-template-footer-btn.secondary {
        background: #f8f9fa;
        color: #5f6368;
        border: 1px solid #dadce0;
      }

      .legal-git-template-footer-btn:hover {
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
      }

      .legal-git-template-footer-btn:disabled {
        opacity: 0.5;
        cursor: not-allowed;
        transform: none;
        box-shadow: none;
      }

      .legal-git-template-favorites {
        background: white;
        border: 1px solid #dadce0;
        border-radius: 8px;
        padding: 16px;
      }

      .legal-git-template-favorites h4 {
        margin: 0 0 12px 0;
        font-size: 14px;
        font-weight: 600;
        color: #1f1f1f;
      }

      .legal-git-favorite-item {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 6px 0;
        font-size: 12px;
        border-bottom: 1px solid #f0f0f0;
        cursor: pointer;
      }

      .legal-git-favorite-item:last-child {
        border-bottom: none;
      }

      .legal-git-favorite-item:hover {
        color: #673ab7;
      }

      @keyframes templateCardAppear {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
      }

      .legal-git-template-card {
        animation: templateCardAppear 0.3s ease-out;
      }

      @keyframes favoriteAdd {
        0% { transform: scale(1); }
        50% { transform: scale(1.2); }
        100% { transform: scale(1); }
      }

      .legal-git-favorite-added {
        animation: favoriteAdd 0.3s ease-out;
      }
    `;

    document.head.appendChild(style);
  }

  // Load template data
  async loadTemplateData() {
    try {
      // Load templates from various sources
      await this.loadBuiltInTemplates();
      await this.loadUserTemplates();
      await this.loadSharedTemplates();

      console.log('Template data loaded successfully');
    } catch (error) {
      console.error('Error loading template data:', error);
    }
  }

  // Load built-in legal templates
  async loadBuiltInTemplates() {
    const builtInTemplates = [
      {
        id: 'contract_nda',
        name: 'Non-Disclosure Agreement',
        description: 'Standard NDA template for protecting confidential information in business relationships.',
        category: 'contracts',
        type: 'built-in',
        author: 'Legal Git',
        tags: ['NDA', 'confidentiality', 'business'],
        difficulty: 'beginner',
        estimatedTime: '15 min',
        downloads: 2847,
        rating: 4.8,
        lastUpdated: Date.now() - 86400000 * 7,
        content: this.generateNDATemplate(),
        metadata: {
          wordCount: 1250,
          clauses: 12,
          jurisdictions: ['US', 'CA', 'UK'],
          industry: 'general'
        }
      },
      {
        id: 'contract_service',
        name: 'Service Agreement',
        description: 'Professional service agreement template for consultants and service providers.',
        category: 'contracts',
        type: 'built-in',
        author: 'Legal Git',
        tags: ['service', 'consulting', 'professional'],
        difficulty: 'intermediate',
        estimatedTime: '25 min',
        downloads: 1923,
        rating: 4.7,
        lastUpdated: Date.now() - 86400000 * 3,
        content: this.generateServiceAgreementTemplate(),
        metadata: {
          wordCount: 2100,
          clauses: 18,
          jurisdictions: ['US', 'CA'],
          industry: 'professional-services'
        }
      },
      {
        id: 'letter_demand',
        name: 'Demand Letter',
        description: 'Professional demand letter template for payment and compliance requests.',
        category: 'letters',
        type: 'built-in',
        author: 'Legal Git',
        tags: ['demand', 'payment', 'compliance'],
        difficulty: 'beginner',
        estimatedTime: '10 min',
        downloads: 3421,
        rating: 4.9,
        lastUpdated: Date.now() - 86400000 * 2,
        content: this.generateDemandLetterTemplate(),
        metadata: {
          wordCount: 850,
          clauses: 8,
          jurisdictions: ['US'],
          industry: 'general'
        }
      },
      {
        id: 'brief_motion',
        name: 'Motion Brief',
        description: 'Legal motion brief template with proper formatting and structure.',
        category: 'briefs',
        type: 'built-in',
        author: 'Legal Git',
        tags: ['motion', 'brief', 'court'],
        difficulty: 'advanced',
        estimatedTime: '45 min',
        downloads: 1567,
        rating: 4.6,
        lastUpdated: Date.now() - 86400000 * 5,
        content: this.generateMotionBriefTemplate(),
        metadata: {
          wordCount: 3200,
          clauses: 25,
          jurisdictions: ['US'],
          industry: 'litigation'
        }
      },
      {
        id: 'policy_privacy',
        name: 'Privacy Policy',
        description: 'GDPR and CCPA compliant privacy policy template for websites and applications.',
        category: 'policies',
        type: 'built-in',
        author: 'Legal Git',
        tags: ['privacy', 'GDPR', 'CCPA', 'compliance'],
        difficulty: 'intermediate',
        estimatedTime: '30 min',
        downloads: 4156,
        rating: 4.8,
        lastUpdated: Date.now() - 86400000 * 1,
        content: this.generatePrivacyPolicyTemplate(),
        metadata: {
          wordCount: 2800,
          clauses: 22,
          jurisdictions: ['US', 'EU', 'CA'],
          industry: 'technology'
        }
      }
    ];

    builtInTemplates.forEach(template => {
      this.templates.set(template.id, template);
    });

    // Initialize categories
    this.initializeCategories();
  }

  // Load user templates
  async loadUserTemplates() {
    // Simulate loading user's custom templates
    const userTemplates = [
      {
        id: 'user_contract_custom',
        name: 'Custom Employment Contract',
        description: 'Customized employment contract template for tech startups.',
        category: 'contracts',
        type: 'user',
        author: 'Current User',
        tags: ['employment', 'startup', 'tech'],
        difficulty: 'intermediate',
        estimatedTime: '35 min',
        downloads: 0,
        rating: 0,
        lastUpdated: Date.now() - 86400000 * 10,
        content: this.generateEmploymentContractTemplate(),
        metadata: {
          wordCount: 2400,
          clauses: 20,
          jurisdictions: ['US'],
          industry: 'technology'
        }
      }
    ];

    userTemplates.forEach(template => {
      this.templates.set(template.id, template);
    });
  }

  // Load shared templates
  async loadSharedTemplates() {
    // Simulate loading shared community templates
    const sharedTemplates = [
      {
        id: 'shared_lease_residential',
        name: 'Residential Lease Agreement',
        description: 'Comprehensive residential lease agreement with tenant protection clauses.',
        category: 'real-estate',
        type: 'shared',
        author: 'Community Contributor',
        tags: ['lease', 'residential', 'rental'],
        difficulty: 'intermediate',
        estimatedTime: '40 min',
        downloads: 2156,
        rating: 4.5,
        lastUpdated: Date.now() - 86400000 * 12,
        content: this.generateLeaseAgreementTemplate(),
        metadata: {
          wordCount: 3100,
          clauses: 28,
          jurisdictions: ['US'],
          industry: 'real-estate'
        }
      }
    ];

    sharedTemplates.forEach(template => {
      this.templates.set(template.id, template);
    });
  }

  // Initialize template categories
  initializeCategories() {
    const categoryData = new Map([
      ['all', { name: 'All Templates', count: this.templates.size, icon: '📄' }],
      ['contracts', { name: 'Contracts', count: 0, icon: '📋' }],
      ['letters', { name: 'Letters', count: 0, icon: '✉️' }],
      ['briefs', { name: 'Legal Briefs', count: 0, icon: '⚖️' }],
      ['policies', { name: 'Policies', count: 0, icon: '📝' }],
      ['real-estate', { name: 'Real Estate', count: 0, icon: '🏠' }],
      ['employment', { name: 'Employment', count: 0, icon: '👔' }],
      ['intellectual-property', { name: 'IP & Patents', count: 0, icon: '💡' }]
    ]);

    // Count templates per category
    this.templates.forEach(template => {
      if (categoryData.has(template.category)) {
        categoryData.get(template.category).count++;
      }
    });

    this.categories = categoryData;
  }

  // Show template gallery
  showTemplateGallery(options = {}) {
    if (this.galleryViewOpen) {
      this.closeTemplateGallery();
    }

    const modal = this.createTemplateGalleryModal(options);
    document.body.appendChild(modal);
    this.galleryViewOpen = true;

    // Focus trap
    setTimeout(() => {
      const searchInput = modal.querySelector('.legal-git-search-input');
      if (searchInput) searchInput.focus();
    }, 100);
  }

  // Create template gallery modal
  createTemplateGalleryModal(options) {
    const modal = document.createElement('div');
    modal.className = 'legal-git-template-container';
    modal.id = 'legal-git-template-gallery';

    modal.innerHTML = `
      <div class="legal-git-template-modal">
        <div class="legal-git-template-header">
          <div class="legal-git-template-title">
            <span>📚</span>
            <span>Legal Template Gallery</span>
          </div>
          <button class="legal-git-template-close" onclick="window.templateGallery.closeTemplateGallery()">×</button>
        </div>

        <div class="legal-git-template-content">
          <div class="legal-git-template-sidebar">
            ${this.generateTemplateSearch()}
            ${this.generateTemplateCategories()}
            ${this.generateTemplateFavorites()}
          </div>

          <div class="legal-git-template-main">
            <div class="legal-git-template-grid" id="template-grid">
              ${this.generateTemplateGrid()}
            </div>
          </div>
        </div>

        <div class="legal-git-template-footer">
          <div class="legal-git-template-footer-info">
            ${this.templates.size} templates available
          </div>
          <div class="legal-git-template-footer-actions">
            <button class="legal-git-template-footer-btn secondary" onclick="window.templateGallery.uploadTemplate()">
              Upload Template
            </button>
            <button class="legal-git-template-footer-btn secondary" onclick="window.templateGallery.createTemplate()">
              Create New
            </button>
          </div>
        </div>
      </div>
    `;

    this.setupTemplateGalleryEvents(modal);
    return modal;
  }

  // Generate template search interface
  generateTemplateSearch() {
    return `
      <div class="legal-git-template-search">
        <h4>🔍 Search Templates</h4>
        <input type="text" class="legal-git-search-input" placeholder="Search templates..." onkeyup="window.templateGallery.filterTemplates()">
        <div class="legal-git-search-filters">
          <select class="legal-git-filter-select" onchange="window.templateGallery.filterTemplates()">
            <option value="">All Difficulties</option>
            <option value="beginner">Beginner</option>
            <option value="intermediate">Intermediate</option>
            <option value="advanced">Advanced</option>
          </select>
          <select class="legal-git-filter-select" onchange="window.templateGallery.filterTemplates()">
            <option value="">All Authors</option>
            <option value="built-in">Legal Git</option>
            <option value="user">My Templates</option>
            <option value="shared">Community</option>
          </select>
        </div>
      </div>
    `;
  }

  // Generate template categories
  generateTemplateCategories() {
    let categoriesHtml = `
      <div class="legal-git-template-categories">
        <h4>📂 Categories</h4>
        <div class="legal-git-category-list">
    `;

    this.categories.forEach((category, key) => {
      const activeClass = key === 'all' ? 'active' : '';
      categoriesHtml += `
        <div class="legal-git-category-item ${activeClass}" data-category="${key}" onclick="window.templateGallery.selectCategory('${key}')">
          <span>${category.icon} ${category.name}</span>
          <span class="legal-git-category-count">${category.count}</span>
        </div>
      `;
    });

    categoriesHtml += '</div></div>';
    return categoriesHtml;
  }

  // Generate template favorites
  generateTemplateFavorites() {
    return `
      <div class="legal-git-template-favorites">
        <h4>⭐ Favorites</h4>
        ${Array.from(this.favoriteTemplates).slice(0, 5).map(templateId => {
          const template = this.templates.get(templateId);
          return template ? `
            <div class="legal-git-favorite-item" onclick="window.templateGallery.showTemplatePreview('${templateId}')">
              <span>📄</span>
              <span>${template.name}</span>
            </div>
          ` : '';
        }).join('')}
        ${this.favoriteTemplates.size === 0 ? '<div style="font-size: 12px; color: #999; text-align: center; padding: 20px;">No favorites yet</div>' : ''}
      </div>
    `;
  }

  // Generate template grid
  generateTemplateGrid(filteredTemplates = null) {
    const templatesToShow = filteredTemplates || Array.from(this.templates.values());

    return templatesToShow.map(template => `
      <div class="legal-git-template-card" data-template-id="${template.id}">
        <div class="legal-git-template-thumbnail">
          <div class="legal-git-template-icon">${this.getCategoryIcon(template.category)}</div>
          <button class="legal-git-template-preview-btn" onclick="event.stopPropagation(); window.templateGallery.showTemplatePreview('${template.id}')">
            👁️
          </button>
        </div>

        <div class="legal-git-template-info">
          <div class="legal-git-template-name">${template.name}</div>
          <div class="legal-git-template-description">${template.description}</div>

          <div class="legal-git-template-meta">
            <span>By ${template.author}</span>
            <span>${this.formatTimeAgo(template.lastUpdated)}</span>
          </div>

          <div class="legal-git-template-tags">
            ${template.tags.slice(0, 3).map(tag => `
              <span class="legal-git-template-tag">${tag}</span>
            `).join('')}
          </div>

          <div class="legal-git-template-actions">
            <button class="legal-git-template-btn primary" onclick="window.templateGallery.useTemplate('${template.id}')">
              Use Template
            </button>
            <button class="legal-git-template-btn secondary" onclick="window.templateGallery.toggleFavorite('${template.id}')">
              ${this.favoriteTemplates.has(template.id) ? '💖' : '🤍'}
            </button>
          </div>
        </div>
      </div>
    `).join('');
  }

  // Show template preview
  showTemplatePreview(templateId) {
    const template = this.templates.get(templateId);
    if (!template) return;

    this.selectedTemplate = template;
    const preview = this.createTemplatePreviewModal(template);
    document.body.appendChild(preview);

    // Trigger preview animation
    setTimeout(() => {
      preview.classList.add('active');
    }, 10);
  }

  // Create template preview modal
  createTemplatePreviewModal(template) {
    const preview = document.createElement('div');
    preview.className = 'legal-git-template-preview';
    preview.id = 'legal-git-template-preview';

    preview.innerHTML = `
      <div class="legal-git-template-preview-modal">
        <div class="legal-git-template-preview-header">
          <div class="legal-git-template-preview-title">${template.name}</div>
          <button class="legal-git-template-preview-close" onclick="window.templateGallery.closeTemplatePreview()">×</button>
        </div>

        <div class="legal-git-template-preview-content">
          <div class="legal-git-template-preview-sidebar">
            ${this.generateTemplateStats(template)}
            ${this.generateTemplateWorkflow(template)}
          </div>

          <div class="legal-git-template-preview-main">
            <div class="legal-git-template-document">
              ${template.content}
            </div>
          </div>
        </div>

        <div class="legal-git-template-footer">
          <div class="legal-git-template-footer-info">
            Preview mode - Document will be customizable after selection
          </div>
          <div class="legal-git-template-footer-actions">
            <button class="legal-git-template-footer-btn secondary" onclick="window.templateGallery.closeTemplatePreview()">
              Close
            </button>
            <button class="legal-git-template-footer-btn primary" onclick="window.templateGallery.useSelectedTemplate()">
              Use This Template
            </button>
          </div>
        </div>
      </div>
    `;

    this.setupTemplatePreviewEvents(preview);
    return preview;
  }

  // Generate template statistics
  generateTemplateStats(template) {
    return `
      <div class="legal-git-template-stats">
        <h4>📊 Template Stats</h4>
        <div class="legal-git-stat-item">
          <span class="legal-git-stat-label">Word Count:</span>
          <span class="legal-git-stat-value">${template.metadata.wordCount.toLocaleString()}</span>
        </div>
        <div class="legal-git-stat-item">
          <span class="legal-git-stat-label">Clauses:</span>
          <span class="legal-git-stat-value">${template.metadata.clauses}</span>
        </div>
        <div class="legal-git-stat-item">
          <span class="legal-git-stat-label">Est. Time:</span>
          <span class="legal-git-stat-value">${template.estimatedTime}</span>
        </div>
        <div class="legal-git-stat-item">
          <span class="legal-git-stat-label">Difficulty:</span>
          <span class="legal-git-stat-value">${template.difficulty}</span>
        </div>
        <div class="legal-git-stat-item">
          <span class="legal-git-stat-label">Downloads:</span>
          <span class="legal-git-stat-value">${template.downloads.toLocaleString()}</span>
        </div>
        <div class="legal-git-stat-item">
          <span class="legal-git-stat-label">Rating:</span>
          <span class="legal-git-stat-value">${template.rating}/5 ⭐</span>
        </div>
      </div>
    `;
  }

  // Generate template workflow options
  generateTemplateWorkflow(template) {
    return `
      <div class="legal-git-template-workflow">
        <h4>🔄 Workflow Options</h4>

        <div class="legal-git-workflow-option selected" data-workflow="fork">
          <div class="legal-git-workflow-title">🍴 Fork Template</div>
          <div class="legal-git-workflow-description">
            Create your own copy that you can modify and track changes
          </div>
        </div>

        <div class="legal-git-workflow-option" data-workflow="clone">
          <div class="legal-git-workflow-title">📋 Clone Template</div>
          <div class="legal-git-workflow-description">
            Make a direct copy without version tracking (quick start)
          </div>
        </div>

        <div class="legal-git-workflow-option" data-workflow="customize">
          <div class="legal-git-workflow-title">✏️ Customize First</div>
          <div class="legal-git-workflow-description">
            Fill in template fields before creating your document
          </div>
        </div>
      </div>
    `;
  }

  // Filter templates based on search and filters
  filterTemplates() {
    const searchInput = document.querySelector('.legal-git-search-input');
    const difficultyFilter = document.querySelectorAll('.legal-git-filter-select')[0];
    const authorFilter = document.querySelectorAll('.legal-git-filter-select')[1];
    const activeCategory = document.querySelector('.legal-git-category-item.active')?.dataset.category || 'all';

    const searchTerm = searchInput?.value.toLowerCase() || '';
    const difficultyValue = difficultyFilter?.value || '';
    const authorValue = authorFilter?.value || '';

    let filteredTemplates = Array.from(this.templates.values()).filter(template => {
      // Category filter
      if (activeCategory !== 'all' && template.category !== activeCategory) {
        return false;
      }

      // Search filter
      if (searchTerm && !template.name.toLowerCase().includes(searchTerm) &&
          !template.description.toLowerCase().includes(searchTerm) &&
          !template.tags.some(tag => tag.toLowerCase().includes(searchTerm))) {
        return false;
      }

      // Difficulty filter
      if (difficultyValue && template.difficulty !== difficultyValue) {
        return false;
      }

      // Author filter
      if (authorValue && template.type !== authorValue) {
        return false;
      }

      return true;
    });

    const gridContainer = document.getElementById('template-grid');
    if (gridContainer) {
      gridContainer.innerHTML = this.generateTemplateGrid(filteredTemplates);
    }
  }

  // Select category
  selectCategory(categoryKey) {
    // Update active category
    document.querySelectorAll('.legal-git-category-item').forEach(item => {
      item.classList.remove('active');
    });
    document.querySelector(`[data-category="${categoryKey}"]`)?.classList.add('active');

    // Filter templates
    this.filterTemplates();
  }

  // Toggle template favorite
  toggleFavorite(templateId) {
    if (this.favoriteTemplates.has(templateId)) {
      this.favoriteTemplates.delete(templateId);
    } else {
      this.favoriteTemplates.add(templateId);
    }

    // Update UI
    const card = document.querySelector(`[data-template-id="${templateId}"]`);
    const favoriteBtn = card?.querySelector('.legal-git-template-btn.secondary');
    if (favoriteBtn) {
      favoriteBtn.textContent = this.favoriteTemplates.has(templateId) ? '💖' : '🤍';
      favoriteBtn.classList.add('legal-git-favorite-added');
      setTimeout(() => {
        favoriteBtn.classList.remove('legal-git-favorite-added');
      }, 300);
    }

    // Refresh favorites sidebar
    const favoritesContainer = document.querySelector('.legal-git-template-favorites');
    if (favoritesContainer) {
      favoritesContainer.innerHTML = this.generateTemplateFavorites().replace(/.*<h4>.*?<\/h4>/, '<h4>⭐ Favorites</h4>');
    }
  }

  // Use template
  useTemplate(templateId) {
    const template = this.templates.get(templateId);
    if (!template) return;

    this.selectedTemplate = template;
    this.showTemplatePreview(templateId);
  }

  // Use selected template
  useSelectedTemplate() {
    if (!this.selectedTemplate) return;

    const workflowOption = document.querySelector('.legal-git-workflow-option.selected')?.dataset.workflow;

    switch (workflowOption) {
      case 'fork':
        this.forkTemplate(this.selectedTemplate.id);
        break;
      case 'clone':
        this.cloneTemplate(this.selectedTemplate.id);
        break;
      case 'customize':
        this.customizeTemplate(this.selectedTemplate.id);
        break;
      default:
        this.forkTemplate(this.selectedTemplate.id);
    }
  }

  // Fork template (with version control)
  async forkTemplate(templateId) {
    const template = this.templates.get(templateId);
    if (!template) return;

    try {
      console.log('Forking template:', template.name);

      // Create forked version with git tracking
      const forkedTemplate = {
        ...template,
        id: `fork_${templateId}_${Date.now()}`,
        type: 'user',
        author: 'Current User',
        originalTemplate: templateId,
        forkedAt: Date.now()
      };

      // Add to user templates
      this.templates.set(forkedTemplate.id, forkedTemplate);

      // Initialize git repository for the forked template
      if (this.gitOpsManager) {
        await this.gitOpsManager.initRepository({
          fileId: forkedTemplate.id,
          fileName: forkedTemplate.name,
          pageType: 'template',
          templateData: forkedTemplate
        });
      }

      this.showTemplateNotification(`Template "${template.name}" forked successfully! You can now edit and track changes.`, 'success');
      this.closeTemplatePreview();
      this.closeTemplateGallery();

      // Open the forked template for editing
      this.openTemplateForEditing(forkedTemplate.id);

    } catch (error) {
      console.error('Error forking template:', error);
      this.showTemplateNotification('Error forking template: ' + error.message, 'error');
    }
  }

  // Clone template (without version control)
  async cloneTemplate(templateId) {
    const template = this.templates.get(templateId);
    if (!template) return;

    try {
      console.log('Cloning template:', template.name);

      // Create a direct copy
      const clonedTemplate = {
        ...template,
        id: `clone_${templateId}_${Date.now()}`,
        type: 'user',
        author: 'Current User',
        originalTemplate: templateId,
        clonedAt: Date.now()
      };

      this.showTemplateNotification(`Template "${template.name}" cloned successfully!`, 'success');
      this.closeTemplatePreview();
      this.closeTemplateGallery();

      // Open the cloned template directly (e.g., in Google Docs or Word)
      this.openTemplateInEditor(clonedTemplate);

    } catch (error) {
      console.error('Error cloning template:', error);
      this.showTemplateNotification('Error cloning template: ' + error.message, 'error');
    }
  }

  // Customize template
  customizeTemplate(templateId) {
    const template = this.templates.get(templateId);
    if (!template) return;

    console.log('Opening customization for template:', template.name);

    // Close preview and gallery
    this.closeTemplatePreview();
    this.closeTemplateGallery();

    // Show customization interface
    this.showTemplateCustomization(template);
  }

  // Show template customization interface
  showTemplateCustomization(template) {
    // This would open a customization interface
    // For now, we'll show a notification and proceed with fork
    this.showTemplateNotification('Customization interface will open here. For now, creating a fork...', 'info');
    setTimeout(() => {
      this.forkTemplate(template.id);
    }, 2000);
  }

  // Open template for editing
  openTemplateForEditing(templateId) {
    const template = this.templates.get(templateId);
    if (!template) return;

    // This would integrate with the document editing system
    console.log('Opening template for editing:', template.name);

    // Create a new document based on the template
    if (window.location.hostname === 'docs.google.com') {
      // Open in Google Docs
      this.createGoogleDocFromTemplate(template);
    } else if (window.location.hostname.includes('office.com')) {
      // Open in Word Online
      this.createWordDocFromTemplate(template);
    } else {
      // Show template content in a new window or modal
      this.openTemplateInNewWindow(template);
    }
  }

  // Open template in editor
  openTemplateInEditor(template) {
    // This would open the template content in the appropriate editor
    console.log('Opening template in editor:', template.name);
    this.openTemplateInNewWindow(template);
  }

  // Open template in new window
  openTemplateInNewWindow(template) {
    const newWindow = window.open('', '_blank');
    newWindow.document.write(`
      <html>
        <head>
          <title>${template.name}</title>
          <style>
            body {
              font-family: 'Times New Roman', serif;
              max-width: 800px;
              margin: 0 auto;
              padding: 40px;
              line-height: 1.6;
            }
            h1 { color: #673ab7; border-bottom: 2px solid #673ab7; padding-bottom: 10px; }
          </style>
        </head>
        <body>
          <h1>${template.name}</h1>
          ${template.content}
          <hr style="margin-top: 40px;">
          <p style="font-size: 12px; color: #666;">
            Template created with Legal Git •
            <a href="#" onclick="window.close()">Close</a>
          </p>
        </body>
      </html>
    `);
  }

  // Create Google Doc from template
  createGoogleDocFromTemplate(template) {
    // This would use Google Docs API to create a new document
    console.log('Creating Google Doc from template:', template.name);
    this.showTemplateNotification('Creating Google Doc...', 'info');
  }

  // Create Word Doc from template
  createWordDocFromTemplate(template) {
    // This would use Office API to create a new document
    console.log('Creating Word document from template:', template.name);
    this.showTemplateNotification('Creating Word document...', 'info');
  }

  // Upload template
  uploadTemplate() {
    this.showTemplateNotification('Template upload interface will open here...', 'info');
  }

  // Create new template
  createTemplate() {
    this.showTemplateNotification('Template creation wizard will open here...', 'info');
  }

  // Close template preview
  closeTemplatePreview() {
    const preview = document.getElementById('legal-git-template-preview');
    if (preview) {
      preview.classList.remove('active');
      setTimeout(() => {
        preview.remove();
      }, 300);
    }
  }

  // Close template gallery
  closeTemplateGallery() {
    const gallery = document.getElementById('legal-git-template-gallery');
    if (gallery) {
      gallery.remove();
      this.galleryViewOpen = false;
    }
  }

  // Show template notification
  showTemplateNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `legal-git-word-notification ${type}`;
    notification.innerHTML = `
      <div style="font-size: 24px;">
        ${type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️'}
      </div>
      <div>
        <div style="font-weight: 600; margin-bottom: 4px;">
          ${type === 'success' ? 'Success' : type === 'error' ? 'Error' : 'Info'}
        </div>
        <div style="font-size: 13px; color: #5f6368;">${message}</div>
      </div>
    `;

    document.body.appendChild(notification);

    setTimeout(() => {
      if (notification.parentNode) {
        notification.remove();
      }
    }, 5000);
  }

  // Setup template gallery events
  setupTemplateGalleryEvents(modal) {
    // Workflow option selection
    modal.addEventListener('click', (e) => {
      if (e.target.closest('.legal-git-workflow-option')) {
        const option = e.target.closest('.legal-git-workflow-option');
        modal.querySelectorAll('.legal-git-workflow-option').forEach(opt => {
          opt.classList.remove('selected');
        });
        option.classList.add('selected');
      }
    });

    // Keyboard navigation
    modal.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        this.closeTemplateGallery();
      }
    });

    // Make globally available
    window.templateGallery = this;
  }

  // Setup template preview events
  setupTemplatePreviewEvents(preview) {
    // Keyboard navigation
    preview.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        this.closeTemplatePreview();
      }
    });
  }

  // Helper methods
  getCategoryIcon(category) {
    const icons = {
      'contracts': '📋',
      'letters': '✉️',
      'briefs': '⚖️',
      'policies': '📝',
      'real-estate': '🏠',
      'employment': '👔',
      'intellectual-property': '💡'
    };
    return icons[category] || '📄';
  }

  formatTimeAgo(timestamp) {
    const now = Date.now();
    const diffMs = now - timestamp;
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays}d ago`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;
    return `${Math.floor(diffDays / 30)}mo ago`;
  }

  // Template content generators
  generateNDATemplate() {
    return `
      <h2>NON-DISCLOSURE AGREEMENT</h2>
      <p>This Non-Disclosure Agreement ("Agreement") is entered into on [DATE] by and between [COMPANY NAME], a [STATE] corporation ("Disclosing Party"), and [RECIPIENT NAME] ("Receiving Party").</p>

      <h3>1. Definition of Confidential Information</h3>
      <p>For purposes of this Agreement, "Confidential Information" shall include all information or material that has or could have commercial value or other utility in the business in which Disclosing Party is engaged...</p>

      <h3>2. Non-Disclosure</h3>
      <p>Receiving Party agrees not to disclose Confidential Information to third parties and to use such information solely for the purpose of [PURPOSE]...</p>

      <h3>3. Return of Materials</h3>
      <p>Upon termination of discussions or upon demand by Disclosing Party, Receiving Party will return all documents and materials...</p>

      <p><strong>Signature:</strong> _____________________</p>
      <p><strong>Date:</strong> _____________________</p>
    `;
  }

  generateServiceAgreementTemplate() {
    return `
      <h2>PROFESSIONAL SERVICE AGREEMENT</h2>
      <p>This Professional Service Agreement ("Agreement") is made between [SERVICE PROVIDER NAME] ("Provider") and [CLIENT NAME] ("Client") effective [DATE].</p>

      <h3>1. Services</h3>
      <p>Provider agrees to perform the following services: [DESCRIPTION OF SERVICES]...</p>

      <h3>2. Compensation</h3>
      <p>Client agrees to pay Provider [AMOUNT] for the services described herein...</p>

      <h3>3. Timeline</h3>
      <p>Services shall commence on [START DATE] and be completed by [END DATE]...</p>

      <h3>4. Intellectual Property</h3>
      <p>All work product created by Provider shall be owned by [OWNER]...</p>
    `;
  }

  generateDemandLetterTemplate() {
    return `
      <p>[DATE]</p>
      <p>[RECIPIENT NAME]<br>[ADDRESS]</p>

      <p><strong>RE: DEMAND FOR PAYMENT</strong></p>

      <p>Dear [RECIPIENT NAME],</p>

      <p>This letter serves as formal notice that you are in default of your obligations under [AGREEMENT/CONTRACT] dated [DATE].</p>

      <p>As of the date of this letter, you owe [AMOUNT] which became due on [DUE DATE].</p>

      <p>DEMAND IS HEREBY MADE that you pay the full amount within [NUMBER] days of receipt of this letter.</p>

      <p>If payment is not received within the specified time, we reserve the right to pursue all available legal remedies.</p>

      <p>Sincerely,</p>
      <p>[YOUR NAME]</p>
    `;
  }

  generateMotionBriefTemplate() {
    return `
      <h2>MOTION FOR [RELIEF REQUESTED]</h2>

      <p>TO THE HONORABLE COURT:</p>

      <p>Plaintiff [NAME], by and through undersigned counsel, hereby moves this Court for [RELIEF REQUESTED] and in support thereof states:</p>

      <h3>I. INTRODUCTION</h3>
      <p>[Brief overview of the motion and relief sought]...</p>

      <h3>II. STATEMENT OF FACTS</h3>
      <p>[Factual background relevant to the motion]...</p>

      <h3>III. ARGUMENT</h3>
      <p>[Legal arguments supporting the motion]...</p>

      <h3>IV. CONCLUSION</h3>
      <p>For the foregoing reasons, Plaintiff respectfully requests that this Court grant the motion for [RELIEF].</p>

      <p>Respectfully submitted,</p>
      <p>[ATTORNEY NAME]<br>[BAR NUMBER]</p>
    `;
  }

  generatePrivacyPolicyTemplate() {
    return `
      <h2>PRIVACY POLICY</h2>
      <p>Last updated: [DATE]</p>

      <h3>1. Information We Collect</h3>
      <p>We collect information you provide directly to us, such as when you create an account...</p>

      <h3>2. How We Use Your Information</h3>
      <p>We use the information we collect to provide, maintain, and improve our services...</p>

      <h3>3. Information Sharing</h3>
      <p>We may share your information in the following circumstances...</p>

      <h3>4. Data Security</h3>
      <p>We implement appropriate technical and organizational measures to protect your personal information...</p>

      <h3>5. Your Rights</h3>
      <p>You have certain rights regarding your personal information, including the right to access, update, or delete...</p>

      <h3>6. Contact Us</h3>
      <p>If you have questions about this Privacy Policy, please contact us at [EMAIL].</p>
    `;
  }

  generateEmploymentContractTemplate() {
    return `
      <h2>EMPLOYMENT AGREEMENT</h2>

      <p>This Employment Agreement is between [COMPANY NAME] ("Company") and [EMPLOYEE NAME] ("Employee").</p>

      <h3>1. Position and Duties</h3>
      <p>Employee is hired as [POSITION TITLE] and agrees to perform duties including [DUTIES]...</p>

      <h3>2. Compensation</h3>
      <p>Employee will receive an annual salary of [AMOUNT], paid [FREQUENCY]...</p>

      <h3>3. Benefits</h3>
      <p>Employee is entitled to participate in company benefit plans including [BENEFITS]...</p>

      <h3>4. Confidentiality</h3>
      <p>Employee agrees to maintain the confidentiality of all proprietary information...</p>

      <h3>5. Termination</h3>
      <p>This agreement may be terminated by either party with [NOTICE PERIOD] written notice...</p>
    `;
  }

  generateLeaseAgreementTemplate() {
    return `
      <h2>RESIDENTIAL LEASE AGREEMENT</h2>

      <p>This Lease Agreement is between [LANDLORD NAME] ("Landlord") and [TENANT NAME] ("Tenant") for the property located at [PROPERTY ADDRESS].</p>

      <h3>1. Term</h3>
      <p>The lease term begins on [START DATE] and ends on [END DATE]...</p>

      <h3>2. Rent</h3>
      <p>Monthly rent is [AMOUNT], due on the [DAY] of each month...</p>

      <h3>3. Security Deposit</h3>
      <p>Tenant has paid a security deposit of [AMOUNT]...</p>

      <h3>4. Use of Premises</h3>
      <p>The premises shall be used solely as a private residence...</p>

      <h3>5. Maintenance and Repairs</h3>
      <p>Landlord is responsible for major repairs while Tenant is responsible for routine maintenance...</p>
    `;
  }
}

// Export for use in other scripts
window.TemplateGallery = TemplateGallery;
