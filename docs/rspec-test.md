# Rspec testing your rails application

## Create workflow pointing to reusable

1. Open your rails app.
2. Create the following file as `.github/workflows/rspec-test.yml`:
```yaml
name: "rspec test"

on:
  push:
    branches:
      - main
  workflow_dispatch:

jobs:
  respect-test:
    uses: Strongmind/public-reusable-workflows/.github/workflows/rspec-test.yml@main
    secrets: inherit
```

## Add required secrets to repository

### Code climate secret
1. Log into codeclimate quality https://codeclimate.com/login
2. Navigate to the repsitory where you are implementing the rspec test.
3. Click "Repo Settings" tab.
4. Click "Test coverate" under "ANALYSIS" on the left.
5. Copy "TEST REPORTER ID"
6. Create new repository secret named "CC_TEST_REPORTER_ID"
7. Paste "TEST REPORTER ID" as the secret.
8. Click "Add secret"

### Rails master key
1. Create new repository secret named "RAILS_MASTER_KEY"
2. Paste your rails master key as the secret.
3. Click "Add secret"

