# Updating
Artemis Cosmos missions that are have their source on Github can be updated using the *fetch* command.

There are two methods to update:

- the sbs tool
- the fetch batch file method 

The sbs tool is the newer method. 
If you mission folder contains the sbs.bat and sbs.pyz file you can use this newer tool.

If you would like to use this newer tool it can be down loaded [here](https://github.com/artemis-sbs/sbs_cli/releases/latest). Get the sbs.bat and sbs.pyz files and place them in the missions folder

You can still use fetch if you prefer. Look below for that section.

## updating using sbs
To update LegendaryMissions using the sbs tool it is quite simple.

Type `sbs fetch LegendaryMissions`

This will remove the current folder, and fetch a clean copy of LegendaryMissions. It will also gather all the needed libraries and addons.

That is it. All done.

### getting a specific version of LegendaryMissions
If you desire a different version of LegendaryMissions do the following. e.g. v1.1.0

Type `sbs fetch LegendaryMissions --version v1.1.0`

Or a hotfix version

Type `sbs fetch LegendaryMissions --version v1.1.0-hotfix`

### Getting another copy in a different folder
If you desire a different copy of LegendaryMissions 

Type `sbs fetch LegendaryMissions --folder MyCopy`
Type `sbs fetch LegendaryMissions --folder OldVersion --version v1.0.6 `

If you have your own fork on git hub you can provide the user information.

Type `sbs fetch LegendaryMissions --folder MyCopy --user my_user_name.

### more ways
see the [help for the sbs tool](https://github.com/artemis-sbs/sbs_cli/blob/main/README.md) for other ways of using the tools. Especial if you are modifying a mission or creating you own missions or addons.


## using fetch batch file __DEPRICATED__
Prior to Artemis 1.3.0, the FETCH.BAT was used to update and get missions.



### Fetching __DEPRICATED__
Open a command line terminal and navigate to the missions directory in Artemis Cosmos location

The fetch command can be used from there.

The fetch command takes at least 2 arguments and can optionally have 2 more

```
fetch GITHUB_USER REPOSITORY [FOLDER] [BRANCH/TAG]
```

GIHUB_USER is the user or organization name e.g. artemis-sbs

REPOSITORY is the mission repository name

FOLDER is the folder under mission to copy the mission to. This is optional. The default the REPOSITORY name.

BRANCH/TAG is the branch or TAG to use. This is optional. The  default is *main*

??? note "Folder is needed when specifying a branch"

    Currently fetch requires the folder when specifying a branch.


### Updating to the latest LegendaryMissions __DEPRICATED__

To update the LegendaryMissions to the latest version use fetch.

```
.\fetch artemis-sbs LegendaryMissions
```

!!! note "Recommendation: Don't copy into an existing folder"

    It is a good idea to rename or delete the existing mission folder so that the content you fetch is as clean as possible.



!!! note "Mission scripter note"

    Also if you have mission that leverage the AddOns from LegendaryMissions, it is a good idea to rebuild the Addons.

    ```
    cd LegendaryMissions
    .\build_addons
    ```

    You may need to update your story.json to the latest version. See the MAKEVERSION.bat file to see what that version is.


## Updating to a specific version LegendaryMissions __DEPRICATED__

You will need all four argument to fetch a specific branch.
The folder is not optional when including the branch/tag.

```
.\fetch artemis-sbs LegendaryMissions LegendaryMissions v1.0.6
```

## Updating LegendaryMissions to a different folder __DEPRICATED__
If you want to keep the existing version, but try a new version you can fetch to a different folder.


```
.\fetch artemis-sbs LegendaryMissions LegendaryMissionsDev
```


## Can you have multiple versions 

Absolutely, you can have two versions of 

the scripting system uses version stamps to make sure the right dependencies are loaded.

## I got the latest, but it doesn't work or has issues
The Latest version is where active development is occurring. While the goal is to have it always working there are times when the latest version has issues.

Issues can include it is targeting a new unreleased version of Artemis Cosmos.

To get back to the copy that shipped with Artemis Cosmos, fetch using the tag for that version. It is best practice to remove or renaming the mission folder before fetching.

```
.\fetch artemis-sbs LegendaryMissions LegendaryMissions v1.0.6
```



