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

import time
import gtk

"""
 Misc. functions for AmpacheGUI
"""

#################
# Formatters
#################
def convert_filesize_to_human_readable(bytes):
	"""Converts bytes to humand_readable form."""
	if bytes >= 1073741824:
		return str(round(bytes / 1024 / 1024 / 1024, 1)) + ' GB'
	elif bytes >= 1048576:
		return str(round(bytes / 1024 / 1024, 1)) + ' MB'
	elif bytes >= 1024:
		return str(round(bytes / 1024, 1)) + ' KB'
	elif bytes < 1024:
		return str(bytes) + ' bytes'
	return str(bytes)
	

def convert_seconds_to_human_readable(seconds):
	"""Converts seconds to a human readable string."""
	if seconds == 0:
		return "0:00"
	# convert time in seconds to HH:MM:SS THIS WILL FAIL IF LENGTH > 24 HOURS
	new_time = time.strftime('%H:%M:%S', time.gmtime(seconds))
	if new_time[:3] == "00:": # strip out hours if below 60 minutes
		new_time = new_time[3:]
	if new_time[:3] == "00:": # convert 00:xx to 0:x
		new_time = new_time[1:]
	return new_time
	
def convert_string_to_html(string):
	"""Change characters to HTML friendly versions."""
	return string.replace('&', '&amp;')

def convert_html_to_string(html):
	"""Replace HTML characters to their normal character counterparts."""
	return html.replace('&amp;', '&').replace('%20', ' ').replace('%27', "'")
	
#################
# Sort Functions
#################
def sort_artists_by_custom_name(model, iter1, iter2, data=None):
	"""Custom Function to sort artists by extracting words like "the" and "a"."""
	band1 = model[iter1][2]
	band2 = model[iter2][2]

	if band1 < band2:
		return -1
	elif band1 > band2:
		return 1
	return 0

def sort_albums_by_year(model, iter1, iter2, column):
	"""Custom function to sort albums by year."""
	year1 = model[iter1][2]
	year2 = model[iter2][2]
	order = column.get_sort_order()
	# First check for -1 album (always top row)
	if year1 == -1:
		if order == gtk.SORT_DESCENDING:
			return 1
		else:
			return -1
	elif year2 == -1:
		if order == gtk.SORT_DESCENDING:
			return -1
		else:
			return 1
	# otherwise organize them by their years
	if year1 < year2:
		return -1
	elif year1 > year2:
		return 1
	else:
		name1 = model[iter1][0]
		name2 = model[iter2][0]
		if name1 < name2:
			return -1
		elif name1 > name2:
			return 1
	return 0

def sort_songs_by_title(model, iter1, iter2, data=None):
	"""Custom function to sort titles alphabetically."""
	title1 = model[iter1][1]
	title2 = model[iter2][1]
	
	if title1 < title2:
		return -1
	elif title2 < title1:
		return 1
	return 0

def sort_songs_by_track(model, iter1, iter2, data=None):
	"""Custom function to sort songs by track."""
	track1 = model[iter1][0]
	track2 = model[iter2][0]

	if track1 < track2:
		return -1
	elif track1 > track2:
		return 1
	return sort_songs_by_title(model, iter1, iter2, data)

def sort_songs_by_album(model, iter1, iter2, data=None):
	"""Custom function to sort songs by album, if the albums are the same it will sort by tracks."""
	album1 = model[iter1][3]
	album2 = model[iter2][3]

	if album1 < album2:
		return -1
	elif album1 > album2:
		return 1
	return sort_songs_by_track(model, iter1, iter2, data)

def sort_songs_by_artist(model, iter1, iter2, data=None):
	"""Custom function to sort songs by artist, if the artists are the same it will sort by albums."""
	artist1 = model[iter1][2]
	artist2 = model[iter2][2]

	if artist1 < artist2:
		return -1
	elif artist1 > artist2:
		return 1
	return sort_songs_by_album(model, iter1, iter2, data)
