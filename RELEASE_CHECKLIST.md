# Release Checklist for Trunk Legal Git

## 🚀 Pre-Release Testing

### 1. Test Docker Build
```bash
# Build the Docker image
docker build -t trunk/legal-git:test .

# Run the container
docker run -d \
  --name trunk-test \
  -p 8080:8080 \
  -e JWT_SECRET_KEY=test-secret-key-123 \
  -e GOOGLE_CLIENT_ID=test-client-id \
  -e GOOGLE_CLIENT_SECRET=test-secret \
  trunk/legal-git:test

# Check logs
docker logs trunk-test

# Test health endpoint
curl http://localhost:8080/health

# Clean up
docker stop trunk-test && docker rm trunk-test
```

### 2. Test Chrome Extension
- [ ] Open Chrome and navigate to `chrome://extensions/`
- [ ] Enable "Developer mode"
- [ ] Click "Load unpacked" and select `frontend/` directory
- [ ] Verify extension icon appears in toolbar
- [ ] Open Developer Tools and check for console errors
- [ ] Click extension popup - should open without errors
- [ ] Check that all UI elements render correctly

### 3. Basic Integration Test
- [ ] Extension connects to backend at http://localhost:8080
- [ ] Can configure server settings in popup
- [ ] Open a Google Doc
- [ ] Click "Track Document" - should succeed
- [ ] Make a change and commit
- [ ] View commit history

## 📋 Final Security Audit

### Critical Security Checklist
- [ ] No hardcoded JWT_SECRET_KEY anywhere
- [ ] All example emails use @example.com domain
- [ ] No personal names or company information
- [ ] No internal URLs or endpoints
- [ ] No API keys or secrets in code
- [ ] Production.env has safe placeholders only
- [ ] .env.example has clear instructions

## 🏷️ Git Release Process

### 1. Final Commit
```bash
# Add all files
git add -A

# Commit with comprehensive message
git commit -m "feat: initial open source release - trunk legal git v0.9.0

- Complete Chrome extension for Google Docs integration
- Self-hosted backend with single Docker container
- SQLite database for simple deployment
- Document version control with git
- Conflict resolution and merge tools
- Built for small to medium law firms
- Memory footprint < 256MB

Co-authored-by: Project Team <team@trunk-legal.org>"
```

### 2. Push to GitHub
```bash
# Add GitHub remote (already exists for you)
git remote add github https://github.com/ielegante/trunk.git

# Push to main branch
git push github integration/sprint-1:main
```

### 3. Create GitHub Release
```bash
# Create and push tag
git tag -a v0.9.0-beta -m "Beta release - Trunk Legal Git"
git push github v0.9.0-beta
```

Then on GitHub:
1. Go to https://github.com/ielegante/trunk/releases/new
2. Choose tag: `v0.9.0-beta`
3. Release title: "Trunk Legal Git v0.9.0-beta - Open Source Release"
4. Check "This is a pre-release"

### 4. Release Notes Template
```markdown
# Trunk Legal Git v0.9.0-beta

We're excited to announce the first public release of Trunk Legal Git - bringing git-level version control to legal document management.

## 🎯 What is Trunk?

Trunk enables lawyers to:
- Track changes in legal documents with git-level precision
- Manage document versions directly in Google Drive
- Resolve conflicts when multiple people edit documents
- Maintain complete audit trails for compliance
- Self-host on minimal infrastructure (< 256MB RAM)

## ✨ Key Features

- **Chrome Extension**: Seamless Google Docs integration
- **Version Control**: Full git history for every document
- **Conflict Resolution**: Smart three-way merge for legal documents
- **Document Locking**: Reserve documents for exclusive editing
- **Self-Hosted**: Complete control over your data
- **Lightweight**: Runs on minimal infrastructure

## 🚀 Quick Start

1. **Run the Backend**:
   ```bash
   docker run -d \
     --name trunk-legal \
     -p 8080:8080 \
     -v trunk-data:/data \
     -e GOOGLE_CLIENT_ID=your-client-id \
     -e GOOGLE_CLIENT_SECRET=your-client-secret \
     -e JWT_SECRET_KEY=$(openssl rand -hex 32) \
     trunk/legal-git:latest
   ```

2. **Install Chrome Extension**:
   - Download from releases
   - Load as unpacked extension
   - Start tracking documents!

## 📦 What's Included

- Complete Chrome extension (25+ JavaScript modules)
- FastAPI backend with SQLite database
- Document processing pipeline
- Docker deployment ready
- Comprehensive documentation

## ⚠️ Beta Limitations

- Microsoft Office support coming soon
- Advanced permissions not yet implemented
- Limited to 100 documents in beta

## 🤝 Contributing

We welcome contributions! This is an open source project built for the legal community. See CONTRIBUTING.md for guidelines.

## 📣 Feedback

Please report issues or suggest features: https://github.com/ielegante/trunk/issues

## 🙏 Acknowledgments

Built with ❤️ for the legal community. Special thanks to all contributors who made this possible.

---

**Note**: This is a beta release. While core features are stable, please test thoroughly before production use.
```

## 📦 Post-Release Actions

### 1. Docker Hub Publication
```bash
# Tag for Docker Hub
docker tag trunk/legal-git:latest yourdockerhub/trunk-legal-git:0.9.0-beta
docker tag trunk/legal-git:latest yourdockerhub/trunk-legal-git:latest

# Push to Docker Hub
docker push yourdockerhub/trunk-legal-git:0.9.0-beta
docker push yourdockerhub/trunk-legal-git:latest
```

### 2. Enable GitHub Features
- [ ] Enable Issues
- [ ] Enable Discussions
- [ ] Enable Wiki (optional)
- [ ] Set up branch protection for main
- [ ] Add topics: legal-tech, chrome-extension, version-control, self-hosted

### 3. Community Setup
- [ ] Create issue templates (bug report, feature request)
- [ ] Pin an issue for "Welcome - Start Here"
- [ ] Create discussion categories (Q&A, Ideas, Show and Tell)

## 🎯 Launch Promotion

### Week 1
- [ ] Post on LinkedIn with demo video
- [ ] Share in legal tech communities
- [ ] Submit to:
  - [ ] Hacker News
  - [ ] r/legaltech
  - [ ] r/selfhosted
  - [ ] Legal tech newsletters

### Week 2
- [ ] Write blog post: "Why We Built Trunk"
- [ ] Create landing page
- [ ] Reach out to legal tech influencers
- [ ] Submit to Product Hunt

## 📊 Success Metrics

Track these in the first month:
- [ ] GitHub stars
- [ ] Docker pulls
- [ ] Issues opened (engagement)
- [ ] Community contributions
- [ ] User feedback

## 🚨 Emergency Contacts

If critical issues arise:
- Security issues: Create private security advisory on GitHub
- Major bugs: Pin issue and provide workaround
- Infrastructure: Have backup Docker registry ready

---

## ✅ Final Checklist

Before making repository public:
- [ ] All tests pass
- [ ] Docker image builds
- [ ] Extension loads without errors
- [ ] No secrets in code
- [ ] Documentation complete
- [ ] License file present
- [ ] Contributing guidelines clear

**Repository URL**: https://github.com/ielegante/trunk

🎉 **Ready to Launch!**
