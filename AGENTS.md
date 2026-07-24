# Repository instructions

## Changelog

Update `CHANGELOG.md` with every user-visible, operational, security, API,
configuration, or dependency change.

- Add ongoing work beneath `## [Unreleased]`.
- Use the `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, and `Security`
  headings where applicable.
- Describe outcomes in concise, user-facing language.
- Do not add entries for formatting-only edits, comments, or test refactors
  that do not change behavior.
- When preparing a release, move the relevant entries into a versioned section
  formatted as `## [x.y.z] - YYYY-MM-DD`, then recreate an empty
  `## [Unreleased]` section.

## GitHub handoff

After every project update, include a GitHub-ready handoff in the final
response with:

- a concise summary suitable for a pull request title or summary field;
- a description of the user-visible and technical changes; and
- the validation or testing performed.
