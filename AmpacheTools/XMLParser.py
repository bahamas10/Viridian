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
XMLParser.py

Functions to convert XML into a python data structure


Original code from:
	http://nonplatonic.com/ben.php?title=python_xml_to_dict_bow_to_my_recursive_g&more=1&c=1&tb=1&pb=1
Modified by:
	Dave Eddy <dave@daveeddy.com>
"""

import xml.dom.minidom
from collections import defaultdict

def xmltodict(xmlstring):
	"""
	Convert an XML string into a dictionary

	@param	xmlstring	{string}	The XML string

	@return	{dict}	The resultant object
	"""
	doc = xml.dom.minidom.parseString(xmlstring)
	return _elementtodict(doc)

def _elementtodict(parent):
	"""
	[Private function]

	Recursively search an XML element and construct a dictionary

	@param	element	{Node.ELEMENT_NODE}	The node to search

	@return	{dict}	The resultant object
	"""
	child = parent.firstChild
	# Return None for the stopping condition
	if not child:
		return None
	while child.nodeType == xml.dom.minidom.Node.TEXT_NODE and not child.data.strip():
		child = child.nextSibling
	# If we hit a text node just return it
	if child.nodeType == xml.dom.minidom.Node.TEXT_NODE:
		return child.nodeValue
	# Create a dictionary of lists
	d = defaultdict(list)
	while child:
		# If we have a node with elements in it
		if child.nodeType == xml.dom.minidom.Node.ELEMENT_NODE:
			attr_dict = {}
			# Check to see if there are attributes
			if child.hasAttributes():
				attrs = child.attributes
				# Loop the attributes
				for i in xrange(0, attrs.length - 1):
					_attr = attrs.item(i)
					attr_dict[_attr.name] = _attr.value
				#d[child.tagName]['attr'] = attr_dict
			d[child.tagName].append({'attr' : attr_dict, 'child' : _elementtodict(child)})
		child = child.nextSibling
	# Convert the default dict to regular dict
	return dict(d)

if __name__ == '__main__':
	import sys
	from pprint import pprint

	try:
		xml_file = sys.argv[1]
	except IndexError:
		print 'File must be given as an argument.'
		sys.exit(1)

	s = open(xml_file, 'r').read()
	d = xmltodict(s)

	pprint(d)
