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

import sys
import os
import urllib2
import time
import thread
import gobject
import urllib
import re

try: # check for pynotify
	import pynotify
	pynotify.init('Viridian')
	pynotify_object = pynotify.Notification(" ", " ")
	PYNOTIFY_INSTALLED = True
except:
	PYNOTIFY_INSTALLED = False
try: # require pygtk
 	import pygtk
  	pygtk.require("2.0")
	import gtk
except:
  	print "pygtk required!"
	sys.exit(1);
	
### Contstants ###
ALBUM_ART_SIZE = 80
SCRIPT_PATH    = os.path.dirname(sys.argv[0])
SCRIPT_PATH    = os.path.abspath(os.path.dirname(__file__))
IMAGES_DIR     = SCRIPT_PATH + os.sep + 'images' + os.sep
THREAD_LOCK    = thread.allocate_lock()

class AmpacheGUI:
	"""The Ampache GUI Class"""
	def main(self):
		"""Method to call gtk.main() and display the GUI."""
		gobject.threads_init()
		gobject.idle_add(self.main_gui_callback)
		### Status tray icon ####
		self.tray_icon_to_display = self.db_session.variable_get('tray_icon_to_display')
		if self.tray_icon_to_display == None: # default to standard
			self.tray_icon_to_display = "standard"
			
		if self.tray_icon_to_display == "standard":
			self.tray_icon = gtk.StatusIcon()
			self.tray_icon.set_from_stock(gtk.STOCK_ABOUT)
			self.tray_icon.connect('activate', self.status_icon_activate)
			self.tray_icon.connect('popup-menu', self.status_icon_popup_menu)
			self.tray_icon.set_tooltip('Viridian')
		thread.start_new_thread(self.query_position, (None,))
		gtk.main()

	def delete_event(self, widget, event, data=None):
		"""Keep the window alive when it is X'd out."""
		if not hasattr(self, 'tray_icon') or self.quit_when_window_closed: # no tray icon set, must destroy
			self.destroy()
		else:
			if self.first_time_closing:
				self.main_gui_toggle_hidden()
				self.create_dialog_alert("info", """Viridian is still running in the status bar.  If you do not want Viridian to continue running when the window is closed you can disable this in the preferences window.""", True)
				self.first_time_closing = False
				self.db_session.variable_set('first_time_closing', 'False')
			else: 
				self.main_gui_toggle_hidden()
		return True

	def destroy(self, widget=None, data=None):
		"""The function when the program exits."""
		if THREAD_LOCK.locked():
			result = self.create_dialog_ok_or_close("Downloads in progress..", "There are unfinished downloads, are you sure you want to quit?")
			if result != "ok":
				return True
		self.stop_all_threads()
		size = self.window.get_size()
		gtk.main_quit()
		self.db_session.variable_set('window_size_width',  size[0])
		self.db_session.variable_set('window_size_height', size[1])

	def __init__(self, ampache_conn, audio_engine, db_session):
		"""Constructor for the AmpacheGUI Class.
		Takes an AmpacheSession Object, an AudioEngine Object and a DatabaseSession Object."""
		#################################
		# Set Variables
		#################################
		self.audio_engine = audio_engine
		self.ampache_conn = ampache_conn
		self.db_session   = db_session

		##################################
		# Load Images
		##################################
		self.images_pixbuf_play  = self.__create_image_pixbuf(IMAGES_DIR + 'play.png', 75)
		self.images_pixbuf_pause = self.__create_image_pixbuf(IMAGES_DIR + 'pause.png', 75)
		self.images_pixbuf_gold_star = self.__create_image_pixbuf(IMAGES_DIR + 'star_rating_gold.png', 16)
		self.images_pixbuf_gray_star = self.__create_image_pixbuf(IMAGES_DIR + 'star_rating_gray.png', 16)
		images_pixbuf_prev = self.__create_image_pixbuf(IMAGES_DIR + 'prev.png', 75)
		images_pixbuf_next = self.__create_image_pixbuf(IMAGES_DIR + 'next.png', 75)
		self.images_pixbuf_playing = self.__create_image_pixbuf(IMAGES_DIR + 'playing.png', 15)
		self.images_pixbuf_empty   = self.__create_image_pixbuf(IMAGES_DIR + 'empty.png', 1)

		##################################
		# Main Window
		##################################
		self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)

		self.window.connect("delete_event", self.delete_event)
		self.window.connect("destroy", self.destroy)
		self.window.set_title("Viridian")
		width = self.db_session.variable_get('window_size_width')
		if width == None:
			width = 900
		height = self.db_session.variable_get('window_size_height')
		if height == None:
			height = 600
		height = int(height)
		width  = int(width)
		self.window.resize(width, height)

		main_box = gtk.VBox()
		
		#################################
		# Menu Bar
		#################################
		menu_bar = gtk.MenuBar()
		
		agr = gtk.AccelGroup()
		self.window.add_accel_group(agr)
		
		"""Start File Menu"""
		file_menu = gtk.Menu()
		filem = gtk.MenuItem("_File")
		filem.set_submenu(file_menu)

		newi = gtk.MenuItem("Reathenticate")
		newi.connect("activate", self.button_reauthenticate_clicked)
		file_menu.append(newi)
		
		sep = gtk.SeparatorMenuItem()
		file_menu.append(sep)
		
		newi = gtk.MenuItem("Clear Album Art")
		newi.connect("activate", self.button_clear_album_art_clicked)
		file_menu.append(newi)
		
		newi = gtk.MenuItem("Clear Local Cache")
		newi.connect("activate", self.button_clear_cached_artist_info_clicked)
		file_menu.append(newi)
		
		newi = gtk.MenuItem("Pre-Cache")
		newi.connect("activate", self.button_pre_cache_info_clicked)
		file_menu.append(newi)
		
		sep = gtk.SeparatorMenuItem()
		file_menu.append(sep)

		exit = gtk.ImageMenuItem(gtk.STOCK_QUIT, agr)
		key, mod = gtk.accelerator_parse("<Control>Q")
		exit.add_accelerator("activate", agr, key, mod, gtk.ACCEL_VISIBLE)

		exit.connect("activate", self.destroy)

		file_menu.append(exit)

		menu_bar.append(filem)
		"""End File Menu"""
		
		"""Start Edit Menu"""
		edit_menu = gtk.Menu()
		editm = gtk.MenuItem("_Edit")
		editm.set_submenu(edit_menu)

		newi = gtk.ImageMenuItem(gtk.STOCK_PREFERENCES, agr)
		key, mod = gtk.accelerator_parse("<Control>E")
		newi.add_accelerator("activate", agr, key, mod, gtk.ACCEL_VISIBLE)

		newi.connect("activate", self.show_settings)

		edit_menu.append(newi)

		menu_bar.append(editm)
		"""End Edit Menu"""

		"""Start View Menu"""
		view_menu = gtk.Menu()
		viewm = gtk.MenuItem("_View")
		viewm.set_submenu(view_menu)

		newi = gtk.CheckMenuItem("Show Playlist")
		show_playlist = self.db_session.variable_get('show_playlist')
		if show_playlist == None:
			show_playlist = False
		newi.set_active(show_playlist)
		newi.connect("activate", self.toggle_playlist_view)
		view_menu.append(newi)
		
		self.show_downloads_checkbox = gtk.CheckMenuItem("Show Downloads")
		show_downloads = self.db_session.variable_get('show_downloads')
		if show_downloads == None:
			show_downloads = False
		self.show_downloads_checkbox.set_active(show_downloads)
		self.show_downloads_checkbox.connect("activate", self.toggle_downloads_view)
		view_menu.append(self.show_downloads_checkbox)
		
		sep = gtk.SeparatorMenuItem()
		view_menu.append(sep)

		newi = gtk.CheckMenuItem("View Statusbar")
		view_statusbar = self.db_session.variable_get('view_statusbar')
		if view_statusbar == None:
			view_statusbar = True
		newi.set_active(view_statusbar)
		newi.connect("activate", self.toggle_statusbar_view)
		view_menu.append(newi)

		menu_bar.append(viewm)
		"""End View Menu"""
		
		"""Start Help Menu"""
		help_menu = gtk.Menu()
		helpm = gtk.MenuItem("_Help")
		helpm.set_submenu(help_menu)
		
		newi = gtk.ImageMenuItem(gtk.STOCK_ABOUT)
		newi.connect("activate", self.create_about_dialog)
		help_menu.append(newi)
		
		menu_bar.append(helpm)
		"""End Help Menu"""

		vbox = gtk.VBox(False, 2)
		vbox.pack_start(menu_bar, False, False, 0)

		main_box.pack_start(vbox, False, False, 0)
		"""End Menu Bar"""
	
		#################################
		# Top Control Bar
		#################################
		top_bar = gtk.HBox()
		
		top_bar_left = gtk.VBox()
		top_bar_left_top = gtk.HBox()
		top_bar_left_bottom = gtk.HBox()
		
		### Prev Button
		prev_image = gtk.Image()
		prev_image.set_from_pixbuf(images_pixbuf_prev)
		
		event_box_prev = gtk.EventBox()
		event_box_prev.connect("button_release_event", self.button_prev_clicked)
		event_box_prev.add(prev_image)
		
		
		### Play/Pause Button
		self.play_pause_image = gtk.Image()
		self.play_pause_image.set_from_pixbuf(self.images_pixbuf_play)
		
		event_box_play = gtk.EventBox()
		event_box_play.connect("button_release_event", self.button_play_pause_clicked)
		event_box_play.add(self.play_pause_image)
		
		
		next_image = gtk.Image()
		next_image.set_from_pixbuf(images_pixbuf_next)
		
		event_box_next = gtk.EventBox()
		event_box_next.connect("button_release_event", self.button_next_clicked)
		event_box_next.add(next_image)

		
		top_bar_left_top.pack_start(event_box_prev, False, False, 0)
		top_bar_left_top.pack_start(event_box_play, False, False, 0)
		top_bar_left_top.pack_start(event_box_next, False, False, 0)
		
		### Repeat Songs
		repeat_songs_checkbutton = gtk.CheckButton("Repeat")
		repeat_songs_checkbutton.set_active(False)
		repeat_songs_checkbutton.connect("toggled", self.toggle_repeat_songs)
		
		self.notification_label = gtk.Label(" ")
		
		top_bar_left_bottom.pack_start(repeat_songs_checkbutton, False, False, 0)
		top_bar_left_bottom.pack_start(self.notification_label, False, False, 10)
		
		top_bar_left.pack_start(top_bar_left_top, False, False, 0)
		top_bar_left.pack_start(top_bar_left_bottom, False, False, 0)
		
		top_bar.pack_start(top_bar_left, False, False, 0)
		"""End Top Control Bar"""
		
		#################################
		# Scrubbing Bar
		#################################
		vbox = gtk.VBox()
		
		hbox = gtk.HBox()
		
		self.time_elapsed_label = gtk.Label("0:00")
		hbox.pack_start(self.time_elapsed_label, False, False, 2)
		
		self.time_elapsed_slider = gtk.HScale()
		self.time_elapsed_slider.set_inverted(False)
		self.time_elapsed_slider.set_range(0, 1)
		self.time_elapsed_slider.set_increments(1, 10)
		self.time_elapsed_slider.set_draw_value(False)
		hbox.pack_start(self.time_elapsed_slider, True, True, 2)
		
		self.time_total_label = gtk.Label("0:00")
		hbox.pack_start(self.time_total_label, False, False, 2)
		
		
		vbox.pack_start(hbox, False, False, 40)
		
		top_bar.pack_start(vbox)
		
		#################################
		# Now Playing / Album Art
		#################################
		now_playing_info = gtk.VBox()

		filler = gtk.Label()
		self.current_song_label   = gtk.Label()
		self.current_artist_label = gtk.Label()
		self.current_album_label  = gtk.Label()

		now_playing_info.pack_start(filler, False, False, 1)
		now_playing_info.pack_start(self.current_song_label,   False, False, 1)
		now_playing_info.pack_start(self.current_artist_label, False, False, 1)
		now_playing_info.pack_start(self.current_album_label,  False, False, 1)
		
		vbox = gtk.VBox()
		
		self.album_art_image = gtk.Image()
		
		event_box_album = gtk.EventBox()
		event_box_album.connect("button_release_event", self.button_album_art_clicked)
		#event_box_album.connect("button_release_event", self.button_album_art_clicked)
		event_box_album.add(self.album_art_image)
		
		hbox = gtk.HBox()
		
		### Stars
		self.rating_stars_list = []
		
		i = 0
		while i < 5: # 5 stars
			self.rating_stars_list.append(gtk.Image())
			hbox.pack_start(self.rating_stars_list[i], False, False, 1)
			i += 1
	
		vbox.pack_start(event_box_album, False, False, 0)
		vbox.pack_start(hbox, False, False, 0)
	
		top_bar.pack_end(vbox, False, False, 0)
		top_bar.pack_end(now_playing_info, False, False, 15)
		
		main_box.pack_start(top_bar, False, False, 3)
		"""End Now Playing Info/Album Art"""
		
		#################################
		# Middle Section
		#################################
		hpaned = gtk.HPaned()
		hpaned.set_position(270)
		
		#################################
		# Playlist / Downloads Window
		#################################
		self.side_panel = gtk.VBox()
		
		###################### Playlist ########################
		self.playlist_window = gtk.VBox()
		
		playlist_scrolled_window = gtk.ScrolledWindow()
		playlist_scrolled_window.set_shadow_type(gtk.SHADOW_ETCHED_IN)
		playlist_scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
			
		# str, title - artist - album, song_id
		self.playlist_list_store = gtk.ListStore(gtk.gdk.Pixbuf, str, int)

		tree_view = gtk.TreeView(self.playlist_list_store)
		tree_view.connect("row-activated", self.playlist_on_activated)
		tree_view.connect("button_press_event", self.playlist_on_right_click)
		tree_view.set_rules_hint(True)
		
		new_column = self.__create_column("    ", 0, None, True)
		new_column.set_reorderable(False)
		new_column.set_resizable(False)
		new_column.set_clickable(False)
		new_column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
		new_column.set_fixed_width(20)
		tree_view.append_column(new_column)
		
		renderer_text = gtk.CellRendererText()
		new_column = gtk.TreeViewColumn("Current Playlist", renderer_text, markup=1)
		#new_column = self.__create_column("Current Playlist", 1)
		new_column.set_reorderable(False)
		new_column.set_resizable(False)
		new_column.set_clickable(False)
		new_column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
		tree_view.append_column(new_column)
		
		playlist_scrolled_window.add(tree_view)
		
		self.playlist_window.pack_start(playlist_scrolled_window)
		
		hbox = gtk.HBox()
		
		button = gtk.Button("Clear Playlist")
		button.connect('clicked', self.audio_engine.clear_playlist)
		
		hbox.pack_start(button, False, False, 2)
		
		self.playlist_window.pack_start(hbox, False, False, 2)
		
		self.side_panel.pack_start(self.playlist_window)
		
		########################## Downloads ######################
				
		self.downloads_window = gtk.VBox()	
		
		downloads_panel_scrolled_window = gtk.ScrolledWindow()
		downloads_panel_scrolled_window.set_shadow_type(gtk.SHADOW_ETCHED_IN)
		downloads_panel_scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
		
		downloads_window_list = gtk.VBox()
		
		self.downloads_list_store = gtk.ListStore(str, int, str)
		tree_view = gtk.TreeView(self.downloads_list_store)
		tree_view.connect("row-activated", self.downloads_on_activated)
		tree_view.connect("button_press_event", self.downloads_on_right_click)
		tree_view.set_rules_hint(True)
		column = gtk.TreeViewColumn("File", gtk.CellRendererText(), text=0)
		column.set_reorderable(False)
		column.set_resizable(True)
		column.set_clickable(False)
		column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
		column.set_fixed_width(100)
		
		tree_view.append_column(column)
		
		rendererprogress = gtk.CellRendererProgress()
		column = gtk.TreeViewColumn("Progress")
		column.pack_start(rendererprogress, True)
		column.add_attribute(rendererprogress, "value", 1)
		column.set_reorderable(False)
		column.set_resizable(True)
		column.set_clickable(False)
		column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
		
		tree_view.append_column(column)
			
		downloads_window_list.pack_start(tree_view)
		
		downloads_panel_scrolled_window.add_with_viewport(downloads_window_list)
		
		self.downloads_window.pack_start(downloads_panel_scrolled_window)
		
		self.side_panel.pack_start(self.downloads_window)
		
		#############################
		
		hpaned.pack1(self.side_panel)
		
		####################################
		# Artists/Albums/Songs
		####################################
		
		middle_vpaned = gtk.VPaned()
		middle_vpaned.set_position(170)
		
		"""Middle Top"""
		middle_top = gtk.HBox()

		"""Middle Top Left"""
		#################################
		# Artists
		#################################
		artists_scrolled_window = gtk.ScrolledWindow()
		artists_scrolled_window.set_shadow_type(gtk.SHADOW_ETCHED_IN)
		artists_scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
		
		# name, id, custom_name
		self.artist_list_store = gtk.ListStore(str, int, str)
		self.artist_list_store.set_sort_func(0, self.__sort_artists_by_custom_name)
		#self.artist_list_store.set_default_sort_func(self.__sort_artists_by_custom_name)
		self.artist_list_store.set_sort_column_id(0, gtk.SORT_ASCENDING)
		tree_view = self.__create_single_column_tree_view("Artist", self.artist_list_store)
		tree_view.connect("cursor-changed", self.artists_cursor_changed)
		#tree_view.connect("popup-menu", self.artists_cursor_changed)
		tree_view.set_search_column(0)
		artists_scrolled_window.add(tree_view)
		"""End Middle Top Left"""
		
		"""Begin Middle Top Right"""
		#################################
		# Albums
		#################################
		albums_scrolled_window = gtk.ScrolledWindow()
		albums_scrolled_window.set_shadow_type(gtk.SHADOW_ETCHED_IN)
		albums_scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
	
		# name, id, year, stars
		self.album_list_store = gtk.ListStore(str, int, int, int)
		#self.album_list_store.set_default_sort_func(self.__sort_albums_by_year)
		self.album_list_store.set_sort_column_id(0, gtk.SORT_ASCENDING)
		self.album_list_store.set_sort_func(0, self.__sort_albums_by_year ) # sort albums by year!
		
		tree_view = gtk.TreeView(self.album_list_store)
		tree_view.set_rules_hint(True)
		self.albums_column = self.__create_column("Albums", 0)
		self.albums_column.set_sizing(gtk.TREE_VIEW_COLUMN_AUTOSIZE)
		tree_view.append_column(self.albums_column)

		tree_view.connect("cursor-changed", self.albums_cursor_changed)
		tree_view.connect("row-activated",  self.albums_on_activated)
		tree_view.connect("button_press_event", self.albums_on_right_click)
		tree_view.set_search_column(0)
		
		albums_scrolled_window.add(tree_view)
		"""End Middle Top Right"""
		
		middle_top.pack_start(artists_scrolled_window, True, True, 0)
		middle_top.pack_start(albums_scrolled_window, True, True, 0)

		"""End Middle Top"""
		
		"""Middle Bottom"""
		#################################
		# Songs
		#################################
		songs_scrolled_window = gtk.ScrolledWindow()
		songs_scrolled_window.set_shadow_type(gtk.SHADOW_ETCHED_IN)
		songs_scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
			
		# track, title, time, size, id
		self.song_list_store = gtk.ListStore(int, str, str, str, str, str, int)
		self.song_list_store.set_sort_func(0, self.__sort_songs_by_track) 
		self.song_list_store.set_sort_func(1, self.__sort_songs_by_title) 
		self.song_list_store.set_sort_func(2, self.__sort_songs_by_artist) 
		self.song_list_store.set_sort_func(3, self.__sort_songs_by_album) 
		self.song_list_store.set_sort_column_id(2,gtk.SORT_ASCENDING)

		tree_view = gtk.TreeView(self.song_list_store)
		tree_view.connect("row-activated", self.songs_on_activated)
		tree_view.connect("button_press_event", self.songs_on_right_click)
		tree_view.set_rules_hint(True)
		tree_view.set_search_column(1)
		
		i = 0
		for column in ("Track", "Title", "Artist", "Album", "Time", "Size"):
			new_column = self.__create_column(column, i)
			new_column.set_reorderable(True)
			new_column.set_resizable(True)
			new_column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
			if column == "Track":
				new_column.set_fixed_width(50)
			elif column == "Title":
				new_column.set_fixed_width(230)
			elif column == "Artist":
				new_column.set_fixed_width(170)
			elif column == "Album":
				new_column.set_fixed_width(190)
			elif column == "Time":
				new_column.set_fixed_width(90)
			elif column == "Size":
				new_column.set_fixed_width(100)
			tree_view.append_column(new_column)
			i += 1
		
		songs_scrolled_window.add(tree_view)
		"""End Middle Bottom"""
		
		middle_vpaned.pack1(middle_top)
		middle_vpaned.pack2(songs_scrolled_window)
		
		hpaned.pack2(middle_vpaned)
		
		main_box.pack_start(hpaned, True, True, 0)
	
		"""End Middle"""	

		"""Start status bar"""
		#################################
		# Status Bar
		#################################
		self.statusbar = gtk.Statusbar()
		self.statusbar.set_has_resize_grip(True)
		self.update_statusbar("Ready")

		
		main_box.pack_start(self.statusbar, False, False, 0)
		"""End status bar"""
		self.window.add(main_box)
		"""Show All"""
		
		self.window.show_all()
		if view_statusbar == False:
			self.statusbar.hide()
		if show_playlist == False:
			self.playlist_window.hide()
		if show_downloads == False:
			self.downloads_window.hide()
		if show_downloads == False and show_playlist == False:
			self.side_panel.hide()
		"""End Show All"""
		
		# check repeat songs if the user wants it
		repeat_songs = self.db_session.variable_get('repeat_songs')
		if repeat_songs:
			repeat_songs_checkbutton.set_active(True)
			self.audio_engine.set_repeat_songs(True)
			
		
	def main_gui_callback(self):
		"""Function that gets called after GUI has loaded.
		This loads all user variables into memory."""
		### Display Notifications ###
		self.display_notifications = self.db_session.variable_get('display_notifications')
		if self.display_notifications == None:
			self.display_notifications = True
		### Automatically Update Cache ###
		self.automatically_update = self.db_session.variable_get('automatically_update')
		if self.automatically_update == None:
			self.automatically_update = False
		### Is first time closing application (alert user it is in status bar) ###
		self.first_time_closing = self.db_session.variable_get('first_time_closing')
		if self.first_time_closing == None:
			self.first_time_closing = True
		### Status tray variables ###
		self.quit_when_window_closed = self.db_session.variable_get('quit_when_window_closed')
		if self.quit_when_window_closed == None:
			self.quit_when_window_closed = False
		### Downloads Directory ###
		self.downloads_directory = self.db_session.variable_get('downloads_directory')
		if self.downloads_directory == None:
			self.downloads_directory = os.path.expanduser("~")
			
		### Check for credentials and login ###
		if self.ampache_conn.has_credentials():
			self.update_statusbar("Attempting to authenticate...")
			self.login_and_get_artists("First")
		else:
			self.update_statusbar("Set Ampache information by going to Edit -> Preferences") 
			if self.ampache_conn.is_first_time():
				self.create_dialog_alert("info", """This looks like the first time you are running Viridian.  To get started, go to Edit -> Preferences and set your account information.""", True)
				
	def main_gui_toggle_hidden(self):
		if self.window.is_active():
			self.window.hide_on_delete()
		else:	
			show_playlist = self.db_session.variable_get('show_playlist')
			if show_playlist == None:
				show_playlist = False
			show_downloads = self.db_session.variable_get('show_downloads')
			if show_playlist == None:
				show_playlist = False
				
			view_statusbar = self.db_session.variable_get('view_statusbar')
			if view_statusbar == None:
				view_statusbar = True
				
			self.window.show_all()
			self.window.grab_focus()
			self.window.present()
			if show_playlist == False:
				self.playlist_window.hide()
			if show_downloads == False:
				self.playlist_window.hide()
			if show_playlist == False and show_downloads == False:
				self.side_panel.hide()
			if view_statusbar == False:
				self.statusbar.hide()
			
			

	def show_settings(self, widget, data=None):
		"""The settings pane"""
		#################################
		# Settings Window
		#################################
		if hasattr(self, 'preferences_window'):
			if self.preferences_window != None:
				self.preferences_window.present()
				return True
				
		self.preferences_window = gtk.Window(gtk.WINDOW_TOPLEVEL)
		self.preferences_window.set_transient_for(self.window)
		self.preferences_window.set_title("Viridian Settings")
		self.preferences_window.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
		self.preferences_window.resize(450, 300)
		self.preferences_window.set_resizable(False)
		self.preferences_window.connect("delete_event", self.destroy_settings)
		self.preferences_window.connect("destroy", self.destroy_settings)
		
		main_vbox = gtk.VBox(False, 8)
		main_vbox.set_border_width(10)
	
		"""Start Notebook"""
		notebook = gtk.Notebook()
		notebook.set_tab_pos(gtk.POS_TOP)
		#self.show_tabs = True
		#self.show_border = True
		
		#################################
		# Account Settings
		#################################
		account_box = gtk.VBox()
		account_box.set_border_width(10)
		
		hbox = gtk.HBox()
		label = gtk.Label()
		label.set_markup('<b>Account Settings</b>')
		hbox.pack_start(label, False, False)
		
		account_box.pack_start(hbox, False, False, 5)

		### Ampache URL ###
		hbox = gtk.HBox()
		hbox.pack_start(gtk.Label("   "), False, False, 0)
		ampache_label = gtk.Label("Ampache URL:")
		hbox.pack_start(ampache_label, False, False, 2)

		self.ampache_text_entry = gtk.Entry()
		try:
			self.ampache_text_entry.set_text(self.ampache_conn.url)
		except:
			pass	
		hbox.pack_start(self.ampache_text_entry)

		account_box.pack_start(hbox, False, False, 2)

		hbox = gtk.HBox()
		label = gtk.Label("")
		label.set_markup('<span size="8000"><b>Example: </b>http://example.com/ampache</span>')
		hbox.pack_end(label, False, False, 2)
		
		account_box.pack_start(hbox, False, False, 2)
		### Ampache Username ###
		hbox = gtk.HBox()	
		hbox.pack_start(gtk.Label("   "), False, False, 0)
		username_label = gtk.Label("Username:")
		hbox.pack_start(username_label, False, False, 2)

		self.username_text_entry = gtk.Entry()
		try:
			self.username_text_entry.set_text(self.ampache_conn.username)
		except:
			pass
		hbox.pack_start(self.username_text_entry)
	
		account_box.pack_start(hbox, False, False, 2)
	
		### Ampache Password ###
		hbox = gtk.HBox()
		hbox.pack_start(gtk.Label("   "), False, False, 0)
		password_label = gtk.Label("Password:")
		hbox.pack_start(password_label, False, False, 2)

		self.password_text_entry = gtk.Entry()
		try:
			self.password_text_entry.set_text(self.ampache_conn.password)
		except:
			pass
		self.password_text_entry.set_visibility(False)
		hbox.pack_start(self.password_text_entry)
	
		account_box.pack_start(hbox, False, False, 2)
		
		save = gtk.Button(stock=gtk.STOCK_SAVE)
		save.connect("clicked", self.button_save_preferences_clicked, self.preferences_window)
		
		hbox = gtk.HBox()
		
		hbox.pack_start(save, False, False, 4)
		
		account_box.pack_end(hbox, False, False, 2)
		"""End Account Settings"""
		"""Start Display Settings"""
		#################################
		# display Settings
		#################################
		display_box = gtk.VBox()
		display_box.set_border_width(10)
		
		hbox = gtk.HBox()
		
		label = gtk.Label()
		label.set_markup('<b>Notifications</b>')
		hbox.pack_start(label, False, False)
		
		display_box.pack_start(hbox, False, False, 5)

		hbox = gtk.HBox()

		hbox.pack_start(gtk.Label("   "), False, False, 0)
		
		display_notifications_checkbutton = gtk.CheckButton("Display OSD Notifications")
		if PYNOTIFY_INSTALLED:
			display_notifications_checkbutton.set_active(self.display_notifications)
		else:
			display_notifications_checkbutton.set_sensitive(False)
			display_notifications_checkbutton.set_active(False)
		display_notifications_checkbutton.connect("toggled", self.toggle_display_notifications)
		hbox.pack_start(display_notifications_checkbutton)
		
		display_box.pack_start(hbox, False, False, 2)
		"""End Display Settings"""
		"""Start Catalog Settings"""
		#################################
		# catalog Settings
		#################################
		catalog_box = gtk.VBox()
		catalog_box.set_border_width(10)
		
		hbox = gtk.HBox()
		
		label = gtk.Label()
		label.set_markup('<b>Catalog Cache</b>')
		
		hbox.pack_start(label, False, False)
		
		catalog_box.pack_start(hbox, False, False, 5)
		
		hbox = gtk.HBox()
		
		hbox.pack_start(gtk.Label("   "), False, False, 0)
		
		
		cb = gtk.CheckButton("Automatically clear local catalog when Ampache is updated")
		cb.set_active(self.automatically_update)
		cb.connect("toggled", self.toggle_automatically_update)
		
		hbox.pack_start(cb)
		
		catalog_box.pack_start(hbox, False, False, 2)
		
		hbox = gtk.HBox()
		
		hbox.pack_start(gtk.Label("       "), False, False, 0)
		label = gtk.Label()
		label.set_line_wrap(True)
		image = gtk.Image()
		
		if self.ampache_conn.has_credentials() and self.ampache_conn.is_authenticated():
			if self.ampache_conn.is_up_to_date():
				image.set_from_stock(gtk.STOCK_YES,gtk.ICON_SIZE_SMALL_TOOLBAR)
				label.set_text("Local catalog is up-to-date.")
			else:
				image.set_from_stock(gtk.STOCK_NO,gtk.ICON_SIZE_SMALL_TOOLBAR)
				label.set_text("Local catalog is older than Ampache catalog! To update the local catalog go to File -> Clear Local Cache.")
		
			hbox.pack_start(image, False, False, 5)
			hbox.pack_start(label, False, False, 0)
		
			catalog_box.pack_start(hbox, False, False, 2)
		"""End Catalog Settings"""
				
		"""Start Download Settings"""
		#################################
		# Download Settings
		#################################
		download_box = gtk.VBox(False, 0)
		download_box.set_border_width(10)
		
		hbox = gtk.HBox()
		
		label = gtk.Label()
		label.set_markup('<b>Local Downloads</b>')
		
		hbox.pack_start(label, False, False)
		
		download_box.pack_start(hbox, False, False, 5)
		
		hbox = gtk.HBox()
		
		label = gtk.Label("    Select where downloaded files should go.")
				
		hbox.pack_start(label, False, False, 4)
		
		download_box.pack_start(hbox, False, False, 2)
		
		hbox = gtk.HBox()
		
		hbox.pack_start(gtk.Label("      "), False, False, 1)
		
		self.downloads_text_entry = gtk.Entry()
		self.downloads_text_entry.set_text(self.downloads_directory)

		hbox.pack_start(self.downloads_text_entry)
		
		fcbutton = gtk.Button(stock=gtk.STOCK_OPEN)
		fcbutton.connect('clicked', self.button_open_downloads_file_chooser_clicked)
				
		hbox.pack_start(fcbutton, False, False, 4)
		
		download_box.pack_start(hbox, False, False, 2)
		"""End Download Settings"""
				
		"""Start Tray Icon Settings"""
		#################################
		# Tray Icon Settings
		#################################
		trayicon_box = gtk.VBox(False, 0)
		trayicon_box.set_border_width(10)
		
		hbox = gtk.HBox()
		
		label = gtk.Label()
		label.set_markup('<b>Status Tray Icon</b>')
		
		hbox.pack_start(label, False, False)
		
		trayicon_box.pack_start(hbox, False, False, 5)
		
		cb = gtk.CheckButton("Quit Viridian when window is closed")
		cb.connect("toggled", self.toggle_quit_when_window_closed)
		cb.set_active(self.quit_when_window_closed)
		
		hbox = gtk.HBox()
		hbox.pack_start(gtk.Label("   "), False, False, 0)

		button = gtk.RadioButton(None, "Standard Tray Icon")
		button.connect("toggled", self.trayicon_settings_toggled, "standard", cb)
		if self.tray_icon_to_display == 'standard':
			button.set_active(True)
		hbox.pack_start(button, True, True, 0)

		trayicon_box.pack_start(hbox, False, False, 2)

		hbox = gtk.HBox()
		hbox.pack_start(gtk.Label("   "), False, False, 0)

		button = gtk.RadioButton(button, "Unified Sound Icon ( Ubuntu 10.10 or higher )")
		button.connect("toggled", self.trayicon_settings_toggled, "unified", cb)
		button.set_sensitive(False) # Ubuntu unified sound
		if self.tray_icon_to_display == 'unified':
			button.set_active(True)
		hbox.pack_start(button, True, True, 0)
		
		trayicon_box.pack_start(hbox, False, False, 2)

		hbox = gtk.HBox()
		hbox.pack_start(gtk.Label("   "), False, False, 0)

		button = gtk.RadioButton(button, "Disabled")
		button.connect("toggled", self.trayicon_settings_toggled, "disabled", cb)
		if self.tray_icon_to_display == 'disabled':
			button.set_active(True)
		hbox.pack_start(button, True, True, 0)

		trayicon_box.pack_start(hbox, False, False, 2)

		hbox = gtk.HBox()
		hbox.pack_start(gtk.Label("      "), False, False, 0)
		
		hbox.pack_start(cb, True, True, 0)
		
		trayicon_box.pack_start(hbox, False, False, 5)
		
		hbox = gtk.HBox()
		hbox.pack_start(gtk.Label("      "), False, False, 0)
		
		label = gtk.Label("Note: changes to the type of icon will take effect the next time this program is opened.")
		label.set_line_wrap(True)
		
		hbox.pack_start(label, False, False, 4)
		
		trayicon_box.pack_start(hbox, False, False, 5)
		"""End Tray Icon Settings"""
		"""Start System Settings"""
		#################################
		# System Settings
		#################################
		system_box = gtk.VBox()
		system_box.set_border_width(10)
		
		hbox = gtk.HBox()
		
		label = gtk.Label()
		label.set_markup('<b>System</b>')
		
		hbox.pack_start(label, False, False)
		
		system_box.pack_start(hbox, False, False, 5)
		
		hbox = gtk.HBox()
		
		hbox.pack_start(gtk.Label("   "), False, False, 0)
		
		label = gtk.Label("To delete all personal information (including your username, password, album-art, cached information, etc.) press this button. NOTE: This will delete all personal settings stored on this computer and close itself.  When you reopen, it will be as though it is the first time you are running Viridian.")
		label.set_line_wrap(True)
		
		hbox.pack_start(label, False, False)
		
		system_box.pack_start(hbox, False, False, 2)
		
		hbox = gtk.HBox()
		
		hbox.pack_start(gtk.Label("       "), False, False, 0)
		
		cb = gtk.Button("Reset Everything")
		cb.connect("clicked", self.button_reset_everything_clicked)
		
		hbox.pack_start(cb, False, False, 2)
		
		system_box.pack_start(hbox, False, False, 2)
		"""End System Settings"""
		
		"""End Notebook"""
		notebook.append_page(account_box,  gtk.Label("Account"))
		notebook.append_page(display_box,  gtk.Label("Display"))
		notebook.append_page(catalog_box,  gtk.Label("Catalog"))
		notebook.append_page(download_box, gtk.Label("Downloads"))
		notebook.append_page(trayicon_box, gtk.Label("Tray Icon"))
		notebook.append_page(system_box,   gtk.Label("System"))
		
		"""Start Bottom Bar"""
		bottom_bar = gtk.HBox()
		
		close = gtk.Button(stock=gtk.STOCK_CLOSE)
		close.connect("clicked", self.button_cancel_preferences_clicked, self.preferences_window)
		
		bottom_bar.pack_end(close, False, False, 2)
		"""End Bottom Bar"""

		main_vbox.pack_start(notebook)
		main_vbox.pack_start(bottom_bar, False, False, 2)

		"""End bottom row"""
		self.preferences_window.add(main_vbox)
		self.preferences_window.show_all()
		
	def destroy_settings(self, widget=None, data=None):
		self.preferences_window.destroy()
		self.preferences_window = None
		

	#######################################
	# Status Icon 
	#######################################
	def status_icon_activate(self, icon=None):
		"""Bring the window back up when the user clicks the sys tray icon."""
		self.main_gui_toggle_hidden()
				

	def status_icon_popup_menu(self, icon, button, activate_time):
		"""Create a menu when the user right clicks the sys tray icon."""
		menu = gtk.Menu()
		
		show_window = gtk.MenuItem("Show Window")
		show_window.connect('activate', self.status_icon_activate)
		menu.append(show_window)
		
		### Display Song Info is song is playing ###
		if self.audio_engine.get_state() == "playing":
			menu.append(gtk.SeparatorMenuItem())
			np = gtk.MenuItem("- Now Playing -")
			np.set_sensitive(False)
			menu.append(np)

			title  = gtk.MenuItem(self.current_song_info['song_title'])
			artist = gtk.MenuItem(self.current_song_info['artist_name'])
			album  = gtk.MenuItem(self.current_song_info['album_name'])

			title.set_sensitive(False)
			artist.set_sensitive(False)
			album.set_sensitive(False)

			menu.append(title)
			menu.append(artist)
			menu.append(album)

		menu.append(gtk.SeparatorMenuItem())
		
		prev_track = gtk.ImageMenuItem(gtk.STOCK_MEDIA_PREVIOUS)
		prev_track.connect('activate', self.button_prev_clicked, None)
		menu.append(prev_track)
		
		play_pause = gtk.MenuItem("")
		if self.audio_engine.get_state() != "playing":
			play_pause = gtk.ImageMenuItem(gtk.STOCK_MEDIA_PLAY)
		else:
			play_pause = gtk.ImageMenuItem(gtk.STOCK_MEDIA_PAUSE)
		play_pause.connect('activate', self.button_play_pause_clicked, None)
		menu.append(play_pause)

		next_track = gtk.ImageMenuItem(gtk.STOCK_MEDIA_NEXT)
		next_track.connect('activate', self.button_next_clicked, None)
		menu.append(next_track)
		
		menu.append(gtk.SeparatorMenuItem())
		
		pref = gtk.ImageMenuItem(gtk.STOCK_PREFERENCES)
		pref.connect('activate', self.show_settings, None)
		menu.append(pref)
		
		quit_ = gtk.ImageMenuItem(gtk.STOCK_QUIT)
		quit_.connect('activate', self.destroy, None)
		menu.append(quit_)
		
		menu.show_all()
		menu.popup(None, None, gtk.status_icon_position_menu, button, activate_time, icon)


	#######################################
	# Check Boxes
	#######################################
	def toggle_statusbar_view(self, widget, data=None):
		"""Toggle the status bar to show or hide it."""
		if widget.active:
			self.statusbar.show()
		else:
			self.statusbar.hide()
		self.db_session.variable_set('view_statusbar', widget.active)
			
	def toggle_playlist_view(self, widget, data=None):
		"""Toggle the playlist window."""
		if widget.active:
			if self.downloads_window.flags() & gtk.VISIBLE == False:
				self.side_panel.show()
			self.playlist_window.show()
		else:
			if self.downloads_window.flags() & gtk.VISIBLE== False:
				self.side_panel.hide()
			self.playlist_window.hide()
		self.db_session.variable_set('show_playlist', widget.active)
		
	def toggle_downloads_view(self, widget, data=None):
		"""Toggle the Downloads window."""
		if widget.active:
			if self.playlist_window.flags() & gtk.VISIBLE == False:
				self.side_panel.show()
			self.downloads_window.show()
		else:
			if self.playlist_window.flags() & gtk.VISIBLE == False:
				self.side_panel.hide()
			self.downloads_window.hide()
		self.db_session.variable_set('show_downloads', widget.active)	
			
	def toggle_repeat_songs(self, widget, data=None):
		"""Toggle repeat songs."""
		self.audio_engine.set_repeat_songs(widget.get_active())
		self.db_session.variable_set('repeat_songs', widget.get_active())
		
	def toggle_display_notifications(self, widget, data=None):
		"""Toggle displaying notify OSD notifications."""
		self.display_notifications = widget.get_active()
		self.db_session.variable_set('display_notifications', widget.get_active())
		
	def toggle_automatically_update(self, widget, data=None):
		"""Toggle automatically updating the local cache."""
		self.automatically_update = widget.get_active()
		self.db_session.variable_set('automatically_update', widget.get_active())
		
	def toggle_quit_when_window_closed(self, widget, data=None):
		"""Toggle to decide if the program quits or keeps running when the main window is closed."""
		self.quit_when_window_closed = widget.get_active()
		self.db_session.variable_set('quit_when_window_closed', self.quit_when_window_closed)
		
	#######################################
	# Radio Buttons
	#######################################
	def trayicon_settings_toggled(self, widget, name=None, cb=None):
		if widget.get_active():
			if name == "disabled":
				self.quit_when_window_closed = True
				self.db_session.variable_set('quit_when_window_closed', self.quit_when_window_closed)
				self.tray_icon_to_display = 'disabled'
				self.db_session.variable_set('tray_icon_to_display', self.tray_icon_to_display)
				cb.set_active(True)
				cb.set_sensitive(False)
			elif name == "unified":
				self.quit_when_window_closed = False
				self.db_session.variable_set('quit_when_window_closed', self.quit_when_window_closed)
				self.tray_icon_to_display = 'unified'
				self.db_session.variable_set('tray_icon_to_display', self.tray_icon_to_display)
				cb.set_sensitive(True)
				cb.set_active(False)
			elif name == "standard":
				self.quit_when_window_closed = False
				self.db_session.variable_set('quit_when_window_closed', self.quit_when_window_closed)
				self.tray_icon_to_display = 'standard'
				self.db_session.variable_set('tray_icon_to_display', self.tray_icon_to_display)
				cb.set_sensitive(True)
				cb.set_active(False)

		
		
	#######################################
	# Initial Authentication
	#######################################
	def login_and_get_artists(self, data=None):
		"""Authenticate and populate the artists."""
		self.stop_all_threads()
		self.__clear_all_list_stores()
		self.update_statusbar("Authenticating...")
		# get the user inforamiton
		ampache  = self.ampache_conn.url
		username = self.ampache_conn.username
		password = self.ampache_conn.password
		print "--- Attempting to login to Ampache ---"
		print "Ampache  = %s" % ampache
		print "Username = %s" % username
		print "Password = " + len(password)*"*"
		# set the credentials and try to login
		if self.ampache_conn.authenticate(): # auth successful
			self.update_statusbar("Authentication Successful.")
			print "Authentication Successful!"
			print "Authentication = %s" % self.ampache_conn.auth
			print "Number of artists = %d" % self.ampache_conn.artists_num
			
			if not self.ampache_conn.is_up_to_date():
				# not up to date
				if data == "First" and self.automatically_update:
					self.ampache_conn.clear_cached_catalog()
				elif data == True or data == "First": # open a popup
					if self.create_catalog_updated_dialog(): # user pressed update
						self.ampache_conn.clear_cached_catalog()
				#else: #do nothing, pull from cache
						
						
			# load the artists window with, you guessed it, artists
			self.update_statusbar("Pulling Artists...")
			artists = self.ampache_conn.get_artist_dict()
			model = self.artist_list_store
			for artist_id in artists:
				artist_name = artists[artist_id]['name']
				custom_name = artists[artist_id]['custom_name']
				model.append([artist_name, artist_id, custom_name])
			self.update_statusbar("Ready.")
		else: # auth failed
			self.update_statusbar("Authentication Failed.")
		
				
	#######################################
	# Selection Methods (Single Click)
	#######################################
	def artists_cursor_changed(self, widget, data=None): 
		"""The function that runs when the user clicks an artist."""
		cursor = widget.get_cursor()
		model  = widget.get_model()
		row    = cursor[0]
		
		artist_name = model[row][0]
		artist_id   = model[row][1]
		
		try:
			if self.artist_id == artist_id and self.artist_name == artist_name:
				return True # don't refresh if the user reclicks the artist
		except:
			pass
		
		self.artist_id   = artist_id
		self.artist_name = artist_name
		
		self.album_id = None # this is the albums refresh
		
		# now display the albums
		model = self.album_list_store
		model.clear()
		model.append(["All Albums", -1, -1, 0])
		albums = self.ampache_conn.get_album_dict(self.artist_id)
		# alphabetize the list
		for album in albums:
			album_name  = albums[album]['name']
			album_year  = albums[album]['year']
			album_stars = albums[album]['stars']
			album_id    = album
			self.update_statusbar("Fetching Album: " + album_name)
			album_string = album_name + ' (' + str(album_year) + ')'
			if album_year == 0:
				album_string = album_name
			model.append([album_string, album_id, album_year, album_stars])
		self.update_statusbar(self.artist_name)
		

	def albums_cursor_changed(self, widget, data=None):
		"""The function that runs when the user clicks an album."""
		cursor = widget.get_cursor()
		model  = widget.get_model()
		row    = cursor[0]
		
		album_name = model[row][0]
		album_id   = model[row][1]
		
		try:
			if self.album_id == album_id and self.album_name == album_name:
				return True # don't refresh if the user reclicks the album
		except:
			pass
		
		self.album_name = album_name
		self.album_id   = album_id

		song_list_store = self.song_list_store
		song_list_store.clear()
		
		if album_id == -1: # all albums
			list = []
			for album in model:
				list.append(album[1])
			for album_id in list:
				if album_id != -1:
					if self.__add_songs_to_list_store(album_id):
						self.update_statusbar("Fetching Album id: " + str(album_id))
			self.update_statusbar(album_name + " - " + self.artist_name)
		else: # single album
			if self.__add_songs_to_list_store(album_id):
				self.update_statusbar(album_name + " - " + self.artist_name)
				
	#######################################
	# Selection Methods (Double Click)
	#######################################
	def albums_on_activated(self, widget, row, col):
		"""The function that runs when the user double-clicks an album."""
		model = widget.get_model()
		
		album_name = model[row][0]
		album_id   = model[row][1]
		
		# get all songs in the current songs menu and play them
		list = []
		for song in self.song_list_store:
			list.append(song[6])
			
		print "Sending this list of songs to player", list
		self.audio_engine.play_from_list_of_songs(list)

	def songs_on_activated(self, widget, row, col):
		"""The function that runs when the user double-clicks a song."""
		model = widget.get_model()
		
		song_title = model[row][1]
		song_id    = model[row][6]

		list = []
		for song in model:
			list.append(song[6])
		
		song_num = row[0]
		
		print "Sending this list of songs to player", list
		self.audio_engine.play_from_list_of_songs(list, song_num)

	def playlist_on_activated(self, widget, row, col):
		"""The function that runs when the user double-clicks a song in the playlist."""
		song_num = row[0]
		self.audio_engine.change_song(song_num)
	
	def downloads_on_activated(self, widget, row, col):
		"""The function that runs when the user double-clicks a song in the downloads window."""
		model = widget.get_model()
		full_path = model[row][2]
		os.popen("gnome-open '%s' &" % (os.path.dirname(full_path)))
		
	#######################################
	# Selection Methods (right-click)
	#######################################
	def playlist_on_right_click(self, treeview, event, data=None):
		if event.button == 3:
			x = int(event.x)
			y = int(event.y)
			pthinfo = treeview.get_path_at_pos(x, y)
			if pthinfo != None:
				path, col, cellx, celly = pthinfo
				# create popup
				song_id = treeview.get_model()[path][2]
				m = gtk.Menu()
				i = gtk.MenuItem("Remove From Playlist")
				i.connect('activate', self.remove_from_playlist, song_id, treeview)
				m.append(i)
				i = gtk.MenuItem("Download Song")
				i.connect('activate', self.download_song_clicked, song_id)
				m.append(i)
				m.show_all()
				m.popup(None, None, None, event.button, event.time, None)
				
	def downloads_on_right_click(self, treeview, event, data=None):
		if event.button == 3:
			x = int(event.x)
			y = int(event.y)
			pthinfo = treeview.get_path_at_pos(x, y)
			if pthinfo != None:
				path, col, cellx, celly = pthinfo
				# create popup
				full_path = treeview.get_model()[path][2]
				m = gtk.Menu()
				i = gtk.MenuItem("Open Song")
				i.connect('activate', lambda _: os.popen("gnome-open '%s' &" % (full_path)))
				m.append(i)
				i = gtk.MenuItem("Open Containing Folder")
				i.connect('activate', lambda _: os.popen("gnome-open '%s' &" % (os.path.dirname(full_path))))
				m.append(i)
				m.show_all()
				m.popup(None, None, None, event.button, event.time, None)
				
	def albums_on_right_click(self, treeview, event, data=None):
		if event.button == 3:
			x = int(event.x)
			y = int(event.y)
			pthinfo = treeview.get_path_at_pos(x, y)
			if pthinfo != None:
				path, col, cellx, celly = pthinfo
				# create popup
				album_id = treeview.get_model()[path][1]
				m = gtk.Menu()
				i = gtk.MenuItem("Add Album to Playlist")
				i.connect('activate', self.add_album_to_playlist)
				m.append(i)
				i = gtk.MenuItem("Download Album")
				i.connect('activate', self.download_album_clicked)
				m.append(i)
				m.show_all()
				m.popup(None, None, None, event.button, event.time, None)
	
	def songs_on_right_click(self, treeview, event, data=None):
		if event.button == 3:
			x = int(event.x)
			y = int(event.y)
			pthinfo = treeview.get_path_at_pos(x, y)
			if pthinfo != None:
				path, col, cellx, celly = pthinfo
				# create popup
				song_id = treeview.get_model()[path][6]
				m = gtk.Menu()
				i = gtk.MenuItem("Add Song to Playlist")
				i.connect('activate', self.add_song_to_playlist, song_id)
				m.append(i)
				i = gtk.MenuItem("Download Song")
				i.connect('activate', self.download_song_clicked, song_id)
				m.append(i)
				m.show_all()
				m.popup(None, None, None, event.button, event.time, None)
				
	
			

	#######################################
	# Button Clicked Methods
	#######################################
	def button_save_preferences_clicked(self, widget, data=None):
		"""When the save button is pressed in the preferences"""
		window = data
		
		url      = self.ampache_text_entry.get_text()
		username = self.username_text_entry.get_text()
		password = self.password_text_entry.get_text()
		
		# check to see if any of the fields have been edited, if so, reauth with new credentials
		try:
			if url == self.ampache_conn.url and username == self.ampache_conn.username and password == self.ampache_conn.password:
				window.destroy()
				return True
		except:
			pass
		
		# if the code makes it this far, the credentials have been changed
		self.stop_all_threads()
		self.ampache_conn.clear_album_art()
		self.ampache_conn.clear_cached_catalog()
		if self.ampache_conn.set_credentials(url, username, password): # credentials saved
			self.update_statusbar("Saved Credentials")
			print "Credentials Saved"
			self.destroy_settings(window)
			self.login_and_get_artists()
		else:
			self.update_statusbar("Couldn't save credentials!")
			print "[Error] Couldn't save credentials!"
			return False
		return True

	def button_cancel_preferences_clicked(self, widget, data=None):
		"""Destroy the preferences window."""
		window = data
		self.destroy_settings(window)
		
	def button_open_downloads_file_chooser_clicked(self, widget, data=None):
		"""Open file chooser for the downloads directory."""
		dialog = gtk.FileChooserDialog("Choose Folder...",
						None,
						gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
						(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
						gtk.STOCK_OPEN, gtk.RESPONSE_OK))
		dialog.set_default_response(gtk.RESPONSE_OK)
		response = dialog.run()
		if response == gtk.RESPONSE_OK:
			self.downloads_directory = dialog.get_current_folder()
			self.downloads_text_entry.set_text(self.downloads_directory)
			self.db_session.variable_set('downloads_directory', self.downloads_directory)
		dialog.destroy()

	def button_reauthenticate_clicked(self, widget=None, data=None):
		"""Reauthenticate button clicked."""
		self.login_and_get_artists(True)

	def button_play_pause_clicked(self, widget, data=None):
		"""The play/pause has been clicked."""
		state = self.audio_engine.get_state()
		if state == "stopped" or state == None:
			return True
		elif state == "playing":
			self.audio_engine.pause()
			self.play_pause_image.set_from_pixbuf(self.images_pixbuf_play)
			self.set_tray_icon(None)
		else:
			if self.audio_engine.play():
				self.play_pause_image.set_from_pixbuf(self.images_pixbuf_pause)
				self.set_tray_icon(self.album_art_image.get_pixbuf())

		
	def button_prev_clicked(self, widget, data=None):
		"""Previous Track."""
		self.audio_engine.prev_track()
		
	def button_next_clicked(self, widget, data=None):
		"""Next Track."""
		self.audio_engine.next_track()
		
	def button_clear_cached_artist_info_clicked(self, widget=None, data=None):
		"""Clear local cache."""
		try: # check to see if this function is running
			if self.button_clear_cache_locked == True:
				print "Already Running"
				return False
		except:
			pass
		self.button_clear_cache_locked = True
		print "Clearing cached catalog -- will reauthenticate and pull artists"
		self.stop_all_threads()
		self.ampache_conn.clear_cached_catalog()
		self.login_and_get_artists()
		self.button_clear_cache_locked = False	
		
	def button_clear_album_art_clicked(self, widget=None, data=None):
		"""Clear local album art."""
		self.ampache_conn.clear_album_art()
		self.update_statusbar("Album Art Cleared")
		
	def button_reset_everything_clicked(self, widget=None, data=None):
		"""Reset everything."""
		answer = self.create_dialog_ok_or_close("Reset Viridian", """Are you sure you want to delete all personal information stored with Viridian?""")
		if answer == "ok":
			self.ampache_conn.reset_everything()
			self.destroy()
		
	def button_pre_cache_info_clicked(self, widget=None, data=None):
		"""Pre-cache all album and song info."""
		if self.ampache_conn.is_authenticated() == False:
			self.create_dialog_alert("warn", "Not Authenticated", True)
			return False
		try: # check to see if this function is running
			if self.button_pre_cache_locked == True:
				print "Already Running"
				self.create_dialog_alert("info", "Pre-Cache already in progress.")
				return False
		except:
			pass
		answer = self.create_dialog_ok_or_close("Pre-Cache", "This process can take a long time depending on the size of your catalog.  Proceed?")
		if answer != "ok":
			return False
		self.button_pre_cache_locked = True
		gobject.idle_add(self.__button_pre_cache_info_clicked)
		#thread.start_new_thread(self.__button_pre_cache_info_clicked, (None,))
		
	def __button_pre_cache_info_clicked(self, widget=None, data=None):
		self.pre_cache_continue = True # this will be set to false if this function should stop
		#try:
		start_time = int(time.time())
		artists = self.ampache_conn.get_artist_ids()
		i = 0
		num_artists = len(artists)
		for artist_id in artists:
			i += 1
			if self.pre_cache_continue == False:
				self.button_pre_cache_locked = False
				return False
			self.ampache_conn.populate_albums_dict(artist_id)
			self.update_statusbar("Pulling all albums from artists: %d/%d" % (i, num_artists) )
			#gobject.idle_add(self.update_statusbar, 1, "Pulling all albums from artists: %d/%d" % (i, num_artists) )
		self.update_statusbar("Finished pulling albums")
		
		albums = self.ampache_conn.get_album_ids()
		i = 0
		num_albums = len(albums)
		for album_id in albums:
			i += 1
			if self.pre_cache_continue == False:
				self.button_pre_cache_locked = False
				return False
			self.ampache_conn.populate_songs_dict(album_id)
			self.update_statusbar("Pulling all songs from albums: %d/%d" % (i, num_albums) )
		end_time = int(time.time())
		time_taken = end_time - start_time
		# convert time in seconds to HH:MM:SS THIS WILL FAIL IF LENGTH > 24 HOURS
		time_taken = time.strftime('%H:%M:%S', time.gmtime(time_taken))
		if time_taken[:2] == "00": # strip out hours if below 60 minutes
			time_taken = time_taken[3:]
		
		self.update_statusbar("Finished Pre Cache -- Time Taken: " + str(time_taken))
		print "Finished Pre Cache -- Time Taken: " + str(time_taken)
		#except:
		#	print "Error!"
		#	self.update_statusbar("Error with pre-cache!")
		#	self.button_pre_cache_locked = False
		#	return False
		self.button_pre_cache_locked = False
		return False
		
	def button_album_art_clicked(self, widget, event=None, data=None):
		"""Handle event box events for the album art."""
		if event.button == 3:
			self.__button_album_art_right_clicked(widget, event, data)
			# right click
		else: 
			self.__button_album_art_left_clicked(widget, event, data)
			# left click
			
	def __button_album_art_left_clicked(self, widget, event, data):
		"""Left click on album art."""
		self.__re_fetch_album_art()
		
	def __button_album_art_right_clicked(self, widget, event, data):
		"""Right click on album art."""
		# create popup
		m = gtk.Menu()
		i = gtk.MenuItem("Open Image")
		i.connect('activate', lambda x: os.popen("gnome-open '%s' &" % (self.current_album_art_file)))
		m.append(i)
		i = gtk.MenuItem("Refresh Album Art")
		i.connect('activate', self.__re_fetch_album_art)
		m.append(i)
		m.show_all()
		m.popup(None, None, None, event.button, event.time, None)
		return False 
	
	#######################################
	# Dialogs
	#######################################
	def create_dialog_alert(self, dialog_type, message, ok=None):
		"""Creates a generic dialog of the type specified with close."""
		if dialog_type == "warn": 
			dialog_type = gtk.MESSAGE_WARNING
		elif dialog_type == "error":
			dialog_type = gtk.MESSAGE_ERROR
		elif dialog_type == "info":
			dialog_type = gtk.MESSAGE_INFO
		elif dialog_type == "question":
			dialog_type = gtk.MESSAGE_QUESTION
		else:
			return False
		if ok == True: # display OK button
			md = gtk.MessageDialog(self.window, gtk.DIALOG_DESTROY_WITH_PARENT, dialog_type, gtk.BUTTONS_OK, message)
		else: # display Close button
			md = gtk.MessageDialog(self.window, gtk.DIALOG_DESTROY_WITH_PARENT, dialog_type, gtk.BUTTONS_CLOSE, message)
		md.run()
		md.destroy()
	
	def create_dialog_ok_or_close(self, title, message):
		"""Creates a generic dialog of the type specified with ok and cancel."""
		md = gtk.Dialog(str(title), self.window, gtk.DIALOG_DESTROY_WITH_PARENT, (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OK, gtk.RESPONSE_OK))
		label = gtk.Label(message)
		label.set_line_wrap(True)
		md.get_child().pack_start(label)
		md.get_child().set_border_width(10)
		md.set_border_width(3)
		md.set_resizable(False)
		md.show_all()
		resp = md.run()
		md.destroy()
		if resp == gtk.RESPONSE_OK:
			return "ok"
		else:
			return "cancel"
		
		
	def create_about_dialog(self, widget, data=None):
		"""About this application."""
		about = gtk.AboutDialog()
		about.set_name("Viridian")
		about.set_version("1.0-alpha")
		#about.set_copyright("(c) Dave Eddy")
		about.set_comments("Viridian is a front-end for an Ampache Server (see http://ampache.org)")
		about.set_website("http://www.viridianplayer.com")
		about.set_authors(["Author:", "Dave Eddy <dave@daveeddy.com>", "http://www.daveeddy.com", "", "AudioEngine by:", "Michael Zeller <link@conquerthesound.com>", "http://conquerthesound.com"])
		about.set_artists(["Skye Sawyer <skyelauren.s@gmail.com>", "http://www.skyeillustration.com", "", "Media Icons by:", "http://mysitemyway.com", "http://ampache.org"])
		try:
			about.set_logo(gtk.gdk.pixbuf_new_from_file(IMAGES_DIR + "logo.png"))
		except:
			pass
		about.run()
		about.destroy()
		
	def create_catalog_updated_dialog(self):
		"""Create a dialog to tell the user the cache has been updated."""
		answer = self.create_dialog_ok_or_close("Ampache Catalog Updated", """The Ampache catalog on the server is newer than the local cached catalog on this computer.  Would you like to update the local catalog by clearing the local cache?
			 
(You can also do this at anytime by going to File -> Clear Local Cache).""")
		if answer == "ok":
			return True
		return False
	
	
	#######################################
	# Audio Engine Callback
	#######################################
	def audioengine_song_changed(self, song_id):
		"""The function that gets called when the AudioEngine changes songs."""
		if song_id != None:
			self.current_song_info = self.ampache_conn.get_single_song_dict(song_id)
		gobject.idle_add(self.__audioengine_song_changed, song_id)
		
	def __audioengine_song_changed(self, song_id):
		"""The function that gets called when the AudioEngine changes songs."""
		if song_id == None: # nothing playing
			self.current_song_info = None
			self.play_pause_image.set_from_pixbuf(self.images_pixbuf_play)
			self.set_tray_tooltip('Viridian')
			self.set_tray_icon(None)
			self.playlist_list_store.clear()
			return False
		self.play_pause_image.set_from_pixbuf(self.images_pixbuf_pause)

		print self.current_song_info # DEBUG
		
		song_time   = self.current_song_info['song_time']
		self.time_elapsed_slider.set_range(0, song_time)
		self.time_total_label.set_text(self.__convert_seconds_to_human_readable(song_time))
		
		song_title  = self.current_song_info['song_title']
		artist_name = self.current_song_info['artist_name']
		album_name  = self.current_song_info['album_name']
		self.current_song_label.set_markup(   '<span size="13000"><b>'+song_title+'</b></span>'  )
		self.current_artist_label.set_markup( '<span size="10000">'+artist_name+'</span>' )
		self.current_album_label.set_markup(  '<span size="10000">'+album_name+'</span>'  )
		### Update the statusbar and tray icon ###
		self.set_tray_tooltip(song_title + ' - ' + artist_name)
		self.update_statusbar(song_title + ' - ' + artist_name)
		
		### Get the album Art ###
		album_id   = self.current_song_info['album_id']
		art_folder = self.ampache_conn.art_folder
		self.current_album_art_file = art_folder + os.sep + str(album_id)
		if os.path.isfile(self.current_album_art_file):
			print "Album art exists locally"
		else:
			print "Fetching album art... ",
			album_art = self.ampache_conn.get_album_art(album_id)
			response = urllib2.urlopen(album_art)
			f = open(self.current_album_art_file, 'w')
			f.write(response.read())
			f.close()
			print "Done!"
		# now create a pixel buffer for the image and set it in the GUI
		image_pixbuf = self.__create_image_pixbuf(self.current_album_art_file, ALBUM_ART_SIZE)
		self.album_art_image.set_from_pixbuf(image_pixbuf)
		self.set_tray_icon(image_pixbuf)
		
		self.update_statusbar(song_title + " - " + artist_name) # refresh
		
		### Send notifications OSD ###
		self.notification("Now Playing", song_title + ' - ' + artist_name, self.current_album_art_file)
		# rating stars
		stars = self.current_song_info['album_stars']
		i = 0
		while i < 5:
			if stars > i:
				self.rating_stars_list[i].set_from_pixbuf(self.images_pixbuf_gold_star)
			else:
				self.rating_stars_list[i].set_from_pixbuf(self.images_pixbuf_gray_star)
			i += 1
		self.update_playlist_window()
		
	def audioengine_buffering_callback(self, percent):
		"""Show the percantage buffered of the current song."""
		gobject.idle_add(lambda : self.notification_label.set_text("Buffering: " + str(percent) + "%"))
		if percent == 100:
			gobject.idle_add(lambda : self.notification_label.set_text(" "))
			
	def audioengine_buffering_callback(self, error_message):
		"""Display the gstreamer error in the notification label."""
		gobject.idle_add(lambda : self.notification_label.set_text(error_message))
			
	#######################################
	# Ampache Session Callback
	#######################################
	def authentication_failed_callback(self):
		"""Clear all lists when the authentication fails."""
		self.__clear_all_list_stores()
	
			
	#######################################
	# Convenience Functions
	#######################################
	def update_statusbar(self, text):
		"""Update the status bar and run pending main_iteration() events."""
		try:
			self.statusbar.pop(0)
		except:
			pass
		self.statusbar.push(0, text)
		self.refresh_gui()
			
	def notification(self, title, message=None, image=None):
		"""Display OSD notifications if the user wants them and it's installed."""
		if PYNOTIFY_INSTALLED and self.display_notifications:
			if message == None:
				message = title
				title = 'Ampache'
			pynotify_object.update(title, message, image)
			pynotify_object.show()
			
	def set_tray_tooltip(self, message):
		"""Set the tooltip of the tray icon if it is set."""
		if hasattr(self, 'tray_icon'):
			self.tray_icon.set_tooltip(message)
			return True
		return False
	
	def set_tray_icon(self, pixbuf):
		"""Set the tray icon to a pixbuf."""
		if hasattr(self, 'tray_icon'):
			if pixbuf == None:
				self.tray_icon.set_from_stock(gtk.STOCK_ABOUT)
			else:
				self.tray_icon.set_from_pixbuf(pixbuf)
			return True
		return False
			
	def add_album_to_playlist(self, widget):
		"""Adds every song in the visible list store and adds it to the playlist."""
		for song in self.song_list_store:
			self.audio_engine.insert_into_playlist(song[6])
		self.update_playlist_window()
		return True
			
		
	def add_song_to_playlist(self, widget, song_id):
		"""Takes a song_id and adds it to the playlist."""
		self.audio_engine.insert_into_playlist(song_id)
		self.update_playlist_window()
		return True
	
			
	def remove_from_playlist(self, widget, song_id, treeview):
		"""Remove a song from the current playlist."""
		if self.audio_engine.remove_from_playlist(song_id):
			selection = treeview.get_selection()
			result = selection.get_selected()
			if result: #result could be None
				model, iter = result
				model.remove(iter)

	def stop_all_threads(self):
		"""Stops all running threads."""
		self.pre_cache_continue = False
		self.download_song_continue = False

	def refresh_gui(self):
		"""Refresh the GUI by calling gtk.main_iteration(). """
		while gtk.events_pending():
			gtk.main_iteration()
			
	def update_playlist_window(self):
		"""Updates the playlist window with the current playing songs."""
		gobject.idle_add(self.__update_playlist_window)		
			
	def __update_playlist_window(self):
		cur_playlist = self.audio_engine.get_playlist()
		cur_song_num = self.audio_engine.get_current_song()
		self.playlist_list_store.clear()
		i = 0
		for temp_song_id in cur_playlist:
			cur_song = self.ampache_conn.get_playlist_song_dict(temp_song_id)
			cur_string = cur_song['song_title'] + ' - ' + cur_song['artist_name'] + ' - ' + cur_song['album_name']
			cur_string = cur_string.replace('&', '&amp;') #HACK
			now_playing = self.images_pixbuf_empty
			if i == cur_song_num:
				now_playing = self.images_pixbuf_playing
				cur_string = '<b>' + cur_string + '</b>'
			self.playlist_list_store.append([now_playing, cur_string, temp_song_id])
			i += 1
			
	def download_album_clicked(self, widget):
		"""The user cliked download album."""
		if self.show_downloads_checkbox.active == False:
			self.side_panel.show()
			self.downloads_window.show()
			self.show_downloads_checkbox.set_active(True)
		for song in self.song_list_store:
			self.download_song_clicked(widget, song[6], False)

	def download_song_clicked(self, widget, song_id, show_panel=True):
		"""The user clicked download song."""
		if show_panel and self.show_downloads_checkbox.active == False:
			self.side_panel.show()
			self.downloads_window.show()
			self.show_downloads_checkbox.set_active(True)
		song_url = self.ampache_conn.get_song_url(song_id)
		m = re.search('name=.*\.[a-zA-Z0-9]+', song_url)
		song_string = m.group(0).replace('name=/','').replace('%20',' ').replace('%27', "'")
		full_file = self.downloads_directory + os.sep + song_string
		self.downloads_list_store.append([song_string, 0, full_file])
		iter1 = self.downloads_list_store.get_iter(len(self.downloads_list_store) - 1)
		thread.start_new_thread(self.download_song, (song_url, full_file, iter1))
		
	def download_song(self, url, dst, iter1):
		THREAD_LOCK.acquire()
		print "get url '%s' to '%s'" % (url, dst)
		urllib.urlretrieve(url, dst,
				lambda nb, bs, fs, url=url: self._reporthook(nb,bs,fs,url,iter1))
		self.notification("Download Complete", os.path.basename(url).replace('%20',' ').replace('%27', "'"))
		THREAD_LOCK.release()
		#urllib.urlretrieve(url, dst, self._reporthook, iter1)
			
	def _reporthook(self, numblocks, blocksize, filesize, url, iter1):
		#print "reporthook(%s, %s, %s)" % (numblocks, blocksize, filesize)
		base = os.path.basename(url).replace('%20',' ').replace('%27', "'")
		#XXX Should handle possible filesize=-1.
		try:
			percent = min((numblocks*blocksize*100)/filesize, 100)
		except:
			percent = 100
		if numblocks != 0:
			#self.update_statusbar("Downloading " + base + ": " + str(percent) + "%")
			gobject.idle_add(lambda : self.downloads_list_store.set(iter1, 1, percent))
			
			
	#######################################
	# Threads
	#######################################
	def query_position(self, data=None):
		"""Thread that updates the label and the seek/slider."""
		while True:
			new_time_nanoseconds = self.audio_engine.query_position()
			new_time_seconds = new_time_nanoseconds / 1000 / 1000 / 1000
			new_time_human_readable = self.__convert_seconds_to_human_readable(new_time_seconds)
			gobject.idle_add(self.__update_slider, new_time_seconds)
			gobject.idle_add(lambda : self.time_elapsed_label.set_text(new_time_human_readable))
			time.sleep(.25)
	
	def __update_slider(self, new_time_seconds):
		self.time_elapsed_slider.set_value(new_time_seconds)
	
	#######################################
	# Private Methods
	#######################################
	def __convert_seconds_to_human_readable(self, number):
		"""Converts seconds to a human readable string."""
		if number == 0:
			return "0:00"
		# convert time in seconds to HH:MM:SS THIS WILL FAIL IF LENGTH > 24 HOURS
		new_time = time.strftime('%H:%M:%S', time.gmtime(number))
		if new_time[:3] == "00:": # strip out hours if below 60 minutes
			new_time = new_time[3:]
		if new_time[:3] == "00:": # strip out hours if below 60 minutes
			new_time = new_time[1:]
		return new_time

	
	#################
	# Sort Functions
	#################
	def __sort_artists_by_custom_name(self, model, iter1, iter2, data=None):
		"""Custom Function to sort artists by extracting words like "the" and "a"."""
		band1 = model[iter1][2]
		band2 = model[iter2][2]
	
		if band1 < band2:
			return -1
		elif band1 > band2:
			return 1
		return 0

	def __sort_albums_by_year(self, model, iter1, iter2, data=None):
		"""Custom function to sort albums by year."""
		year1 = model[iter1][2]
		year2 = model[iter2][2]
		order = self.albums_column.get_sort_order()
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
		return 0
	
	def __sort_songs_by_title(self, model, iter1, iter2, data=None):
		"""Custom function to sort titles alphabetically."""
		title1 = model[iter1][1]
		title2 = model[iter2][1]
		
		if title1 < title2:
			return -1
		elif title2 < title1:
			return 1
		return 0

	def __sort_songs_by_track(self, model, iter1, iter2, data=None):
		"""Custom function to sort songs by track."""
		track1 = model[iter1][0]
		track2 = model[iter2][0]

		if track1 < track2:
			return -1
		elif track1 > track2:
			return 1
		return self.__sort_songs_by_title(model, iter1, iter2, data)

	def __sort_songs_by_album(self, model, iter1, iter2, data=None):
		"""Custom function to sort songs by album, if the albums are the same it will sort by tracks."""
		album1 = model[iter1][3]
		album2 = model[iter2][3]

		if album1 < album2:
			return -1
		elif album1 > album2:
			return 1
		return self.__sort_songs_by_track(model, iter1, iter2, data)

	def __sort_songs_by_artist(self, model, iter1, iter2, data=None):
		"""Custom function to sort songs by artist, if the artists are the same it will sort by albums."""
		artist1 = model[iter1][2]
		artist2 = model[iter2][2]

		if artist1 < artist2:
			return -1
		elif artist1 > artist2:
			return 1
		return self.__sort_songs_by_album(model, iter1, iter2, data)

	#################
	# Internal Helper Functions
	#################
	def __clear_all_list_stores(self):
		"""Clears all list stores in the GUI."""
		self.song_list_store.clear()
		self.album_list_store.clear()
		self.artist_list_store.clear()
		
	def __re_fetch_album_art(self, data=None):
		try: # check to see if this function is running
			if self.button_album_art_locked == True:
				print "Already Running"
				return False
		except:
			pass
		self.button_album_art_locked = True
		print "Re-Fetching album art... ",
		self.update_statusbar("Re-Fetching album art...")
		try:
			album_id   = self.current_song_info['album_id']
			art_folder = self.ampache_conn.art_folder
			art_file   = art_folder + os.sep + str(album_id)
			album_art  = self.ampache_conn.get_album_art(album_id)
			response   = urllib2.urlopen(album_art)
			f = open(art_file, 'w')
			f.write(response.read())
			f.close()
			image_pixbuf = self.__create_image_pixbuf(art_file, ALBUM_ART_SIZE)
			self.album_art_image.set_from_pixbuf(image_pixbuf)
			print "Done!"
		except: 
			self.update_statusbar("Re-Fetching album art... Failed!")
			print "Failed!"
			self.button_album_art_locked = False
			return False
		self.update_statusbar("Re-Fetching album art... Success!")
		self.button_album_art_locked = False
		return True

	def __add_songs_to_list_store(self, album_id):
		"""Takes an album_id, and adds all of that albums songs to the GUI."""
		songs = self.ampache_conn.get_song_dict(album_id)
		model = self.song_list_store
		
		if not songs:
			print "Error pulling ", album_id
			self.update_statusbar("Error with album -- Check Ampache")
			return False
		
		for song in songs:
			song_track  = songs[song]['track']
			song_title  = songs[song]['title']
			song_time   = songs[song]['time']
			song_size   = songs[song]['size']
			song_id     = song
			artist_name = songs[song]['artist_name']
			album_name  = songs[song]['album_name']
			#album_year  = self.ampache_conn.get_album_year(album_id)S

			# convert time in seconds to HH:MM:SS THIS WILL FAIL IF LENGTH > 24 HOURS
			song_time = time.strftime('%H:%M:%S', time.gmtime(song_time))
			if song_time[:2] == "00": # strip out hours if below 60 minutes
				song_time = song_time[3:]
			# convert size to humand_readable
			song_size = self.__human_readable_filesize(float(song_size))
			
			model.append([song_track, song_title, artist_name, album_name, song_time, song_size, song_id])
		return True

	def __create_single_column_tree_view(self, column_name, model, sort_column=None):
		"""Create a treeview by passing a column_name and a  model (gtk.ListStore())."""
		tree_view = gtk.TreeView(model)
		tree_view.set_rules_hint(True)
		column = self.__create_column(column_name, 0, sort_column)
		tree_view.append_column(column)
		return tree_view

	def __create_column(self, column_name, column_id, sort_column=None, pixbuf=False):
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

	def __create_image_pixbuf(self, file, width, height=None):
		"""Helper function to create a pixel buffer from a file of a set width and height."""
		if height == None:
			height = width
		image = gtk.gdk.pixbuf_new_from_file(file).scale_simple(width, height, gtk.gdk.INTERP_BILINEAR)
		return image
	
	
	def __human_readable_filesize(self, bytes):
		"""Converts bytes to humand_readable form."""
		if bytes >= 1073741824:
			return str(round(bytes / 1024 / 1024 / 1024, 1)) + ' GB'
		elif bytes >= 1048576:
			return str(round(bytes / 1024 / 1024, 1)) + ' MB'
		elif bytes >= 1024:
			return str(round(bytes / 1024, 1)) + ' KB'
		elif bytes < 1024:
			return str(bytes) + ' bytes'

