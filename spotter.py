#!/usr/bin/env python3
"""
Watch files and then run commands

TODO:
- Reload on .spotter changes
- Only print output on error/allow commands to be marked as silent
  - This could be done with a second script?
"""

import os
import re
import fnmatch
import subprocess
import collections

import pyinotify

class Spotter(pyinotify.ProcessEvent):
    INOTIFY_EVENT_MASK = pyinotify.IN_CREATE | pyinotify.IN_CLOSE_WRITE

    RE_DEFINE  = r'define: (.*) -> (.*)'
    RE_ENTRY   = r'(?:start|enter|begin): (.*)'
    RE_WATCH   = r'watch: (.*) -> (.*)'
    RE_EXIT    = r'(?:stop|exit|end): (.*)'
    RE_COMMENT = r'^#'

    def __init__(self, filename=None):
        self.definitions = dict()
        
        self.entry_commands = list()
        self.watches = collections.OrderedDict()
        self.exit_commands = list()

        # Lines matching each regex are passed to it's paired function
        self.regexes = [(re.compile(r, re.I), f) for r, f in [
            (self.RE_DEFINE,  self.add_definition),
            (self.RE_ENTRY,   self.entry_commands.append),
            (self.RE_WATCH,   self.add_watch),
            (self.RE_EXIT,    self.exit_commands.append),
            (self.RE_COMMENT, None),
        ]]

        # Read in the configuration, if initialised with a filename
        if not filename is None:
            self.read_file(filename)

    def add_definition(self, key, value):
        self.definitions[key] = value

    def add_watch(self, pattern, command):
        if not pattern in self.watches:
            self.watches[pattern] = list()
        self.watches[pattern].append(command)
        # self.watches.append((pattern, command))

    def read_file(self, filename):
        """Read the watches and other options from a config file"""        
        with open(filename, 'r') as file:
            for line in file:
                line = line.strip()
                if line:
                    self.read_line(line)

    def read_line(self, line):
        """Read in a single line"""
        for regex, func in self.regexes:
            match = regex.match(line)
            if match and func is not None:
                return func(*match.groups())

    def run_command(self, command, **kwargs):
        """Run a single command

        The command is formatted using the stored definitions and any keyword
        arguments passed to the function."""
        arguments = dict()
        arguments.update(self.definitions)
        arguments.update(kwargs)
        subprocess.call(command.format(**arguments), shell=True)

    def run_commands(self, commands, **kwargs):
        """Run a list of commands"""
        for command in commands:
            self.run_command(command, **kwargs)

    def loop(self):
        watch_manager = pyinotify.WatchManager()
        notifier = pyinotify.Notifier(watch_manager, self)
        watch_manager.add_watch('.', Spotter.INOTIFY_EVENT_MASK, rec=True)

        with self:
            notifier.loop()

    def __enter__(self):
        self.run_commands(self.entry_commands)

    def process_default(self, event):
        """Run the command associated with the event"""
        for pattern, commands in self.watches.items():
            path = os.path.relpath(event.pathname)
            if fnmatch.fnmatch(path, pattern) or path == pattern:
                return self.run_commands(commands, filename=event.pathname)
    
    def __exit__(self, type, value, traceback):
        self.run_commands(self.exit_commands)

if __name__ == '__main__':
    Spotter('.spotter').loop()
