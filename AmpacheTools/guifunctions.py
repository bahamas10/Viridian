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

import pygtk
pygtk.require("2.0")
import gtk
import os

"""
 GTK Helper functions
"""

def create_single_column_tree_view(column_name, model, sort_column=None):
	"""Create a treeview by passing a column_name and a  model (gtk.ListStore())."""
	tree_view = gtk.TreeView(model)
	tree_view.set_rules_hint(True)
	column = create_column(column_name, 0, sort_column)
	tree_view.append_column(column)
	return tree_view

def create_column(column_name, column_id, sort_column=None, pixbuf=False):
	"""Helper function for treeviews, this will return a column ready to be appended."""
	if pixbuf:
		renderer_text = gtk.CellRendererPixbuf()
		column = gtk.TreeViewColumn(column_name)
		column.pack_start(renderer_text, expand=False)
		column.add_attribute(renderer_text, 'pixbuf', 0)
	else:
		renderer_text = gtk.CellRendererText()
		column = gtk.TreeViewColumn(column_name, renderer_text, text=column_id)
	if sort_column != None:
		column.set_sort_column_id(sort_column)
	else:
		column.set_sort_column_id(column_id)
	return column

def create_image_pixbuf(file, width, height=None):
	"""Helper function to create a pixel buffer from a file of a set width and height."""
	if height == None:
		height = width
	image = gtk.gdk.pixbuf_new_from_file(file).scale_simple(width, height, gtk.gdk.INTERP_BILINEAR)
	return image

def hyperlink(url, text=None):
	"""Returns a button that acts as a hyperlink."""
	if text == None:
		text = url
	label = gtk.Label("<span foreground='blue' underline='low'>"+text+"</span>")
	label.set_use_markup(True)
	button = gtk.Button()
	button.add(label)
	button.set_relief(gtk.RELIEF_NONE)
	button.connect('clicked', lambda x_: os.popen("gnome-open '%s' &" % (url)))
	return button
