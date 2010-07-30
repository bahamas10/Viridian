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

try:
	import sqlite3
except:
	print "[Warn] sqlite3 not found -- loading sqlite2"
	from pysqlite2 import dbapi2 as sqlite3

class DatabaseSession:
	"""A class to access and modify the sqlite database."""
	def __init__(self):
		"""Initialize the database session."""
		home = os.path.expanduser("~")
		ampache_dir = home + os.sep + '.viridian'
		sqlite_db = ampache_dir + os.sep + 'db.sqlite'
		if not os.path.exists(ampache_dir):
			self.first_time_running = True
			os.mkdir(ampache_dir)
			os.chmod(ampache_dir, 0700) # set strict permissions
		else:
			self.first_time_running = False
		
		# start the database
		self.db_conn = sqlite3.connect(sqlite_db)
		os.chmod(sqlite_db, 0700)
		self.__create_initial_tables()

	def is_first_time(self):
		"""Returns True if this is the first time the program is running."""
		return self.first_time_running
	
	def cursor(self):
		"""Returns a cursor to the database."""
		return self.db_conn.cursor()
	
	def commit(self):
		"""Closes the current cursor."""
		self.db_conn.commit()
		
	def clear_cached_catalog(self):
		"""Clear the locally cached catalog."""
		try:
			c = self.cursor()
			tables = ["artists", "albums", "songs"]
			for table_name in tables:
				c.execute("""DELETE FROM %s""" % table_name)
			self.commit()
			c.close()
		except:
			return False
		return True
		
	def table_is_empty(self, table_name, query_id=None):
		"""Check to see if the table is empty."""
		try:
			c = self.cursor()
			if query_id == None: # checking the artists table
				c.execute("""SELECT 1 FROM %s LIMIT 1""" % table_name)
			else: # check the songs or album table
				if table_name == "albums": # albums
					c.execute("""SELECT 1 FROM %s WHERE artist_id = ? LIMIT 1""" % table_name, [query_id])
				elif table_name == "songs":
					c.execute("""SELECT 1 FROM %s WHERE album_id = ? LIMIT 1""" % table_name, [query_id])
			result = c.fetchone()
			self.commit()
			c.close()
			if result != None:
				return False # not empty
		except:
			return True
		return True
	
	def variable_set(self, var_name, var_value):
		"""Save a variable in the database."""
		try:
			var_value = self.__convert_specials_to_strings(var_value)
			c = self.cursor()
			c.execute("""DELETE FROM variable WHERE name = ?""", [var_name])
			c.execute("""INSERT INTO variable (name, value) VALUES (?, ?)""", [var_name, var_value])
			self.commit()
			c.close()
		except:
			return False
		return True
	
	def variable_get(self, var_name):
		"""Retrieve a variable from the database."""
		try:
			c = self.cursor()
			c.execute("""SELECT value FROM variable WHERE name = ?""", [var_name])
			result = self.__convert_strings_to_specials(c.fetchone()[0])
			self.commit()
			c.close()
		except:
			return None
		return result
	
	##########################################
	# Functions to store artists/albums/songs
	##########################################
	def populate_artists_table(self, list):
		"""Save the list of artists in the artists table."""
		if not list: # list is empty
			return False
		c = self.cursor()
		c.execute("""DELETE FROM artists""")
		for artist_list in list:
			c.execute("""INSERT INTO artists (artist_id, name, custom_name)
				VALUES (?, ?, ?)""", artist_list)
		self.commit()
		c.close
		return True
		
	def populate_albums_table(self, artist_id, list):
		"""Save the list of albums in the albums table."""
		if not list: # list is empty
			return False
		c = self.cursor()
		c.execute("""DELETE FROM albums WHERE artist_id = ?""", [artist_id])
		for album_list in list:
			c.execute("""INSERT INTO albums (artist_id, album_id, name, year, stars)
				VALUES (?,?,?,?,?)""", album_list)
		self.commit()
		c.close
		return True
		
	def populate_songs_table(self, album_id, list):
		"""Save the list of songs in the songs table."""
		if not list: # list is empty
			return False
		c = self.cursor()
		c.execute("""DELETE FROM songs WHERE album_id = ?""", [album_id])
		for song_list in list:
			c.execute("""INSERT INTO songs (album_id, song_id, title,
					track, time, size, artist_name, album_name)
					VALUES (?,?,?,?,?,?,?,?)""", song_list)
		self.commit()
		c.close
		return True
		
	
	##########################################
	# Public Getter Functions
	##########################################
	def get_album_id(self, song_id):
		"""Takes a song_id and returns the album_id"""
		c = self.cursor()
		c.execute("""SELECT album_id FROM songs WHERE song_id = ?""", [song_id])
		result = c.fetchone()[0]
		self.commit()
		c.close()
		return result
		
	def get_album_name(self, album_id):
		"""Takes an album_id and returns the album_name"""
		c = self.cursor()
		c.execute("""SELECT album_name FROM albums WHERE album_id = ?""", [album_id])
		result = c.fetchone()[0]
		self.commit()
		c.close()
		return result
	
	def get_album_year(self, album_id):
		"""Takes an album_id and returns the album_year"""
		c = self.cursor()
		c.execute("""SELECT year FROM albums WHERE album_id = ?""", [album_id])
		result = c.fetchone()[0]
		self.commit()
		c.close()
		return result
	
	def get_artist_id(self, album_id):
		"""Takes an album_id and returns the artist_id"""
		c = self.cursor()
		c.execute("""SELECT artist_id FROM albums WHERE album_id = ?""", [album_id])
		result = c.fetchone()[0]
		self.commit()
		c.close
		return result
		
	def get_artist_name(self, artist_id):
		"""Takes an album_id and returns the album_name"""
		c = self.cursor()
		c.execute("""SELECT name FROM artists WHERE artist_id = ?""", [artist_id])
		result = c.fetchone()[0]
		self.commit()
		c.close()
		return result
	
	def get_artist_ids(self):
		"""Returns a list of all artist ID's."""
		c = self.cursor()
		c.execute("""SELECT artist_id FROM artists""")
		list = []
		for row in c:
			list.append(row[0])
		self.commit()
		c.close()
		return list
		
	def get_album_ids(self):
		"""Returns a list of all album ID's."""
		c = self.cursor()
		c.execute("""SELECT album_id FROM albums""")
		list = []
		for row in c:
			list.append(row[0])
		self.commit()
		c.close()
		return list
		
		
	#######################################
	# Public Dictionary Getter Methods
	#######################################
	def get_artist_dict(self):
		"""Returns a dictionary of all the artists populated from the database.
		This will check to see if the info exists locally before querying Ampache."""
		try:
			c = self.cursor()
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
		self.commit()
		c.close()
		return artist_dict
		
	def get_album_dict(self, artist_id):
		"""Returns a dictionary of all the albums from an artist from the database
		This will check to see if the info exists locally before querying Ampache."""
		try:
			c = self.cursor()
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
		self.commit()
		c.close()
		return album_dict
		
	def get_song_dict(self, album_id):
		"""Returns a dictionary of all the songs from an album from the database
		This will check to see if the info exists locally before querying Ampache."""
		try:
			c = self.cursor()
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
		self.commit()
		c.close()
		return song_dict		
		
	def get_single_song_dict(self, song_id):
		"""Returns a dictionary of one song based on its song_id"""
		try:
			c = self.cursor()
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
		self.commit()
		c.close()
		return song_dict
	
	def get_playlist_song_dict(self, song_id):
		"""Returns a dictionary of one song with slightly less information (faster query)."""
		try:
			c = self.cursor()
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
		self.commit()
		c.close()
		return song_dict

	#######################################
	# Private Functions
	#######################################	
	def __convert_specials_to_strings(self, var_value):
		"""Helper function to convert special variables (like None, True, False) to strings."""
		if var_value == None:
			var_value = "None"
		elif var_value == False:
			var_value = "False"
		elif var_value == True:
			var_value = "True"
		return var_value
		
	def __convert_strings_to_specials(self, var_value):
		"""Helper function to convert strings like None, True, and False to their special object counter-parts."""
		if var_value == "None":
			var_value = None
		if var_value == "False":
			var_value = False
		if var_value == "True":
			var_value = True
		return var_value
		
	def __create_initial_tables(self):
		"""Create the tables in the database when the program starts"""
		c = self.cursor()
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
		self.commit()
		c.close()
		return True

	