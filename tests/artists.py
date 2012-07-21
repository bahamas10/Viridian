#!/usr/bin/env python
#
# Copyright (c) 2012, Dave Eddy <dave@daveeddy.com>
# BSD 3 Clause License
#
# Test authentication

import json
import sys

from os.path import abspath, dirname, join, realpath

# Load the AmpacheTools
sys.path.insert(0, realpath(join(dirname(abspath(__file__)), '..')))
from AmpacheTools import AmpacheSession

# Load the conf
try:
    conf = json.loads(open('config.json').read())
except Exception, e:
    print >>sys.stderr, 'Error parsing config\n', e
    sys.exit(1)

# Create the AmpacheSession object
ampache_conn = AmpacheSession.AmpacheSession()
ampache_conn.set_credentials(conf['username'], conf['password'], conf['url'])

if not ampache_conn.authenticate():
    print >>sys.stderr, 'Failed to authenticate!'
    sys.exit(2)

i = 0
for artist in ampache_conn.get_artists():
    print json.dumps(artist, indent=4)
    i+=1
    if i > 10: break
