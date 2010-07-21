#!/usr/bin/env python
# -*- coding: utf-8 -*-
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

import pygst
import gst
import time

class AudioEngine:
	"""The class that controls playing the media from Ampache."""
	def __init__(self, ampache_conn):
		"""To construct an AudioEngine object you need to pass it an AmpacheSession object."""
		# save the ampache connection
		self.ampache_conn = ampache_conn
		# set the engine to default to no repeat
		self.repeat_songs = False
		# create a playbin (plays media form an uri)
		self.player = gst.element_factory_make("playbin", "player")
		bus = self.player.get_bus()
		bus.add_signal_watch()
		bus.enable_sync_message_emission()
		bus.connect("message", self.on_message)

	def set_ampache_gui_hook(self, ampache_gui):
		"""Attach the GUI to this object, so the audio_engine can alert the GUI of song changes"""
		self.ampache_gui = ampache_gui
	
	def play_from_list_of_songs(self, songs_list, song_num=0):
		"""Takes a list of song_ids and position in the list and plays it.
		This function will use the AmpacheSession to turn song_ids into song_urls."""
		if not songs_list:
			print "Can't play empty list"
			return False
		self.songs_list = songs_list
		self.song_num = song_num
		try: # get the song_url and play it
			song_url = self.ampache_conn.get_song_url( self.songs_list[self.song_num] )
			self.stop()
			self.player.set_property('uri', song_url)
			self.player.set_state(gst.STATE_PLAYING)
			self.ampache_gui.audioengine_song_changed(songs_list[song_num]) # hook into GUI
		except: # out of songs
			self.ampache_gui.audioengine_song_changed(None) # hook into GUI
			print "No more songs"


	def on_message(self, bus, message):
		"""This function runs when the player gets a message (event).
		This allows the GUI to determine when it reaches the end of a song."""
		t = message.type
		if t == gst.MESSAGE_EOS: # end of song
			self.stop()
			print "Song is over -- trying next song"
			self.next_track()
		elif t == gst.MESSAGE_ERROR: # error!
			self.stop()
			err, debug = message.parse_error()
			print "Error: %s" % err, debug

	def get_state(self):
		"""Returns a string that tells the current state of the player."""
		state = self.player.get_state()

		for current_state in state:
			current_state = str(current_state)
			try:
				if current_state == str(gst.STATE_PLAYING):
					return "playing"
				elif current_state == str(gst.STATE_PAUSED):
					return "paused"
				elif current_state == str(gst.STATE_NULL):
					return "stopped"
			except:
				pass
		return None
		
	def get_playlist(self):
		"""Returns the current playlist in a list of song_ids."""
		return self.songs_list
	
	def get_current_song(self):
		"""Returns the current playing songs position in the list."""
		return self.song_num
		
	def set_repeat_songs(self, value): # must be True or False
		"""Set songs to repeat.  Takes True or False."""
		try:
			self.repeat_songs = value
		except:
			return False
		return True
	
	def stop(self): 
		"""Tells the player to stop."""
		try:
			self.player.set_state(gst.STATE_NULL)
		except:
			return False
		return True

	def pause(self):
		"""Tells the player to pause."""
		try:
			self.player.set_state(gst.STATE_PAUSED)
		except:
			return False
		return True
		
	def play(self):
		"""Tells the player to play."""
		try:
			self.player.set_state(gst.STATE_PLAYING)
		except:
			return False
		return True
	
	def change_song(self, song_num):
		self.play_from_list_of_songs(self.songs_list, song_num)
	
	def remove_from_playlist(self, song_id):
		try:
			self.songs_list.remove(song_id)
		except:
			return False
		return True
	
	def insert_into_playlist(self, song_id, song_num=None):
		if song_num == None:
			self.songs_list.append(song_id)
		else:
			self.songs_list.insert(song_num, song_id)
	
	def prev_track(self):
		"""Tells the player to go back a song in the playlist.
		This function takes care of repeating songs if enabled."""
		try:
			self.song_num -= 1
			if self.repeat_songs: # if the user wants the album to repeat
				self.song_num = (self.song_num + len(self.songs_list)) % len(self.songs_list) # this is for repeating tracks
			else: # the user doesn't want the album to repeat
				if self.song_num < 0:
					self.song_num = None
			print "New song_num", self.song_num
			self.play_from_list_of_songs(self.songs_list, self.song_num)
		except:
			return False
		return True
	
	
	def next_track(self):
		"""Tells the player to go forward a song in the playlist.
		This function takes care of repeating songs if enabled."""
		try:
			if self.song_num == None: # the user clicked prev too many times
				self.song_num = 0
			self.song_num += 1
			if self.repeat_songs: # if the user wants the album to repeat
				self.song_num = self.song_num % len(self.songs_list)
			else: # don't repeat
				if self.song_num > len(self.songs_list):
					# dont' let the current position go over the playlist length
					self.song_num = len(self.songs_list) 
			print "New song_num", self.song_num
			self.play_from_list_of_songs(self.songs_list, self.song_num)
		except:
			return False
		return True
