# Hosting modes

The Legendary Missions can be configured to help automate startup, and help operators have more control over the startup.

## Artemis Cosmos: Nearly headless mode

When running a Artemis Cosmos Server in some scenarios e.g. cloud based servers, it is often desired run in a headless mode.

Artemis Cosmos still runs in a grapical manner, however there are now options to simplify the running a remote server.

## Preference: default_mission_folder
In the Artemis Cosmos data directory there is a file *preferences.json". In this file there is a setting to automatically start a mission when the artemis executable runs: default_mission_folder.

By uncommenting and setting this value it will run in server mode the specified mission.

For example:

``` ini
"default_mission_folder":  "LegendaryMissions"
```

Will run the the Legendary Mission on startup.

## Remote mission picker
There is also a mission script to present the mission picker remotely.

If you do not have it, it can be obtained my opening a command line in the missions folder and typing:

``` cmd
.\fetch artemis-sbs remote_mission_pick
```

You must have an internet connection for this. The fetch command retrieves missions from github.

Alternatively you can get the mission from github.

[Mission on github](https://github.com/artemis-sbs/remote_mission_pick)



## setup.json
The Legendary Missions has a setup.json file. This file can set the default starting values as well as enable operator mode.

To enable operator mode, a 'nearly headless' operation for LegendaryMissions, set the operator mode enable to true.

With operator mode turned on, a client console can act as the mission startup settings screen and it also has some useful things for operators.

``` json
"OPERATOR_MODE": {
        "enable": true,
        "logo": "media/operator",
        "show_logo_on_main": true,
        "pin": "000000"
    },
```


[see here ](setup.json.md) for more settings.
