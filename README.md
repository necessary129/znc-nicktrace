# znc-nicktrace
A ZNC module to track users

## Table of Contents
- [Requirements](#requirements)
- [Installation](#installation)
- [Loading](#loading)
- [Commands](#commands)
	- [Aggregate Commands](#aggregate-commands)
	- [`trace` Commands](#trace-commands)
	- [Moderation History Commands](#moderation-history-commands)
	- [User Info Commands](#user-info-commands)
	- [Modify Data Commands](#modify-data-commands)
	- [Other Commands](#other-commands)
- [Configuration Variables](#configuration-variables)
- [Contact](#contact)

## Requirements
 * <a href="http://znc.in">ZNC</a>
 * <a href="https://www.python.org">Python 3</a>
 * <a href="http://wiki.znc.in/Modpython">modpython</a>
 * <a href="http://docs.python-requests.org/en/latest/">python3-requests</a>
 * <a href="https://www.sqlite.org">sqlite3</a>

## Installation
To install aka, place aka.py in your ZNC modules folder

## Loading
aka must be loaded on each network you wish to use it on
`/msg *status loadmod aka`

## Commands

### Aggregate Commands

`all nick <nick>` Perform complete lookup on nick (trace, channels, offenses, geoip, seen)

`all host <host>` Perform complete lookup on host (trace, channels, offenses, geoip, seen)

### User Lookup Commands

`trace nick <nick>` Show nick change and host history for given nick

`trace host <host>` Show nick change and host history for given host

`trace lasthost <nick` Show host history for last known host of given nick

`userinfo <nick>` Show last known information for given nick

`userinfo <host>` Show last known information for given nick

`sharedchans nicks <nick1> <nick2> ... <nick#>` Show common channels between a list of nicks

`sharedchans hosts <host1> <host2> ... <host#>` Show common channels between a list of hosts

`intersect nicks <#channel1> <#channel2> ... <#channel#>` Display nicks common to a list of channels

`intersect hosts <#channel1> <#channel2> ... <#channel#>` Display hosts common to a list of channels

`channels nick <nick>` Get all channels a nick has been seen in

`channels host <host>` Get all channels a host has been seen in

### Moderation History Commands

`offenses nick <nick>` Display kick/ban/quiet history for nick

`offenses host <host>` Display kick/ban/quiet history for host

`offenses in nick <#channel> <nick>` Display kick/ban/quiet history for nick in channel

`offenses in host <#channel> <host>` Display kick/ban/quiet history for host in channel

### User Info Commands

`seen nick <nick>` Display last time nick was seen speaking globally

`seen host <host>` Display last time host was seen speaking globally

`seen in nick <#channel> <nick>` Display last time nick was seen speaking in channel

`seen in host <#channel> <host>` Display last time host was seen speaking in channel

`geoip <host>` Geolocates the given host

`geoip <nick>` Geolocates a user by nick

### Modify Data Commands

`process all` Processes all channels

`process channel <#channel>` Processes a given channel

`process nick <nick>` Processes a given nick

`add <nick> <host>` Manually add a nick/host entry to the database

`rawquery <query>` Run raw sqlite query

`dbimport <filename.db>` Imports an entire `aka.db` database in `moddata` folder for network (both users must be using latest `aka` version)

`import <url>` Imports user data to DB from valid JSON file url

`export nick <nick>` Exports nick data to JSON file

`export host <host>` Exports host data to JSON file

### Other Commands

`about` Display information about aka

`version` Get current module version

`stats` Print nick and host stats for the network

`update` Updates aka to the newest version

`help` Print help from the module

## Configuration

### Commands

`getconfig` Print current network configuration

`config <variable> <value>` Set configuration variables

### Variables

 * **DEBUG_MODE** *(True/False)* Display raw output
 * **NOTIFY_ON_JOIN** *(True/False)* Automatically run `trace nick` when a user joins a channel
 * **NOTIFY_ON_JOIN_TIMEOUT** *(int: seconds)* How long to wait before sending notification again for same user
 * **NOTIFY_DEFAULT_MODE** *(nick/host)* Whether to use nick or host for on join `trace all`
 * **NOTIFY_ON_MODE** *(True/False)* Automatically be notified when channel modes are changed
 * **NOTIFY_ON_MODERATED** *(True/False)* Be notified when a user is banned, quieted, or kicked
 * **PROCESS_CHANNEL_ON_JOIN** *(True/False)* Process all users in a channel on join
 * **PROCESS_CHANNELS_ON_LOAD** *(True/False)* Process users in all channels when module is loaded
 * **TRACK_SEEN** *(True/False)* Whether or not to track the last seen status of users

## Contact

Issues/bugs should be submitted on the <a href="https://github.com/emagaliff/znc-nicktrace/issues">GitHub issues page</a>.

For assistance, please PM Evan (Evan) on <a href="https://kiwiirc.com/client/irc.freenode.net:+6697">freenode<a/> or <a href="https://kiwiirc.com/client/irc.snoonet.org:+6697">Snoonet<a>.
