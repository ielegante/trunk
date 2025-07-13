# Legal Git Chrome Extension

A Chrome extension that brings git-level version control to legal document management in Google Drive.

## Features

- **Google Drive Integration**: Seamlessly integrates with Google Drive and Google Docs interfaces
- **Version Tracking**: Start tracking any document with a single click
- **Milestone Saving**: Save important document versions with descriptive commit messages
- **Document History**: View complete change history for tracked documents
- **Legal Conventional Commits**: Use legal-specific commit message types (feat, fix, review, draft, final, etc.)

## Installation (Development)

1. Clone this repository
2. Open Chrome and navigate to `chrome://extensions/`
3. Enable "Developer mode" in the top right
4. Click "Load unpacked" and select the `frontend` directory
5. The Legal Git extension should now appear in your extensions list

## Usage

### First Time Setup

1. Click the Legal Git extension icon in your browser toolbar
2. Click "Configure Git Server" and enter your git server details
3. Navigate to a Google Drive folder or Google Docs document

### Starting Version Control

1. In Google Drive, right-click on a file or use the Legal Git toolbar
2. Click "Start Version Tracking"
3. The document will now be tracked in your git repository

### Saving Milestones

1. Make changes to your tracked document
2. Click "Save Milestone" in the Legal Git toolbar
3. Enter a descriptive commit message using legal conventional commit format
4. Your changes are now saved as a git commit

### Viewing History

1. Click "View History" for any tracked document
2. Browse through previous versions and changes
3. See who made what changes and when

## Legal Conventional Commit Types

- `feat:` - New clauses/sections
- `fix:` - Corrections/changes
- `review:` - Incorporate feedback
- `draft:` - Work in progress
- `final:` - Ready for signature
- `docs:` - Administrative updates
- `redact:` - Remove confidential info
- `merge:` - Combine multiple versions
- `revert:` - Undo changes
- `comment:` - Add internal notes/questions
- `cite:` - Add legal citations/references
- `format:` - Styling/layout changes only

## Architecture

The extension consists of:

- **manifest.json**: Extension configuration and permissions
- **background.js**: Service worker for handling git operations and context menus
- **content-script.js**: Injected into Google Drive/Docs pages for UI integration
- **popup.html/js**: Extension popup for configuration and quick actions
- **styles.css**: Styling for injected UI elements

## Development

### File Structure

```
frontend/
├── manifest.json          # Extension manifest
├── background.js          # Service worker
├── content-script.js      # Content script for Drive/Docs
├── popup.html            # Extension popup UI
├── popup.js              # Popup functionality
├── styles.css            # Content script styles
├── icons/                # Extension icons
└── README.md             # This file
```

### Key Components

1. **Google Drive Detection**: Automatically detects when user is on Google Drive or Docs
2. **File Tracking**: Identifies and tracks document IDs and names
3. **UI Injection**: Adds Legal Git toolbar to Drive/Docs interface
4. **Git Operations**: Communicates with backend git server for version control
5. **Context Menus**: Right-click options for git operations

## Sprint 1 Implementation

This is the Sprint 1 MVP implementation focusing on:

- ✅ Chrome extension shell with Manifest v3
- ✅ Basic Google Drive integration and file detection
- ✅ Context menus for git operations
- ✅ Popup interface for configuration
- ✅ UI injection into Drive/Docs pages
- 🔄 GitHub repository setup (in progress)

## Next Steps (Future Sprints)

- Git server integration and authentication
- Document conversion pipeline (Google Docs ↔ Markdown)
- Conflict resolution interface
- Template management system
- Cross-document reference tracking

## License

AGPL v3 - See LICENSE file for details

## Contributing

See CONTRIBUTING.md for development guidelines and contribution process.
