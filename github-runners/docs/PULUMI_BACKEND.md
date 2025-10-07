# Pulumi Backend Configuration

This project uses an S3-based Pulumi backend for state management.

## Backend Location

```
s3://pulumi-backend-058264302180/github-runners
```

## Login Command

Before running any Pulumi commands, ensure you're logged in to the backend:

```bash
export AWS_ACCOUNT_ID=058264302180
pulumi login s3://pulumi-backend-${AWS_ACCOUNT_ID}/github-runners
```

Or with the account ID directly:

```bash
pulumi login s3://pulumi-backend-058264302180/github-runners
```

## State Management

### Why S3 Backend?

- **Team Collaboration**: Multiple team members can access the same state
- **State Locking**: Prevents concurrent modifications
- **Versioning**: S3 versioning tracks state history
- **Security**: Access controlled via AWS IAM
- **Cost**: More cost-effective than Pulumi Cloud for large teams

### State File Structure

```
s3://pulumi-backend-058264302180/github-runners/
├── .pulumi/
│   ├── stacks/
│   │   └── stage.json          # Stack configuration and state
│   └── meta.yaml               # Project metadata
```

### Verify Backend Connection

```bash
pulumi login s3://pulumi-backend-058264302180/github-runners
pulumi whoami -v
```

Expected output:
```
User: s3://pulumi-backend-058264302180/github-runners
Backend URL: s3://pulumi-backend-058264302180/github-runners
```

## Stack Operations

### List Available Stacks

```bash
pulumi stack ls
```

### Select a Stack

```bash
pulumi stack select stage
```

### View Stack State

```bash
pulumi stack --show-ids
```

### Export Stack State

```bash
pulumi stack export --file stack-backup.json
```

### Import Stack State

```bash
pulumi stack import --file stack-backup.json
```

## Troubleshooting

### Error: "not logged in"

**Solution:**
```bash
pulumi login s3://pulumi-backend-058264302180/github-runners
```

### Error: "no stack selected"

**Solution:**
```bash
pulumi stack select stage
# Or create new stack
pulumi stack init stage
```

### Error: "access denied" to S3 bucket

**Solution:**
1. Verify AWS credentials: `aws sts get-caller-identity`
2. Ensure your IAM user/role has S3 access to the bucket
3. Required IAM permissions:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "s3:ListBucket",
           "s3:GetObject",
           "s3:PutObject",
           "s3:DeleteObject"
         ],
         "Resource": [
           "arn:aws:s3:::pulumi-backend-058264302180",
           "arn:aws:s3:::pulumi-backend-058264302180/*"
         ]
       }
     ]
   }
   ```

### Error: "state file is locked"

**Solution:**
Wait for the lock to be released (another user is running `pulumi up`), or:
```bash
pulumi cancel
```

### Corrupted State

**Solution:**
1. Export current state: `pulumi stack export > backup.json`
2. Manually fix the JSON
3. Import fixed state: `pulumi stack import < backup.json`

## Best Practices

### 1. Always Login Before Operations

Add this to your workflow:
```bash
pulumi login s3://pulumi-backend-058264302180/github-runners
```

### 2. Use Stack Isolation

Different environments should use different stacks:
- `stage` - staging environment
- `prod` - production environment

### 3. Enable S3 Versioning

Ensure the S3 bucket has versioning enabled:
```bash
aws s3api put-bucket-versioning \
  --bucket pulumi-backend-058264302180 \
  --versioning-configuration Status=Enabled
```

### 4. Regular Backups

Schedule regular state exports:
```bash
pulumi stack export > backups/github-runners-$(date +%Y%m%d).json
```

### 5. Access Control

Use IAM policies to control who can modify infrastructure:
- **Read-only**: `s3:GetObject`, `s3:ListBucket`
- **Read-write**: Add `s3:PutObject`, `s3:DeleteObject`

## Migration

### From Pulumi Cloud to S3

```bash
# Export from Pulumi Cloud
pulumi login
pulumi stack select stage
pulumi stack export > state-backup.json

# Login to S3 backend
pulumi login s3://pulumi-backend-058264302180/github-runners

# Create new stack and import
pulumi stack init stage
pulumi stack import < state-backup.json
```

### From S3 to Pulumi Cloud

```bash
# Export from S3
pulumi login s3://pulumi-backend-058264302180/github-runners
pulumi stack select stage
pulumi stack export > state-backup.json

# Login to Pulumi Cloud
pulumi login

# Create new stack and import
pulumi stack init stage
pulumi stack import < state-backup.json
```

## CI/CD Integration

### GitHub Actions

The backend login is included in the deployment workflow:

```yaml
- name: Deploy with Pulumi
  env:
    AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
    AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
  run: |
    pulumi login s3://pulumi-backend-058264302180/github-runners
    cd github-runners
    pulumi up --yes
```

### Local Development

Set environment variable for persistent login:

```bash
export PULUMI_BACKEND_URL=s3://pulumi-backend-058264302180/github-runners
```

Add to your `~/.bashrc` or `~/.zshrc`:
```bash
export PULUMI_BACKEND_URL=s3://pulumi-backend-058264302180/github-runners
```

## Security Considerations

1. **Encryption**: Enable S3 bucket encryption
2. **Access Logs**: Enable S3 access logging
3. **Lifecycle Policies**: Set up policies to archive old versions
4. **IAM Roles**: Use IAM roles instead of access keys when possible
5. **MFA**: Require MFA for state modifications in production

## References

- [Pulumi S3 Backend Documentation](https://www.pulumi.com/docs/intro/concepts/state/#aws-s3)
- [AWS S3 Best Practices](https://docs.aws.amazon.com/AmazonS3/latest/userguide/best-practices.html)

