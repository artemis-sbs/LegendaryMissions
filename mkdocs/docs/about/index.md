# About

Basic Siege is a mission script for Artemis: Cosmos

It was written by:

Doug Reichard
Darrin Bright
Mike Substelny
and
Thom Robertson

The mission was created as part of the initial release of Artemis: Cosmos to test the engine. The goal is to provide a set of missions that match the out of the box missions provided by Artemis: Spaceship Bridge Simulator.

It is written in a mixture of the Python and MAST Languages. 

It began as a Python. The Python Library [sbs_utils](https://artemis-sbs.github.io/sbs_utils/) was created to have a reusable python library.

The [MAST Language](https://artemis-sbs.github.io/sbs_utils/mast/) was then added as the main script on top of the sbs_utils library.

MAST is a language that is similar to python in syntax, but provides:

- The Agent Model
- Managing running multiple task in parallel (in a single thread)
- Artemis: Cosmos specific functionality to:
    - Creating user interfaces
    - Managing communications
    - Managing Science
    - Managing engineering communications




