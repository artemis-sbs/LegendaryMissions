echo OFF
REM Release, Unrelease, Rerelease

echo %1
echo %2


if "%1" NEQ "rel" if "%1" NEQ "unrel" if "%1" NEQ "rerel" goto :error
call make_version

if "%1" == "unrel" goto :unrelease
if [%2] == [] goto :error
if "%1" == "rerel" goto :unrelease
if "%1" == "rel" goto :release

:unrelease 

REM  Cleanup existing version
git tag --delete %VERSION%
git push --delete origin %VERSION%


if "%1" == "unrel" goto :end
if "%1" == "rerel" goto :release

REM Flow through is an relrelease
:error
echo Invalid arguments
echo make_release rel or  unrel or rerel
echo rel and rerel require a description

goto :end

:release 

git tag -a %VERSION% -m %2
git push --tags

:end

