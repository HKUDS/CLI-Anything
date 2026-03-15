# Publishing the cli-anything Plugin

This comprehensive guide explains how to make the cli-anything plugin installable and publish it through various distribution channels.

## Option 1: Local Installation (Development)

### For Testing

1. **Copy to Claude Code plugins directory:**
   ```bash
   cp -r /root/cli-anything/cli-anything-plugin ~/.claude/plugins/cli-anything
   ```

2. **Reload plugins in Claude Code:**
   ```bash
   /reload-plugins
   ```

3. **Verify installation:**
   ```bash
   /help cli-anything
   ```

### For Sharing Locally

Package as a tarball for easy distribution:
```bash
cd /root/cli-anything
tar -czf cli-anything-plugin-v1.0.0.tar.gz cli-anything-plugin/
```

Others can install by extracting:
```bash
cd ~/.claude/plugins
tar -xzf cli-anything-plugin-v1.0.0.tar.gz
```

## Option 2: GitHub Repository (Recommended)

### 1. Create GitHub Repository

```bash
cd /root/cli-anything/cli-anything-plugin

# Initialize git repository
git init
git add .
git commit -m "Initial commit: cli-anything plugin v1.0.0"

# Create repository on GitHub (via web interface or gh CLI)
gh repo create cli-anything-plugin --public --source=. --remote=origin

# Push to remote repository
git push -u origin main
```

### 2. Create Release

```bash
# Tag the release with semantic version
git tag -a v1.0.0 -m "Release v1.0.0: Initial release"
git push origin v1.0.0

# Create GitHub release with detailed notes
gh release create v1.0.0 \
  --title "cli-anything Plugin v1.0.0" \
  --notes "Initial release with 4 commands and complete 6-phase methodology"
```

### 3. Install from GitHub

Users can install directly from the repository:
```bash
cd ~/.claude/plugins
git clone https://github.com/yourusername/cli-anything-plugin.git
```

Or via Claude Code (if plugin registry is configured):
```bash
/plugin install cli-anything@github:yourusername/cli-anything-plugin
```

## Option 3: Claude Plugin Directory (Official)

To publish to the official Claude Plugin Directory for maximum visibility:

### 1. Prepare for Submission

Ensure your plugin meets all requirements:
- ✅ Complete `plugin.json` with all required metadata
- ✅ Comprehensive README.md with usage examples
- ✅ LICENSE file (MIT recommended for compatibility)
- ✅ All commands documented with examples
- ✅ No security vulnerabilities or hardcoded credentials
- ✅ Thoroughly tested and working

### 2. Submit to External Plugins

1. **Fork the official repository:**
   ```bash
   gh repo fork anthropics/claude-plugins-official
   ```

2. **Add your plugin to external_plugins directory:**
   ```bash
   cd claude-plugins-official
   mkdir -p external_plugins/cli-anything
   cp -r /root/cli-anything/cli-anything-plugin/* external_plugins/cli-anything/
   ```

3. **Create pull request:**
   ```bash
   git checkout -b add-cli-anything-plugin
   git add external_plugins/cli-anything
   git commit -m "Add cli-anything plugin to external plugins"
   git push origin add-cli-anything-plugin
   gh pr create --title "Add cli-anything plugin" \
     --body "Adds cli-anything plugin for building CLI harnesses for GUI applications"
   ```

4. **Complete submission form:**
   - Visit: https://forms.anthropic.com/claude-plugin-submission
   - Provide detailed plugin information
   - Link to your pull request

### 3. Review Process

Anthropic will review for:
- Code quality and security standards
- Documentation completeness
- Functionality and usefulness to community
- Compliance with plugin development standards

Approval typically takes 1-2 weeks for review and feedback.

### 4. After Approval

Users can install via the official directory:
```bash
/plugin install cli-anything@claude-plugin-directory
```

## Option 4: NPM Package (Alternative)

If you prefer npm-based distribution:

### 1. Create package.json

```json
{
  "name": "@yourusername/cli-anything-plugin",
  "version": "1.0.0",
  "description": "Claude Code plugin for building CLI harnesses for GUI applications",
  "main": ".claude-plugin/plugin.json",
  "scripts": {
    "install": "bash scripts/setup-cli-anything.sh"
  },
  "keywords": ["claude-code", "plugin", "cli", "harness", "automation"],
  "author": "Your Name <your-email@example.com>",
  "license": "MIT",
  "repository": {
    "type": "git",
    "url": "https://github.com/yourusername/cli-anything-plugin.git"
  },
  "bugs": {
    "url": "https://github.com/yourusername/cli-anything-plugin/issues"
  }
}
```

### 2. Publish to npm

```bash
npm login
npm publish --access public
```

### 3. Install via npm

```bash
cd ~/.claude/plugins
npm install @yourusername/cli-anything-plugin
```

## Versioning Strategy

Follow semantic versioning (semver) for consistent releases:
- **Major** (1.0.0 → 2.0.0): Breaking changes that require user action
- **Minor** (1.0.0 → 1.1.0): New features that are backward compatible
- **Patch** (1.0.0 → 1.0.1): Bug fixes and minor improvements

Update version consistently in:
- `.claude-plugin/plugin.json`
- `README.md` installation examples
- Git tags and releases

## Pre-Publication Checklist

Before publishing to any platform:

- [ ] All commands tested and working correctly
- [ ] README.md is comprehensive with clear examples
- [ ] LICENSE file included (MIT recommended)
- [ ] plugin.json has correct metadata and version
- [ ] No hardcoded paths, credentials, or sensitive data
- [ ] All shell scripts are executable (`chmod +x`)
- [ ] Documentation is up to date and accurate
- [ ] Version number is correct across all files
- [ ] Git repository is clean with no uncommitted changes
- [ ] Tests pass (if applicable)
- [ ] Security review completed

## Maintenance and Updates

### Updating the Plugin

1. Make and test changes thoroughly
2. Update version in `plugin.json`
3. Document changes in CHANGELOG.md
4. Commit and tag the release:
   ```bash
   git commit -am "Release v1.1.0: Add new features and improvements"
   git tag v1.1.0
   git push origin main --tags
   ```
5. Create GitHub release with detailed notes
6. Notify users through appropriate channels

### Deprecation Process

If deprecating the plugin:
1. Mark as deprecated in `plugin.json`
2. Update README with clear deprecation notice
3. Provide migration path to alternatives
4. Keep plugin available for minimum 6 months
5. Communicate timeline to users

## Support and Community

### Documentation Maintenance

- Keep README.md updated with latest features
- Document all breaking changes clearly
- Provide comprehensive migration guides
- Include troubleshooting section

### Issue Management

Use GitHub Issues effectively for:
- Bug reports with clear reproduction steps
- Feature requests from community
- General questions and support
- Community discussions

### Community Engagement

- Respond to issues and PRs promptly
- Accept and review community pull requests
- Credit all contributors appropriately
- Foster welcoming community environment

## Security Considerations

### Vulnerability Reporting

Create SECURITY.md file:
```markdown
# Security Policy

## Reporting a Vulnerability

Email: security@yourdomain.com

Please do not open public issues for security vulnerabilities.
We will respond within 48 hours with next steps.
```

### Security Best Practices

- Never include credentials or API keys in code
- Validate and sanitize all user inputs
- Use secure, up-to-date dependencies
- Conduct regular security audits
- Follow principle of least privilege

## Legal and Compliance

### License Selection

MIT License is recommended as it allows:
- Commercial use without restrictions
- Modification and distribution
- Private use in proprietary projects

Requirements:
- Include license and copyright notice
- Credit original authors

### Trademark Considerations

When using "Claude" or "Anthropic" in marketing:
- Follow official brand guidelines
- Don't imply official endorsement
- Use "for Claude Code" not "Claude's official plugin"
- Respect trademark rights

## Helpful Resources

- [Claude Code Plugin Documentation](https://code.claude.com/docs/en/plugins)
- [Official Plugin Directory](https://github.com/anthropics/claude-plugins-official)
- [Plugin Submission Form](https://forms.anthropic.com/claude-plugin-submission)
- [Community Discord/Forum](https://discord.gg/claude-code)

## Getting Help

For questions or support:

- **GitHub Issues**: https://github.com/yourusername/cli-anything-plugin/issues
- **Email**: your-email@example.com
- **Discord**: Your Discord handle
- **Community Forum**: Link to relevant forum