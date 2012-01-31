#!/usr/bin/env python
#
# Copyright (c) 2012, Dave Eddy <dave@daveeddy.com>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the project nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


import pygst
import gst
import time
import random

class AudioEngine:
	"""The class that controls playing the media from Ampache."""
	def __init__(self, ampache_conn):
		"""To construct an AudioEngine object you need to pass it an AmpacheSession object."""
		##################################
		# Variables
		##################################
		self.ampache_conn = ampache_conn

		self.ampache_gui  = None

		self.repeat_songs  = False
		self.shuffle_songs = False
		self.songs_list = []
		self.song_num = -1

		# create a playbin (plays media form an uri)
		self.player = gst.element_factory_make("playbin2", "player")
	#	source = gst.element_factory_make("souphttpsrc", "source")
	#	source.set_property('user-agent', 'Viridian 1.0 (http://viridian.daveeddy.com)')
	#	self.player.add(source)

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
			if self.ampache_gui != None:
				self.ampache_gui.audioengine_song_changed(songs_list[song_num]) # hook into GUI
		except: # out of songs
			self.stop()
			if self.ampache_gui != None:
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
			if self.ampache_gui != None:
				self.ampache_gui.audioengine_error_callback(result)
	def on_about_to_finish(self, player):
		#self.next_track_gapless()
		return

	def query_position(self):
		"""Returns position in nanoseconds"""
		try:
			position, _ = self.player.query_position(gst.FORMAT_TIME)
		except:
			position = -1
		#try:
		#       duration, format = self.player.query_duration(gst.FORMAT_TIME)
		#except:
		#       duration = gst.CLOCK_TIME_NONE
		return position

	def get_state(self, *args):
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

	def set_playlist(self, l):
		"""Sets the current playlist to list."""
		self.songs_list = l

	def get_playlist(self, *args):
		"""Returns the current playlist in a list of song_ids."""
		return self.songs_list

	def set_current_song(self, song_num, *args):
		"""Sets the current song num (doesn't affect what is currently playing)."""
		self.song_num = song_num

	def get_current_song(self, *args):
		"""Returns the current playing songs position in the list."""
		return self.song_num

	def get_current_song_id(self, *args):
		"""Returns the current playing song_id or None."""
		if self.song_num == -1:
			return None
		return self.songs_list[self.song_num]

	def set_repeat_songs(self, value, *args): # must be True or False
		"""Set songs to repeat.  Takes True or False."""
		self.repeat_songs = value

	def get_repeat_songs(self, *args):
		"""True if songs are set to repeat."""
		return self.repeat_songs

	def set_shuffle_songs(self, value, *args):
		"""Set songs to shuffle.  Takes True or False."""
		self.shuffle_songs = value

	def get_shuffle_songs(self, value, *args):
		"""True if songs are set to shuffle."""
		return self.shuffle_songs

	def set_volume(self, percent, *args):
		"""Sets the volume, must be 0-100."""
		if percent <= 0:
			volume = 0
		elif percent >= 100:
			volume = 1
		else:
			volume = percent / 100.0
		self.player.set_property('volume', float(volume))
		return True

	def get_volume(self, *args):
		"""Gets the volume."""
		return self.player.get_property('volume')*100

	def clear_playlist(self, *args):
		"""Clear the current playlist and stop the song."""
		self.stop()
		self.songs_list = []
		self.song_num = -1
		if self.ampache_gui != None:
			self.ampache_gui.audioengine_song_changed(None)

	def seek(self, seek_time_secs):
		"""Seek function, doesn't work on some distros."""
		return self.player.seek_simple(gst.FORMAT_TIME, gst.SEEK_FLAG_FLUSH | gst.SEEK_FLAG_KEY_UNIT, int(seek_time_secs) * gst.SECOND)

	def stop(self, *args):
		"""Tells the player to stop."""
		try:
			self.player.set_state(gst.STATE_NULL)
		except:
			return False
		return True

	def pause(self, *args):
		"""Tells the player to pause."""
		try:
			self.player.set_state(gst.STATE_PAUSED)
		except:
			return False
		return True

	def play(self, *args):
		"""Tells the player to play."""
		try:
			self.player.set_state(gst.STATE_PLAYING)
		except:
			return False
		return True

	def restart(self, *args):
		"""Tells tho player to restart the song if it is playing."""
		if self.get_state() == "playing":
			self.play_from_list_of_songs(self.songs_list, self.song_num)
			return True
		return False

	def change_song(self, song_num, *args):
		"""Change song to the given song number."""
		self.play_from_list_of_songs(self.songs_list, song_num)
		return True

	def remove_from_playlist(self, song_id, *args):
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

	def prev_track(self, *args):
		"""Tells the player to go back a song in the playlist.
		This function takes care of repeating songs if enabled."""

		self.song_num -= 1
		if self.repeat_songs: # if the user wants the album to repeat
			self.song_num = (self.song_num + len(self.songs_list)) % len(self.songs_list) # this is for repeating tracks
		else: # the user doesn't want the album to repeat
			if self.song_num < 0:
				self.song_num = 0
				return False
		self.play_from_list_of_songs(self.songs_list, self.song_num)
		return True

	def next_track(self, auto=False):
		"""Tells the player to go forward a song in the playlist.
		This function takes care of repeating songs if enabled."""
		if self.shuffle_songs:
			new_song_num = int( random.random() * len(self.songs_list) ) - 1
			if new_song_num == self.song_num:
				self.song_num = None
			else:
				self.song_num = new_song_num
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
					if self.ampache_gui != None:
						self.ampache_gui.audioengine_song_changed(None)
					return True
				else:
					self.song_num = len(self.songs_list) - 1
					return False
		self.play_from_list_of_songs(self.songs_list, self.song_num)
		return True

'''
	def next_track_gapless(self):
		"""Tell the player to play the next song right away."""
		try:
			if self.song_num == None: # the user clicked prev too many times
				self.song_num = 0
			else:
				self.song_num += 1
			if self.repeat_songs: # if the user wants the album to repeat
				self.song_num = self.song_num % len(self.songs_list)
			else: # don't repeat
				if self.song_num >= len(self.songs_list):
					## dont' let the current position go over the playlist length
					self.song_num = -1
					self.stop()
					return

			print "New song_num", self.song_num
			self.player.set_property('uri', self.ampache_conn.get_song_url(self.songs_list[self.song_num]))
			self.ampache_gui.audioengine_song_changed(songs_list[song_num])
		except:
			return False
		return True
'''
