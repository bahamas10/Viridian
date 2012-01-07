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

import os
import hashlib
import time
import xml.dom.minidom
import urllib2
import urllib
import datetime
import re
import socket
import sys, traceback


### Constants ###
AUTH_MAX_RETRY = 3 # how many times to try and reauth before failure
DEFAULT_TIMEOUT = 10 # default 10 second timeout
__ILLEGAL_XML = u'([\u0000-\u0008\u000b-\u000c\u000e-\u001f\ufffe-\uffff])' + \
		 u'|' + \
		 u'([%s-%s][^%s-%s])|([^%s-%s][%s-%s])|([%s-%s]$)|(^[%s-%s])' % \
		 (unichr(0xd800),unichr(0xdbff),unichr(0xdc00),unichr(0xdfff),
		  unichr(0xd800),unichr(0xdbff),unichr(0xdc00),unichr(0xdfff),
		  unichr(0xd800),unichr(0xdbff),unichr(0xdc00),unichr(0xdfff))
ILLEGAL_XML_RE = re.compile(__ILLEGAL_XML)
socket.setdefaulttimeout(DEFAULT_TIMEOUT)

class AmpacheSession:
	"""
	The AmpacheSession Class.  This is used to communicate to Ampache via the API.
	"""
	def __init__(self):
		"""
		Initialize an AmpacheSession.
		"""
		self.url = None
		self.username = None
		self.password = None
		self.xml_rpc = None
		self.auth = None
		self.last_update_time = -1
		self.artists_num = -1
		self.albums_num = -1
		self.songs_num = -1
		self.auth_current_retry = 0

	def set_credentials(self, username, password, url):
		"""
		Save the ampache url, username, and password.
		"""
		# remove trailing slash off URL
		if url != None:
			while ( url[-1:] == '/' ):
				url = url[:-1]
		# save variables to object
		self.url = url
		self.username = username
		self.password = password
		try:
			self.xml_rpc = self.url + "/server/xml.server.php"
		except:
			pass

	def get_credentials(self):
		"""
		Retrun the url, username, and password as a tuple.
		"""
		return (self.username, self.password, self.url)

	def has_credentials(self):
		"""
		Checks to see if the AmpacheSession object has credentials set.
		"""
		return self.username and self.password and self.url and self.xml_rpc

	def authenticate(self):
		"""
		Attempt to authenticate to Ampache.  Returns True if successful and False if not.
		This will retry AUTH_MAX_RETRY(=3) times.
		"""
		# check for the necessary information
		if not self.has_credentials():
			return False
		# generate the necessary information for the authentication
		timestamp = int(time.time())
		password = hashlib.sha256(self.password).hexdigest()
		authkey = hashlib.sha256(str(timestamp) + password).hexdigest()
		values = {'action'    : 'handshake',
			  'auth'      : authkey,
			  'timestamp' : timestamp,
			  'user'      : self.username,
			  'version'   : '350001',
		}
		data = urllib.urlencode(values)

		# now send the authentication request to Ampache
		try:
			socket.setdefaulttimeout(7) # lower timeout
			response = urllib2.urlopen(self.xml_rpc + '?' + data)
			socket.setdefaulttimeout(DEFAULT_TIMEOUT) # reset timeout
			xml_string = response.read()
			dom = xml.dom.minidom.parseString(xml_string)
			self.auth        = dom.getElementsByTagName("auth")[0].childNodes[0].data
			self.artists_num = int(dom.getElementsByTagName("artists")[0].childNodes[0].data)
			self.albums_num  = int(dom.getElementsByTagName("albums")[0].childNodes[0].data)
			self.songs_num   = int(dom.getElementsByTagName("songs")[0].childNodes[0].data)
		except: # couldn't auth, try up to AUTH_MAX_RETRY times
			self.auth = None
			self.auth_current_retry += 1
			print "[Error] Authentication Failed -- Retry = %d" % self.auth_current_retry
			if ( self.auth_current_retry < AUTH_MAX_RETRY ):
				return self.authenticate()
			else: # authentication failed more than AUTH_MAX_RETRY times
				self.auth_current_retry = 0
				error = None
				try: # to find the error
					error = dom.getElementsByTagName("error")[0].childNodes[0].data
					print "[Error] Authentication Failed :: %s" % error
					return error
				except: # no error found.. must have failed because data was sent to wrong place
					return False
		# if it made it this far, the auth was successfull, now check to see if the catalog needs updating
		try:
			# check to see if ampache has been updated or cleaned since the last time this ran
			update = dom.getElementsByTagName("update")[0].childNodes[0].data
			add    = dom.getElementsByTagName("add")[0].childNodes[0].data
			clean  = dom.getElementsByTagName("clean")[0].childNodes[0].data
			# convert ISO 8601 to epoch
			update = int(time.mktime(time.strptime( update[:-6], "%Y-%m-%dT%H:%M:%S" )))
			add    = int(time.mktime(time.strptime( add[:-6], "%Y-%m-%dT%H:%M:%S" )))
			clean  = int(time.mktime(time.strptime( clean[:-6], "%Y-%m-%dT%H:%M:%S" )))

			new_time  = max([update, add, clean])
			self.last_update_time = new_time
		except Exception, detail:
			print "Couldn't get time catalog was updated -- assuming catalog is dirty -- ", detail
			self.last_update_time = -1
		self.auth_current_retry = 0
		return True

	def is_authenticated(self):
		"""
		Returns True if self.auth is set, and False if it is not.
		"""
		if self.auth != None:
			return True
		return False

	def ping(self):
		"""
		Ping extends the current session to Ampache.
		Returns None if it fails, or the time the session expires if it is succesful
		"""
		values = {'action' : 'ping',
			  'auth'   : self.auth,
		}
		root = self.__call_api(values)
		if not root:
			return None
		session = root.getElementsByTagName('session_expire')[0].childNodes[0].data
		return session

	#######################################
	# Public Getter Methods
	#######################################
	def get_last_update_time(self):
		"""
		Returns the last time the catalog on the Ampache server was updated.
		"""
		return self.last_update_time

	def get_song_url(self, song_id):
		"""
		Takes a song_id and returns the url to the song (with the current authentication).
		"""
		values = {'action' : 'song',
			  'filter' : song_id,
			  'auth'   : self.auth,
		}
		root = self.__call_api(values)
		if not root:
			return None
		song     = root.getElementsByTagName('song')[0]
		song_url = song.getElementsByTagName('url')[0].childNodes[0].data
		return song_url

	def get_album_art(self, album_id):
		"""
		Takes an album_id and returns the url to the artwork (with the current authentication).
		"""
		if album_id == None:
			return None
		values = {'action' : 'album',
			  'filter' : album_id,
			  'auth'   : self.auth,
		}

		root = self.__call_api(values)
		if not root:
			return None
		album     = root.getElementsByTagName('album')[0]
		album_art = album.getElementsByTagName('art')[0].childNodes[0].data
		return album_art

	def get_artists(self, offset=None):
		"""
		Gets all artists and return as a list of dictionaries.
		Example: [
				{ 'artist_id' : artist_id, 'artist_name' : artist_name},
				{ 'artist_id' : 1, 'artist_name' : 'The Reign of Kindo'},
				{ ... },
			 ]
		"""
		if offset == None:
			if self.artists_num > 5000: # offset needed
				print "More than 5000 artists"
				list = []
				for i in range(0, self.artists_num, 5000):
					print "Offset = ", i
					list += self.get_artists(i)
				return list
			values = {'action' : 'artists',
				  'auth'   : self.auth,
			}
		else:
			values = {'action' : 'artists',
				  'auth'   : self.auth,
				  'offset' : offset,
			}

		root = self.__call_api(values)
		if not root: 
			return None
		nodes = root.getElementsByTagName('artist')

		list = []
		try: # get the artists
			for child in nodes:
				artist_name = child.getElementsByTagName('name')[0].childNodes[0].data
				artist_id   = int(child.getAttribute('id'))
				dict = { 'artist_id'   : artist_id,
					 'artist_name' : artist_name,
				       }
				list.append( dict )
		except: # something failed
			traceback.print_exc()
			return None
		return list

	def get_albums(self, offset=None):
		"""
		Gets all albums and return as a list of dictionaries.
		Example: [
				{	 'artist_id'      : artist_id,
					 'artist_name'    : artist_name,
					 'album_id'       : album_id,
					 'album_name'     : album_name,
					 'album_year'     : album_year,
					 'album_tracks'   : album_tracks,
					 'album_disk'     : album_disk,
					 'album_rating'   : album_rating,
					 'precise_rating' : precise_rating,
				},
				{ ... },
			 ]
		"""
		if offset == None:
			if self.albums_num > 5000: # offset needed
				list = []
				for i in range(0, self.albums_num, 5000):
					list += self.get_artists(i)
				return list
			values = {'action' : 'albums',
				  'auth'   : self.auth,
			}
		else:
			values = {'action' : 'albums',
				  'auth'   : self.auth,
				  'offset' : offset,
			}

		root  = self.__call_api(values)
		if not root:
			return None
		nodes = root.getElementsByTagName('album')
		if not nodes:
			return None
		list = []
		try:
			for child in nodes:
				album_id       = int(child.getAttribute('id'))
				album_name     = child.getElementsByTagName('name')[0].childNodes[0].data
				artist_id      = int(child.getElementsByTagName('artist')[0].getAttribute('id'))
				artist_name    = child.getElementsByTagName('artist')[0].childNodes[0].data
				album_year     = child.getElementsByTagName('year')[0].childNodes[0].data
				album_tracks   = int(child.getElementsByTagName('tracks')[0].childNodes[0].data)
				album_disk     = int(child.getElementsByTagName('disk')[0].childNodes[0].data)
				try: # new version doesn't put data in the middle... 
					precise_rating = int(child.getElementsByTagName('preciserating')[0].childNodes[0].data)
				except:
					precise_rating = 0
				try: 
					album_rating = child.getElementsByTagName('rating')[0].childNodes[0].data
				except:
					album_rating = 0
				if album_year == "N/A":
					album_year = 0
				album_year = int(album_year)

				dict = { 'artist_id'      : artist_id,
					 'artist_name'    : artist_name,
					 'album_id'       : album_id,
					 'album_name'     : album_name,
					 'album_year'     : album_year,
					 'album_tracks'   : album_tracks,
					 'album_disk'     : album_disk,
					 'album_rating'   : album_rating,
					 'precise_rating' : precise_rating,
				       }
				list.append( dict )
		except: #something failed
			traceback.print_exc()
			return None
		return list

	def get_songs(self, offset=None):
		"""
		Gets all songs and returns as a list of dictionaries.
		Example: [
				{	'song_id'	: song_id,
					'song_title'     : song_title,
					'artist_id'      : artist_id,
					'artist_name'    : artist_name,
					'album_id'       : album_id,
					'album_name'     : album_name,
					'song_track'     : song_track,
					'song_time'      : song_time,
					'song_size'      : song_size,
					'precise_rating' : precise_rating,
					'rating'	 : rating,
					'art'		 : art,
					'url'		 : url,
				},
				{ ... },
			 ]
		"""
		if offset == None:
			if self.songs_num > 100: # offset needed
				print "over 5000"
				list = []
				for i in range(0, self.songs_num, 100):
					list += self.get_songs(i)
				return list
			values = {'action' : 'songs',
				  'auth'   : self.auth,
			}
		else:
			values = {'action' : 'songs',
				  'auth'   : self.auth,
				  'offset' : offset,
			}
		print values
		root  = self.__call_api(values)
		if not root:
			return None
		nodes = root.getElementsByTagName('song')
		if not nodes:
			return None
		list = []
		try:
			for song in nodes:
				song_id	= int(song.getAttribute('id'))
				song_title     = song.getElementsByTagName('title')[0].childNodes[0].data
				artist_id      = int(song.getElementsByTagName('artist')[0].getAttribute('id'))
				artist_name    = song.getElementsByTagName('artist')[0].childNodes[0].data
				album_id       = int(song.getElementsByTagName('album')[0].getAttribute('id'))
				album_name     = song.getElementsByTagName('album')[0].childNodes[0].data

				song_track     = int(song.getElementsByTagName('track')[0].childNodes[0].data)
				song_time      = int(song.getElementsByTagName('time')[0].childNodes[0].data)
				song_size      = int(song.getElementsByTagName('size')[0].childNodes[0].data)

				try: # New version doesn't initialize this...
					precise_rating = int(song.getElementsByTagName('preciserating')[0].childNodes[0].data)
				except:
					precise_rating = 0
				try:
					rating = float(song.getElementsByTagName('rating')[0].childNodes[0].data)
				except:
					rating = 0

				art	    = song.getElementsByTagName('art')[0].childNodes[0].data
				url	    = song.getElementsByTagName('url')[0].childNodes[0].data
				dict = {   'song_id'	: song_id,
						'song_title'     : song_title,
						'artist_id'      : artist_id,
						'artist_name'    : artist_name,
						'album_id'       : album_id,
						'album_name'     : album_name,
						'song_track'     : song_track,
						'song_time'      : song_time,
						'song_size'      : song_size,
						'precise_rating' : precise_rating,
						'rating'	 : rating,
						'art'	    : art,
						'url'	    : url,
					}
				list.append( dict )
		except:
			traceback.print_exc()
			return None
		return list

	def get_albums_by_artist(self, artist_id):
		"""
		Gets all albums by the artist_id and returns as a list of dictionaries.
		Example: [
				{	 'artist_id'      : artist_id,
					 'artist_name'    : artist_name,
					 'album_id'       : album_id,
					 'album_name'     : album_name,
					 'album_year'     : album_year,
					 'album_tracks'   : album_tracks,
					 'album_disk'     : album_disk,
					 'album_rating'   : album_rating,
					 'precise_rating' : precise_rating,
				},
				{ ... },
			 ]
		"""
		values = {'action' : 'artist_albums',
			  'filter' : artist_id,
			  'auth'   : self.auth,
		}
		root  = self.__call_api(values)
		nodes = root.getElementsByTagName('album')
		if not nodes: 
			return None
		list = []
		try:
			for child in nodes:
				album_id       = int(child.getAttribute('id'))
				album_name     = child.getElementsByTagName('name')[0].childNodes[0].data
				artist_id      = int(child.getElementsByTagName('artist')[0].getAttribute('id'))
				artist_name    = child.getElementsByTagName('artist')[0].childNodes[0].data
				album_year     = child.getElementsByTagName('year')[0].childNodes[0].data
				album_tracks   = int(child.getElementsByTagName('tracks')[0].childNodes[0].data)
				try:
					album_disk = int(child.getElementsByTagName('disk')[0].childNodes[0].data)
				except:
					album_disk = 0
				try: 
					precise_rating = int(child.getElementsByTagName('preciserating')[0].childNodes[0].data)
				except:
					precise_rating = 0
				try: 
					album_rating = child.getElementsByTagName('rating')[0].childNodes[0].data
				except:
					album_rating = 0
				if album_year == "N/A":
					album_year = 0
				album_year = int(album_year)
				
				dict = { 'artist_id'      : artist_id,
					 'artist_name'    : artist_name,
					 'album_id'       : album_id,
					 'album_name'     : album_name,
					 'album_year'     : album_year,
					 'album_tracks'   : album_tracks,
					 'album_disk'     : album_disk,
					 'album_rating'   : album_rating,
					 'precise_rating' : precise_rating,
				       }
				list.append( dict )
		except: #something failed
			print "This artist failed", artist_id
			traceback.print_exc()
			return None
		return list

	def get_songs_by_album(self, album_id):
		"""
		Gets all songs on album_id and returns as a list of dictionaries.
		Example: [
		  		{	'song_id'	: song_id,
					'song_title'     : song_title,
					'artist_id'      : artist_id,
					'artist_name'    : artist_name,
					'album_id'       : album_id,
					'album_name'     : album_name,
					'song_track'     : song_track,
					'song_time'      : song_time,
					'song_size'      : song_size,
					'precise_rating' : precise_rating,
					'rating'	 : rating,
					'art'	    : art,
					'url'	    : url,
				},
				{ ... },
			 ]
		"""
		values = {'action' : 'album_songs',
			  'filter' : album_id,
			  'auth'   : self.auth,
		}
		root  = self.__call_api(values)
		nodes = root.getElementsByTagName('song')
		if not nodes: # list is empty, reauth
			return None
		list = []
		try:
			for song in nodes:
				song_id	= int(song.getAttribute('id'))
				song_title     = song.getElementsByTagName('title')[0].childNodes[0].data
				artist_id      = int(song.getElementsByTagName('artist')[0].getAttribute('id'))
				artist_name    = song.getElementsByTagName('artist')[0].childNodes[0].data
				album_id       = int(song.getElementsByTagName('album')[0].getAttribute('id'))
				album_name     = song.getElementsByTagName('album')[0].childNodes[0].data
				
				song_track     = int(song.getElementsByTagName('track')[0].childNodes[0].data)
				song_time      = int(song.getElementsByTagName('time')[0].childNodes[0].data)
				song_size      = int(song.getElementsByTagName('size')[0].childNodes[0].data)
				
				try: # New version doesn't initialize this...
					precise_rating = int(song.getElementsByTagName('preciserating')[0].childNodes[0].data)
				except: 
					precise_rating = 0
				try:
					rating = float(song.getElementsByTagName('rating')[0].childNodes[0].data)
				except:
					rating = 0

				art	    = song.getElementsByTagName('art')[0].childNodes[0].data
				url	    = song.getElementsByTagName('url')[0].childNodes[0].data
				dict = {   'song_id'	: song_id,
						'song_title'     : song_title,
						'artist_id'      : artist_id,
						'artist_name'    : artist_name,
						'album_id'       : album_id,
						'album_name'     : album_name,
						'song_track'     : song_track,
						'song_time'      : song_time,
						'song_size'      : song_size,
						'precise_rating' : precise_rating,
						'rating'	 : rating,
						'art'	    : art,
						'url'	    : url,
					}
				list.append( dict )
		except:
			print "This album failed", album_id
			traceback.print_exc()
			return None
		return list
		
	def get_song_info(self, song_id):
		"""
		Gets all info about a song from the song_id and returns it as a dictionary.
		Example: {      'song_id'	: song_id,
				'song_title'     : song_title,
				'artist_id'      : artist_id,
				'artist_name'    : artist_name,
				'album_id'       : album_id,
				'album_name'     : album_name,
				'song_track'     : song_track,
				'song_time'      : song_time,
				'song_size'      : song_size,
				'precise_rating' : precise_rating,
				'rating'	 : rating,
				'art'	    : art,
				'url'	    : url,
			 }
		
		"""
		values = {'action' : 'song',
			  'filter' : song_id,
			  'auth'   : self.auth,
		}
		root = self.__call_api(values)
		song = root.getElementsByTagName('song')[0]
		if not song: 
			return None

		song_dict = {}
		try:
			song_id	= int(song.getAttribute('id'))
			song_title     = song.getElementsByTagName('title')[0].childNodes[0].data
			artist_id      = int(song.getElementsByTagName('artist')[0].getAttribute('id'))
			artist_name    = song.getElementsByTagName('artist')[0].childNodes[0].data
			album_id       = int(song.getElementsByTagName('album')[0].getAttribute('id'))
			album_name     = song.getElementsByTagName('album')[0].childNodes[0].data
			
			song_track     = int(song.getElementsByTagName('track')[0].childNodes[0].data)
			song_time      = int(song.getElementsByTagName('time')[0].childNodes[0].data)
			song_size      = int(song.getElementsByTagName('size')[0].childNodes[0].data)
			
			try: # New version doesn't set this...
				precise_rating = int(song.getElementsByTagName('preciserating')[0].childNodes[0].data)
			except:
				precise_rating = 0
			try:
				rating = float(song.getElementsByTagName('rating')[0].childNodes[0].data)
			except:
				rating = 0
			art	    = song.getElementsByTagName('art')[0].childNodes[0].data
			url	    = song.getElementsByTagName('url')[0].childNodes[0].data
			song_dict = {   'song_id'	: song_id,
					'song_title'     : song_title,
					'artist_id'      : artist_id,
					'artist_name'    : artist_name,
					'album_id'       : album_id,
					'album_name'     : album_name,
					'song_track'     : song_track,
					'song_time'      : song_time,
					'song_size'      : song_size,
					'precise_rating' : precise_rating,
					'rating'	 : rating,
					'art'	    : art,
					'url'	    : url,
					}
		except:
			print "This song failed", song_id
			traceback.print_exc()
			return None
		return song_dict

	def get_playlists(self):
		"""
		Gets a list of all of the playlists on the server.
		Example: [
				{	 'id'      : id,
					 'owner'   : owner,
					 'name'    : name,
					 'items'   : items,
					 'type'    : type,
				},
				{ ... },
			 ]
		"""
		values = {'action' : 'playlists',
			  'auth'   : self.auth,
		}
		root  = self.__call_api(values)
		nodes = root.getElementsByTagName('playlist')
		if not nodes: # list is empty, reauth
			return None

		list = []
		try:
			for child in nodes:
				id       = int(child.getAttribute('id'))
				name     = child.getElementsByTagName('name')[0].childNodes[0].data
				owner    = child.getElementsByTagName('owner')[0].childNodes[0].data
				items    = int(child.getElementsByTagName('items')[0].childNodes[0].data)
				type     = child.getElementsByTagName('type')[0].childNodes[0].data
					
				dict = { 'id'      : id,
					 'name'    : name,
					 'items'   : items,
					 'owner'   : owner,
					 'type'    : type,
				}
				list.append( dict )
		except: #something failed
			traceback.print_exc()
			return []
		return list
		
	def get_playlist_songs(self, playlist_id):
		"""
		Gets all info about a song from the song_id and returns it as a dictionary.
		Example: [ 
				{      	'song_id'	: song_id,
					'song_title'     : song_title,
					'artist_id'      : artist_id,
					'artist_name'    : artist_name,
					'album_id'       : album_id,
					'album_name'     : album_name,
					'song_track'     : song_track,
					'song_time'      : song_time,
					'song_size'      : song_size,
					'precise_rating' : precise_rating,
					'rating'	 : rating,
					'art'	    : art,
					'url'	    : url,
				 },
				 {...}
			]
		
		"""
		values = {'action' : 'playlist_songs',
			  'filter' : playlist_id,
			  'auth'   : self.auth,
		}
		root = self.__call_api(values)
		songs = root.getElementsByTagName('song')
		if not songs:
			return None
		list = []
		try:
			for song in songs:
				song_id	       = int(song.getAttribute('id'))
				song_title     = song.getElementsByTagName('title')[0].childNodes[0].data
				artist_id      = int(song.getElementsByTagName('artist')[0].getAttribute('id'))
				artist_name    = song.getElementsByTagName('artist')[0].childNodes[0].data
				album_id       = int(song.getElementsByTagName('album')[0].getAttribute('id'))
				album_name     = song.getElementsByTagName('album')[0].childNodes[0].data
				
				song_track     = int(song.getElementsByTagName('track')[0].childNodes[0].data)
				song_time      = int(song.getElementsByTagName('time')[0].childNodes[0].data)
				song_size      = int(song.getElementsByTagName('size')[0].childNodes[0].data)
				
				try: # New Ampache puts nothing here...
					precise_rating = int(song.getElementsByTagName('preciserating')[0].childNodes[0].data)
				except:
					precise_rating = 0
				try:
					rating = float(song.getElementsByTagName('rating')[0].childNodes[0].data)
				except:
					rating = 0
				art	    = song.getElementsByTagName('art')[0].childNodes[0].data
				url	    = song.getElementsByTagName('url')[0].childNodes[0].data
				song_dict = {   'song_id'        : song_id,
						'song_title'     : song_title,
						'artist_id'      : artist_id,
						'artist_name'    : artist_name,
						'album_id'       : album_id,
						'album_name'     : album_name,
						'song_track'     : song_track,
						'song_time'      : song_time,
						'song_size'      : song_size,
						'precise_rating' : precise_rating,
						'rating'	 : rating,
						'art'	    : art,
						'url'	    : url,
						}
				list.append(song_dict)
		except:
			print "This playlist failed", playlist_id
			traceback.print_exc()
			return None
		return list


	def __call(self, **kwargs):
		"""Takes kwargs and talks to the ampach API.. returning the root element of the XML
		Example: __call(action="artists", filter="kindo") """
		values = kwargs
		return self.__call_api(values)

	def __call_api(self, values):
		"""Takes a dictionary of values and talks to the ampache API... returning the root elemnent of the XML
		Example: __call_api({action: 'artists', filter: 'kindo'}) 
		Automatically adds {auth: <auth>}"""
		values['auth'] = self.auth
		data = urllib.urlencode(values)
		try: # to query ampache
			response = urllib2.urlopen(self.xml_rpc + '?' + data)
			x = self.__sanatize(response.read()) 
			dom = xml.dom.minidom.parseString(x)
		except: # The data pulled from Ampache was invalid
			traceback.print_exc()
			return None
		try: # to make sure authentication is valid and extract the root element
			root  = dom.getElementsByTagName('root')[0]
			if not root: # list is empty, reauth
				raise Exception('Reauthenticate')
			else: # try to find an error
				try: 
					error = root.getElementsByTagName("error")[0].childNodes[0].data
					print "Error! Trying to reauthenticate :: %s" % error
					if self.authenticate():
						return self.__call_api(values)
					return None
				except: # no error found.. must be good XML :)
					return root
		except: # something failed, try to reauth and do it again
			if self.authenticate():
				return self.__call_api(values)
			else: # couldn't authenticate
				return None
		return None


	def __sanatize(self, string):
		"""Sanatize the given string to remove bad characters."""
		# from http://boodebr.org/main/python/all-about-python-and-unicode#UNI_XML 
		for match in ILLEGAL_XML_RE.finditer(string):
			string = string[:match.start()] + "?" + string[match.end():]
		string = string.replace('—', '-')

		try: # try to encode the whole string to UTF-8
			string2 = string.encode("utf-8")
		except: # if it fails try it character by character, stripping out bad characters
			string2 = ""
			for c in string:
				try:
					a = c.encode("utf-8")
					string2 += a
				except:
					string2 += '?'	
		return string2
