# Changelog

## [1.0.1] - Pulumi Backend & Configuration Updates

### Added
- ✅ Pulumi S3 backend login command to all scripts and documentation
- ✅ New comprehensive guide: `docs/PULUMI_BACKEND.md`
- ✅ Automatic Pulumi backend login in `scripts/deploy.sh`
- ✅ Updated all config references to use proper namespace (`github-runners:*`)

### Changed
- ✅ AWS Account ID updated from `728293958233` to `058264302180` across all files
- ✅ Default runner count changed from 100 to 10 in `Pulumi.yaml`
- ✅ Default CPU changed from 2048 to 1024 in `Pulumi.yaml`
- ✅ Default memory changed from 4096 to 2048 in `Pulumi.yaml`
- ✅ Pulumi configuration now uses namespaced keys:
  - `github_token` → `github-runners:github_token`
  - `runner_count` → `github-runners:runner_count`
  - `cpu` → `github-runners:cpu`
  - `memory` → `github-runners:memory`

### Fixed
- ✅ Pulumi configuration error: Removed invalid `default` attribute for `aws:region`
- ✅ Updated `__main__.py` to use namespaced config
- ✅ Updated all deployment scripts to use correct config keys
- ✅ Updated GitHub Actions workflow to use correct config keys
- ✅ Fixed config references in all documentation

### Documentation Updates
- ✅ `README.md` - Added Pulumi backend login steps and config namespace note
- ✅ `QUICKSTART.md` - Added Pulumi backend login command
- ✅ `SETUP.md` - Updated with backend login information
- ✅ `DEPLOYMENT_SUMMARY.md` - Added backend login to deployment steps
- ✅ `ARCHITECTURE.md` - Updated AWS account ID
- ✅ `docs/FAQ.md` - Updated all config commands with proper namespacing
- ✅ `INDEX.md` - Added reference to PULUMI_BACKEND.md
- ✅ `scripts/deploy.sh` - Added automatic backend login
- ✅ `scripts/update-runner-count.sh` - Updated config key
- ✅ `scripts/build-and-push.sh` - Updated AWS account ID
- ✅ `scripts/check-status.sh` - Updated AWS account ID
- ✅ `scripts/full-deploy.sh` - Updated AWS account ID
- ✅ `.github/workflows/deploy-github-runners.yml` - Updated config keys

### Pulumi Backend Command

All scripts and documentation now include:

```bash
pulumi login s3://pulumi-backend-058264302180/github-runners
```

Or with environment variable:

```bash
export AWS_ACCOUNT_ID=058264302180
pulumi login s3://pulumi-backend-${AWS_ACCOUNT_ID}/github-runners
```

### Configuration Commands

Updated syntax for all config operations:

```bash
# Set GitHub token
pulumi config set --secret github-runners:github_token <token>

# Set runner count
pulumi config set github-runners:runner_count 100

# Set CPU/memory
pulumi config set github-runners:cpu 2048
pulumi config set github-runners:memory 4096

# View config
pulumi config get github-runners:github_token
```

## [1.0.0] - Initial Release

### Added
- Initial infrastructure for 100 GitHub self-hosted runners
- Pulumi-based deployment with Python
- Comprehensive documentation (8 guides)
- Automated deployment scripts (5 scripts)
- GitHub Actions CI/CD workflow
- Ruby 3.2.6 pre-installed in runners
- Ephemeral runner configuration
- CloudWatch logging integration
- Secrets Manager integration for GitHub token
- ECR repository with lifecycle policies
- IAM roles with least-privilege access

### Features
- 100 ephemeral runners on AWS ECS Fargate
- Pre-configured with Ruby 3.2.6
- Label: `ecs` for workflow targeting
- Auto-recovery via ECS
- Centralized logging
- Secure secrets management
- Infrastructure as Code

---

**For full documentation**, see [INDEX.md](INDEX.md)

