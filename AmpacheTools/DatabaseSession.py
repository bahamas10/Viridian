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
	"""
	A class to access and modify a sqlite database.
	"""
	def __init__(self, database):
		"""
		Initialize the database session and create a `variable` table.
		"""
		self.db_conn = sqlite3.connect(database)
		c = self.cursor()
		c.execute('''CREATE TABLE IF NOT EXISTS variable
			(name text NOT NULL DEFAULT '', 
			 value text NOT NULL DEFAULT ''
			)
		''')
		self.commit()
		c.close()
	
	def cursor(self):
		"""
		Returns a cursor to the database.
		"""
		return self.db_conn.cursor()
	
	def commit(self):
		"""
		Commits the database.
		"""
		self.db_conn.commit()

	def table_is_empty(self, table_name):
		"""
		Returns True if the table is empty.
		"""
		c = self.cursor()
		c.execute("""SELECT 1 FROM %s LIMIT 1""" % table_name)
		result = c.fetchone()
		self.commit()
		c.close()
		if result == None:
			return True # empty
		return False
	
	def variable_set(self, var_name, var_value):
		"""
		Save a variable in the database.
		"""
		var_value = self.__convert_specials_to_strings(var_value)
		c = self.cursor()
		c.execute("""DELETE FROM variable WHERE name = ?""", [var_name])
		c.execute("""INSERT INTO variable (name, value) VALUES (?, ?)""", [var_name, var_value])
		self.commit()
		c.close()
	
	def variable_get(self, var_name):
		"""
		Retrieve a variable from the database.
		"""
		try:
			c = self.cursor()
			c.execute("""SELECT value FROM variable WHERE name = ?""", [var_name])
			result = self.__convert_strings_to_specials(c.fetchone()[0])
			self.commit()
			c.close()
		except:
			c.close()
			return None
		return result
		
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
		
