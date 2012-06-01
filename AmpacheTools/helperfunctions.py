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


import time
import gtk
import urllib
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
    return urllib.url2pathname(html.replace('&amp;', '&'))

#################
# Sort Functions
#################
def sort_artists_by_custom_name(model, iter1, iter2, column):
    """Custom Function to sort artists by extracting words like "the" and "a"."""
    id1   = model[iter1][1]
    id2   = model[iter2][1]
    band1 = model[iter1][2]
    band2 = model[iter2][2]
    order = column.get_sort_order()
    # First check for -1 artist (always top row)
    if id1 == -1:
        if order == gtk.SORT_DESCENDING:
            return 1
        else:
            return -1
    elif id2 == -1:
        if order == gtk.SORT_DESCENDING:
            return -1
        else:
            return 1

    # sort alphabetically
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
