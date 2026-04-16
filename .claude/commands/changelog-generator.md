# Changelog Generator Command

Generate and update CHANGELOG.md from git commit history.

## Instructions

Generate a changelog entry following these steps. Version argument (optional): **$ARGUMENTS**

1. **Gather Commit History**

   ```bash
   # Get the latest tag
   git describe --tags --abbrev=0 2>/dev/null || echo "no tags"

   # Get commits since last tag (or all commits if no tag)
   git log $(git describe --tags --abbrev=0 2>/dev/null)..HEAD --oneline --no-merges

   # If no tags exist, get all commits
   git log --oneline --no-merges
   ```

2. **Classify Commits by Type**

   Map commit prefixes to changelog sections:

   | Commit prefix | Changelog section |
   |---|---|
   | `feat:`, `feature:` | ### Added |
   | `fix:`, `bugfix:` | ### Fixed |
   | `refactor:`, `update:`, `change:` | ### Changed |
   | `remove:`, `delete:` | ### Removed |
   | `deprecate:` | ### Deprecated |
   | `security:`, `sec:` | ### Security |
   | `docs:`, `doc:` | ### Changed (documentation) |
   | `perf:` | ### Changed (performance) |

   Commits with no prefix: use judgment to classify by content.

3. **Determine Version**

   - If `$ARGUMENTS` contains a version number (e.g. `1.2.3` or `v1.2.3`), use it as the release version.
   - If no version is given, use `[Unreleased]`.
   - Follow Semantic Versioning:
     - Breaking changes → MAJOR
     - New features → MINOR
     - Bug fixes only → PATCH

4. **Generate Changelog Entry**

   Use [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format:

   ```markdown
   ## [VERSION] - YYYY-MM-DD

   ### Added
   - Description of new feature (#issue or commit hash)

   ### Changed
   - Description of change

   ### Deprecated
   - Description of deprecated feature

   ### Removed
   - Description of removed feature

   ### Fixed
   - Description of bug fix

   ### Security
   - Description of security improvement
   ```

   Rules:
   - Omit sections that have no entries.
   - Write entries in plain language focused on user impact, not implementation detail.
   - Include issue or PR number if referenced in commit message.

5. **Update CHANGELOG.md**

   - If `CHANGELOG.md` does not exist, create it with a header:

     ```markdown
     # Changelog

     All notable changes to this project will be documented in this file.

     The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
     and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
     ```

   - Insert the new entry immediately after the header (or after `## [Unreleased]` if it exists).
   - Do not delete or overwrite existing entries.

6. **Summary**

   After updating CHANGELOG.md, report:
   - Number of commits processed
   - Version recorded
   - Sections included
   - Path to CHANGELOG.md
