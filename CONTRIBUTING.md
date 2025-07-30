# Contributing to Trunk

Thank you for your interest in contributing to Trunk! We welcome contributions from the community and are grateful for any help you can provide.

## Code of Conduct

By participating in this project, you agree to abide by our Code of Conduct:
- Be respectful and inclusive
- Welcome newcomers and help them get started
- Focus on constructive criticism
- Respect differing viewpoints and experiences

## How to Contribute

### Reporting Issues

Before creating an issue, please check if it already exists. If not, create a new issue with:
- Clear, descriptive title
- Steps to reproduce (for bugs)
- Expected vs actual behavior
- Your environment (OS, browser version, etc.)
- Screenshots if applicable

### Suggesting Features

We love feature suggestions! Please:
- Check if the feature has already been requested
- Explain the use case (especially from a lawyer's perspective)
- Describe how it would work
- Consider if it aligns with our goal of simple, self-hosted deployment

### Pull Requests

1. **Fork and Clone**
   ```bash
   git clone https://github.com/your-username/trunk.git
   cd trunk
   ```

2. **Create a Branch**
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/issue-number
   ```

3. **Make Your Changes**
   - Follow the existing code style
   - Add tests for new functionality
   - Update documentation as needed
   - Ensure all tests pass

4. **Commit Your Changes**
   ```bash
   git add .
   git commit -m "feat: add document comparison feature"
   ```

   We use [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat:` New feature
   - `fix:` Bug fix
   - `docs:` Documentation changes
   - `style:` Code style changes (formatting, etc.)
   - `refactor:` Code refactoring
   - `test:` Test additions or corrections
   - `chore:` Maintenance tasks

5. **Push and Create PR**
   ```bash
   git push origin feature/your-feature-name
   ```
   Then create a Pull Request on GitHub.

## Development Setup

### Backend Development
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt  # For testing tools
```

### Frontend Development
```bash
cd frontend
# Load as unpacked extension in Chrome
# Navigate to chrome://extensions/
# Enable Developer mode
# Click "Load unpacked" and select the frontend directory
```

### Running Tests

#### Backend Tests
```bash
cd backend
pytest
```

#### Frontend Tests
```bash
cd frontend
# Manual testing in Chrome for now
# Automated tests coming soon
```

## Architecture Overview

- **Frontend**: Chrome extension using Manifest V3
  - Content scripts for Google Docs integration
  - Background service worker for git operations
  - Popup UI for quick actions

- **Backend**: FastAPI application
  - RESTful API for document operations
  - Embedded git server
  - SQLite for metadata storage
  - JWT authentication

- **Document Processing**: Conversion pipeline
  - Google Docs ↔ Markdown conversion
  - Diff generation and visualization
  - Conflict resolution algorithms

## Style Guidelines

### Python (Backend)
- Follow PEP 8
- Use type hints where possible
- Maximum line length: 88 characters (Black formatter)
- Docstrings for all public functions

### JavaScript (Frontend)
- Use ES6+ features
- Async/await over promises
- Descriptive variable names
- JSDoc comments for functions

## Getting Help

- Join our [Discord server](https://discord.gg/trunk-legal)
- Check the [documentation](https://docs.trunk-legal.org)
- Ask questions in GitHub Discussions
- Email: developers@trunk-legal.org

## Recognition

Contributors will be recognized in:
- The project README
- Release notes
- Our website's contributors page

Thank you for helping make legal document management better! 🎉
