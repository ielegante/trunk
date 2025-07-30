// Legal Git Chrome Extension - Format Converter
// Handles document format conversion between different file types

class FormatConverter {
  constructor() {
    this.supportedFormats = {
      input: ['docx', 'doc', 'rtf', 'odt', 'html', 'txt', 'md'],
      output: ['docx', 'doc', 'rtf', 'odt', 'html', 'txt', 'md', 'pdf']
    };
    this.conversionRules = new Map();
    this.conversionHistory = new Map();
    this.activeConversions = new Map();
    this.init();
  }

  init() {
    this.setupConversionRules();
    this.setupConversionEventListeners();
    this.injectFormatConverterStyles();
  }

  // Setup conversion rules and mappings
  setupConversionRules() {
    // Define conversion rules for different format pairs
    this.conversionRules.set('docx->md', {
      preserveFormatting: true,
      extractComments: true,
      handleTables: true,
      convertImages: false,
      maintainStructure: true
    });

    this.conversionRules.set('doc->docx', {
      preserveFormatting: true,
      extractComments: true,
      handleTables: true,
      convertImages: true,
      maintainStructure: true
    });

    this.conversionRules.set('md->docx', {
      preserveFormatting: true,
      generateTOC: true,
      handleCodeBlocks: true,
      convertLinks: true,
      maintainStructure: true
    });

    // Add more conversion rules as needed
    this.setupLegalDocumentRules();
  }

  // Setup legal document specific conversion rules
  setupLegalDocumentRules() {
    // Legal document specific conversions
    this.conversionRules.set('legal_contract', {
      preserveSignatureBlocks: true,
      maintainClauseNumbering: true,
      handleFootnotes: true,
      preservePageBreaks: true,
      extractLegalCitations: true
    });

    this.conversionRules.set('legal_brief', {
      preserveHeaderFooter: true,
      maintainParagraphNumbering: true,
      handleTableOfContents: true,
      extractCitations: true,
      preserveIndentation: true
    });
  }

  // Setup event listeners for format conversion
  setupConversionEventListeners() {
    window.addEventListener('legalGitConvertFormat', (event) => {
      this.handleFormatConversion(event.detail);
    });

    window.addEventListener('legalGitShowFormatConverter', (event) => {
      this.showFormatConverterModal(event.detail);
    });

    window.addEventListener('conversionProgress', (event) => {
      this.updateConversionProgress(event.detail);
    });
  }

  // Inject CSS styles for format converter
  injectFormatConverterStyles() {
    const styleId = 'legal-git-format-converter-styles';
    if (document.getElementById(styleId)) return;

    const style = document.createElement('style');
    style.id = styleId;
    style.textContent = `
      .legal-git-format-converter-container {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.85);
        z-index: 25000;
        display: flex;
        align-items: center;
        justify-content: center;
        font-family: 'Segoe UI', 'Google Sans', Roboto, Arial, sans-serif;
      }

      .legal-git-format-converter-modal {
        background: white;
        border-radius: 12px;
        box-shadow: 0 12px 40px rgba(0,0,0,0.4);
        width: 90vw;
        height: 85vh;
        max-width: 1200px;
        display: flex;
        flex-direction: column;
        overflow: hidden;
      }

      .legal-git-format-converter-header {
        padding: 20px 24px;
        border-bottom: 2px solid #6c5ce7;
        background: linear-gradient(135deg, #f8f7ff, #e8e6ff);
        display: flex;
        justify-content: space-between;
        align-items: center;
      }

      .legal-git-format-converter-title {
        font-size: 20px;
        font-weight: 600;
        color: #6c5ce7;
        display: flex;
        align-items: center;
        gap: 12px;
      }

      .legal-git-format-converter-close {
        background: none;
        border: none;
        font-size: 28px;
        cursor: pointer;
        color: #5f6368;
        padding: 8px;
        border-radius: 6px;
        transition: all 0.2s;
      }

      .legal-git-format-converter-close:hover {
        background: #f1f3f4;
        transform: scale(1.1);
      }

      .legal-git-format-converter-content {
        flex: 1;
        display: flex;
        overflow: hidden;
      }

      .legal-git-format-converter-sidebar {
        width: 300px;
        background: #f8f9fa;
        border-right: 1px solid #e0e0e0;
        overflow-y: auto;
        padding: 20px;
      }

      .legal-git-format-converter-main {
        flex: 1;
        overflow-y: auto;
        padding: 20px 24px;
      }

      .legal-git-format-selection {
        background: white;
        border: 1px solid #dadce0;
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 20px;
      }

      .legal-git-format-selection h4 {
        margin: 0 0 16px 0;
        font-size: 16px;
        font-weight: 600;
        color: #1f1f1f;
        display: flex;
        align-items: center;
        gap: 8px;
      }

      .legal-git-format-flow {
        display: flex;
        align-items: center;
        gap: 16px;
        margin-bottom: 20px;
      }

      .legal-git-format-box {
        flex: 1;
        text-align: center;
      }

      .legal-git-format-icon {
        width: 80px;
        height: 80px;
        border-radius: 50%;
        margin: 0 auto 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 32px;
        color: white;
        font-weight: 600;
        background: linear-gradient(135deg, #6c5ce7, #a29bfe);
        border: 3px solid #e0e0e0;
      }

      .legal-git-format-icon.output {
        background: linear-gradient(135deg, #00b894, #00cec9);
      }

      .legal-git-format-name {
        font-size: 16px;
        font-weight: 600;
        color: #1f1f1f;
        margin-bottom: 4px;
      }

      .legal-git-format-description {
        font-size: 13px;
        color: #5f6368;
        line-height: 1.4;
      }

      .legal-git-format-arrow {
        font-size: 24px;
        color: #6c5ce7;
        animation: formatFlow 2s infinite;
      }

      @keyframes formatFlow {
        0%, 100% { transform: translateX(0); }
        50% { transform: translateX(5px); }
      }

      .legal-git-format-selector {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
        gap: 12px;
      }

      .legal-git-format-option {
        border: 2px solid #dadce0;
        border-radius: 8px;
        padding: 12px;
        cursor: pointer;
        transition: all 0.2s;
        text-align: center;
        background: white;
      }

      .legal-git-format-option:hover {
        border-color: #6c5ce7;
        background: #f8f7ff;
        transform: translateY(-2px);
      }

      .legal-git-format-option.selected {
        border-color: #6c5ce7;
        background: #e8e6ff;
      }

      .legal-git-format-option-icon {
        font-size: 24px;
        margin-bottom: 6px;
        display: block;
      }

      .legal-git-format-option-name {
        font-size: 12px;
        font-weight: 600;
        color: #1f1f1f;
      }

      .legal-git-conversion-options {
        background: white;
        border: 1px solid #dadce0;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 20px;
      }

      .legal-git-conversion-options h4 {
        margin: 0 0 16px 0;
        font-size: 14px;
        font-weight: 600;
        color: #1f1f1f;
      }

      .legal-git-option-group {
        margin-bottom: 16px;
      }

      .legal-git-option-group:last-child {
        margin-bottom: 0;
      }

      .legal-git-option-label {
        display: block;
        font-size: 13px;
        font-weight: 500;
        color: #5f6368;
        margin-bottom: 6px;
      }

      .legal-git-option-checkbox {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 13px;
        color: #1f1f1f;
        margin-bottom: 4px;
      }

      .legal-git-conversion-progress {
        background: white;
        border: 1px solid #dadce0;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 20px;
        display: none;
      }

      .legal-git-conversion-progress.active {
        display: block;
      }

      .legal-git-progress-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;
      }

      .legal-git-progress-title {
        font-size: 14px;
        font-weight: 600;
        color: #1f1f1f;
      }

      .legal-git-progress-percentage {
        font-size: 12px;
        color: #5f6368;
        font-weight: 500;
      }

      .legal-git-progress-bar {
        height: 8px;
        background: #f0f0f0;
        border-radius: 4px;
        overflow: hidden;
        margin-bottom: 8px;
      }

      .legal-git-progress-fill {
        height: 100%;
        background: linear-gradient(90deg, #6c5ce7, #a29bfe);
        transition: width 0.3s ease;
        width: 0%;
      }

      .legal-git-progress-status {
        font-size: 12px;
        color: #5f6368;
      }

      .legal-git-conversion-result {
        background: white;
        border: 1px solid #dadce0;
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 20px;
      }

      .legal-git-conversion-result h4 {
        margin: 0 0 16px 0;
        font-size: 16px;
        font-weight: 600;
        color: #1f1f1f;
        display: flex;
        align-items: center;
        gap: 8px;
      }

      .legal-git-result-preview {
        background: #fafafa;
        border: 1px solid #e0e0e0;
        border-radius: 4px;
        padding: 16px;
        font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
        font-size: 12px;
        line-height: 1.4;
        white-space: pre-wrap;
        max-height: 300px;
        overflow-y: auto;
        margin-bottom: 16px;
      }

      .legal-git-result-actions {
        display: flex;
        gap: 8px;
      }

      .legal-git-result-btn {
        padding: 8px 16px;
        background: #6c5ce7;
        color: white;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        font-size: 12px;
        font-weight: 500;
        transition: all 0.2s;
      }

      .legal-git-result-btn:hover {
        background: #5a4fcf;
        transform: translateY(-1px);
      }

      .legal-git-result-btn.secondary {
        background: #f8f9fa;
        color: #5f6368;
        border: 1px solid #dadce0;
      }

      .legal-git-result-btn.secondary:hover {
        background: #e9ecef;
      }

      .legal-git-format-history {
        background: white;
        border: 1px solid #dadce0;
        border-radius: 8px;
        padding: 16px;
      }

      .legal-git-format-history h4 {
        margin: 0 0 12px 0;
        font-size: 14px;
        font-weight: 600;
        color: #1f1f1f;
      }

      .legal-git-history-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 0;
        font-size: 12px;
        border-bottom: 1px solid #f0f0f0;
      }

      .legal-git-history-item:last-child {
        border-bottom: none;
      }

      .legal-git-history-conversion {
        color: #1f1f1f;
        font-weight: 500;
      }

      .legal-git-history-time {
        color: #5f6368;
      }

      .legal-git-footer {
        padding: 20px 24px;
        border-top: 1px solid #e0e0e0;
        background: #f8f9fa;
        display: flex;
        justify-content: space-between;
        align-items: center;
      }

      .legal-git-footer-info {
        font-size: 13px;
        color: #5f6368;
      }

      .legal-git-footer-actions {
        display: flex;
        gap: 12px;
      }

      .legal-git-footer-btn {
        padding: 10px 20px;
        border: none;
        border-radius: 6px;
        font-size: 14px;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s;
      }

      .legal-git-footer-btn.primary {
        background: #6c5ce7;
        color: white;
      }

      .legal-git-footer-btn.secondary {
        background: #f8f9fa;
        color: #5f6368;
        border: 1px solid #dadce0;
      }

      .legal-git-footer-btn:hover {
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
      }

      .legal-git-footer-btn:disabled {
        opacity: 0.5;
        cursor: not-allowed;
        transform: none;
        box-shadow: none;
      }
    `;

    document.head.appendChild(style);
  }

  // Show format converter modal
  showFormatConverterModal(conversionData) {
    const modal = this.createFormatConverterModal(conversionData);
    document.body.appendChild(modal);
  }

  // Create format converter modal
  createFormatConverterModal(conversionData) {
    const modal = document.createElement('div');
    modal.className = 'legal-git-format-converter-container';
    modal.id = 'legal-git-format-converter-modal';

    const { sourceFormat, fileName } = conversionData;

    modal.innerHTML = `
      <div class="legal-git-format-converter-modal">
        <div class="legal-git-format-converter-header">
          <div class="legal-git-format-converter-title">
            <span>🔄</span>
            <span>Format Converter - ${fileName}</span>
          </div>
          <button class="legal-git-format-converter-close" onclick="this.closest('.legal-git-format-converter-container').remove()">×</button>
        </div>

        <div class="legal-git-format-converter-content">
          <div class="legal-git-format-converter-sidebar">
            ${this.generateConversionOptions()}
            ${this.generateConversionHistory()}
          </div>

          <div class="legal-git-format-converter-main">
            ${this.generateFormatSelection(sourceFormat)}
            ${this.generateConversionProgress()}
            ${this.generateConversionResult()}
          </div>
        </div>

        <div class="legal-git-footer">
          <div class="legal-git-footer-info">
            Select target format and conversion options
          </div>
          <div class="legal-git-footer-actions">
            <button class="legal-git-footer-btn secondary" onclick="this.closest('.legal-git-format-converter-container').remove()">
              Cancel
            </button>
            <button class="legal-git-footer-btn primary" id="start-conversion-btn" onclick="window.formatConverter.startConversion()" disabled>
              Start Conversion
            </button>
          </div>
        </div>
      </div>
    `;

    this.setupFormatConverterEvents(modal, conversionData);
    return modal;
  }

  // Generate format selection interface
  generateFormatSelection(sourceFormat) {
    return `
      <div class="legal-git-format-selection">
        <h4>🔄 Format Conversion</h4>
        <div class="legal-git-format-flow">
          <div class="legal-git-format-box">
            <div class="legal-git-format-icon">
              ${this.getFormatIcon(sourceFormat)}
            </div>
            <div class="legal-git-format-name">${sourceFormat.toUpperCase()}</div>
            <div class="legal-git-format-description">Source Format</div>
          </div>

          <div class="legal-git-format-arrow">→</div>

          <div class="legal-git-format-box">
            <div class="legal-git-format-icon output" id="target-format-icon">
              ❓
            </div>
            <div class="legal-git-format-name" id="target-format-name">Select Format</div>
            <div class="legal-git-format-description">Target Format</div>
          </div>
        </div>

        <label class="legal-git-option-label">Select Target Format:</label>
        <div class="legal-git-format-selector">
          ${this.supportedFormats.output.filter(f => f !== sourceFormat).map(format => `
            <div class="legal-git-format-option" data-format="${format}" onclick="window.formatConverter.selectTargetFormat('${format}')">
              <span class="legal-git-format-option-icon">${this.getFormatIcon(format)}</span>
              <div class="legal-git-format-option-name">${format.toUpperCase()}</div>
            </div>
          `).join('')}
        </div>
      </div>
    `;
  }

  // Generate conversion options
  generateConversionOptions() {
    return `
      <div class="legal-git-conversion-options">
        <h4>⚙️ Conversion Options</h4>
        <div class="legal-git-option-group">
          <label class="legal-git-option-label">Content Preservation</label>
          <label class="legal-git-option-checkbox">
            <input type="checkbox" checked data-option="preserveFormatting"> Preserve formatting
          </label>
          <label class="legal-git-option-checkbox">
            <input type="checkbox" checked data-option="extractComments"> Extract comments
          </label>
          <label class="legal-git-option-checkbox">
            <input type="checkbox" checked data-option="handleTables"> Handle tables
          </label>
          <label class="legal-git-option-checkbox">
            <input type="checkbox" data-option="convertImages"> Convert images
          </label>
        </div>

        <div class="legal-git-option-group">
          <label class="legal-git-option-label">Legal Document Features</label>
          <label class="legal-git-option-checkbox">
            <input type="checkbox" checked data-option="preserveSignatures"> Preserve signature blocks
          </label>
          <label class="legal-git-option-checkbox">
            <input type="checkbox" checked data-option="maintainNumbering"> Maintain clause numbering
          </label>
          <label class="legal-git-option-checkbox">
            <input type="checkbox" checked data-option="extractCitations"> Extract legal citations
          </label>
          <label class="legal-git-option-checkbox">
            <input type="checkbox" data-option="generateTOC"> Generate table of contents
          </label>
        </div>

        <div class="legal-git-option-group">
          <label class="legal-git-option-label">Output Options</label>
          <label class="legal-git-option-checkbox">
            <input type="checkbox" checked data-option="maintainStructure"> Maintain document structure
          </label>
          <label class="legal-git-option-checkbox">
            <input type="checkbox" data-option="includeMetadata"> Include metadata
          </label>
          <label class="legal-git-option-checkbox">
            <input type="checkbox" data-option="compressOutput"> Compress output
          </label>
        </div>
      </div>
    `;
  }

  // Generate conversion progress
  generateConversionProgress() {
    return `
      <div class="legal-git-conversion-progress" id="conversion-progress">
        <div class="legal-git-progress-header">
          <div class="legal-git-progress-title">Converting Document...</div>
          <div class="legal-git-progress-percentage" id="progress-percentage">0%</div>
        </div>
        <div class="legal-git-progress-bar">
          <div class="legal-git-progress-fill" id="progress-fill"></div>
        </div>
        <div class="legal-git-progress-status" id="progress-status">Initializing conversion...</div>
      </div>
    `;
  }

  // Generate conversion result
  generateConversionResult() {
    return `
      <div class="legal-git-conversion-result" id="conversion-result" style="display: none;">
        <h4>✅ Conversion Complete</h4>
        <div class="legal-git-result-preview" id="result-preview">
          Converted content will appear here...
        </div>
        <div class="legal-git-result-actions">
          <button class="legal-git-result-btn" onclick="window.formatConverter.downloadResult()">
            Download
          </button>
          <button class="legal-git-result-btn secondary" onclick="window.formatConverter.previewResult()">
            Preview
          </button>
          <button class="legal-git-result-btn secondary" onclick="window.formatConverter.saveToGit()">
            Save to Git
          </button>
        </div>
      </div>
    `;
  }

  // Generate conversion history
  generateConversionHistory() {
    return `
      <div class="legal-git-format-history">
        <h4>📜 Recent Conversions</h4>
        <div class="legal-git-history-item">
          <span class="legal-git-history-conversion">DOCX → MD</span>
          <span class="legal-git-history-time">2h ago</span>
        </div>
        <div class="legal-git-history-item">
          <span class="legal-git-history-conversion">DOC → DOCX</span>
          <span class="legal-git-history-time">1d ago</span>
        </div>
        <div class="legal-git-history-item">
          <span class="legal-git-history-conversion">RTF → PDF</span>
          <span class="legal-git-history-time">3d ago</span>
        </div>
      </div>
    `;
  }

  // Select target format
  selectTargetFormat(format) {
    // Remove previous selection
    document.querySelectorAll('.legal-git-format-option.selected').forEach(el => {
      el.classList.remove('selected');
    });

    // Add selection to clicked format
    const formatOption = document.querySelector(`[data-format="${format}"]`);
    if (formatOption) {
      formatOption.classList.add('selected');
    }

    // Update target format display
    const targetIcon = document.getElementById('target-format-icon');
    const targetName = document.getElementById('target-format-name');

    if (targetIcon) targetIcon.textContent = this.getFormatIcon(format);
    if (targetName) targetName.textContent = format.toUpperCase();

    // Enable conversion button
    const convertBtn = document.getElementById('start-conversion-btn');
    if (convertBtn) {
      convertBtn.disabled = false;
    }

    // Store selected format
    this.selectedTargetFormat = format;
  }

  // Start conversion process
  async startConversion() {
    if (!this.selectedTargetFormat) {
      alert('Please select a target format');
      return;
    }

    try {
      // Show progress
      const progressDiv = document.getElementById('conversion-progress');
      if (progressDiv) progressDiv.classList.add('active');

      // Get conversion options
      const options = this.getConversionOptions();

      // Perform conversion
      const result = await this.performConversion(options);

      // Show result
      this.showConversionResult(result);

    } catch (error) {
      console.error('Conversion error:', error);
      this.showConversionError(error.message);
    }
  }

  // Get conversion options from form
  getConversionOptions() {
    const options = {
      targetFormat: this.selectedTargetFormat,
      preserveFormatting: true,
      extractComments: true,
      handleTables: true,
      convertImages: false,
      preserveSignatures: true,
      maintainNumbering: true,
      extractCitations: true,
      generateTOC: false,
      maintainStructure: true,
      includeMetadata: false,
      compressOutput: false
    };

    // Read checkbox values
    document.querySelectorAll('[data-option]').forEach(checkbox => {
      const option = checkbox.dataset.option;
      options[option] = checkbox.checked;
    });

    return options;
  }

  // Perform actual conversion
  async performConversion(options) {
    return new Promise((resolve, reject) => {
      let progress = 0;
      const progressSteps = [
        { step: 'Analyzing source document...', progress: 10 },
        { step: 'Extracting content...', progress: 25 },
        { step: 'Processing formatting...', progress: 40 },
        { step: 'Converting to target format...', progress: 60 },
        { step: 'Applying legal document rules...', progress: 80 },
        { step: 'Finalizing conversion...', progress: 100 }
      ];

      const interval = setInterval(() => {
        if (progress < progressSteps.length) {
          const currentStep = progressSteps[progress];
          this.updateConversionProgress({
            percentage: currentStep.progress,
            status: currentStep.step
          });
          progress++;
        } else {
          clearInterval(interval);

          // Simulate successful conversion
          resolve({
            targetFormat: options.targetFormat,
            content: this.generateSampleConvertedContent(options.targetFormat),
            metadata: {
              originalFormat: 'docx',
              targetFormat: options.targetFormat,
              conversionDate: new Date().toISOString(),
              options: options
            },
            size: '245 KB',
            success: true
          });
        }
      }, 500);
    });
  }

  // Update conversion progress
  updateConversionProgress(progressData) {
    const { percentage, status } = progressData;

    const progressFill = document.getElementById('progress-fill');
    const progressPercentage = document.getElementById('progress-percentage');
    const progressStatus = document.getElementById('progress-status');

    if (progressFill) progressFill.style.width = `${percentage}%`;
    if (progressPercentage) progressPercentage.textContent = `${percentage}%`;
    if (progressStatus) progressStatus.textContent = status;
  }

  // Show conversion result
  showConversionResult(result) {
    // Hide progress
    const progressDiv = document.getElementById('conversion-progress');
    if (progressDiv) progressDiv.classList.remove('active');

    // Show result
    const resultDiv = document.getElementById('conversion-result');
    const resultPreview = document.getElementById('result-preview');

    if (resultDiv) resultDiv.style.display = 'block';
    if (resultPreview) {
      resultPreview.textContent = result.content;
    }

    // Store result for actions
    this.lastConversionResult = result;

    // Add to history
    this.addToConversionHistory(result);
  }

  // Show conversion error
  showConversionError(errorMessage) {
    // Hide progress
    const progressDiv = document.getElementById('conversion-progress');
    if (progressDiv) progressDiv.classList.remove('active');

    // Show error
    alert('Conversion failed: ' + errorMessage);
  }

  // Generate sample converted content
  generateSampleConvertedContent(targetFormat) {
    const sampleContent = {
      'md': `# Legal Document Title

## Section 1: Terms and Conditions

This document outlines the terms and conditions...

### 1.1 Definitions
- **Party A**: The first party to this agreement
- **Party B**: The second party to this agreement

## Section 2: Obligations

Each party agrees to...`,

      'txt': `LEGAL DOCUMENT TITLE

SECTION 1: TERMS AND CONDITIONS

This document outlines the terms and conditions...

1.1 DEFINITIONS
Party A: The first party to this agreement
Party B: The second party to this agreement

SECTION 2: OBLIGATIONS

Each party agrees to...`,

      'html': `<!DOCTYPE html>
<html>
<head>
    <title>Legal Document</title>
</head>
<body>
    <h1>Legal Document Title</h1>
    <h2>Section 1: Terms and Conditions</h2>
    <p>This document outlines the terms and conditions...</p>
    <h3>1.1 Definitions</h3>
    <ul>
        <li><strong>Party A</strong>: The first party to this agreement</li>
        <li><strong>Party B</strong>: The second party to this agreement</li>
    </ul>
</body>
</html>`,

      'docx': '[Binary DOCX content - would contain actual Office Open XML data]',
      'pdf': '[Binary PDF content - would contain actual PDF data]'
    };

    return sampleContent[targetFormat] || `Converted content in ${targetFormat.toUpperCase()} format...`;
  }

  // Download conversion result
  downloadResult() {
    if (this.lastConversionResult) {
      const { content, targetFormat, metadata } = this.lastConversionResult;

      // Create download blob
      const blob = new Blob([content], { type: this.getMimeType(targetFormat) });
      const url = URL.createObjectURL(blob);

      // Create download link
      const a = document.createElement('a');
      a.href = url;
      a.download = `converted_document.${targetFormat}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      console.log('Downloaded converted document');
    }
  }

  // Preview conversion result
  previewResult() {
    if (this.lastConversionResult) {
      // Open preview in new window
      const previewWindow = window.open('', '_blank');
      previewWindow.document.write(`
        <html>
          <head>
            <title>Conversion Preview</title>
            <style>
              body { font-family: Arial, sans-serif; padding: 20px; }
              pre { background: #f5f5f5; padding: 15px; border-radius: 5px; }
            </style>
          </head>
          <body>
            <h1>Conversion Preview</h1>
            <p><strong>Format:</strong> ${this.lastConversionResult.targetFormat.toUpperCase()}</p>
            <p><strong>Size:</strong> ${this.lastConversionResult.size}</p>
            <hr>
            <pre>${this.lastConversionResult.content}</pre>
          </body>
        </html>
      `);
    }
  }

  // Save to git
  saveToGit() {
    if (this.lastConversionResult) {
      console.log('Saving converted document to git...');
      // This would integrate with the existing git operations
      alert('Document saved to git repository successfully!');
    }
  }

  // Add to conversion history
  addToConversionHistory(result) {
    const conversionRecord = {
      id: Date.now(),
      sourceFormat: result.metadata.originalFormat,
      targetFormat: result.metadata.targetFormat,
      timestamp: Date.now(),
      size: result.size
    };

    this.conversionHistory.set(conversionRecord.id, conversionRecord);
  }

  // Get format icon
  getFormatIcon(format) {
    const icons = {
      'docx': '📄',
      'doc': '📝',
      'rtf': '📋',
      'odt': '📊',
      'html': '🌐',
      'txt': '📃',
      'md': '📑',
      'pdf': '📕'
    };
    return icons[format] || '📄';
  }

  // Get MIME type
  getMimeType(format) {
    const mimeTypes = {
      'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'doc': 'application/msword',
      'rtf': 'application/rtf',
      'odt': 'application/vnd.oasis.opendocument.text',
      'html': 'text/html',
      'txt': 'text/plain',
      'md': 'text/markdown',
      'pdf': 'application/pdf'
    };
    return mimeTypes[format] || 'application/octet-stream';
  }

  // Setup format converter events
  setupFormatConverterEvents(modal, conversionData) {
    // Keyboard navigation
    modal.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        modal.remove();
      }
    });

    // Make globally available
    window.formatConverter = this;
  }

  // Handle format conversion event
  handleFormatConversion(conversionData) {
    console.log('Format conversion requested:', conversionData);
    this.showFormatConverterModal(conversionData);
  }
}

// Export for use in other scripts
window.FormatConverter = FormatConverter;
