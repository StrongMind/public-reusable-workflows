[Link to Jira ticket](https://strongmind.atlassian.net/browse/STK-11656)

## Purpose 
Add Vips library installation to the CI workflow to fix issues with image processing in tests, but only for the central repository.

## Approach 
Added a new step in both the `run-tests-in-folder` and `run-tests` jobs to install the Vips library and its development files using apt-get. The step is placed after the repository checkout and before any test execution. The installation is conditional on the workflow being run in the `StrongMind/central` repository using the `github.repository` context variable.

## Testing 
The changes can be verified by:
1. Running the CI workflow in the central repository to confirm Vips is installed
2. Running the CI workflow in other repositories to confirm Vips is not installed
3. Checking that tests that depend on Vips in central now pass successfully
4. Verifying that the Vips installation step completes without errors in the workflow logs when running in central

## Screenshots/Video
N/A - This is a CI workflow change that affects the test environment setup. 