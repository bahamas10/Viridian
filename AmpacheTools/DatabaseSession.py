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

	def is_first_time(self):
		"""Returns True if this is the first time the program is running."""
		return self.first_time_running
	
	def cursor(self):
		"""Returns a cursor to the database."""
		return self.db_conn.cursor()
	
	def commit(self):
		"""Closes the current cursor."""
		self.db_conn.commit()
		
	def table_is_empty(self, table_name, query_id=None):
		"""Check to see if the table is empty."""
		try:
			c = self.db_conn.cursor()
			if query_id == None: # checking the artists table
				c.execute("""SELECT 1 FROM %s LIMIT 1""" % table_name)
			else: # check the songs or album table
				if table_name == "albums": # albums
					c.execute("""SELECT 1 FROM %s WHERE artist_id = ? LIMIT 1""" % table_name, [query_id])
				elif table_name == "songs":
					c.execute("""SELECT 1 FROM %s WHERE album_id = ? LIMIT 1""" % table_name, [query_id])
			result = c.fetchone()
			if result != None:
				return False # not empty
			self.db_conn.commit()
			c.close()
		except:
			return True
		return True
	
	def variable_set(self, var_name, var_value):
		"""Save a variable in the database."""
		try:
			var_value = self.__convert_specials_to_strings(var_value)
			c = self.db_conn.cursor()
			c.execute("""DELETE FROM variable WHERE name = ?""", [var_name])
			c.execute("""INSERT INTO variable (name, value) VALUES (?, ?)""", [var_name, var_value])
			self.db_conn.commit()
			c.close()
		except:
			return False
		return True
	
	def variable_get(self, var_name):
		"""Retrieve a variable from the database."""
		try:
			c = self.db_conn.cursor()
			c.execute("""SELECT value FROM variable WHERE name = ?""", [var_name])
			result = self.__convert_strings_to_specials(c.fetchone()[0])
			self.db_conn.commit()
			c.close()
		except:
			return None
		return result
	
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

	