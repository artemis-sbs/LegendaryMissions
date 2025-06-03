# The mission startup
All Artemis: Cosmos Missions start by running script.py. Without reusable code, the scripter would need to write code to listen for al the events the engine fires to the script side.

This section begins to tell how BasicSiege runs from this startup script.py.

# script.py startup
The scripy.py for BasicSiege leverages the sbs_utils library and MAST Runtime. The following code is added to load the library and it adds functons that implement things to handle the events from the engine.

===  ":simple-python: Python"

    ``` python 
    import sbslibs
    from  sbs_utils.handlerhooks import *
    ```

The [sbs_utils library](https://artemis-sbs.github.io/sbs_utils/) library adds several high level systems over the Artemis: Cosmos engine to hopefully make scripters more productive and focus on the mission scripting, rather than needing a wealth of programming experience. Scripters can focus on These systems are used to build the MAST Runtime which can be used from both Python and the [MAST](https://artemis-sbs.github.io/sbs_utils/mast/) scripting language.


# Bootstrapping the MAST runtime

Basic Seige is written using both the scripting language, with several procedural function written in Python. In general reusable functions are written in python, and the script flow leverages MAST.

Leverage the library makes script.py a small file that creates a StoryPage, and setting the startup MAST file *story.mast* to run.

===  ":simple-python: Python"

    ``` python 
    class MyStoryPage(StoryPage):
        story_file = "story.mast"
    ```

Using the Gui system of sbs_utils the StoryPage class to be used for both server and client consoles. The server and each client create a gui Page, and start the story.mast main label. 

===  ":simple-python: Python"

    ``` python 
    Gui.server_start_page_class(MyStoryPage)
    Gui.client_start_page_class(MyStoryPage)
    ```

The code essentially is more configuration than code. But by configuring the system in this manner the server and clients can run opening up a Gui Page for drawing the content on the users see on the screen.

For BasicSiege these gui screen are code using code in story.mast

## Starting story.mast and running the main label
The server and each client creates their own Gui page (StoryPage). Each page creates a MAST Task that runs story.mast. A task is a execution unit in MAST that runs script. The MAST runtime manages all the running Tasks in the system.

``` mermaid
stateDiagram-v2
state fork_state 

state "server" as srv
state "client 1" as c1
state "client ..." as cn
state "MAST runtime" as m

    script.py --> story.mast
    story.mast --> m

    state m {
    srv
    --
    c1
    --
    cn
    }
   
```

The very first thing story.mast mast runs in each task is the *main label*.

All content prior to the first label in a MAST file in referred to as the main label. 

??? info "What is a Label"

    A label is a section of code in a mast file. Labels can be used as a heading, and can be used to redirect code to that point in the code i.e. the code can *jump* to a label rerouting the code to that point.

    Labels are denoted by 3 or more equals signs followed by a name followed by 3 or more equal signs. names are letter, numbers, or underscores no spaces, but spaces can be before or after the name.

    === ":mast-icon: MAST"

        ``` mast

        # Code before the first label is in "main"

        ===== my_label ====
        # The label code
        ```

All files imported, will have their own main label's code merged into a single main label.

??? info "Imports"
    imports are a way to include code from other files. In this way you can break your script into smaller chucks for organization, and reuse possibilities.

    Imported files are imported in order they occur in listed, and the files they imported are import with them. However, if a file that has been imported already it will not be imported again.

    Imports in mast are in the main label area of a file. An import statement can import MAST code or python code.

    === ":mast-icon: MAST"

        ``` mast
        include basic_ai.mast
        include map.mast
        include upgrade.py
        include upgrade.mast
        ```

The main label runs for the server and each client. However, the assignment of shared data is only run on the server to avoid resetting the data whenever a client console connects.

??? info "what is shared data"

    Share data is by server and all clients reference thee same value
    In the main label the assigning of these values only runs once
    
    Data that is not shared, the server and all client have their own version of the variable.
    
    === ":mast-icon: MAST"

        ``` mast
        # Shared by server and all clients
        shared DIFFICULTY=5
        shared PLAYER_COUNT = 1
        # Unique for each client + server
        user_name = "Player"
        console_name = "helm"
        ```

When the main label ends, it then route to the server or client gui. The label it jumps to is set via the *gui_reroute_server* or *gui_reroute_clients* functions. These functions take a label to run when main completes. 

=== ":mast-icon: MAST"
    ``` python
    gui_reroute_server("start_server")
    gui_reroute_clients("client_main")
    ```

If their is no gui reroute, then the main label will execute the first label in the main file (story.mast) as is customary for labels the continue through labels they encounter the labels is said it *falls through* to the next label.

??? info "Label fall through"
    The below example will print **A** and **B** when **a_label** executes because it falls through and runs **b_label**.

    === ":mast-icon: MAST"
        ``` python
        ==== a_label ===
        print("A")

        ==== b_label ===
        print("B")
        ```


Remove this its examples to copy from



===  ":simple-python: Python"

    ``` python 
    import sbslibs
    from  sbs_utils.handlerhooks import *
    ```

===  ":simple-windowsterminal: Cmd-line"

    ``` python 
    import sbslibs
    from  sbs_utils.handlerhooks import *
    ```

===  ":mast-icon: MAST"

    ``` python 
    import sbslibs
    from  sbs_utils.handlerhooks import *
    ```


