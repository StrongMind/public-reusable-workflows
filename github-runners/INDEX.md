# GitHub Runners Documentation Index

This index helps you find the right documentation for your needs.

## 🎯 Quick Navigation

### I want to...

#### Get Started Immediately
→ **[QUICKSTART.md](QUICKSTART.md)** - 5-minute deployment guide

#### Understand What Was Built
→ **[DEPLOYMENT_SUMMARY.md](DEPLOYMENT_SUMMARY.md)** - Overview of all components

#### Follow Step-by-Step Instructions
→ **[SETUP.md](SETUP.md)** - Detailed setup walkthrough

#### Learn About the Architecture
→ **[ARCHITECTURE.md](ARCHITECTURE.md)** - System design and components

#### Find Complete Reference
→ **[README.md](README.md)** - Comprehensive documentation

#### Troubleshoot Issues
→ **[docs/FAQ.md](docs/FAQ.md)** - Common questions and solutions

## 📚 Documentation Files

| File | Purpose | When to Read |
|------|---------|--------------|
| **QUICKSTART.md** | Get running in 5 minutes | You're ready to deploy now |
| **DEPLOYMENT_SUMMARY.md** | Overview of what's included | You want to understand what you're getting |
| **SETUP.md** | Detailed setup instructions | You need step-by-step guidance |
| **ARCHITECTURE.md** | Technical architecture | You need to understand how it works |
| **README.md** | Complete reference | You need detailed information |
| **FAQ.md** | Questions and answers | You have a specific question |
| **PULUMI_BACKEND.md** | Pulumi state backend setup | You need to configure Pulumi backend |
| **INDEX.md** | This file | You're not sure where to start |

## 🔧 Script Files

| Script | Purpose | Usage |
|--------|---------|-------|
| **full-deploy.sh** | Complete deployment | First-time setup or full redeploy |
| **build-and-push.sh** | Build Docker image | After modifying Dockerfile |
| **deploy.sh** | Deploy infrastructure | After image is already built |
| **update-runner-count.sh** | Change runner count | Scaling up or down |
| **check-status.sh** | View current status | Monitoring and verification |

## 🎓 Learning Path

### Beginner
1. Read [QUICKSTART.md](QUICKSTART.md) to deploy
2. Review [DEPLOYMENT_SUMMARY.md](DEPLOYMENT_SUMMARY.md) to understand what you deployed
3. Check [docs/FAQ.md](docs/FAQ.md) for common issues

### Intermediate
1. Study [SETUP.md](SETUP.md) for detailed operations
2. Read [README.md](README.md) for configuration options
3. Learn about scaling and cost optimization

### Advanced
1. Study [ARCHITECTURE.md](ARCHITECTURE.md) for system design
2. Customize infrastructure in `__main__.py`
3. Implement auto-scaling and monitoring

## 📖 By Use Case

### First-Time Deployment
1. [QUICKSTART.md](QUICKSTART.md) - Quick deployment
2. [docs/PULUMI_BACKEND.md](docs/PULUMI_BACKEND.md) - Pulumi backend setup
3. [SETUP.md](SETUP.md) - Detailed steps
4. **Script**: `./scripts/full-deploy.sh`

### Understanding the System
1. [DEPLOYMENT_SUMMARY.md](DEPLOYMENT_SUMMARY.md) - What's included
2. [ARCHITECTURE.md](ARCHITECTURE.md) - How it works
3. [README.md](README.md) - Complete details

### Troubleshooting
1. [docs/FAQ.md](docs/FAQ.md) - Common issues
2. **Script**: `./scripts/check-status.sh`
3. [SETUP.md](SETUP.md) - Troubleshooting section

### Scaling and Optimization
1. [ARCHITECTURE.md](ARCHITECTURE.md) - Scaling section
2. [README.md](README.md) - Configuration options
3. **Script**: `./scripts/update-runner-count.sh`

### Monitoring
1. [SETUP.md](SETUP.md) - Monitoring section
2. **Script**: `./scripts/check-status.sh`
3. [docs/FAQ.md](docs/FAQ.md) - Monitoring questions

### Cost Management
1. [ARCHITECTURE.md](ARCHITECTURE.md) - Cost analysis
2. [docs/FAQ.md](docs/FAQ.md) - Cost questions
3. [DEPLOYMENT_SUMMARY.md](DEPLOYMENT_SUMMARY.md) - Cost estimates

## 🆘 Quick Help

### Problem: Runners not showing up in GitHub
→ [docs/FAQ.md](docs/FAQ.md#q-runners-arent-showing-up-in-github)

### Problem: Tasks failing to start
→ [docs/FAQ.md](docs/FAQ.md#q-tasks-keep-failing-to-start)

### Problem: Need Docker support
→ [docs/FAQ.md](docs/FAQ.md#q-can-i-run-docker-commands-in-the-runners)

### Problem: Too expensive
→ [ARCHITECTURE.md](ARCHITECTURE.md#cost-optimization-options)

### Problem: Not sure what to configure
→ [README.md](README.md#configuration)

### Problem: Pulumi backend issues
→ [docs/PULUMI_BACKEND.md](docs/PULUMI_BACKEND.md)

## 🔗 External Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [AWS ECS Fargate](https://aws.amazon.com/fargate/)
- [Pulumi Documentation](https://www.pulumi.com/docs/)
- [myoung34/github-runner](https://github.com/myoung34/docker-github-actions-runner)

## 📞 Support

- **Platform Team**: @strongmind/platform-team
- **Issues**: Create an issue in this repository
- **Questions**: See [docs/FAQ.md](docs/FAQ.md)

---

**Still not sure where to start?** → [QUICKSTART.md](QUICKSTART.md)

