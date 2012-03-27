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


import hashlib
import os
import re
import sys
import time
import traceback
import urllib
import urllib2

from XMLParser import xmltodict

# The api version this class communicates with
API_VERSION = 350001

# The max number of data to ask for in a single request
MAX_OFFSET = 5000

# how many times to try and reauth before failure
AUTH_MAX_RETRY = 3

__ILLEGAL_XML = u'([\u0000-\u0008\u000b-\u000c\u000e-\u001f\ufffe-\uffff])' + \
		 u'|' + \
		 u'([%s-%s][^%s-%s])|([^%s-%s][%s-%s])|([%s-%s]$)|(^[%s-%s])' % \
		 (unichr(0xd800),unichr(0xdbff),unichr(0xdc00),unichr(0xdfff),
		  unichr(0xd800),unichr(0xdbff),unichr(0xdc00),unichr(0xdfff),
		  unichr(0xd800),unichr(0xdbff),unichr(0xdc00),unichr(0xdfff))
ILLEGAL_XML_RE = re.compile(__ILLEGAL_XML)

class AmpacheSession:
	"""
	Communicate with Ampache via the API.
	"""
	def __init__(self):
		"""
		Initialize an AmpacheSession.
		"""
		self.url = None
		self.username = None
		self.password = None
		self.xml_rpc = None
		self.auth_data = {}

	def set_credentials(self, username, password, url):
		"""
		Save the ampache url, username, and password.
		"""
		# remove trailing slash off URL
		if url:
			while url[-1:] == '/':
				url = url[:-1]
		# save variables to object
		self.url = url
		self.username = username
		self.password = password
		try:
			self.xml_rpc = '%s/server/xml.server.php' % (self.url)
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
		values = {
			'action'    : 'handshake',
			'auth'      : authkey,
			'timestamp' : timestamp,
			'user'      : self.username,
			'version'   : API_VERSION,
		}

		# now send the authentication request to Ampache
		try:
			res = self.__call_api(values)
			for k,v in res.iteritems():
				res[k] = v[0]['child']
			# Save the data returned from the initial authentication
			self.auth_data = res
			print self.auth_data
		except Exception, e: # couldn't auth, try up to AUTH_MAX_RETRY times
			print e
			self.auth_current_retry += 1
			print "[Error] Authentication Failed -- Retry = %d" % self.auth_current_retry
			if self.auth_current_retry < AUTH_MAX_RETRY:
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
		return self.ping() is not None

	def ping(self):
		"""
		Ping extends the current session to Ampache.
		Returns None if it fails, or the time the session expires if it is succesful
		"""
		values = {
			'action' : 'ping',
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
		values = {
			'action' : 'song',
			'filter' : song_id,
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
		if not album_id:
			return None
		values = {
			'action' : 'album',
			'filter' : album_id,
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
		"""
		return self.__get('artists')

	def get_albums(self, offset=None):
		"""
		Gets all albums and return as a list of dictionaries.
		"""
		return self.__get('albums')

	def get_songs(self, offset=None):
		"""
		Gets all songs and returns as a list of dictionaries.
		"""
		return self.__get('songs')

	def get_albums_by_artist(self, artist_id):
		"""
		Gets all albums by the artist_id and returns as a list of dictionaries.
		"""
		return self.__get('album', artist_id)

	def get_songs_by_album(self, album_id):
		"""
		Gets all songs on album_id and returns as a list of dictionaries.
		"""
		return self.__get('song', album_id)

	def get_song_info(self, song_id):
		"""
		Gets all info about a song from the song_id and returns it as a dictionary.
		"""
		return self.__get('song', song_id)

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
		values = {
			'action' : 'playlists',
		}
		root  = self.__call_api(values)
		nodes = root.getElementsByTagName('playlist')
		if not nodes: # list is empty, reauth
			return None

		l = []
		try:
			for child in nodes:
				id       = int(child.getAttribute('id'))
				name     = child.getElementsByTagName('name')[0].childNodes[0].data
				owner    = child.getElementsByTagName('owner')[0].childNodes[0].data
				items    = int(child.getElementsByTagName('items')[0].childNodes[0].data)
				type     = child.getElementsByTagName('type')[0].childNodes[0].data

				d = {
					'id'      : id,
					'name'    : name,
					'items'   : items,
					'owner'   : owner,
					'type'    : type,
				}
				l.append(d)
		except: #something failed
			traceback.print_exc()
			return []
		return l

	def get_playlist_songs(self, playlist_id):
		"""
		Gets all info about a song from the song_id and returns it as a dictionary.
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
				 {...}
			]
		"""
		values = {'action' : 'playlist_songs',
			  'filter' : playlist_id,
		}
		root = self.__call_api(values)
		songs = root.getElementsByTagName('song')
		if not songs:
			return None
		l= []
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
				art = song.getElementsByTagName('art')[0].childNodes[0].data
				url = song.getElementsByTagName('url')[0].childNodes[0].data
				song_dict = {
					'song_id'        : song_id,
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
					'art'            : art,
					'url'            : url,
				}
				l.append(song_dict)
		except:
			print "This playlist failed", playlist_id
			traceback.print_exc()
			return None
		return l


	def __call(self, **kwargs):
		"""Takes kwargs and talks to the ampach API.. returning the root element of the XML
		Example: __call(action="artists", filter="kindo") """
		return self.__call_api(kwargs)

	def __call_api(self, values):
		"""
		Takes a dictionary of values and talks to the ampache API... returning the root elemnent of the XML
		Example: __call_api({action: 'artists', filter: 'kindo'})
		Automatically adds {auth: <auth>}
		"""
		# Add auth key to the request dictionary if not supplie
		if 'auth' not in values:
			values['auth'] = self.auth_data['auth']

		# Encode the data for a GET request
		data = urllib.urlencode(values)

		print values

		# Try to make the request
		xml_string = urllib2.urlopen(self.xml_rpc + '?' + data).read()

		# Parse the XML
		response_data = xmltodict(xml_string)

		# Ensure that there was XML to parse
		if not response_data:
			return None

		# Grab the root element
		response_data = response_data['root'][0]['child']
		print response_data
		return response_data
		'''
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
		'''

	def __get(self, action, _filter=None, offset=None):
		auth_key = action
		if auth_key[-1] == 's':
			# unpluralize
			auth_key = auth_key[:-1]

		values = {
			'action' : action
		}

		# Check if a filter is given
		if _filter:
			values['filter'] = _filter

		# Check if an offset is given
		if offset is not None:
			values['offset'] = offset
		else:
			# No offset given, check to see if one is needed
			if self.auth_data[action] > MAX_OFFSET:
				l = []
				for i in range(0, self.auth_data[action], MAX_OFFSET):
					print 'Offset = %d' % (i)
					l += self.__get(action, offset=i, _filter=_filter)
				return l

		# Make the call
		data = self.__call_api(values)

		# Check to see if the selut was empty
		if not data:
			return []

		# Parse the output
		ret = []
		for item in data[auth_key]:
			d = {}
			if item['attr']:
				d.update(item['attr'])
			for k, v in item['child'].iteritems():
				d[k] = v[0]['child']
			ret.append(d)

		# Return the value
		return ret

	def __sanatize(self, string):
		"""Sanatize the given string to remove bad characters."""
		# from http://boodebr.org/main/python/all-about-python-and-unicode#UNI_XML
		for match in ILLEGAL_XML_RE.finditer(string):
			string = string[:match.start()] + "?" + string[match.end():]

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
