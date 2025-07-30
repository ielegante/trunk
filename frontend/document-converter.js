// Legal Git Chrome Extension - Document Conversion Pipeline
// Handles Google Docs ↔ Markdown conversion and content extraction

class DocumentConverter {
  constructor() {
    this.conversionCache = new Map();
    this.lastKnownContent = new Map();
    this.changeListeners = new Map();
    this.init();
  }

  async init() {
    await this.loadConversionCache();
    this.setupChangeDetection();
  }

  async loadConversionCache() {
    try {
      const result = await chrome.storage.local.get(['documentCache']);
      if (result.documentCache) {
        this.conversionCache = new Map(Object.entries(result.documentCache));
      }
    } catch (error) {
      console.error('Failed to load conversion cache:', error);
    }
  }

  async saveConversionCache() {
    try {
      const cacheObject = Object.fromEntries(this.conversionCache);
      await chrome.storage.local.set({ documentCache: cacheObject });
    } catch (error) {
      console.error('Failed to save conversion cache:', error);
    }
  }

  // Extract content from Google Docs
  async extractGoogleDocsContent(documentId) {
    try {
      // Method 1: Extract from DOM (current document)
      if (this.isCurrentDocument(documentId)) {
        return this.extractFromDOM();
      }

      // Method 2: Use Google Docs API (requires authentication)
      return await this.extractFromAPI(documentId);
    } catch (error) {
      console.error('Content extraction failed:', error);
      throw new Error(`Failed to extract document content: ${error.message}`);
    }
  }

  // Check if we're currently viewing the document
  isCurrentDocument(documentId) {
    const currentUrl = window.location.href;
    return currentUrl.includes(documentId);
  }

  // Extract content from current Google Docs DOM
  extractFromDOM() {
    try {
      const docContent = {
        title: this.extractTitle(),
        body: this.extractBody(),
        comments: this.extractComments(),
        suggestions: this.extractSuggestions(),
        metadata: this.extractMetadata()
      };

      return docContent;
    } catch (error) {
      console.error('DOM extraction failed:', error);
      throw new Error('Failed to extract content from document');
    }
  }

  // Extract document title
  extractTitle() {
    const titleSelectors = [
      '.docs-title-input',
      '[data-tooltip="Rename"]',
      '.kix-document-title'
    ];

    for (const selector of titleSelectors) {
      const element = document.querySelector(selector);
      if (element) {
        return element.textContent?.trim() || element.value?.trim() || 'Untitled Document';
      }
    }

    return 'Untitled Document';
  }

  // Extract document body content
  extractBody() {
    const bodySelectors = [
      '.kix-canvas-tile-content',
      '.kix-page-content-wrap',
      '.doc-content'
    ];

    for (const selector of bodySelectors) {
      const elements = document.querySelectorAll(selector);
      if (elements.length > 0) {
        return this.extractTextFromElements(elements);
      }
    }

    // Fallback: try to get any text content
    const docBody = document.querySelector('.kix-appview-editor');
    if (docBody) {
      return this.extractTextFromElements([docBody]);
    }

    return '';
  }

  // Extract text from DOM elements with structure preservation
  extractTextFromElements(elements) {
    const extractedContent = [];

    elements.forEach(element => {
      const content = this.processElement(element);
      if (content.trim()) {
        extractedContent.push(content);
      }
    });

    return extractedContent.join('\n\n');
  }

  // Process individual element and preserve structure
  processElement(element) {
    const tagName = element.tagName?.toLowerCase();
    const textContent = element.textContent?.trim() || '';

    // Handle different element types
    switch (tagName) {
      case 'h1':
        return `# ${textContent}`;
      case 'h2':
        return `## ${textContent}`;
      case 'h3':
        return `### ${textContent}`;
      case 'h4':
        return `#### ${textContent}`;
      case 'h5':
        return `##### ${textContent}`;
      case 'h6':
        return `###### ${textContent}`;
      case 'p':
        return textContent;
      case 'ul':
      case 'ol':
        return this.extractListContent(element);
      case 'blockquote':
        return `> ${textContent}`;
      case 'code':
        return `\`${textContent}\``;
      case 'pre':
        return `\`\`\`\n${textContent}\n\`\`\``;
      default:
        return textContent;
    }
  }

  // Extract list content with proper formatting
  extractListContent(listElement) {
    const items = listElement.querySelectorAll('li');
    const isOrdered = listElement.tagName.toLowerCase() === 'ol';
    const listItems = [];

    items.forEach((item, index) => {
      const text = item.textContent?.trim();
      if (text) {
        const prefix = isOrdered ? `${index + 1}. ` : '- ';
        listItems.push(`${prefix}${text}`);
      }
    });

    return listItems.join('\n');
  }

  // Extract comments from document
  extractComments() {
    const comments = [];
    const commentElements = document.querySelectorAll('[data-comment-id]');

    commentElements.forEach(element => {
      const commentId = element.getAttribute('data-comment-id');
      const commentText = element.textContent?.trim();

      if (commentId && commentText) {
        comments.push({
          id: commentId,
          text: commentText,
          position: this.getElementPosition(element)
        });
      }
    });

    return comments;
  }

  // Extract suggestions/tracked changes
  extractSuggestions() {
    const suggestions = [];
    const suggestionElements = document.querySelectorAll('.kix-selection-overlay');

    suggestionElements.forEach(element => {
      const suggestionData = this.parseSuggestionElement(element);
      if (suggestionData) {
        suggestions.push(suggestionData);
      }
    });

    return suggestions;
  }

  // Parse suggestion element data
  parseSuggestionElement(element) {
    try {
      const rect = element.getBoundingClientRect();
      const style = window.getComputedStyle(element);

      return {
        type: this.determineSuggestionType(style),
        position: { x: rect.left, y: rect.top },
        content: element.textContent?.trim() || ''
      };
    } catch (error) {
      return null;
    }
  }

  // Determine suggestion type from styling
  determineSuggestionType(style) {
    const backgroundColor = style.backgroundColor;
    const textDecoration = style.textDecoration;

    if (backgroundColor.includes('green') || style.color.includes('green')) {
      return 'addition';
    } else if (textDecoration.includes('line-through') || backgroundColor.includes('red')) {
      return 'deletion';
    } else if (backgroundColor.includes('blue') || backgroundColor.includes('yellow')) {
      return 'modification';
    }

    return 'unknown';
  }

  // Extract document metadata
  extractMetadata() {
    return {
      url: window.location.href,
      documentId: this.getDocumentIdFromUrl(),
      extractedAt: new Date().toISOString(),
      userAgent: navigator.userAgent,
      viewport: {
        width: window.innerWidth,
        height: window.innerHeight
      }
    };
  }

  // Get document ID from current URL
  getDocumentIdFromUrl() {
    const pathParts = window.location.pathname.split('/');
    const docIndex = pathParts.indexOf('d');
    return docIndex !== -1 ? pathParts[docIndex + 1] : null;
  }

  // Get element position for reference tracking
  getElementPosition(element) {
    const rect = element.getBoundingClientRect();
    return {
      x: rect.left,
      y: rect.top,
      width: rect.width,
      height: rect.height
    };
  }

  // Convert Google Docs content to Markdown
  convertToMarkdown(docContent) {
    if (!docContent) return '';

    let markdown = '';

    // Add title
    if (docContent.title && docContent.title !== 'Untitled Document') {
      markdown += `# ${docContent.title}\n\n`;
    }

    // Add body content
    if (docContent.body) {
      markdown += this.processBodyToMarkdown(docContent.body);
    }

    // Add comments as footnotes
    if (docContent.comments && docContent.comments.length > 0) {
      markdown += '\n\n## Comments\n\n';
      docContent.comments.forEach((comment, index) => {
        markdown += `[^${index + 1}]: ${comment.text}\n`;
      });
    }

    // Add metadata
    if (docContent.metadata) {
      markdown += '\n\n---\n';
      markdown += `*Document extracted: ${docContent.metadata.extractedAt}*\n`;
      markdown += `*Document ID: ${docContent.metadata.documentId}*\n`;
    }

    return markdown;
  }

  // Process body content to proper Markdown
  processBodyToMarkdown(bodyText) {
    if (!bodyText) return '';

    // Clean up and normalize text
    let markdown = bodyText
      .replace(/\r\n/g, '\n')
      .replace(/\r/g, '\n')
      .replace(/\n{3,}/g, '\n\n')
      .trim();

    // Process paragraphs
    markdown = this.processParagraphs(markdown);

    return markdown;
  }

  // Process paragraphs and preserve structure
  processParagraphs(text) {
    const lines = text.split('\n');
    const processedLines = [];

    lines.forEach(line => {
      const trimmedLine = line.trim();
      if (trimmedLine) {
        processedLines.push(trimmedLine);
      } else {
        processedLines.push('');
      }
    });

    return processedLines.join('\n');
  }

  // Convert Markdown back to Google Docs format (placeholder)
  convertFromMarkdown(markdown) {
    // This would be implemented in Sprint 4 when we have full bidirectional conversion
    console.log('Markdown to Google Docs conversion - Sprint 4 feature');
    return {
      title: this.extractMarkdownTitle(markdown),
      body: markdown,
      formatting: {}
    };
  }

  // Extract title from Markdown
  extractMarkdownTitle(markdown) {
    const lines = markdown.split('\n');
    for (const line of lines) {
      if (line.startsWith('# ')) {
        return line.substring(2).trim();
      }
    }
    return 'Untitled Document';
  }

  // Setup real-time change detection
  setupChangeDetection() {
    if (window.location.hostname === 'docs.google.com') {
      this.startDocumentMonitoring();
    }
  }

  // Monitor document for changes
  startDocumentMonitoring() {
    const documentId = this.getDocumentIdFromUrl();
    if (!documentId) return;

    // Store initial content
    this.captureInitialContent(documentId);

    // Set up mutation observer for content changes
    this.setupMutationObserver(documentId);

    // Set up periodic content comparison
    this.setupPeriodicCheck(documentId);
  }

  // Capture initial document content
  async captureInitialContent(documentId) {
    try {
      const content = await this.extractGoogleDocsContent(documentId);
      this.lastKnownContent.set(documentId, content);

      // Cache the content
      this.conversionCache.set(documentId, {
        content: content,
        markdown: this.convertToMarkdown(content),
        timestamp: Date.now()
      });

      await this.saveConversionCache();
    } catch (error) {
      console.error('Failed to capture initial content:', error);
    }
  }

  // Set up mutation observer for DOM changes
  setupMutationObserver(documentId) {
    const targetNode = document.querySelector('.kix-appview-editor') || document.body;

    const observer = new MutationObserver((mutations) => {
      let hasRelevantChanges = false;

      mutations.forEach(mutation => {
        if (mutation.type === 'childList' || mutation.type === 'characterData') {
          hasRelevantChanges = true;
        }
      });

      if (hasRelevantChanges) {
        this.debounceContentCheck(documentId);
      }
    });

    observer.observe(targetNode, {
      childList: true,
      subtree: true,
      characterData: true,
      attributes: false
    });

    // Store observer for cleanup
    this.changeListeners.set(documentId, observer);
  }

  // Debounced content checking to avoid excessive calls
  debounceContentCheck(documentId) {
    clearTimeout(this.checkTimeout);
    this.checkTimeout = setTimeout(() => {
      this.checkForChanges(documentId);
    }, 1000); // Wait 1 second after last change
  }

  // Check for content changes
  async checkForChanges(documentId) {
    try {
      const currentContent = await this.extractGoogleDocsContent(documentId);
      const lastContent = this.lastKnownContent.get(documentId);

      if (lastContent && this.hasContentChanged(lastContent, currentContent)) {
        const changes = this.detectChanges(lastContent, currentContent);
        this.handleContentChange(documentId, currentContent, changes);
      }
    } catch (error) {
      console.error('Change detection failed:', error);
    }
  }

  // Check if content has changed
  hasContentChanged(oldContent, newContent) {
    return oldContent.body !== newContent.body ||
           oldContent.title !== newContent.title;
  }

  // Detect specific changes between content versions
  detectChanges(oldContent, newContent) {
    const changes = {
      title: oldContent.title !== newContent.title,
      body: oldContent.body !== newContent.body,
      comments: this.compareArrays(oldContent.comments, newContent.comments),
      suggestions: this.compareArrays(oldContent.suggestions, newContent.suggestions),
      timestamp: new Date().toISOString()
    };

    if (changes.body) {
      changes.textDiff = this.generateTextDiff(oldContent.body, newContent.body);
    }

    return changes;
  }

  // Compare arrays for changes
  compareArrays(oldArray = [], newArray = []) {
    return {
      added: newArray.filter(item => !oldArray.some(old =>
        JSON.stringify(old) === JSON.stringify(item))),
      removed: oldArray.filter(item => !newArray.some(newItem =>
        JSON.stringify(newItem) === JSON.stringify(item))),
      modified: oldArray.length !== newArray.length
    };
  }

  // Generate basic text diff
  generateTextDiff(oldText, newText) {
    const oldLines = oldText.split('\n');
    const newLines = newText.split('\n');
    const diff = [];

    const maxLines = Math.max(oldLines.length, newLines.length);

    for (let i = 0; i < maxLines; i++) {
      const oldLine = oldLines[i] || '';
      const newLine = newLines[i] || '';

      if (oldLine !== newLine) {
        diff.push({
          lineNumber: i + 1,
          type: this.determineDiffType(oldLine, newLine),
          old: oldLine,
          new: newLine
        });
      }
    }

    return diff;
  }

  // Determine type of diff (add, delete, modify)
  determineDiffType(oldLine, newLine) {
    if (!oldLine && newLine) return 'add';
    if (oldLine && !newLine) return 'delete';
    return 'modify';
  }

  // Handle content change event
  handleContentChange(documentId, newContent, changes) {
    // Update stored content
    this.lastKnownContent.set(documentId, newContent);

    // Update cache
    this.conversionCache.set(documentId, {
      content: newContent,
      markdown: this.convertToMarkdown(newContent),
      timestamp: Date.now(),
      changes: changes
    });

    this.saveConversionCache();

    // Trigger change event for UI updates
    window.dispatchEvent(new CustomEvent('documentContentChanged', {
      detail: {
        documentId: documentId,
        content: newContent,
        changes: changes
      }
    }));
  }

  // Set up periodic content checking as fallback
  setupPeriodicCheck(documentId) {
    setInterval(() => {
      this.checkForChanges(documentId);
    }, 30000); // Check every 30 seconds
  }

  // Get cached content for document
  getCachedContent(documentId) {
    return this.conversionCache.get(documentId);
  }

  // Get all cached documents
  getAllCachedDocuments() {
    return Array.from(this.conversionCache.entries());
  }

  // Clean up change listeners
  cleanup(documentId) {
    const observer = this.changeListeners.get(documentId);
    if (observer) {
      observer.disconnect();
      this.changeListeners.delete(documentId);
    }
  }
}

// Export for use in other scripts
window.DocumentConverter = DocumentConverter;
