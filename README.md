# Trunk - Git for Legal Documents

Trunk brings git-level version control to legal document management, enabling lawyers to track changes, manage conflicts, and maintain document history directly within Google Drive and Microsoft Office.

## 🚀 Quick Start

### Prerequisites
- Docker (for backend)
- Chrome browser (for extension)
- Google account with Drive access

### 1. Run the Backend

**Option A: Using Docker Compose (Recommended)**
```bash
# Copy environment template
cp .env.example .env
# Edit .env with your Google OAuth credentials

# Run the application
docker-compose -f docker-compose.prod.yml up -d
```

**Option B: Using Docker Run**
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

### 2. Install Chrome Extension

1. Download the latest release from [Releases](https://github.com/trunk/legal-git/releases)
2. Open Chrome and navigate to `chrome://extensions/`
3. Enable "Developer mode" (top right)
4. Click "Load unpacked" and select the `frontend` folder
5. The Trunk icon should appear in your toolbar

### 3. Start Tracking Documents

1. Open any Google Doc
2. Click the Trunk extension icon
3. Click "Track Document" to start version control
4. Make changes and commit them with descriptive messages

## ✨ Features

- **Version Control**: Full git-powered history for legal documents
- **Diff Visualization**: See exactly what changed between versions
- **Conflict Resolution**: Handle multiple editors with merge tools
- **Document Locking**: Reserve documents for exclusive editing
- **Bulk Operations**: Manage multiple documents at once
- **Legal Formatting**: Maintains formatting, track changes, and comments
- **Self-Hosted**: Your data stays on your infrastructure

## 🏗️ Architecture

Trunk uses a simplified, single-container architecture optimized for small to medium law firms:

- **Frontend**: Chrome extension for Google Docs/Drive integration
- **Backend**: FastAPI server with embedded git
- **Database**: SQLite for metadata and document tracking
- **Storage**: Local filesystem for git repositories

Memory footprint: < 256MB (runs on minimal infrastructure)

## 🔧 Configuration

Create a `.env` file with:

```env
# Google OAuth (required)
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret

# Optional
JWT_SECRET_KEY=your-secret-key
DATABASE_URL=sqlite:////data/db/trunk.db
```

## 📦 Development Setup

### Backend Development
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

### Frontend Development
```bash
cd frontend
# 1. Open Chrome and go to chrome://extensions/
# 2. Enable "Developer mode"
# 3. Click "Load unpacked"
# 4. Select the frontend directory
```

### Docker Development
```bash
# Development with hot reload
docker-compose up --build

# Production build
docker build -t trunk/legal-git:latest .
```

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Workflow
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📊 Current Status

- ✅ Core version control functionality
- ✅ Google Docs integration
- ✅ Conflict resolution
- ✅ Document locking
- ⚠️ Microsoft Office support (coming soon)
- ⚠️ Multi-user permissions (in development)

## 🔒 Security

- All data is stored locally on your server
- OAuth2 for Google authentication
- JWT tokens for API security
- No data is sent to external services

Report security issues to: security@trunk-legal.org

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

Built with ❤️ for the legal community by developers who understand the importance of document integrity and version control.

---

**Note**: This is an early release. While core features are stable, we recommend thorough testing before production use. Please report any issues on our [GitHub Issues](https://github.com/trunk/legal-git/issues) page.
