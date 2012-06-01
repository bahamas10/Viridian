#!/usr/bin/env python
### BEGIN LICENSE
# Copyright (C) 2010 Dave Eddy <dave@daveeddy.com>
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3, as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranties of
# MERCHANTABILITY, SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR
# PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
### END LICENSE
#
# Plugin for Viridian to set your pidgin status
# to the currently playing song.
#

import dbus

def __init__():
    """Return an instance of the class used by the plugin when __init__() is called"""
    return PidginPlugin()

class PidginPlugin:
    def __init__(self):
        """called before the plugin is asked to do anything"""
        self.title       = "Pidgin Status"
        self.author      = "Dave Eddy <dave@daveeddy.com>"
        self.description = "Sets the current playing song as your pidgin status."

    def on_song_change(self, song_dict):
        """Called when the song changes in Viridian.
        A dictionary with all of the songs information is passed in as 'song_dict'"""
        try:
            bus = dbus.SessionBus()
            obj = bus.get_object("im.pidgin.purple.PurpleService", "/im/pidgin/purple/PurpleObject")
            self.purple = dbus.Interface(obj, "im.pidgin.purple.PurpleInterface")
            self.set_message('Now Playing :: %s by %s' % (song_dict['song_title'], song_dict['artist_name']))
            print "Status Set"
        except:
            print "Error setting status"
            pass


    def set_message(self, message):
        # Get current status type (Available/Away/etc.)
        current = self.purple.PurpleSavedstatusGetType(self.purple.PurpleSavedstatusGetCurrent())
        # Create new transient status and activate it
        status = self.purple.PurpleSavedstatusNew("", current)
        self.purple.PurpleSavedstatusSetMessage(status, message)
        self.purple.PurpleSavedstatusActivate(status)
