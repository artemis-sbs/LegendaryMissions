
call make_version

# Cleanup existing version
# This is now in make_unrelease.bat
git tag --delete %VERSION%
git push --delete origin %VERSION%

# This is now in make_release.bat
git tag -a %VERSION% -m %1
git push --tags