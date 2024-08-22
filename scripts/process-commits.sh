#!/bin/bash

# Debugging: Show current branch and commit history
echo "Current branch: $(git rev-parse --abbrev-ref HEAD)"
echo "Recent commits:"
git log --oneline -5

# Get repository name from GitHub context
repo_name=$(echo "${REPO_NAME}" | cut -d '/' -f2)


# Fetch all branches and tags to ensure we have the complete history
git fetch --all

# Get the latest merge commit hash
merge_commit=$(git log --pretty=format:"%H" --merges -1)

if [ -z "$merge_commit" ]; then
    echo "No merge commit found"
    exit 1
fi

# Get the list of commits in the merge
commits=$(git log --pretty=format:"%H" $merge_commit^1..$merge_commit^2)

if [ -z "$commits" ]; then
    echo "No commits found in the merge"
    exit 1
fi

for commit in $commits; do
    author=$(git show -s --format='%an <%ae>' $commit)
    date=$(git show -s --format='%ci' $commit)
    co_authors=$(git show -s --format='%b' $commit | grep -oE 'Co-authored-by:.*' | sed 's/Co-authored-by: //g')
    co_authors_array="["

    if [ -z "$co_authors" ]; then
        co_authors_array="[]"
    else
        # Use a while read loop to handle each co-author properly
        while IFS= read -r co_author; do
            co_authors_array="$co_authors_array\"$co_author\","
        done <<< "$co_authors"

        co_authors_array="${co_authors_array%,}]"  # Remove trailing comma and close array
    fi

    lines_added=$(git show --stat $commit | grep -E 'files? changed' | awk '{print $4}')
    lines_removed=$(git show --stat $commit | grep -E 'files? changed' | awk '{print $6}')

    commit_info="{\"commit\": {\"commit_hash\": \"$commit\", \"author\": \"$author\", \"date\": \"$date\", \"co_authors\": $co_authors_array, \"lines_added\": \"$lines_added\", \"lines_removed\": \"$lines_removed\", \"repository\": \"$repo_name\"}}"
    
    # Debugging: Print JSON data
    echo "Commit Info: $commit_info"

    #Send each commit info separately
    curl -X POST \
        -H "Content-Type: application/json" \
        -d "$commit_info" \
       https://repository-dashboard.strongmind.com/api/commits.json
done
