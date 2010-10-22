#!/usr/bin/env python
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

from distutils.core import setup

setup(name='Viridian',
	version='1.1',
	description='Viridian Media Player',
	author='Dave Eddy',
	author_email='dave@daveeddy.com',
	url='http://www.daveeddy.com',
	scripts=['viridian', 'viridian-cli'],
	packages=['AmpacheTools'],
	package_data={'AmpacheTools' : ['images/*', 'doc/*']}
)
