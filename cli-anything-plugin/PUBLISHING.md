# Publishing the cli-anything Plugin

This guide explains how to make the cli-anything plugin installable and publish it.

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

Package as a tarball:
```bash
cd /root/cli-anything
tar -czf cli-anything-plugin-v1.0.0.tar.gz cli-anything-plugin/
```

Others can install:
```bash
cd ~/.claude/plugins
tar -xzf cli-anything-plugin-v1.0.0.tar.gz
```

## Option 2: GitHub Repository (Recommended)

### 1. Create GitHub Repository

```bash
cd /root/cli-anything/cli-anything-plugin

# Initialize git
git init
git add .
git commit -m "Initial commit: cli-anything plugin v1.0.0"

# Create repo on GitHub (via web or gh CLI)
gh repo create cli-anything-plugin --public --source=. --remote=origin

# Push
git push -u origin main
```

### 2. Create Release

```bash
# Tag the release
git tag -a v1.0.0 -m "Release v1.0.0: Initial release"
git push origin v1.0.0

# Create GitHub release
gh release create v1.0.0 \
  --title "cli-anything Plugin v1.0.0" \
  --notes "Initial release with 4 commands and complete 6-phase methodology"
```

### 3. Install from GitHub

Users can install directly:
```bash
cd ~/.claude/plugins
git clone https://github.com/yourusername/cli-anything-plugin.git
```

Or via Claude Code (if you set up a plugin registry):
```bash
/plugin install cli-anything@github:yourusername/cli-anything-plugin
```

## Option 3: Claude Plugin Directory (Official)

To publish to the official Claude Plugin Directory:

### 1. Prepare for Submission

Ensure your plugin meets requirements:
- ✅ Complete `plugin.json` with all metadata
- ✅ Comprehensive README.md
- ✅ LICENSE file (MIT recommended)
- ✅ All commands documented
- ✅ No security vulnerabilities
- ✅ Tested and working

### 2. Submit to External Plugins

1. **Fork the official repository:**
   ```bash
   gh repo fork anthropics/claude-plugins-official
   ```

2. **Add your plugin to external_plugins:**
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

4. **Fill out submission form:**
   - Visit: https://forms.anthropic.com/claude-plugin-submission
   - Provide plugin details
   - Link to your PR

### 3. Review Process

Anthropic will review:
- Code quality and security
- Documentation completeness
- Functionality and usefulness
- Compliance with plugin standards

Approval typically takes 1-2 weeks.

### 4. After Approval

Users can install via:
```bash
/plugin install cli-anything@claude-plugin-directory
```

## Option 4: NPM Package (Alternative)

If you want to distribute via npm:

### 1. Create package.json

```json
{
  "name": "@yourusername/cli-anything-plugin",
  "version": "1.0.0",
  "description": "Claude Code plugin for building CLI harnesses",
  "main": ".claude-plugin/plugin.json",
  "scripts": {
    "install": "bash scripts/setup-cli-anything.sh"
  },
  "keywords": ["claude-code", "plugin", "cli", "harness"],
  "author": "Your Name",
  "license": "MIT",
  "repository": {
    "type": "git",
    "url": "https://github.com/yourusername/cli-anything-plugin.git"
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

## Versioning

Follow semantic versioning (semver):
- **Major** (1.0.0 → 2.0.0): Breaking changes
- **Minor** (1.0.0 → 1.1.0): New features, backward compatible
- **Patch** (1.0.0 → 1.0.1): Bug fixes

Update version in:
- `.claude-plugin/plugin.json`
- `README.md`
- Git tags

## Distribution Checklist

Before publishing:

- [ ] All commands tested and working
- [ ] README.md is comprehensive
- [ ] LICENSE file included
- [ ] plugin.json has correct metadata
- [ ] No hardcoded paths or credentials
- [ ] Scripts are executable (`chmod +x`)
- [ ] Documentation is up to date
- [ ] Version number is correct
- [ ] Git repository is clean
- [ ] Tests pass (if applicable)

## Maintenance

### Updating the Plugin

1. Make changes
2. Update version in `plugin.json`
3. Update CHANGELOG.md
4. Commit and tag:
   ```bash
   git commit -am "Release v1.1.0: Add new features"
   git tag v1.1.0
   git push origin main --tags
   ```
5. Create GitHub release
6. Notify users of update

### Deprecation

If deprecating:
1. Mark as deprecated in `plugin.json`
2. Update README with deprecation notice
3. Provide migration path
4. Keep available for 6 months minimum

## Support

### Documentation

- Keep README.md updated
- Document breaking changes
- Provide migration guides

### Issue Tracking

Use GitHub Issues for:
- Bug reports
- Feature requests
- Questions

### Community

- Respond to issues promptly
- Accept pull requests
- Credit contributors

## Security

### Reporting Vulnerabilities

Create SECURITY.md:
```markdown
# Security Policy

## Reporting a Vulnerability

Email: security@yourdomain.com

Please do not open public issues for security vulnerabilities.
```

### Best Practices

- No credentials in code
- Validate all inputs
- Use secure dependencies
- Regular security audits

## Legal

### License

MIT License allows:
- Commercial use
- Modification
- Distribution
- Private use

Requires:
- License and copyright notice

### Trademark

If using "Claude" or "Anthropic":
- Follow brand guidelines
- Don't imply official endorsement
- Use "for Claude Code" not "Claude's plugin"

## Resources

- Claude Code Plugin Docs: https://code.claude.com/docs/en/plugins
- Plugin Directory: https://github.com/anthropics/claude-plugins-official
- Submission Form: https://forms.anthropic.com/claude-plugin-submission
- Community: Claude Code Discord/Forum

## Questions?

- GitHub Issues: https://github.com/yourusername/cli-anything-plugin/issues
- Email: your-email@example.com
- Discord: Your Discord handle
