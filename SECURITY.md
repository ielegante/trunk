# Security Policy

## Reporting Security Vulnerabilities

The Trunk team takes security seriously. We appreciate your efforts to responsibly disclose your findings.

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report them via email to: security@trunk-legal.org

You should receive a response within 48 hours. If for some reason you do not, please follow up via email to ensure we received your original message.

Please include the following information:
- Type of issue (e.g., buffer overflow, SQL injection, cross-site scripting, etc.)
- Full paths of source file(s) related to the issue
- Location of the affected source code (tag/branch/commit or direct URL)
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the issue, including how an attacker might exploit it

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.9.x   | :white_check_mark: |
| < 0.9   | :x:                |

## Security Best Practices

When deploying Trunk:

1. **Always use HTTPS** for production deployments
2. **Change default secrets** in `.env` file
3. **Use strong JWT secret keys** (minimum 32 characters)
4. **Restrict CORS origins** to your specific domains
5. **Keep Docker images updated** with security patches
6. **Enable rate limiting** to prevent abuse
7. **Use OAuth2** instead of basic authentication
8. **Regularly backup** your data volume

## Known Security Considerations

- **Data Storage**: All document data is stored locally on your server
- **Authentication**: Uses Google OAuth2 for user authentication
- **API Security**: JWT tokens expire after 1 hour by default
- **File Access**: The application has access to the `/data` directory in Docker
- **Network**: Ensure firewall rules restrict access to port 8080

## Security Updates

Security updates will be released as:
- **Critical**: Within 24-48 hours
- **High**: Within 1 week
- **Medium**: Within 1 month
- **Low**: Next regular release

Subscribe to security announcements:
- Watch this repository with "Security alerts" enabled
- Join our security mailing list: security-announce@trunk-legal.org

## Acknowledgments

We thank the following people for responsibly disclosing security issues:
- *Your name could be here!*

## Contact

For any security-related questions, contact: security@trunk-legal.org

PGP Key: [Coming Soon]
