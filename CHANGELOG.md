#### Upcoming changes
  * DNS lookup for valid hosts (maybe)
  * Has been authed to host
  * Killed server and reason
  * Convert query %s to ?
  * Count unique nicks in trace nick
  * \*net \*split warning
  * Display both seen and process
  * REGEX search for host match / IP / rDNS
  * ident and name tracking
  * Flood warning
  * Account name tracking
  * Ban evasion warning
  * Trace IP if in host
  * User modes in channel
  * Trace ident

# Changelog

### Version 1.10.0
  * `trace` only refers to `nick` or `host`; other commands not under `trace`
  * Provided proper credit to contributors
  * `seen` and `offenses` output formatting
  * Logs "removed by" and "remove requested by" as moderated
  * Fixed channel output for `seen` when not specified
  * Removed `save` command
  * Logs last server user was connected to
  * Fix `all` for `offenses` and `seen`
  * Identity updated when user processed
  * `NOTIFY_ON_JOIN` uses `all` instead of `trace NOTIFY_DEFAULT_MODE`
  * New `dbimport` command to import an entire database
  * Real name added to user info
  * `userinfo` command to show last known information for a nick or host
  * `rawquery` command to run raw sqlite3 query
  * [README](README.md) Table of Contents
  * `PART` and `QUIT` tracking
  * Do not process `WHO` every time client sends `WHO #channel` (OnLoad for many clients)
  * New `process` command to manually trigger processing of a channel, user, or all channels
  * Raw user information processed separately
  * `geoip` uses last `processed_time` instead of `seen`
  * `info` changed to `about`
  * Only `PROCESS_CHANNELS_ON_LOAD` if not also set to `PROCESS_CHANNEL_ON_JOIN`
  * Display `host` in `geoip nick`
  * New `TRACK_SEEN` setting to turn on/off last seen tracking for users
  * New `trace lasthost <nick>` command trace the last known host of the nick
  * Improved pattern matching for \*-Lines
  * No result messages for `userinfo`
  * AWAY status now tracked
  * Last quit, away, or return now displayed in seen
  * Improper command output now shows valid options
  * Tracks last join time per channel

### Version 1.0.9
  * Process all channels on load
  * Process all users in channel on join
  * Better string processing
  * `seen in host` fix
  * Clarified output when no results found ([@iynque](https://github.com/iynque))
  * Improved `geoip`
  * `trace nickchans` and `trace hostchans` merged into `channels`
  * Use native ZNC python settings `module.nv`

### Version 1.0.8
  * `all` command to run complete trace on nick or host ([@iynque](https://github.com/iynque))
  * More reliable `geoip nick` functionality

### Version 1.0.7
  * Date/time formatting
  * Intersect nicks or hosts

### Version 1.0.6
  * Users tracked on Private Message

### Version 1.0.5
  * Added output if no results found
  * `seen host`, `seen in nick <#channel> <nick>`, and `seen in host <#channel> <host>`
  * New `trace sharedchans nicks` and `trace sharedchans hosts`

### Version 1.0.4
  * New `import` and `export` commands for sharing data ([@KindOne](https://github.com/KindOne-))
  * G/K/Z/Q-Line and Kill tracking

### Version 1.0.3
  * Kick, ban, and quiet tracking ("moderated")
  * `offenses` command to see kick/ban/quiet history

### Version 1.0.2
  * Bug fixes
  * Track OnChanAction

### Version 1.0.1
  * New option to be notified of channel mode changes
  * `seen` command added

### Version 1.0.0
  * **Rewritten** to use sqlite instead over json
  * Reversion

### Version 0.9.0
  * Fixed reload on `update`
  * `update` limited to administrators
  * `geoip <nick>` added
  * Bug fixes
  * `getconfig` to print the current settings for the network
  * Spelling fix

### Version 0.8.2
  * Added `geoip <host>` command
  * Module reloads after `update`
  * Fixed OnNick and OnQuit bug ([@KindOne](https://github.com/KindOne-))

### Version 0.8.1
  * Relocated save files to proper location
  * Added on join `trace` for new users

### Version 0.8.0
  * New 'update' command to auto-update from master

### Version 0.7.1
  * Clarified `trace` commands in `help`

### Version 0.7.0
  * Added option to automatically run `trace nick` for users on channel join
  * New variable to set limit on notification frequency for a given nick
  * Adds new config variables to file
  * Fixed config variable bug

### Version 0.6.1
  * Added wiki page to module

### Version 0.6.0
  * Added `help` output
  * Added `info` command

### Version 0.5.6
  * Added nick and channel inputs to intersect and sharedchans output

### Version 0.5.5
  * Spelling fixes ([@Equinox](https://github.com/Equinox))

### Version 0.5.4
  * Fixed initialization error

### Version 0.5.3:
  * You no longer need to specify the user in the file
  * New command `stats` tell you how many users/hosts you have added to your hosts.json

### Version 0.5.2:
  * Config is saved when you change a setting via ZNC

### Version 0.5.1:
  * Command validation for sub-commands

### Version 0.5.0:
  * Fixed typos
  * New command `nickchans` same thing as `hostchans` but with nicks
  * New command `version` tells the you version of the script

### Version 0.4.0:
  * New command `merge chans` combine someone else's \*\_chans.json with yours!
  * The script will now make you a config file if you don't already have one
  * Nick searches are now case-insensitive

### Version 0.3.0:
  * Public release
  * Code refactoring
  * Added checks to ensure all files and folders are created before loading
  * New command `merge hosts` combine someone else's \*\_hosts.json with yours!

### Version 0.2.2:
  * Spelling and grammar fixes

### Version 0.2.1:
  * Fixed FileNotFoundError bug.
  * You can now manually map nick to host
  * Code refactoring
  * fixed a bug with `sharedchans` and `intersect`

### Version 0.2.0:
  * Config file is now pretty.
  * New command `hostchans` added. Prints all the channels a host is in
  * New command `intersect` added. Prints all nicks that share channels
  * New command `sharedchans` added. Prints all channels shared by those nicks

### Version 0.1.0:
  * You can now manually save with `save`
  * You can now change the config within ZNC

### Version 0.0.1:
  * OnQuit() and OnPart() functions added
  * Trace outputs are now sorted.
  * Implemented a save timer
  * Now adds nicks when a `WHO` is done on a channel
  * Now adds nicks when a `WHOIS` is done on a user
  * Now adds nicks when a `WHOWAS` is done on a user
