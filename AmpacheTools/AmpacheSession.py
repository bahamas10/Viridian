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
import time
import re
import shutil

### Constants ###
AUTH_MAX_RETRY = 3 # how many times to try and reauth before failure

class AmpacheSession:
	"""The AmpacheSession Class.  This is used to communicate to Ampache via the API."""
	def __init__(self, db_session):
		"""Initialize an AmpacheSession object and create/load the database in ~/.viridian/."""
		#################################
		# Set Variables
		#################################
		home = os.path.expanduser("~")
		self.ampache_dir = home + os.sep + '.viridian'
		self.db_session = db_session
		
		self.first_time_running = self.db_session.is_first_time()
		self.is_catalog_up_to_date = None

		# get the art folder
		self.art_folder = self.ampache_dir + os.sep + 'album_art'
		if not os.path.exists(self.art_folder):
			os.mkdir(self.art_folder)
		

		# start the database
		c = self.db_session.cursor()
		self.__create_initial_tables(c) # check to see if tables exists
		self.db_session.commit()
		c.close()

		self.auth_current_retry = 0
		
	def set_ampache_gui_hook(self, ampache_gui):
		"""Save the AmpacheGUI in the AmpacheSession to allow this object to communicate to the GUI."""
		self.ampache_gui = ampache_gui

	def set_credentials(self, url, username, password):
		"""Save the ampache url, username, and password"""
		# remove trailing slash off URL
		if ( url[-1:] == '/' ):
			url = url[:-1]
		# save variables to object
		self.url = url
		self.username = username
		self.password = password
		self.xml_rpc = self.url + "/server/xml.server.php"
		# save to database
		try:
			c = self.db_session.cursor()
			self.__set_credentials_in_db(c)
			self.db_session.commit()
			c.close()
		except:
			return False
		return True
	
	def has_credentials(self):
		"""Checks to see if the AmpacheSession object has credentials set.
		If not, this function will attempt to pull the credentials from the database."""
		if hasattr(self, 'username') and hasattr(self, 'password') and hasattr(self, 'url') and hasattr(self, 'xml_rpc'):
			if self.username == "" or self.password == "" or self.url == "" or self.xml_rpc == "":
				return False
			return True
		try: # now check DB
			c = self.db_session.cursor()
			if self.__get_credentials_from_db(c): # variables pulled from DB
				self.db_session.commit()
				c.close()
			else: # variables not found, 
				self.db_session.commit()
				c.close()
				return False
		except: # no db???? shouldn't happen
			return False
		# make sure the credentials aren't blank
		if hasattr(self, 'username') and hasattr(self, 'password') and hasattr(self, 'url') and hasattr(self, 'xml_rpc'):
			if self.username == "" or self.password == "" or self.url == "" or self.xml_rpc == "":
				return False
		return True
			
	def authenticate(self):
		"""Attempt to authenticate to Ampache.  Returns True if successful and False if not.
		This will retry AUTH_MAX_RETRY times."""
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
			response = urllib2.urlopen(self.xml_rpc, data)
			dom = xml.dom.minidom.parseString(response.read())
			self.auth        = dom.getElementsByTagName("auth")[0].childNodes[0].data
			self.artists_num = int(dom.getElementsByTagName("artists")[0].childNodes[0].data)
		except: # couldn't auth, try up to AUTH_MAX_RETRY times
			self.auth = None
			self.auth_current_retry += 1
			print "[Error] Authentication Failed -- Retry = %d -- Sleeping 1 second before retry." % self.auth_current_retry
			if ( self.auth_current_retry < AUTH_MAX_RETRY ):
				time.sleep(.5)
				return self.authenticate()
			else:
				self.auth_current_retry = 0
				print "[Error] Authentication Failed!"
				self.ampache_gui.authentication_failed_callback()
			return False
		# if it made it this far, the auth was successfull, now check to see if the catalog needs updating
		self.new_last_update_time = 0
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
			self.new_last_update_time = new_time
			c = self.db_session.cursor()
			last_time = self.__get_last_catalog_update_time(c)
			if (last_time < new_time) and last_time != -1:
				self.is_catalog_up_to_date = False
			else:
				self.save_new_time()
				self.is_catalog_up_to_date = True
			self.db_session.commit()
			c.close()
		except:
			print "Couldn't get time catalog was updated -- assuming catalog is dirty"
			self.is_catalog_up_to_date = False
		self.auth_current_retry = 0
		return True
				
	def is_authenticated(self):
		"""Returns True if self.auth is set, and False if it is not."""
		try:
			if self.auth != None:
				return True
			else:
				return False
		except:
			return False
				
	
	#######################################
	# Public Getter Methods
	#######################################
	def get_song_url(self, song_id):
		"""Takes a song_id and returns the url to the song (with the current authentication)."""
		values = {'action' : 'song',
			  'filter' : song_id,
			  'auth'   : self.auth,
		}
		data = urllib.urlencode(values)

		try:
			response = urllib2.urlopen(self.xml_rpc, data)
			dom = xml.dom.minidom.parseString(response.read())
		except: # The data pulled from Ampache was invalid
			print "Error Pulling Data! -- Check Ampache"
			return False
		try:
			root     = dom.getElementsByTagName('root')[0]
			song     = root.getElementsByTagName('song')[0]
			song_url = song.getElementsByTagName('url')[0].childNodes[0].data
		except: # something failed, try to reauth and do it again
			if self.authenticate():
				return self.get_song_url(song_id)
			else: # couldn't authenticate
				return False
		return song_url
		
	def get_album_art(self, album_id):
		"""Takes an album_id and returns the url to the artwork (with the current authentication)."""
		values = {'action' : 'album',
			  'filter' : album_id,
			  'auth'   : self.auth,
		}
		data = urllib.urlencode(values)

		try:
			response = urllib2.urlopen(self.xml_rpc, data)
			dom = xml.dom.minidom.parseString(response.read())
		except: # The data pulled from Ampache was invalid
			print "Error Pulling Data! -- Check Ampache"
			return False
		try:
			root      = dom.getElementsByTagName('root')[0]
			album     = root.getElementsByTagName('album')[0]
			album_art = album.getElementsByTagName('art')[0].childNodes[0].data
		except: # something failed, try to reauth and do it again
			if self.authenticate():
				return self.get_album_art(album_id)
			else: # couldn't authenticate
				return False
		return album_art
	
	
	#######################################
	# Public Dictionary Getter Methods
	#######################################
	def get_artist_dict(self):
		"""Returns a dictionary of all the artists populated from the database.
		This will check to see if the info exists locally before querying Ampache."""
		if self.db_session.table_is_empty('artists'):
			c = self.db_session.cursor()
			c.execute("""DELETE FROM artists""")
			self.db_session.commit()
			c.close()
			if self.artists_num <= 5000: # no offset needed
				print "Less than 5000 artists"
				self.__populate_artists_dict()
			else:
				print "More than 5000 artists"
				for i in range(0, self.artists_num, 5000):
					print "Offset = ", i
					self.__populate_artists_dict(i)
		try:
			c = self.db_session.cursor()
			c.execute("""SELECT artist_id, name, custom_name FROM artists order by name""")
			artist_dict = {}
			for row in c:
				artist_id   = row[0]
				artist_name = row[1]
				custom_name = row[2]
				artist_dict[artist_id] = { 'name'        : artist_name,
							   'custom_name' : custom_name,
							}
		except:
			return None
		self.db_session.commit()
		c.close()
		return artist_dict
		
	def get_album_dict(self, artist_id):
		"""Returns a dictionary of all the albums from an artist from the database
		This will check to see if the info exists locally before querying Ampache."""
		if self.db_session.table_is_empty('albums', artist_id):
			self.__populate_albums_dict(artist_id)
		try:
			c = self.db_session.cursor()
			c.execute("""SELECT album_id, name, year, stars FROM albums
				WHERE artist_id = ? order by year""", [artist_id])
			album_dict = {}
			for row in c:
				album_id    = row[0]
				album_name  = row[1]
				album_year  = row[2]
				album_stars = row[3]
				album_dict[album_id] = { 'name'  : album_name,
							 'year'  : album_year,
							 'stars' : album_stars,
							}
		except:
			return None
		self.db_session.commit()
		c.close()
		return album_dict
		
	def get_song_dict(self, album_id):
		"""Returns a dictionary of all the songs from an album from the database
		This will check to see if the info exists locally before querying Ampache."""
		if self.db_session.table_is_empty('songs', album_id):
			self.__populate_songs_dict(album_id)
		try:
			c = self.db_session.cursor()
			c.execute("""SELECT song_id, title, track, time, size, artist_name, album_name FROM songs
				WHERE album_id = ? order by track""", [album_id])
			song_dict = {}
			for row in c:
				song_id     = row[0]
				song_title  = row[1]
				song_track  = row[2]
				song_time   = row[3]
				song_size   = row[4]
				artist_name = row[5]
				album_name  = row[6]
				song_dict[song_id] = {  'title' : song_title,
							'track' : song_track,
							'time'  : song_time,
							'size'  : song_size,
							'artist_name' : artist_name,
							'album_name'  : album_name,
						}
		except:
			return None
		self.db_session.commit()
		c.close()
		return song_dict
		
	def get_single_song_dict(self, song_id):
		"""Returns a dictionary of one song based on its song_id"""
		try:
			c = self.db_session.cursor()
			c.execute("""SELECT album_id, title, track, time, size, artist_name FROM songs
				WHERE song_id = ?""", [song_id])
			for row in c:
				album_id    = row[0]
				song_title  = row[1]
				song_track  = row[2]
				song_time   = row[3]
				song_size   = row[4]
				artist_name = row[5]
				song_dict = {   'album_id'    : album_id,
						'song_title'  : song_title,
						'song_track'  : song_track,
						'song_time'   : song_time,
						'song_size'   : song_size,
						'song_id'     : song_id,
						'artist_name' : artist_name,
						}
			c.execute("""SELECT name, album_id, stars FROM albums 
				WHERE album_id = ?""", [song_dict['album_id']])
			data = c.fetchone()
			song_dict['album_name']  = data[0]
			song_dict['artist_id']   = data[1]
			song_dict['album_stars'] = data[2]
		except:
			return None
		self.db_session.commit()
		c.close()
		return song_dict
		
	def get_playlist_song_dict(self, song_id):
		"""Returns a dictionary of one song with slightly less information (faster query)."""
		try:
			c = self.db_session.cursor()
			c.execute("""SELECT title, artist_name, album_name FROM songs
				WHERE song_id = ?""", [song_id])
			for row in c:
				song_title  = row[0]
				artist_name = row[1]
				album_name  = row[2]
				song_dict = {   'song_title'  : song_title,
						'artist_name' : artist_name,
						'album_name'  : album_name,
						}
		except:
			return None
		self.db_session.commit()
		c.close()
		return song_dict
		
	#######################################
	# Public Populator Methods
	#######################################
	def populate_albums_dict(self, artist_id):
		"""This populates the albums dictionary, skipping already cached items."""
		if self.db_session.table_is_empty('albums', artist_id):
			self.__populate_albums_dict(artist_id)
	
	def populate_songs_dict(self, album_id):
		"""This populates the songs dictionary, skipping already cached items."""
		if self.db_session.table_is_empty('songs', album_id):
			self.__populate_songs_dict(album_id)
		
	#######################################
	# Public Simple Getter Methods
	#######################################
	def get_album_id(self, song_id):
		"""Takes a song_id and returns the album_id"""
		c = self.db_session.cursor()
		c.execute("""SELECT album_id FROM songs WHERE song_id = ?""", [song_id])
		result = c.fetchone()[0]
		self.db_session.commit()
		c.close()
		return result
		
	def get_album_name(self, album_id):
		"""Takes an album_id and returns the album_name"""
		c = self.db_session.cursor()
		c.execute("""SELECT album_name FROM albums WHERE album_id = ?""", [album_id])
		result = c.fetchone()[0]
		self.db_session.commit()
		c.close()
		return result
	
	def get_album_year(self, album_id):
		"""Takes an album_id and returns the album_year"""
		c = self.db_session.cursor()
		c.execute("""SELECT year FROM albums WHERE album_id = ?""", [album_id])
		result = c.fetchone()[0]
		self.db_session.commit()
		c.close()
		return result
	
	def get_artist_id(self, album_id):
		"""Takes an album_id and returns the artist_id"""
		c = self.db_session.cursor()
		c.execute("""SELECT artist_id FROM albums WHERE album_id = ?""", [album_id])
		result = c.fetchone()[0]
		self.db_session.commit()
		c.close
		return result
		
	def get_artist_name(self, artist_id):
		"""Takes an album_id and returns the album_name"""
		c = self.db_session.cursor()
		c.execute("""SELECT name FROM artists WHERE artist_id = ?""", [artist_id])
		result = c.fetchone()[0]
		self.db_session.commit()
		c.close()
		return result
	
	def get_artist_ids(self):
		"""Returns a list of all artist ID's."""
		c = self.db_session.cursor()
		c.execute("""SELECT artist_id FROM artists""")
		list = []
		for row in c:
			list.append(row[0])
		self.db_session.commit()
		c.close()
		return list
		
	def get_album_ids(self):
		"""Returns a list of all album ID's."""
		c = self.db_session.cursor()
		c.execute("""SELECT album_id FROM albums""")
		list = []
		for row in c:
			list.append(row[0])
		self.db_session.commit()
		c.close()
		return list

	#######################################
	# Public Miscellanous Methods
	#######################################
	def clear_cached_catalog(self):
		"""Clear the cached catalog completely."""
		c = self.db_session.cursor()
		return_val = self.__clear_cached_catalog(c)
		self.db_session.commit()
		c.close()
		self.save_new_time()
		return return_val
	
	def clear_album_art(self):
		"""Clear local album art."""
		art_folder = self.art_folder
		print "+++ Checking for album art +++"
		for root, dirs, files in os.walk(art_folder):
			for name in files:
				print "Deleting ", os.path.join(root, name)
				os.remove(os.path.join(root, name))
				
	def reset_everything(self):
		"""Delete all private/personal data from the users system."""
		try:
			shutil.rmtree(self.ampache_dir)
			os.rmdir(self.ampache_dir)
		except:
			pass
						
	def is_first_time(self):
		"""Returns True if this is the first time this program is ran (if ~/.ampache didn't exist)."""
		return self.first_time_running
	
	def is_up_to_date(self):
		"""Returns True if the catalog is up to date."""
		return self.is_catalog_up_to_date
	
	def save_new_time(self):
		"""Saves the last check time."""
		c = self.db_session.cursor()
		try:
			result = self.__set_last_catalog_update_time(c, self.new_last_update_time)
			self.is_catalog_up_to_date = True
		except:
			result = False
			pass
		self.db_session.commit()
		c.close()
		return result
	
	
	#######################################
	# Private Methods
	#######################################
	def __unknown_error(self):
		print "An unknown error has occured -- could be related to Ampache itself!"
	
	def __populate_artists_dict(self, offset=None):
		"""Populates self.artist.dict with all artists and artists id's"""
		if offset == None:
			values = {'action' : 'artists',
				  'auth'   : self.auth,
			}
		else:
			values = {'action' : 'artists',
				  'auth'   : self.auth,
				  'offset' : offset,
			}
		data = urllib.urlencode(values)
		try: 
			response = urllib2.urlopen(self.xml_rpc, data)
			dom = xml.dom.minidom.parseString(response.read())
		except: # The data pulled from Ampache was invalid
			print "Error Pulling Data! -- Check Ampache"
			return False
		try: # try to get the list of artists
			root  = dom.getElementsByTagName('root')[0]
			nodes = root.getElementsByTagName('artist')
		except: # something failed, try to reauth and do it again
			if self.authenticate():
				return self.__populate_artists_dict(offset)
			else: # couldn't authenticate
				return False
		try: # add the artists to the database
			c = self.db_session.cursor()
			for child in nodes:
				artist_name = child.getElementsByTagName('name')[0].childNodes[0].data
				artist_id   = int(child.getAttribute('id'))
				custom_artist_name = re.sub('^the |^a ', '', artist_name.lower())
				c.execute("""INSERT INTO artists (artist_id, name, custom_name)
						VALUES (?, ?, ?)""", [artist_id, artist_name, custom_artist_name])
			self.db_session.commit()
			c.close()
		except: # something failed
			return False
		return True

	def __populate_albums_dict(self, artist_id):
		values = {'action' : 'artist_albums',
			  'filter' : artist_id,
			  'auth'   : self.auth,
		}
		data = urllib.urlencode(values)
		try:
			response = urllib2.urlopen(self.xml_rpc, data)
			dom = xml.dom.minidom.parseString(response.read())
		except: # The data pulled from Ampache was invalid
			print "Error Pulling Data! -- Check Ampache -- Artist ID = %d" % artist_id
			return False
		try:
			root  = dom.getElementsByTagName('root')[0]
			nodes = root.getElementsByTagName('album')
			if not nodes: # list is empty, reauth
				raise Exception('Reauthenticate')
		except: # something failed, try to reauth and do it again
			if self.authenticate():
				return self.__populate_albums_dict(artist_id)
			else: # couldn't authenticate
				return False
		try:
			c = self.db_session.cursor()
			c.execute("""DELETE FROM albums WHERE artist_id = ?""", [artist_id])
			self.db_session.commit()
			for child in nodes:
				album_id    = int(child.getAttribute('id'))
				album_name  = child.getElementsByTagName('name')[0].childNodes[0].data
				album_year  = child.getElementsByTagName('year')[0].childNodes[0].data
				album_stars = child.getElementsByTagName('preciserating')[0].childNodes[0].data 
				if album_year == "N/A":
					album_year = 0
				album_year = int(album_year)
				c.execute("""INSERT INTO albums (artist_id, album_id, name, year, stars)
						VALUES (?,?,?,?,?)""", [artist_id, album_id, album_name, album_year, album_stars])
			self.db_session.commit()
			c.close()
		except: #something failed
			return False
		return True

	def __populate_songs_dict(self, album_id):
		values = {'action' : 'album_songs',
			  'filter' : album_id,
			  'auth'   : self.auth,
		}
		data = urllib.urlencode(values)
		try:
			response = urllib2.urlopen(self.xml_rpc, data)
			dom = xml.dom.minidom.parseString(response.read())
		except: # The data pulled from Ampache was invalid
			print "Error Pulling Data! -- Check Ampache -- Album ID = %d" % album_id
			return False
		try:
			root  = dom.getElementsByTagName('root')[0]
			nodes = root.getElementsByTagName('song')
			if not nodes: # list is empty, reauth
				raise Exception('Reauthenticate')
		except: # something failed, try to reauth and do it again
			if self.authenticate():
				return self.__populate_songs_dict(album_id)
			else: # couldn't authenticate
				return False
		### Now put the data in the database
		try:
			c = self.db_session.cursor()
			c.execute("""DELETE FROM songs WHERE album_id = ?""", [album_id])
			self.db_session.commit()
			for child in nodes:
				song_id     = int(child.getAttribute('id'))
				song_title  = child.getElementsByTagName('title')[0].childNodes[0].data
				song_track  = int(child.getElementsByTagName('track')[0].childNodes[0].data)
				song_time   = int(child.getElementsByTagName('time')[0].childNodes[0].data)
				song_size   = int(child.getElementsByTagName('size')[0].childNodes[0].data)
				artist_name = child.getElementsByTagName('artist')[0].childNodes[0].data
				album_name  = child.getElementsByTagName('album')[0].childNodes[0].data
				c.execute("""INSERT INTO songs (album_id, song_id, title, 
						track, time, size, artist_name, album_name)
						VALUES (?,?,?,?,?,?,?,?)
						""", [album_id, song_id, song_title, song_track, song_time, song_size, artist_name, album_name])
			self.db_session.commit()
			c.close()
			# append to self.song.dict
		except:
			return False
		return True
		


	def __create_initial_tables(self, c):
		"""Create the tables in the database when the program starts"""
		c.execute('''CREATE TABLE IF NOT EXISTS variable
			(name text NOT NULL DEFAULT '', 
			 value text NOT NULL DEFAULT ''
			)
		''')
		c.execute('''CREATE TABLE IF NOT EXISTS artists
			(artist_id INTEGER NOT NULL DEFAULT '', 
			 name text NOT NULL DEFAULT '',
			 custom_name text NOT NULL DEFAULT '',
			 PRIMARY KEY (artist_id)
			)
		''')
		c.execute('''CREATE TABLE IF NOT EXISTS albums
			(artist_id int NOT NULL DEFAULT '', 
			 album_id int NOT NULL DEFAULT '',
			 name text NOT NULL DEFAULT '',
			 year int DEFAULT '',
			 stars int DEFAULT 0,
			 PRIMARY KEY (album_id, artist_id)
			)
		''')
		c.execute('''CREATE TABLE IF NOT EXISTS songs
			(album_id int NOT NULL DEFAULT '', 
			 song_id int NOT NULL DEFAULT '',
			 title text NOT NULL DEFAULT '',
			 track int NOT NULL DEFAULT 0,
			 time int DEFAULT 0,
			 size int DEFAULT 0,
			 artist_name text NOT NULL DEFAULT '',
			 album_name text NOT NULL DEFAULT '',
			 PRIMARY KEY (song_id)
			)
		''')
		return True
		
		
	def __set_credentials_in_db(self, c):
		"""Save the credentials to the database."""
		try:
			c.execute('''DELETE FROM variable
				WHERE name like "credentials_%"''')
			c.execute("""INSERT INTO variable(name, value) VALUES
				('credentials_username', ?)""", [self.username])
			c.execute("""INSERT INTO variable(name, value) VALUES
				('credentials_password', ?)""", [self.password])
			c.execute("""INSERT INTO variable(name, value) VALUES
				('credentials_url', ?)""", [self.url])
			c.execute("""INSERT INTO variable(name, value) VALUES
				('credentials_xml_rpc', ?)""", [self.xml_rpc])
		except:
			return False
		return True
	
	def __get_credentials_from_db(self, c):
		"""Try to retrieve the credentials from the database."""
		try:
			c.execute("""SELECT value FROM variable
				WHERE name = 'credentials_username'""")
			self.username = c.fetchone()[0]
			c.execute("""SELECT value FROM variable
				WHERE name = 'credentials_password'""")
			self.password = c.fetchone()[0]
			c.execute("""SELECT value FROM variable
				WHERE name = 'credentials_url'""")
			self.url = c.fetchone()[0]
				
			self.xml_rpc = self.url + "/server/xml.server.php"
		except:
			return False
		return True


	def __set_last_catalog_update_time(self, c, last_time):
		"""Save the last update time to the database."""
		try:	
			c.execute("""DELETE FROM variable WHERE NAME = 'catalog_update'""")
			c.execute("""INSERT INTO variable (name, value) VALUES 
					('catalog_update', ?)""", [last_time])
		except:
			return False
		return True
	
		
	def __get_last_catalog_update_time(self, c):
		"""Retrieve the last update time from the database."""
		try:
			c.execute("""SELECT value FROM variable
				WHERE name = 'catalog_update'""")
			last_time = c.fetchone()[0]
		except:
			return -1
		return int(last_time)
	
	def __clear_cached_catalog(self, c):
		"""Clear the locally cached catalog."""
		try:
			tables = ["artists", "albums", "songs"]
			for table_name in tables:
				c.execute("""DELETE FROM %s""" % table_name)
		except:
			return False
		return True
		
