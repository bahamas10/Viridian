#!/usr/bin/python

# basic XML parsing

import xml.dom.minidom

# make the DOM document
dom = xml.dom.minidom.parse('test.xml') 

# separate tags by the tag <root>, and grab the first one by using [0] (i know it's the first because there is only one <root> tag at the beginning
root  = dom.getElementsByTagName('root')[0]
# now parse the root object we just got for every object inside <song> tags
nodes = root.getElementsByTagName('song')

# parse element by element
for child in nodes:
	song_title = child.getElementsByTagName('title')[0].childNodes[0].data
	song_id    = int(child.getAttribute('id'))
	print "id = %d -- name = %s" % (song_id, song_title)

