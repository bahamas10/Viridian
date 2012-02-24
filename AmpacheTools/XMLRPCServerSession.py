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
"""
XML RPC Server
"""
import xmlrpclib
import thread
import socket

from SimpleXMLRPCServer import SimpleXMLRPCServer
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler

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
