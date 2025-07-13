// Legal Git Chrome Extension - Git Operations Manager
// Handles git repository creation, commits, and branch management

class GitOperationsManager {
  constructor() {
    this.serverConfig = null;
    this.repositories = new Map(); // Cache of repository states
    this.init();
  }

  async init() {
    await this.loadServerConfig();
    await this.loadRepositoryCache();
  }

  async loadServerConfig() {
    try {
      const result = await chrome.storage.local.get(['gitServerConfig']);
      this.serverConfig = result.gitServerConfig;
    } catch (error) {
      console.error('Failed to load server config:', error);
    }
  }

  async loadRepositoryCache() {
    try {
      const result = await chrome.storage.local.get(['repositoryCache']);
      if (result.repositoryCache) {
        this.repositories = new Map(Object.entries(result.repositoryCache));
      }
    } catch (error) {
      console.error('Failed to load repository cache:', error);
    }
  }

  async saveRepositoryCache() {
    try {
      const cacheObject = Object.fromEntries(this.repositories);
      await chrome.storage.local.set({ repositoryCache: cacheObject });
    } catch (error) {
      console.error('Failed to save repository cache:', error);
    }
  }

  // Create git repository for Google Drive folder
  async createRepository(folderInfo) {
    if (!this.serverConfig || !this.serverConfig.url) {
      throw new Error('Git server not configured. Please configure server first.');
    }

    const folderId = folderInfo.folderId || folderInfo.fileId;
    const folderName = folderInfo.folderName || folderInfo.fileName;

    // Check if repository already exists
    if (this.repositories.has(folderId)) {
      return this.repositories.get(folderId);
    }

    try {
      // Get Google Drive permissions for the folder
      const permissions = await this.getDrivePermissions(folderId);

      const repositoryData = {
        id: folderId,
        name: this.sanitizeRepositoryName(folderName),
        driveId: folderId,
        driveName: folderName,
        permissions: permissions,
        branches: ['main'],
        currentBranch: 'main',
        status: 'active',
        createdAt: new Date().toISOString(),
        lastSync: null
      };

      // Call git server API to create repository
      const response = await this.callGitServerAPI('POST', '/repositories', {
        name: repositoryData.name,
        driveId: folderId,
        permissions: permissions,
        private: true // Default to private as per Google Drive behavior
      });

      if (response.success) {
        repositoryData.remoteId = response.data.id;
        repositoryData.gitUrl = response.data.gitUrl;

        // Cache repository info
        this.repositories.set(folderId, repositoryData);
        await this.saveRepositoryCache();

        return repositoryData;
      } else {
        throw new Error(response.error || 'Failed to create repository');
      }
    } catch (error) {
      console.error('Repository creation failed:', error);
      throw new Error(`Failed to create repository: ${error.message}`);
    }
  }

  // Get Google Drive permissions using Drive API
  async getDrivePermissions(fileId) {
    try {
      // This would typically use the Google Drive API
      // For now, we'll simulate the permission structure
      const mockPermissions = [
        {
          emailAddress: 'current.user@lawfirm.com',
          role: 'owner',
          type: 'user'
        }
      ];

      return this.mapDrivePermissionsToGit(mockPermissions);
    } catch (error) {
      console.error('Failed to get Drive permissions:', error);
      return [];
    }
  }

  // Map Google Drive permissions to git repository permissions
  mapDrivePermissionsToGit(drivePermissions) {
    const gitPermissions = drivePermissions.map(permission => {
      const roleMap = {
        'owner': 'maintainer',
        'writer': 'developer',
        'commenter': 'reporter',
        'reader': 'guest'
      };

      return {
        email: permission.emailAddress,
        role: roleMap[permission.role] || 'guest',
        type: permission.type,
        inherited: permission.inherited || false
      };
    });

    return gitPermissions;
  }

  // Create commit with legal conventional commit format
  async createCommit(repositoryId, commitData) {
    const repository = this.repositories.get(repositoryId);
    if (!repository) {
      throw new Error('Repository not found. Please initialize repository first.');
    }

    // Validate legal conventional commit format
    const validatedCommit = this.validateLegalCommit(commitData);

    try {
      const response = await this.callGitServerAPI('POST', `/repositories/${repository.remoteId}/commits`, {
        message: validatedCommit.message,
        type: validatedCommit.type,
        description: validatedCommit.description,
        branch: validatedCommit.branch || repository.currentBranch,
        files: commitData.files || [],
        author: commitData.author || 'Unknown'
      });

      if (response.success) {
        // Update repository cache
        repository.lastSync = new Date().toISOString();
        repository.lastCommit = response.data.commitId;
        await this.saveRepositoryCache();

        return response.data;
      } else {
        throw new Error(response.error || 'Failed to create commit');
      }
    } catch (error) {
      console.error('Commit creation failed:', error);
      throw new Error(`Failed to create commit: ${error.message}`);
    }
  }

  // Validate and format legal conventional commit
  validateLegalCommit(commitData) {
    const legalCommitTypes = {
      'feat': 'New clauses/sections',
      'fix': 'Corrections/changes',
      'review': 'Incorporate feedback',
      'draft': 'Work in progress',
      'final': 'Ready for signature',
      'docs': 'Administrative updates',
      'redact': 'Remove confidential info',
      'merge': 'Combine multiple versions',
      'revert': 'Undo changes',
      'comment': 'Add internal notes/questions',
      'cite': 'Add legal citations/references',
      'format': 'Styling/layout changes only'
    };

    if (!commitData.type || !legalCommitTypes[commitData.type]) {
      throw new Error(`Invalid commit type. Must be one of: ${Object.keys(legalCommitTypes).join(', ')}`);
    }

    if (!commitData.description || commitData.description.length === 0) {
      throw new Error('Commit description is required');
    }

    if (commitData.description.length > 50) {
      throw new Error('Commit description must be 50 characters or less');
    }

    return {
      type: commitData.type,
      description: commitData.description,
      message: `${commitData.type}: ${commitData.description}`,
      branch: commitData.branch
    };
  }

  // Create or switch to branch
  async createBranch(repositoryId, branchName, fromBranch = 'main') {
    const repository = this.repositories.get(repositoryId);
    if (!repository) {
      throw new Error('Repository not found');
    }

    const sanitizedBranchName = this.sanitizeBranchName(branchName);

    try {
      const response = await this.callGitServerAPI('POST', `/repositories/${repository.remoteId}/branches`, {
        name: sanitizedBranchName,
        from: fromBranch
      });

      if (response.success) {
        // Update repository cache
        if (!repository.branches.includes(sanitizedBranchName)) {
          repository.branches.push(sanitizedBranchName);
        }
        repository.currentBranch = sanitizedBranchName;
        await this.saveRepositoryCache();

        return response.data;
      } else {
        throw new Error(response.error || 'Failed to create branch');
      }
    } catch (error) {
      console.error('Branch creation failed:', error);
      throw new Error(`Failed to create branch: ${error.message}`);
    }
  }

  // Switch to existing branch
  async switchBranch(repositoryId, branchName) {
    const repository = this.repositories.get(repositoryId);
    if (!repository) {
      throw new Error('Repository not found');
    }

    if (!repository.branches.includes(branchName)) {
      throw new Error(`Branch '${branchName}' does not exist`);
    }

    try {
      const response = await this.callGitServerAPI('POST', `/repositories/${repository.remoteId}/checkout`, {
        branch: branchName
      });

      if (response.success) {
        repository.currentBranch = branchName;
        await this.saveRepositoryCache();
        return response.data;
      } else {
        throw new Error(response.error || 'Failed to switch branch');
      }
    } catch (error) {
      console.error('Branch switch failed:', error);
      throw new Error(`Failed to switch branch: ${error.message}`);
    }
  }

  // Get repository status
  getRepositoryStatus(folderId) {
    return this.repositories.get(folderId) || null;
  }

  // Get all repositories
  getAllRepositories() {
    return Array.from(this.repositories.values());
  }

  // Utility: Sanitize repository name for git
  sanitizeRepositoryName(name) {
    return name
      .toLowerCase()
      .replace(/[^a-z0-9\-_]/g, '-')
      .replace(/--+/g, '-')
      .replace(/^-|-$/g, '')
      .substring(0, 50);
  }

  // Utility: Sanitize branch name for git
  sanitizeBranchName(name) {
    return name
      .toLowerCase()
      .replace(/[^a-z0-9\-_\/]/g, '-')
      .replace(/--+/g, '-')
      .replace(/^-|-$/g, '')
      .substring(0, 30);
  }

  // Call git server API
  async callGitServerAPI(method, endpoint, data = null) {
    if (!this.serverConfig || !this.serverConfig.url) {
      return {
        success: false,
        error: 'Git server not configured'
      };
    }

    try {
      const url = `${this.serverConfig.url}${endpoint}`;
      const options = {
        method: method,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.serverConfig.token}`
        }
      };

      if (data && (method === 'POST' || method === 'PUT')) {
        options.body = JSON.stringify(data);
      }

      // For Sprint 2, return mock responses since backend isn't ready
      return this.mockGitServerResponse(method, endpoint, data);

      // Actual implementation would be:
      // const response = await fetch(url, options);
      // return await response.json();
    } catch (error) {
      console.error('Git server API call failed:', error);
      return {
        success: false,
        error: error.message
      };
    }
  }

  // Mock git server responses for Sprint 2 development
  mockGitServerResponse(method, endpoint, data) {
    console.log(`Mock Git API: ${method} ${endpoint}`, data);

    if (endpoint === '/repositories' && method === 'POST') {
      return {
        success: true,
        data: {
          id: `repo_${Date.now()}`,
          name: data.name,
          gitUrl: `${this.serverConfig.url}/git/${data.name}.git`,
          created: new Date().toISOString()
        }
      };
    }

    if (endpoint.includes('/commits') && method === 'POST') {
      return {
        success: true,
        data: {
          commitId: `commit_${Date.now()}`,
          message: data.message,
          branch: data.branch,
          timestamp: new Date().toISOString()
        }
      };
    }

    if (endpoint.includes('/branches') && method === 'POST') {
      return {
        success: true,
        data: {
          name: data.name,
          created: new Date().toISOString()
        }
      };
    }

    if (endpoint.includes('/checkout') && method === 'POST') {
      return {
        success: true,
        data: {
          branch: data.branch,
          switched: new Date().toISOString()
        }
      };
    }

    return {
      success: true,
      data: { message: 'Mock response' }
    };
  }
}

// Export for use in other scripts
window.GitOperationsManager = GitOperationsManager;
