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
# Template plugin... this plugin prints some information about the current song
# Dave Eddy <dave@daveeddy.com>

def __init__():
	"""Return an instance of the class used by the plugin when __init__() is called"""
	return TemplatePlugin()

class TemplatePlugin:
	def __init__(self):
		"""Called before the plugin is asked to do anything.
		title, author, and description must be set for Viridian to read the plugin."""
		self.title       = "Template Plugin"
		self.author      = "Dave Eddy <dave@daveeddy.com>"
		self.description = "Prints some information when the song changes"

	def on_song_change(self, song_dict):
		"""Called when the song changes in Viridian.
		A dictionary with all of the songs information is passed in as 'song_dict'"""
		for k,v in song_dict.iteritems():
			print "song_dict['%s'] = '%s'" % (k,v)
