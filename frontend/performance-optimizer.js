// Legal Git Chrome Extension - Performance Optimizer
// Optimizes performance for self-hosted deployment with limited resources

class PerformanceOptimizer {
  constructor() {
    this.cache = new Map();
    this.cacheMaxSize = 50; // Max cached items
    this.cacheMaxAge = 300000; // 5 minutes
    this.pendingRequests = new Map();
    this.init();
  }

  init() {
    this.setupCacheCleanup();
    this.optimizeEventListeners();
    this.setupLazyLoading();
    this.monitorMemoryUsage();
  }

  // Setup periodic cache cleanup
  setupCacheCleanup() {
    setInterval(() => {
      this.cleanupCache();
    }, 60000); // Clean every minute
  }

  // Clean expired cache entries
  cleanupCache() {
    const now = Date.now();
    const entriesToDelete = [];

    for (const [key, value] of this.cache) {
      if (now - value.timestamp > this.cacheMaxAge) {
        entriesToDelete.push(key);
      }
    }

    entriesToDelete.forEach(key => this.cache.delete(key));

    // If cache is still too large, remove oldest entries
    if (this.cache.size > this.cacheMaxSize) {
      const sortedEntries = Array.from(this.cache.entries())
        .sort((a, b) => a[1].timestamp - b[1].timestamp);

      const toRemove = sortedEntries.slice(0, this.cache.size - this.cacheMaxSize);
      toRemove.forEach(([key]) => this.cache.delete(key));
    }
  }

  // Cache API responses
  async cachedFetch(url, options = {}) {
    const cacheKey = `${url}:${JSON.stringify(options)}`;

    // Check cache first
    const cached = this.getCached(cacheKey);
    if (cached) {
      return cached;
    }

    // Check if request is already pending
    if (this.pendingRequests.has(cacheKey)) {
      return this.pendingRequests.get(cacheKey);
    }

    // Make request
    const requestPromise = fetch(url, options)
      .then(response => response.json())
      .then(data => {
        this.setCached(cacheKey, data);
        this.pendingRequests.delete(cacheKey);
        return data;
      })
      .catch(error => {
        this.pendingRequests.delete(cacheKey);
        throw error;
      });

    this.pendingRequests.set(cacheKey, requestPromise);
    return requestPromise;
  }

  // Get cached data
  getCached(key) {
    const cached = this.cache.get(key);
    if (cached && Date.now() - cached.timestamp < this.cacheMaxAge) {
      cached.hits = (cached.hits || 0) + 1;
      return cached.data;
    }
    return null;
  }

  // Set cached data
  setCached(key, data) {
    this.cache.set(key, {
      data: data,
      timestamp: Date.now(),
      hits: 0
    });
  }

  // Optimize event listeners with debouncing
  optimizeEventListeners() {
    // Debounce scroll events
    let scrollTimeout;
    const originalAddEventListener = EventTarget.prototype.addEventListener;

    EventTarget.prototype.addEventListener = function(type, listener, options) {
      if (type === 'scroll') {
        const debouncedListener = function(event) {
          clearTimeout(scrollTimeout);
          scrollTimeout = setTimeout(() => listener.call(this, event), 150);
        };
        return originalAddEventListener.call(this, type, debouncedListener, options);
      }
      return originalAddEventListener.call(this, type, listener, options);
    };
  }

  // Setup lazy loading for heavy components
  setupLazyLoading() {
    // Lazy load images
    const lazyLoadImages = () => {
      const images = document.querySelectorAll('img[data-src]:not(.loaded)');

      const imageObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            const img = entry.target;
            img.src = img.dataset.src;
            img.classList.add('loaded');
            imageObserver.unobserve(img);
          }
        });
      });

      images.forEach(img => imageObserver.observe(img));
    };

    // Run on DOM changes
    const observer = new MutationObserver(lazyLoadImages);
    observer.observe(document.body, { childList: true, subtree: true });
    lazyLoadImages();
  }

  // Monitor memory usage
  monitorMemoryUsage() {
    if (!performance.memory) return; // Not supported in all browsers

    setInterval(() => {
      const memoryUsage = performance.memory.usedJSHeapSize / 1048576; // Convert to MB

      if (memoryUsage > 100) { // If using more than 100MB
        console.warn('High memory usage detected:', memoryUsage.toFixed(2), 'MB');
        this.performMemoryCleanup();
      }
    }, 30000); // Check every 30 seconds
  }

  // Perform memory cleanup
  performMemoryCleanup() {
    // Clear large cache entries
    const largeCacheThreshold = 1024 * 1024; // 1MB

    for (const [key, value] of this.cache) {
      const size = JSON.stringify(value.data).length;
      if (size > largeCacheThreshold) {
        this.cache.delete(key);
      }
    }

    // Force garbage collection if available
    if (window.gc) {
      window.gc();
    }
  }

  // Throttle function calls
  throttle(func, delay) {
    let lastCall = 0;
    return function(...args) {
      const now = Date.now();
      if (now - lastCall >= delay) {
        lastCall = now;
        return func.apply(this, args);
      }
    };
  }

  // Debounce function calls
  debounce(func, delay) {
    let timeout;
    return function(...args) {
      clearTimeout(timeout);
      timeout = setTimeout(() => func.apply(this, args), delay);
    };
  }

  // Batch DOM updates
  batchDOMUpdates(updates) {
    requestAnimationFrame(() => {
      updates.forEach(update => update());
    });
  }

  // Optimize API calls with request batching
  batchAPIRequests(requests, batchSize = 5) {
    const batches = [];
    for (let i = 0; i < requests.length; i += batchSize) {
      batches.push(requests.slice(i, i + batchSize));
    }

    return batches.reduce((promise, batch) => {
      return promise.then(results => {
        return Promise.all(batch).then(batchResults => {
          return results.concat(batchResults);
        });
      });
    }, Promise.resolve([]));
  }

  // Preload critical resources
  preloadResources(urls) {
    urls.forEach(url => {
      const link = document.createElement('link');
      link.rel = 'prefetch';
      link.href = url;
      document.head.appendChild(link);
    });
  }

  // Optimize document list rendering
  virtualizeList(container, items, renderItem, itemHeight = 50) {
    const visibleItems = Math.ceil(container.clientHeight / itemHeight) + 2;
    let scrollTop = 0;
    let startIndex = 0;

    const render = () => {
      startIndex = Math.floor(scrollTop / itemHeight);
      const endIndex = Math.min(startIndex + visibleItems, items.length);

      container.innerHTML = '';

      // Add spacer for items above
      if (startIndex > 0) {
        const spacer = document.createElement('div');
        spacer.style.height = `${startIndex * itemHeight}px`;
        container.appendChild(spacer);
      }

      // Render visible items
      for (let i = startIndex; i < endIndex; i++) {
        container.appendChild(renderItem(items[i], i));
      }

      // Add spacer for items below
      if (endIndex < items.length) {
        const spacer = document.createElement('div');
        spacer.style.height = `${(items.length - endIndex) * itemHeight}px`;
        container.appendChild(spacer);
      }
    };

    container.addEventListener('scroll', this.throttle(() => {
      scrollTop = container.scrollTop;
      render();
    }, 16));

    render();
  }

  // Get performance metrics
  getMetrics() {
    const metrics = {
      cacheSize: this.cache.size,
      cacheHitRate: this.calculateCacheHitRate(),
      memoryUsage: performance.memory ?
        (performance.memory.usedJSHeapSize / 1048576).toFixed(2) + ' MB' :
        'N/A',
      pendingRequests: this.pendingRequests.size
    };

    return metrics;
  }

  // Calculate cache hit rate
  calculateCacheHitRate() {
    let totalHits = 0;
    let totalRequests = 0;

    for (const [_, value] of this.cache) {
      totalHits += value.hits || 0;
      totalRequests += (value.hits || 0) + 1;
    }

    return totalRequests > 0 ?
      ((totalHits / totalRequests) * 100).toFixed(2) + '%' :
      '0%';
  }

  // Clear all caches
  clearCache() {
    this.cache.clear();
    this.pendingRequests.clear();
  }
}

// Initialize performance optimizer
window.legalGitPerformance = new PerformanceOptimizer();

// Export for use in other modules
window.PerformanceOptimizer = PerformanceOptimizer;
