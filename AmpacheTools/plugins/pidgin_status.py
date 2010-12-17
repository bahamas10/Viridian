#!/usr/bin/env python
# 
# Plugin for Viridian to set your pidgin status
# to the currently playing song.
#

def __init__():
	return PidginPlugin()

class PidginPlugin:
	def __init__(self):
		"""called before the plugin is asked to do anything"""

	def on_song_change(self, song_dict):
		"""Called when the song changes in Viridian.
		A dictionary with all of the songs information is passed in as 'song_dict'"""
		try: 
			import dbus
			bus = dbus.SessionBus()
			obj = bus.get_object("im.pidgin.purple.PurpleService", "/im/pidgin/purple/PurpleObject")
			self.purple = dbus.Interface(obj, "im.pidgin.purple.PurpleInterface")
			self.set_message('Now Playing :: ' + song_dict['song_title'] + ' by ' + song_dict['artist_name'])
		except:
			pass

	def set_message(self, message):
		# Get current status type (Available/Away/etc.)
		current = self.purple.PurpleSavedstatusGetType(self.purple.PurpleSavedstatusGetCurrent())
		# Create new transient status and activate it
		status = self.purple.PurpleSavedstatusNew("", current)
		self.purple.PurpleSavedstatusSetMessage(status, message)
		self.purple.PurpleSavedstatusActivate(status)

