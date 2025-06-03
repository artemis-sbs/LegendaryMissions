call make_version

# Cleanup existing version
git tag --delete %VERSION%
git push --delete origin %VERSION%
