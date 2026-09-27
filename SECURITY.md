# Security Policy

## Reporting a vulnerability

Please report security vulnerabilities privately using GitHub's "Report a
vulnerability" feature (Security tab → Advisories) on this repository, or by
contacting the maintainer via their GitHub profile (@iamzayn19). Do not open
a public issue for security-sensitive reports.

We will acknowledge reports and work on a fix before public disclosure.

## Scope

- Image/file parsing (decompression bombs, malformed files, oversized inputs)
- Model download/verification (checksum bypass, path traversal into the
  model cache directory)
- Subprocess/protocol handling between the Python sidecar and JS/Ruby clients
- Dependency vulnerabilities (tracked via Dependabot and periodic audits)

## Out of scope

- OCR accuracy issues (not a security concern; file a regular issue)
- Vulnerabilities in third-party OCR backends upstream of this project
  (report to the upstream project, but let us know so we can track exposure)

## Supported versions

Pre-1.0: only the latest released version receives security fixes. After
1.0, a supported-versions table will be published here per the project's
semantic versioning policy.
