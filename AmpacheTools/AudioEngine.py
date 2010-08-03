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
		##################################
		# Variables
		##################################
		self.ampache_conn = ampache_conn
		
		self.repeat_songs = False
		self.songs_list = []
		self.song_num = -1
		
		# create a playbin (plays media form an uri)
		self.player = gst.element_factory_make("playbin2", "player")
		bus = self.player.get_bus()
		bus.add_signal_watch()
		bus.enable_sync_message_emission()
		bus.connect("message", self.on_message)
		self.player.connect("about-to-finish", self.on_about_to_finish)

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
			self.player.set_state(gst.STATE_NULL)
			self.player.set_property('uri', song_url)
			self.player.set_state(gst.STATE_PLAYING)
			self.ampache_gui.audioengine_song_changed(songs_list[song_num]) # hook into GUI
		except: # out of songs
			self.stop()
			self.ampache_gui.audioengine_song_changed(None) # hook into GUI
			print "No more songs"


	def on_message(self, bus, message):
		"""This function runs when the player gets a message (event).
		This allows the GUI to determine when it reaches the end of a song."""
		t = message.type
		if t == gst.MESSAGE_EOS: # end of song
			self.stop()
			print "Song is over -- trying next song"
			self.next_track(True)
		elif t == gst.MESSAGE_ERROR: # error!
			self.stop()
			err, debug = message.parse_error()
			result =  "Gstreamer Error: %s %s" % (err, debug)
			print result
			self.ampache_gui.audioengine_error_callback(result)
			
	def on_about_to_finish(self, player):
		print "almost..."
		#self.next_track_gapless()
			
	def query_position(self):
		"""Returns position in nanoseconds"""
		try:
			position, format = self.player.query_position(gst.FORMAT_TIME)
		except:
			position = -1
		#try:
		#       duration, format = self.player.query_duration(gst.FORMAT_TIME)
		#except:
		#       duration = gst.CLOCK_TIME_NONE
		return position

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
	
	def set_playlist(self, list):
		"""Sets the current playlist to list."""
		self.songs_list = list
		
	def get_playlist(self):
		"""Returns the current playlist in a list of song_ids."""
		return self.songs_list
	
	def get_current_song(self):
		"""Returns the current playing songs position in the list."""
		return self.song_num
	
	def get_current_song_id(self):
		"""Returns the current playing song_id or None."""
		if self.song_num == -1:
			return None
		return self.songs_list[self.song_num]
		
	def set_repeat_songs(self, value): # must be True or False
		"""Set songs to repeat.  Takes True or False."""
		self.repeat_songs = value
		
	def get_repeat_songs(self):
		"""True if songs are set to repeat."""
		return self.repeat_songs
	
	def set_volume(self, percent):
		"""Sets the volume, must be 0-100."""
		if percent < 0 or percent > 100:
			return False
		volume = percent / 100.0
		self.player.set_property('volume', volume)
		
	def get_volume(self):
		"""Gets the volume."""
		return self.player.get_property('volume')*100
	
	def clear_playlist(self, data=None):
		"""Clear the current playlist and stop the song."""
		self.stop()
		self.songs_list = []
		self.song_num = -1
		self.ampache_gui.audioengine_song_changed(None)
	
	def seek(self, seek_time_secs):
		"""Seek function, doesn't work on some distros."""
		return self.player.seek_simple(gst.FORMAT_TIME, gst.SEEK_FLAG_FLUSH | gst.SEEK_FLAG_KEY_UNIT, int(seek_time_secs) * gst.SECOND)
		
	def stop(self): 
		"""Tells the player to stop."""
		try:
			self.player.seek_simple(gst.FORMAT_TIME, gst.SEEK_FLAG_FLUSH, 0)
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
		"""Change song to the given song number."""
		self.play_from_list_of_songs(self.songs_list, song_num)
	
	def remove_from_playlist(self, song_id):
		"""Remove the song_id from the playlist."""
		try:
			song_num = self.songs_list.index(song_id)
			if song_num <= self.song_num:
				self.song_num -= 1
			self.songs_list.remove(song_id)
		except:
			return False
		return True
	
	def insert_into_playlist(self, song_id, song_num=None):
		"""insert the song_id into the playlist, song_num is optional."""
		if song_num == None:
			self.songs_list.append(song_id)
		else:
			self.songs_list.insert(song_num, song_id)
	
	def prev_track(self):
		"""Tells the player to go back a song in the playlist.
		This function takes care of repeating songs if enabled."""

		self.song_num -= 1
		if self.repeat_songs: # if the user wants the album to repeat
			self.song_num = (self.song_num + len(self.songs_list)) % len(self.songs_list) # this is for repeating tracks
		else: # the user doesn't want the album to repeat
			if self.song_num < 0:
				self.song_num = 0
				return True
		print "New song_num", self.song_num
		self.play_from_list_of_songs(self.songs_list, self.song_num)

	
	
	def next_track(self, auto=False):
		"""Tells the player to go forward a song in the playlist.
		This function takes care of repeating songs if enabled."""
		if self.song_num == None: # the user clicked prev too many times
			self.song_num = 0
		else:
			self.song_num += 1
		if self.repeat_songs: # if the user wants the album to repeat
			self.song_num = self.song_num % len(self.songs_list)
		else: # don't repeat
			if self.song_num >= len(self.songs_list):
				# dont' let the current position go over the playlist length
				if auto:
					self.song_num = -1
					self.stop()
					self.ampache_gui.audioengine_song_changed(None)
					return
				else:
					self.song_num = len(self.songs_list) - 1
					return
		print "New song_num", self.song_num
		self.play_from_list_of_songs(self.songs_list, self.song_num)

	
	#def next_track_gapless(self):
		#"""Tell the player to play the next song right away."""
		#try:
			#if self.song_num == None: # the user clicked prev too many times
				#self.song_num = 0
			#else:
				#self.song_num += 1
			#if self.repeat_songs: # if the user wants the album to repeat
				#self.song_num = self.song_num % len(self.songs_list)
			#else: # don't repeat
				#if self.song_num >= len(self.songs_list):
					## dont' let the current position go over the playlist length
					#self.song_num = -1
					#self.stop()
					#return

			#print "New song_num", self.song_num
			#self.player.set_property('uri', self.ampache_conn.get_song_url(self.songs_list[self.song_num]))
			#self.ampache_gui.audioengine_song_changed(songs_list[song_num])
		#except:
			#return False
		#return True
