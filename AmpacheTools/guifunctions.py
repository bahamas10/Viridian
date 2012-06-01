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
