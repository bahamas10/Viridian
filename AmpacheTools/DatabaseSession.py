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


import os
import cPickle

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
		c.close()
		if not result:
			return True
		return False

	def variable_set(self, var_name, var_value):
		"""
		Save a variable in the database.
		"""
		#var_value = self.__convert_specials_to_strings(var_value)
		c = self.cursor()
		c.execute("""DELETE FROM variable WHERE name = ?""", [var_name])
		c.execute("""INSERT INTO variable (name, value) VALUES (?, ?)""", [var_name, str(cPickle.dumps(var_value))])
		self.commit()
		c.close()

	def variable_get(self, var_name, default_value=None):
		"""
		Retrieve a variable from the database.
		"""
		try:
			c = self.cursor()
			c.execute("""SELECT value FROM variable WHERE name = ?""", [var_name])
			result = c.fetchone()[0]
			c.close()
		except:
			c.close()
			return default_value
		return cPickle.loads(str(result))
