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
 Extra functions to query the database, to be used by AmpacheTools.AmpacheGUI
"""

import cPickle

def clear_cached_catalog(db_session):
    """Clear the locally cached catalog."""
    try:
        c = db_session.cursor()
        tables = ["artists", "albums", "songs"]
        for table_name in tables:
            c.execute("""DELETE FROM %s""" % table_name)
        db_session.commit()
        c.close()
    except:
        return False
    return True

def table_is_empty(db_session, table_name, query_id):
    """Check to see if a portion of the table is empty."""
    try:
        c = db_session.cursor()
        if table_name == "albums": # albums
            c.execute("""SELECT 1 FROM %s WHERE artist_id = ? LIMIT 1""" % table_name, [query_id])
        elif table_name == "songs":
            c.execute("""SELECT 1 FROM %s WHERE album_id = ? LIMIT 1""" % table_name, [query_id])
        result = c.fetchone()
        #db_session.commit()
        c.close()
        if result is not None:
            return False # not empty
    except:
        pass
    return True

def song_has_info(db_session, song_id):
    """Check to see if a portion of the table is empty."""
    try:
        c = db_session.cursor()
        c.execute("""SELECT 1 FROM %s WHERE song_id = ? LIMIT 1""" % 'songs', [song_id])
        result = c.fetchone()
        #db_session.commit()
        c.close()
        if result is None:
            return False # not empty
    except:
        return False
    return True

##########################################
# Functions to store artists/albums/songs
##########################################
def populate_artists_table(db_session, l):
    """Save the list of artists in the artists table."""
    if not l: # list is empty
        return False
    c = db_session.cursor()
    c.execute("""DELETE FROM artists""")
    for artist_list in l:
        c.execute("""INSERT INTO artists (artist_id, name, custom_name)
            VALUES (?, ?, ?)""", artist_list)
    db_session.commit()
    c.close()
    return True

def populate_full_albums_table(db_session, l):
    """Save all albums to the albums table"""
    if not l:
        return False
    c = db_session.cursor()
    c.execute("""DELETE FROM albums""")
    for album_list in l:
        c.execute("""INSERT INTO albums (artist_id, album_id, name, year, precise_rating)
            VALUES (?,?,?,?,?)""", album_list)
    db_session.commit()
    c.close()
    return True

def populate_albums_table(db_session, artist_id, l):
    """Save the list of albums in the albums table."""
    if not l: # list is empty
        return False
    #print list
    c = db_session.cursor()
    c.execute("""DELETE FROM albums WHERE artist_id = ?""", [artist_id])
    for album_list in l:
        c.execute("""INSERT INTO albums (artist_id, album_id, name, year, precise_rating)
            VALUES (?,?,?,?,?)""", album_list)
    db_session.commit()
    c.close()
    return True

def populate_full_songs_table(db_session, l):
    """Save the list of songs in the songs table."""
    if not l: # list is empty
        return False
    c = db_session.cursor()
    c.execute("""DELETE FROM songs""")
    for song_list in l:
        c.execute("""INSERT INTO songs (album_id, song_id, title,
                track, time, size, artist_name, album_name)
                VALUES (?,?,?,?,?,?,?,?)""", song_list)
    db_session.commit()
    c.close()
    return True

def populate_songs_table(db_session, album_id, l):
    """Save the list of songs in the songs table."""
    if not l: # list is empty
        return False
    c = db_session.cursor()
    c.execute("""DELETE FROM songs WHERE album_id = ?""", [album_id])
    for song_list in l:
        c.execute("""INSERT INTO songs (album_id, song_id, title,
                track, time, size, artist_name, album_name)
                VALUES (?,?,?,?,?,?,?,?)""", song_list)
    db_session.commit()
    c.close()
    return True

##########################################
# Public Getter Functions
##########################################
def get_album_id(db_session, song_id):
    """Takes a song_id and returns the album_id"""
    c = db_session.cursor()
    c.execute("""SELECT album_id FROM songs WHERE song_id = ?""", [song_id])
    result = c.fetchone()[0]
    #db_session.commit()
    c.close()
    return result

def get_album_name(db_session, album_id):
    """Takes an album_id and returns the album_name"""
    c = db_session.cursor()
    c.execute("""SELECT album_name FROM albums WHERE album_id = ?""", [album_id])
    result = c.fetchone()[0]
    #db_session.commit()
    c.close()
    return result

def get_album_year(db_session, album_id):
    """Takes an album_id and returns the album_year"""
    c = db_session.cursor()
    c.execute("""SELECT year FROM albums WHERE album_id = ?""", [album_id])
    result = c.fetchone()[0]
    #db_session.commit()
    c.close()
    return result

def get_artist_id(db_session, album_id):
    """Takes an album_id and returns the artist_id"""
    c = db_session.cursor()
    c.execute("""SELECT artist_id FROM albums WHERE album_id = ?""", [album_id])
    result = c.fetchone()[0]
    #db_session.commit()
    c.close
    return result

def get_artist_name(db_session, artist_id):
    """Takes an album_id and returns the album_name"""
    c = db_session.cursor()
    c.execute("""SELECT name FROM artists WHERE artist_id = ?""", [artist_id])
    result = c.fetchone()[0]
    #db_session.commit()
    c.close()
    return result

def get_artist_ids(db_session):
    """Returns a list of all artist ID's."""
    c = db_session.cursor()
    c.execute("""SELECT artist_id FROM artists""")
    l = []
    for row in c:
        l.append(row[0])
    #db_session.commit()
    c.close()
    return l

def get_album_ids(db_session):
    """Returns a list of all album ID's."""
    c = db_session.cursor()
    c.execute("""SELECT album_id FROM albums""")
    l = []
    for row in c:
        l.append(row[0])
    #db_session.commit()
    c.close()
    return l

#######################################
# Public Dictionary Getter Methods
#######################################
def get_artist_dict(db_session):
    """Returns a dictionary of all the artists populated from the database.
    This will check to see if the info exists locally before querying Ampache."""
    artist_dict = {}
    try:
        c = db_session.cursor()
        c.execute("""SELECT artist_id, name, custom_name FROM artists order by name""")
        for row in c:
            artist_id   = row[0]
            artist_name = row[1]
            custom_name = row[2]
            artist_dict[artist_id] = { 'name'        : artist_name,
                           'custom_name' : custom_name,
                        }
    except:
        artist_dict = None
    #db_session.commit()
    c.close()
    return artist_dict

def get_album_dict(db_session, artist_id=None):
    """Returns a dictionary of all the albums from an artist from the database
    This will check to see if the info exists locally before querying Ampache."""
    album_dict = {}
    if artist_id is None:
        try:
            c = db_session.cursor()
            c.execute("""SELECT album_id, name, year, precise_rating FROM albums""")
            for row in c:
                album_id       = row[0]
                album_name     = row[1]
                album_year     = row[2]
                precise_rating = row[3]
                album_dict[album_id] = {'name'          : album_name,
                            'year'          : album_year,
                            'precise_rating' : precise_rating,
                            }
        except:
            album_dict = None
        #db_session.commit()
        c.close()
    else:
        try:
            c = db_session.cursor()
            c.execute("""SELECT album_id, name, year, precise_rating FROM albums
                WHERE artist_id = ? order by year""", [artist_id])
            for row in c:
                album_id       = row[0]
                album_name     = row[1]
                album_year     = row[2]
                precise_rating = row[3]
                album_dict[album_id] = {'name'          : album_name,
                            'year'          : album_year,
                            'precise_rating' : precise_rating,
                            }
        except:
            album_dict = None
        #db_session.commit()
        c.close()
    return album_dict

def get_song_dict(db_session, album_id):
    """Returns a dictionary of all the songs from an album from the database
    This will check to see if the info exists locally before querying Ampache."""
    song_dict = {}
    try:
        c = db_session.cursor()
        c.execute("""SELECT song_id, title, track, time, size, artist_name, album_name FROM songs
            WHERE album_id = ? order by track""", [album_id])
        for row in c:
            song_id     = row[0]
            song_title  = row[1]
            song_track  = row[2]
            song_time   = row[3]
            song_size   = row[4]
            artist_name = row[5]
            album_name  = row[6]
            song_dict[song_id] = {  'title' : song_title,
                            'track' : song_track,
                            'time'  : song_time,
                            'size'  : song_size,
                            'artist_name' : artist_name,
                            'album_name'  : album_name,
                        }
    except:
        song_dict = None
    #db_session.commit()
    c.close()
    return song_dict

def get_single_song_dict(db_session, song_id):
    """Returns a dictionary of one song based on its song_id"""
    song_dict = {}
    try:
        c = db_session.cursor()
        c.execute("""SELECT album_id, title, track, time, size, artist_name FROM songs
            WHERE song_id = ?""", [song_id])
        for row in c:
            album_id    = row[0]
            song_title  = row[1]
            song_track  = row[2]
            song_time   = row[3]
            song_size   = row[4]
            artist_name = row[5]
            song_dict = {   'album_id'    : album_id,
                    'song_title'  : song_title,
                    'song_track'  : song_track,
                    'song_time'   : song_time,
                    'song_size'   : song_size,
                    'song_id'     : song_id,
                    'artist_name' : artist_name,
                    }
        c.execute("""SELECT name, album_id, precise_rating FROM albums
            WHERE album_id = ?""", [song_dict['album_id']])
        data = c.fetchone()
        song_dict['album_name']    = data[0]
        song_dict['artist_id']     = data[1]
        song_dict['precise_rating'] = data[2]
    except:
        song_dict = None
    #db_session.commit()
    c.close()
    return song_dict

def get_playlist_song_dict(db_session, song_id):
    """Returns a dictionary of one song with slightly less information (faster query)."""
    song_dict = {}
    try:
        c = db_session.cursor()
        c.execute("""SELECT title, artist_name, album_name FROM songs
            WHERE song_id = ?""", [song_id])
        for row in c:
            song_title  = row[0]
            artist_name = row[1]
            album_name  = row[2]
            song_dict = {   'song_title'  : song_title,
                    'artist_name' : artist_name,
                    'album_name'  : album_name,
                    }
    except:
        song_dict = None
    #db_session.commit()
    c.close()
    return song_dict

def set_playlist(db_session, name, songs):
    """Saves a playilst with the given name in the database, automatically pickles list."""
    c = db_session.cursor()
    c.execute("""DELETE FROM playlists WHERE name = ?""", [name])
    c.execute("""INSERT INTO playlists (name, songs) VALUES (?, ?)""", [name, str(cPickle.dumps(songs))])
    db_session.commit()
    c.close()

def remove_playlist(db_session, name):
    """Removes a playlist from the database"""
    c = db_session.cursor()
    c.execute("""DELETE FROM playlists WHERE name = ?""", [name])
    db_session.commit()
    c.close()

def get_playlist(db_session, name, default_value=[]):
    """Retrieve a playlist from the database."""
    try:
        c = db_session.cursor()
        c.execute("""SELECT songs FROM playlists WHERE name = ?""", [name])
        result = c.fetchone()[0]
        c.close()
    except:
        c.close()
        return default_value
    return cPickle.loads(str(result))

def get_playlists(db_session):
    """Retrieve all playlists stored locally as a list"""
    c = db_session.cursor()
    c.execute("""SELECT name,songs FROM playlists""")
    l = []
    for row in c:
        l.append(
            {'name' : row[0],
             'songs': cPickle.loads(str(row[1])),
            }
        )
    c.close()
    return l

def create_initial_tables(db_session):
    """Create the tables in the database when the program starts"""
    c = db_session.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS artists
        (artist_id INTEGER NOT NULL DEFAULT '',
        name text NOT NULL DEFAULT '',
        custom_name text NOT NULL DEFAULT '',
        PRIMARY KEY (artist_id)
        )
    ''')
    c.execute('''CREATE TABLE IF NOT EXISTS albums
        (artist_id int NOT NULL DEFAULT '',
        album_id int NOT NULL DEFAULT '',
        name text NOT NULL DEFAULT '',
        year int DEFAULT '',
        precise_rating int DEFAULT 0,
        PRIMARY KEY (artist_id, album_id)
        )
    ''')
    c.execute('''CREATE TABLE IF NOT EXISTS songs
        (album_id int NOT NULL DEFAULT '',
        song_id int NOT NULL DEFAULT '',
        title text NOT NULL DEFAULT '',
        track int NOT NULL DEFAULT 0,
        time int DEFAULT 0,
        size int DEFAULT 0,
        artist_name text NOT NULL DEFAULT '',
        album_name text NOT NULL DEFAULT '',
        PRIMARY KEY (song_id)
        )
    ''')
    c.execute('''CREATE TABLE IF NOT EXISTS playlists
        (name text NOT NULL DEFAULT '',
        songs text NOT NULL DEFAULT '',
        PRIMARY KEY (name)
        )
    ''')
    db_session.commit()
    c.close()
