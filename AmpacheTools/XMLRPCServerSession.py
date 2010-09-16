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

from SimpleXMLRPCServer import SimpleXMLRPCServer
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler
import xmlrpclib
import thread
import socket


"""
XML RPC Server
"""

class RequestHandler(SimpleXMLRPCRequestHandler):
	# Restrict to a particular path.
	rpc_paths = ('/RPC2',)

class XMLServer:
	def __init__(self, ip, port):
		self.ip   = ip
		self.port = port
		
		self.is_running = False

		self.server = SimpleXMLRPCServer((ip, port), requestHandler=RequestHandler)
		
		self.server.register_introspection_functions()

	def serve_forever(self, data=None):
		"""Start the server."""
		if self.is_running == False:
			self.is_running = True
			thread.start_new_thread(self.__serve_forever, (None,))

	def __serve_forever(self, data=None):
		"""Helper to start in a thread."""
		#self.server.socket.setblocking(0)
		#self.server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		try: self.server.serve_forever()
		except: pass

	def shutdown(self):
		"""Shutdown and close the server."""
		if self.is_running:
			self.server.server_close()
		self.server.socket.close()
		self.is_running = False
			
	
	def register_function(self, function, name=None):
		"""Register a function to use with the XML RPC server."""
		if name == None:
			self.server.register_function(function)
		else:
			self.server.register_function(function, name)

if __name__ == "__main__":
	xml_server = XMLServer("localhost", 8000)
	xml_server.serve_forever()
	import time
	time.sleep(30) # server will run for 30 seconds

