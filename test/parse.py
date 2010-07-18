#!/usr/bin/python
import xml.dom.minidom
import os
import hashlib
import time
import urllib2
import urllib
import exceptions
import sys

dom = xml.dom.minidom.parse('test.xml')

root  = dom.getElementsByTagName('root')[0]
nodes = root.getElementsByTagName('song')

for child in nodes:
	artist_name = child.getElementsByTagName('title')[0].childNodes[0].data
	artist_id   = int(child.getAttribute('id'))
	print "id = %d -- name = %s" % (artist_id, artist_name)

