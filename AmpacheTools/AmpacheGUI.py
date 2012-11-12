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


import sys
import os
import urllib2
import time
import thread
import gobject
import urllib
import re
import shutil
import cPickle
import getpass
import traceback

try:
    import dbus
    from dbus.mainloop.glib import threads_init
    threads_init()
    DBUS_AVAILABLE = True
except:
    DBUS_AVAILABLE = False

try:
    import glib
    GLIB_AVAILABLE = True
except ImportError:
    GLIB_AVAILABLE = False

try:
    import gtk
    import pygtk
    pygtk.require("2.0")
except:
    print "pygtk required!"
    sys.exit(1);


try:
    import pynotify
    pynotify.init('Viridian')
    pynotify_object = pynotify.Notification(" ", " ")
    PYNOTIFY_INSTALLED = True
except:
    PYNOTIFY_INSTALLED = False


# personal helper functions
import dbfunctions
import helperfunctions
import guifunctions

from XMLRPCServerSession import XMLServer

### Contstants ###
ALBUM_ART_SIZE = 90
SCRIPT_PATH    = os.path.abspath(os.path.dirname(__file__))
PLUGINS_DIR    = os.path.join(SCRIPT_PATH, 'plugins/')
IMAGES_DIR     = os.path.join(SCRIPT_PATH, 'images/')
THREAD_LOCK    = thread.allocate_lock() # used for downloads
THREAD_LOCK_B  = thread.allocate_lock() # used for song changing
VIRIDIAN_DIR   = os.path.join(os.environ['HOME'], '.viridian')
ALBUM_ART_DIR  = os.path.join(VIRIDIAN_DIR, 'album_art')
XML_RPC_PORT   = 4596
VERSION_NUMBER = ''


class AmpacheGUI:
    """The Ampache GUI Class"""
    def main(self):
        """Method to call gtk.main() and display the GUI."""
        gobject.threads_init()
        gobject.idle_add(self.main_gui_callback)

        ### Status tray icon ####
        self.tray_icon_to_display = self.db_session.variable_get('tray_icon_to_display', 'standard')

        if self.tray_icon_to_display == "standard":
            self.tray_icon = gtk.StatusIcon()
            self.tray_icon.set_from_pixbuf(self.images_pixbuf_viridian_app)
            self.tray_icon.connect('activate', self.status_icon_activate)
            self.tray_icon.connect('popup-menu', self.status_icon_popup_menu)
            self.tray_icon.set_tooltip('Viridian')

        ### Seek Bar Thread (1/5 second) ###
        gobject.timeout_add(200, self.query_position)

        gtk.main()

    def delete_event(self, widget, event, data=None):
        """Keep the window alive when it is X'd out."""
        if not hasattr(self, 'tray_icon') or self.quit_when_window_closed: # no tray icon set, must destroy
            self.destroy()
        else: # don't quit, just hide
            if self.first_time_closing:
                self.main_gui_toggle_hidden()
                self.create_dialog_alert("info", _("Viridian is still running in the status bar.  If you do not want Viridian to continue running when the window is closed you can disable it in Preferences."), True)
                self.first_time_closing = False
                self.db_session.variable_set('first_time_closing', False)
            else:
                self.main_gui_toggle_hidden()
        return True

    def destroy(self, widget=None, data=None):
        """The function when the program exits."""
        if THREAD_LOCK.locked():
            result = self.create_dialog_ok_or_close(_("Downloads in progress.."), _("There are unfinished downloads, are you sure you want to quit?"))
            if result != "ok":
                return True
        self.stop_all_threads()
        size = self.window.get_size()
        self.stop_xml_server()
        self.db_session.variable_set('current_playlist', self.audio_engine.get_playlist())
        self.db_session.variable_set('volume', self.audio_engine.get_volume())
        self.db_session.variable_set('window_size_width',  size[0])
        self.db_session.variable_set('window_size_height', size[1])
        gtk.main_quit()

    def __init__(self, ampache_conn, audio_engine, db_session, is_first_time, version):
        """Constructor for the AmpacheGUI Class.
        Takes an AmpacheSession Object, an AudioEngine Object and a DatabaseSession Object."""
        #################################
        # Set Variables
        #################################
        global VERSION_NUMBER
        VERSION_NUMBER    = version
        self.audio_engine = audio_engine
        self.ampache_conn = ampache_conn
        self.db_session   = db_session

        plugins_list = self.__find_plugins(PLUGINS_DIR)
        self.plugins = {}
        for plugin_name in plugins_list:
            plugin = self.__import_plugin(plugin_name)
            if plugin:
                self.plugins[plugin_name] = plugin
        print "Plugins = ", self.plugins # DEBUG

        self.enabled_plugins = self.db_session.variable_get('enabled_plugins', [])

        xmlrpc_port       = self.db_session.variable_get('xmlrpc_port', XML_RPC_PORT)
        self.xml_server   = XMLServer('', xmlrpc_port)

        self.is_first_time = is_first_time

        self.catalog_up_to_date = None
        self.current_song_info = None
        self.tree_view_dict = {}
        dbfunctions.create_initial_tables(self.db_session)

        volume = self.db_session.variable_get('volume', float(100))
        width  = self.db_session.variable_get('window_size_width', 1150)
        height = self.db_session.variable_get('window_size_height', 600)

        ##################################
        # Load Images
        ##################################
        self.images_pixbuf_play  = guifunctions.create_image_pixbuf(IMAGES_DIR + 'play.png', 75)
        self.images_pixbuf_pause = guifunctions.create_image_pixbuf(IMAGES_DIR + 'pause.png', 75)
        self.images_pixbuf_gold_star = guifunctions.create_image_pixbuf(IMAGES_DIR + 'star_rating_gold.png', 16)
        self.images_pixbuf_gray_star = guifunctions.create_image_pixbuf(IMAGES_DIR + 'star_rating_gray.png', 16)
        images_pixbuf_prev = guifunctions.create_image_pixbuf(IMAGES_DIR + 'prev.png', 75)
        images_pixbuf_next = guifunctions.create_image_pixbuf(IMAGES_DIR + 'next.png', 75)
        self.images_pixbuf_playing = guifunctions.create_image_pixbuf(IMAGES_DIR + 'playing.png', 15)
        self.images_pixbuf_empty   = guifunctions.create_image_pixbuf(IMAGES_DIR + 'empty.png', 1)

        self.images_pixbuf_viridian_simple = guifunctions.create_image_pixbuf(IMAGES_DIR + 'ViridianSimple.png', 20)
        self.images_pixbuf_viridian_app    = guifunctions.create_image_pixbuf(IMAGES_DIR + 'ViridianApp.png', 70)

        ##################################
        # Main Window
        ##################################
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)

        self.window.connect("delete_event", self.delete_event)
        self.window.connect("destroy", self.destroy)
        self.window.set_title("Viridian")
        self.window.resize(width, height)
        self.window.set_icon(self.images_pixbuf_viridian_simple)

        main_box = gtk.VBox()

        #################################
        # Menu Bar
        #################################
        menu_bar = gtk.MenuBar()

        agr = gtk.AccelGroup()
        self.window.add_accel_group(agr)

        """Start File Menu"""
        file_menu = gtk.Menu()
        filem = gtk.MenuItem(_("_File"))
        filem.set_submenu(file_menu)

        newi = gtk.MenuItem(_("Reauthenticate"))
        newi.connect("activate", self.button_reauthenticate_clicked)
        file_menu.append(newi)

        self.go_to_ampache_menu_item = gtk.MenuItem(_("Open Ampache"))
        self.go_to_ampache_menu_item.connect("activate", lambda x: self.gnome_open(self.ampache_conn.url))
        self.go_to_ampache_menu_item.set_sensitive(False)
        file_menu.append(self.go_to_ampache_menu_item)

        sep = gtk.SeparatorMenuItem()
        file_menu.append(sep)

        newi = gtk.ImageMenuItem(_("Save Playlist"), agr)
        img = gtk.image_new_from_stock(gtk.STOCK_SAVE, gtk.ICON_SIZE_MENU)
        newi.set_image(img)
        key, mod = gtk.accelerator_parse("<Control>S")
        newi.add_accelerator("activate", agr, key, mod, gtk.ACCEL_VISIBLE)
        newi.connect("activate", self.button_save_playlist_clicked)
        file_menu.append(newi)

        newi = gtk.ImageMenuItem(_("Load Playlist"), agr)
        img = gtk.image_new_from_stock(gtk.STOCK_OPEN, gtk.ICON_SIZE_MENU)
        newi.set_image(img)
        key, mod = gtk.accelerator_parse("<Control>O")
        newi.add_accelerator("activate", agr, key, mod, gtk.ACCEL_VISIBLE)
        newi.connect("activate", self.button_load_playlist_clicked)
        file_menu.append(newi)

        newi = gtk.ImageMenuItem(_("Export Playlist..."))#, agr)
        img = gtk.image_new_from_stock(gtk.STOCK_SAVE_AS, gtk.ICON_SIZE_MENU)
        newi.set_image(img)
        #key, mod = gtk.accelerator_parse("<Control>E")
        #newi.add_accelerator("activate", agr, key, mod, gtk.ACCEL_VISIBLE)
        newi.connect("activate", self.button_export_playlist_clicked)
        file_menu.append(newi)

        sep = gtk.SeparatorMenuItem()
        file_menu.append(sep)

        newi = gtk.MenuItem(_("Clear Album Art"))
        newi.connect("activate", self.button_clear_album_art_clicked)
        file_menu.append(newi)

        newi = gtk.MenuItem(_("Clear Local Cache"))
        newi.connect("activate", self.button_clear_cached_artist_info_clicked)
        file_menu.append(newi)

        newi = gtk.MenuItem(_("Pre-Cache"))
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
        editm = gtk.MenuItem(_("_Edit"))
        editm.set_submenu(edit_menu)

        newi = gtk.MenuItem(_("Plugins"))
        newi.connect("activate", self.show_plugins_window)
        edit_menu.append(newi)

        newi = gtk.ImageMenuItem(gtk.STOCK_PREFERENCES, agr)
        key, mod = gtk.accelerator_parse("<Control>P")
        newi.add_accelerator("activate", agr, key, mod, gtk.ACCEL_VISIBLE)

        newi.connect("activate", self.show_settings)

        edit_menu.append(newi)

        menu_bar.append(editm)
        """End Edit Menu"""

        """Start View Menu"""
        view_menu = gtk.Menu()
        viewm = gtk.MenuItem(_("_View"))
        viewm.set_submenu(view_menu)

        newi = gtk.CheckMenuItem(_("Show Playlist"))
        show_playlist = self.db_session.variable_get('show_playlist', True)

        newi.set_active(show_playlist)
        newi.connect("activate", self.toggle_playlist_view)
        view_menu.append(newi)

        self.show_downloads_checkbox = gtk.CheckMenuItem(_("Show Downloads"))
        show_downloads = self.db_session.variable_get('show_downloads', False)
        self.show_downloads_checkbox.set_active(show_downloads)
        self.show_downloads_checkbox.connect("activate", self.toggle_downloads_view)
        view_menu.append(self.show_downloads_checkbox)

        sep = gtk.SeparatorMenuItem()
        view_menu.append(sep)

        newi = gtk.CheckMenuItem(_("View Statusbar"))
        view_statusbar = self.db_session.variable_get('view_statusbar', True)
        newi.set_active(view_statusbar)
        newi.connect("activate", self.toggle_statusbar_view)
        view_menu.append(newi)

        menu_bar.append(viewm)
        """End View Menu"""

        """Start Help Menu"""
        help_menu = gtk.Menu()
        helpm = gtk.MenuItem(_("_Help"))
        helpm.set_submenu(help_menu)

        newi = gtk.ImageMenuItem(gtk.STOCK_HELP)
        newi.connect("activate", self.show_help)
        help_menu.append(newi)

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

        ### Volume slider, repeat songs
        self.volume_slider = gtk.HScale()
        self.volume_slider.set_inverted(False)
        self.volume_slider.set_range(0, 100)
        self.volume_slider.set_increments(1, 10)
        self.volume_slider.set_draw_value(False)
        self.volume_slider.connect('change-value', self.on_volume_slider_change)
        self.volume_slider.set_size_request(80, 20)
        self.volume_slider.set_value(volume)

        repeat_songs_checkbutton = gtk.CheckButton(_("Repeat"))
        repeat_songs_checkbutton.set_active(False)
        repeat_songs_checkbutton.connect("toggled", self.toggle_repeat_songs)

        shuffle_songs_checkbutton = gtk.CheckButton(_("Shuffle"))
        shuffle_songs_checkbutton.set_active(False)
        shuffle_songs_checkbutton.connect("toggled", self.toggle_shuffle_songs)

        hbox = gtk.HBox()
        vbox = gtk.VBox()
        label = gtk.Label()
        label.set_markup(_('<span size="6000"><b>Volume</b></span>'))
        vbox.pack_start(label, False, False, 0)
        vbox.pack_start(self.volume_slider, False, False, 0)

        hbox.pack_start(vbox, False, False, 0)

        vbox = gtk.VBox()
        vbox.pack_start(repeat_songs_checkbutton, False, False, 0)

        hbox.pack_start(vbox, False, False, 0)

        vbox = gtk.VBox()
        vbox.pack_start(shuffle_songs_checkbutton, False, False, 0)

        hbox.pack_start(vbox, False, False, 0)

        top_bar_left_bottom.pack_start(hbox, False, False, 0)


        #top_bar_left_bottom.pack_start(gtk.Label("Volume: "), False, False, 0)
        #top_bar_left_bottom.pack_start(self.volume_slider, False, False, 2)
        #top_bar_left_bottom.pack_start(repeat_songs_checkbutton, False, False, 2)

        top_bar_left.pack_start(top_bar_left_top, False, False, 0)
        top_bar_left.pack_start(top_bar_left_bottom, False, False, 0)

        top_bar.pack_start(top_bar_left, False, False, 0)
        """End Top Control Bar"""

        #################################
        # Scrubbing Bar
        #################################
        vbox = gtk.VBox()

        vbox.pack_start(gtk.Label(" "), False, False, 1) # filler

        self.time_seek_label = gtk.Label(" ")
        vbox.pack_start(self.time_seek_label, False, False, 2)

        hbox = gtk.HBox()

        self.time_elapsed_label = gtk.Label("0:00")
        hbox.pack_start(self.time_elapsed_label, False, False, 2)

        self.time_elapsed_slider = gtk.HScale()
        self.time_elapsed_slider.set_inverted(False)
        self.time_elapsed_slider.set_range(0, 1)
        self.time_elapsed_slider.set_increments(1, 10)
        self.time_elapsed_slider.set_draw_value(False)
        self.time_elapsed_slider.set_update_policy(gtk.UPDATE_DELAYED)
        self.time_elapsed_signals = []
        self.time_elapsed_signals.append(self.time_elapsed_slider.connect('value-changed', self.on_time_elapsed_slider_change))
        self.time_elapsed_signals.append(self.time_elapsed_slider.connect('change-value', self.on_time_elapsed_slider_change_value))
        hbox.pack_start(self.time_elapsed_slider, True, True, 2)

        self.time_total_label = gtk.Label("0:00")
        hbox.pack_start(self.time_total_label, False, False, 2)

        vbox.pack_start(hbox, False, False, 2)

        top_bar.pack_start(vbox)
        #################################
        # Now Playing
        #################################
        now_playing_info = gtk.VBox()

        filler = gtk.Label()
        self.current_song_label   = gtk.Label()
        self.current_artist_label = gtk.Label()
        self.current_album_label  = gtk.Label()

        now_playing_info.pack_start(filler, False, False, 0)
        now_playing_info.pack_start(self.current_song_label,   False, False, 1)
        now_playing_info.pack_start(self.current_artist_label, False, False, 1)
        now_playing_info.pack_start(self.current_album_label,  False, False, 1)

        top_bar.pack_start(now_playing_info, False, False, 5)

        #################################
        #  Album Art
        #################################
        vbox = gtk.VBox()

        self.album_art_image = gtk.Image()

        event_box_album = gtk.EventBox()
        event_box_album.connect("button_release_event", self.button_album_art_clicked)
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

        top_bar.pack_start(vbox, False, False, 1)


        ########
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
        self.tree_view_dict['playlist'] = tree_view
        tree_view.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        tree_view.set_reorderable(True)
        tree_view.connect("drag-end", self.on_playlist_drag)
        tree_view.connect("row-activated", self.playlist_on_activated)
        tree_view.connect("button_press_event", self.playlist_on_right_click)
        tree_view.set_rules_hint(True)

        new_column = guifunctions.create_column("    ", 0, None, True)
        new_column.set_reorderable(False)
        new_column.set_resizable(False)
        new_column.set_clickable(False)
        new_column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        new_column.set_fixed_width(20)
        tree_view.append_column(new_column)

        renderer_text = gtk.CellRendererText()
        new_column = gtk.TreeViewColumn(_("Current Playlist"), renderer_text, markup=1)
        #new_column = guifunctions.create_column("Current Playlist", 1)
        new_column.set_reorderable(False)
        new_column.set_resizable(False)
        new_column.set_clickable(False)
        new_column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        tree_view.append_column(new_column)

        playlist_scrolled_window.add(tree_view)

        self.playlist_window.pack_start(playlist_scrolled_window)

        hbox = gtk.HBox()

        button = gtk.Button(_("Clear Playlist"))
        button.connect('clicked', self.audio_engine.clear_playlist)

        hbox.pack_start(button, False, False, 2)

        combobox = gtk.combo_box_new_text()
        combobox.append_text(_('Replace Mode'))
        combobox.append_text(_('Add Mode'))
        combobox.connect('changed', self.playlist_mode_changed)


        hbox.pack_start(combobox, False, False, 2)

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
        self.tree_view_dict['downloads'] = tree_view
        tree_view.connect("row-activated", self.downloads_on_activated)
        tree_view.connect("button_press_event", self.downloads_on_right_click)
        tree_view.set_rules_hint(True)
        column = gtk.TreeViewColumn(_("File"), gtk.CellRendererText(), text=0)
        column.set_reorderable(False)
        column.set_resizable(True)
        column.set_clickable(False)
        column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        column.set_fixed_width(100)

        tree_view.append_column(column)

        rendererprogress = gtk.CellRendererProgress()
        column = gtk.TreeViewColumn(_("Progress"))
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

        renderer_text = gtk.CellRendererText()
        artists_column = gtk.TreeViewColumn(_("Artists"), renderer_text, markup=0)
        artists_column.set_resizable(False)
        artists_column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        artists_column.set_sort_column_id(0)


        # name, id, custom_name
        self.artist_list_store = gtk.ListStore(str, int, str)
        self.artist_list_store.set_sort_func(0, helperfunctions.sort_artists_by_custom_name, artists_column)
        self.artist_list_store.set_sort_column_id(0, gtk.SORT_ASCENDING)

        tree_view = gtk.TreeView(self.artist_list_store)
        self.tree_view_dict['artists'] = tree_view
        tree_view.set_rules_hint(False)
        artists_column.set_sizing(gtk.TREE_VIEW_COLUMN_AUTOSIZE)
        tree_view.append_column(artists_column)


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


        #albums_column = guifunctions.create_column("Albums", 0)
        renderer_text = gtk.CellRendererText()
        albums_column = gtk.TreeViewColumn(_("Albums"), renderer_text, markup=0)
        albums_column.set_resizable(False)
        albums_column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        albums_column.set_sort_column_id(0)

        # name, id, year, stars
        self.album_list_store = gtk.ListStore(str, int, int, int)
        self.album_list_store.set_sort_column_id(0, gtk.SORT_ASCENDING)
        self.album_list_store.set_sort_func(0, helperfunctions.sort_albums_by_year, albums_column ) # sort albums by year!

        tree_view = gtk.TreeView(self.album_list_store)
        self.tree_view_dict['albums'] = tree_view
        tree_view.set_rules_hint(False)
        albums_column.set_sizing(gtk.TREE_VIEW_COLUMN_AUTOSIZE)
        tree_view.append_column(albums_column)

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
        self.song_list_store.set_sort_func(0, helperfunctions.sort_songs_by_track)
        self.song_list_store.set_sort_func(1, helperfunctions.sort_songs_by_title)
        self.song_list_store.set_sort_func(2, helperfunctions.sort_songs_by_artist)
        self.song_list_store.set_sort_func(3, helperfunctions.sort_songs_by_album)
        self.song_list_store.set_sort_column_id(2,gtk.SORT_ASCENDING)

        tree_view = gtk.TreeView(self.song_list_store)
        self.tree_view_dict['songs'] = tree_view
        tree_view.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        tree_view.connect("row-activated", self.songs_on_activated)
        tree_view.connect("button_press_event", self.songs_on_right_click)
        tree_view.set_rules_hint(True)
        tree_view.set_search_column(1)

        i = 0
        for column in (_("Track"), _("Title"), _("Artist"), _("Album"), _("Time"), _("Size")):
            new_column = guifunctions.create_column(column, i)
            new_column.set_reorderable(True)
            new_column.set_resizable(True)
            new_column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
            if column == _("Track"):
                new_column.set_fixed_width(65)
            elif column == _("Title"):
                new_column.set_fixed_width(230)
            elif column == _("Artist"):
                new_column.set_fixed_width(170)
            elif column == _("Album"):
                new_column.set_fixed_width(190)
            elif column == _("Time"):
                new_column.set_fixed_width(90)
            elif column == _("Size"):
                new_column.set_fixed_width(70)
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
        self.update_statusbar(_("Ready"))


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
        repeat_songs = self.db_session.variable_get('repeat_songs', False)
        repeat_songs_checkbutton.set_active(repeat_songs)
        self.audio_engine.set_repeat_songs(repeat_songs)

        # check shuffle songs_on_activated
        shuffle_songs = self.db_session.variable_get('shuffle_songs', False)
        shuffle_songs_checkbutton.set_active(shuffle_songs)
        self.audio_engine.set_shuffle_songs(shuffle_songs)

        self.playlist_mode = self.db_session.variable_get('playlist_mode', 0)
        combobox.set_active(self.playlist_mode)

        # media keys
        if DBUS_AVAILABLE:
            try:
                session_bus = dbus.SessionBus()
                gnome_settings_daemon = session_bus.get_object("org.gnome.SettingsDaemon", "/org/gnome/SettingsDaemon/MediaKeys")
                media_keys = dbus.Interface(gnome_settings_daemon, "org.gnome.SettingsDaemon.MediaKeys")
                media_keys.connect_to_signal("MediaPlayerKeyPressed", self.media_key_pressed)
            except:
                pass

    def media_key_pressed(self, *args):
        """Support Media Key Presses -- Merged from Andrew Barr"""
        key = args[1]
        op_function = { "Previous" : self.button_prev_clicked,
            "Next" : self.button_next_clicked ,
            "Stop" : self.audio_engine.stop ,
            "Play" : self.button_play_pause_clicked }
        op_function[key]()

    def main_gui_callback(self):
        """Function that gets called after GUI has loaded.
        This loads all user variables into memory."""
        ### Display Notifications ###
        self.display_notifications = self.db_session.variable_get('display_notifications', True)
        ### Automatically Update Cache ###
        self.automatically_update = self.db_session.variable_get('automatically_update', False)
        ### Is first time closing application (alert user it is in status bar) ###
        self.first_time_closing = self.db_session.variable_get('first_time_closing', True)
        ### Status tray variables ###
        self.quit_when_window_closed = self.db_session.variable_get('quit_when_window_closed', False)
        ### Downloads Directory ###
        # first check if xdg_downloads exists, if not then check if
        # ~/Downloads exist, then fallback to ~ (only if the user hasn't set one)
        download_dir = os.path.expanduser("~")
        if GLIB_AVAILABLE: # first try to set the Downloads dir to the users locale Download dir
            xdg_download_dir = glib.get_user_special_dir(glib.USER_DIRECTORY_DOWNLOAD)
            if not xdg_download_dir is None: # xdg was set
                download_dir = xdg_download_dir
            elif os.path.exists(os.path.join(download_dir, 'Downloads')):
                download_dir = os.path.join(download_dir, 'Downloads')
        else: # no glib.. try to set it to ~/Downloads
            if os.path.exists(os.path.join(download_dir, 'Downloads')):
                download_dir = os.path.join(download_dir, 'Downloads')
        self.downloads_directory = self.db_session.variable_get('downloads_directory', download_dir)

        ### Alternate Row Colors ###
        playlist = self.db_session.variable_get('playlist', True)
        downloads = self.db_session.variable_get('downloads', True)
        artists = self.db_session.variable_get('artists', False)
        albums = self.db_session.variable_get('albums', False)
        songs = self.db_session.variable_get('songs', True)

        self.tree_view_dict['playlist'].set_rules_hint(playlist)
        self.tree_view_dict['downloads'].set_rules_hint(downloads)
        self.tree_view_dict['artists'].set_rules_hint(artists)
        self.tree_view_dict['albums'].set_rules_hint(albums)
        self.tree_view_dict['songs'].set_rules_hint(songs)

        ### Check for credentials and login ###
        username = self.db_session.variable_get('credentials_username')
        password = self.db_session.variable_get('credentials_password')
        url      = self.db_session.variable_get('credentials_url')

        self.ampache_conn.set_credentials(username, password, url)
        if self.ampache_conn.has_credentials():
            self.go_to_ampache_menu_item.set_sensitive(True)
            self.update_statusbar(_("Attempting to authenticate..."))
            if self.login_and_get_artists("First"):
                list = self.db_session.variable_get('current_playlist', None)
                if list != None:
                    self.load_playlist(list)
                    #self.update_playlist_window()
        else:
            self.update_statusbar(_("Set Ampache information by going to Edit -> Preferences"))
            if self.is_first_time:
                self.create_dialog_alert("info", _("""This looks like the first time you are running Viridian.  To get started, go to Edit -> Preferences and set your account information."""), True)

        if self.db_session.variable_get('enable_xmlrpc_server', False): # start the xmlrpc server
            self.start_xml_server()


    def main_gui_toggle_hidden(self):
        if self.window.is_active():
            self.window.hide_on_delete()
        else:
            show_playlist  = self.db_session.variable_get('show_playlist', True)
            show_downloads = self.db_session.variable_get('show_downloads', False)
            view_statusbar = self.db_session.variable_get('view_statusbar', True)

            self.window.show_all()
            self.window.grab_focus()
            self.window.present()
            if show_playlist == False:
                self.playlist_window.hide()
            if show_downloads == False:
                self.downloads_window.hide()
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
        self.preferences_window.set_icon(self.images_pixbuf_viridian_simple)
        self.preferences_window.set_transient_for(self.window)
        self.preferences_window.set_title(_("Viridian Settings"))
        self.preferences_window.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        self.preferences_window.resize(450, 300)
        self.preferences_window.set_resizable(False)
        self.preferences_window.set_icon(self.images_pixbuf_viridian_simple)
        self.preferences_window.connect("delete_event", self.destroy_settings)
        self.preferences_window.connect("destroy", self.destroy_settings)

        main_vbox = gtk.VBox(False, 8)
        main_vbox.set_border_width(10)

        """Start Notebook"""
        notebook = gtk.Notebook()
        notebook.set_tab_pos(gtk.POS_LEFT)

        #################################
        # Account Settings
        #################################
        account_box = gtk.VBox()
        account_box.set_border_width(10)

        hbox = gtk.HBox()
        label = gtk.Label()
        label.set_markup(_('<b>Account Settings</b>'))
        hbox.pack_start(label, False, False)

        account_box.pack_start(hbox, False, False, 3)

        ### Ampache URL ###
        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label("   "), False, False, 0)
        ampache_label = gtk.Label(_("Ampache URL:"))
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
        label.set_markup(_('<span size="8000"><b>Example: </b>http://example.com/ampache</span>'))
        hbox.pack_end(label, False, False, 2)

        account_box.pack_start(hbox, False, False, 2)
        ### Ampache Username ###
        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label("   "), False, False, 0)
        username_label = gtk.Label(_("Username:"))
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
        password_label = gtk.Label(_("Password:"))
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
        label.set_markup(_('<b>Notifications</b>'))
        hbox.pack_start(label, False, False)

        display_box.pack_start(hbox, False, False, 3)

        hbox = gtk.HBox()

        hbox.pack_start(gtk.Label("   "), False, False, 0)

        display_notifications_checkbutton = gtk.CheckButton(_("Display OSD Notifications"))
        if PYNOTIFY_INSTALLED:
            display_notifications_checkbutton.set_active(self.display_notifications)
        else:
            display_notifications_checkbutton.set_sensitive(False)
            display_notifications_checkbutton.set_active(False)
        display_notifications_checkbutton.connect("toggled", self.toggle_display_notifications)
        hbox.pack_start(display_notifications_checkbutton)

        display_box.pack_start(hbox, False, False, 1)

        hbox = gtk.HBox()

        label = gtk.Label()
        label.set_markup(_('<b>Alternate Row Colors</b>'))
        hbox.pack_start(label, False, False)

        display_box.pack_start(hbox, False, False, 3)

        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label("   "), False, False, 0)
        cb = gtk.CheckButton(_("Artists Column"))
        cb.connect("toggled", self.toggle_alternate_row_colors, 'artists')
        cb.set_active(self.tree_view_dict['artists'].get_rules_hint())
        hbox.pack_start(cb)
        display_box.pack_start(hbox, False, False, 0)

        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label("   "), False, False, 0)
        cb = gtk.CheckButton(_("Albums Column"))
        cb.connect("toggled", self.toggle_alternate_row_colors, 'albums')
        cb.set_active(self.tree_view_dict['albums'].get_rules_hint())
        hbox.pack_start(cb)
        display_box.pack_start(hbox, False, False, 0)

        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label("   "), False, False, 0)
        cb = gtk.CheckButton(_("Songs Column"))
        cb.connect("toggled", self.toggle_alternate_row_colors, 'songs')
        cb.set_active(self.tree_view_dict['songs'].get_rules_hint())
        hbox.pack_start(cb)
        display_box.pack_start(hbox, False, False, 0)

        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label("   "), False, False, 0)
        cb = gtk.CheckButton(_("Playlist Column"))
        cb.connect("toggled", self.toggle_alternate_row_colors, 'playlist')
        cb.set_active(self.tree_view_dict['playlist'].get_rules_hint())
        hbox.pack_start(cb)
        display_box.pack_start(hbox, False, False, 0)

        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label("   "), False, False, 0)
        cb = gtk.CheckButton(_("Downloads Column"))
        cb.connect("toggled", self.toggle_alternate_row_colors, 'downloads')
        cb.set_active(self.tree_view_dict['downloads'].get_rules_hint())
        hbox.pack_start(cb)
        display_box.pack_start(hbox, False, False, 0)

        """End Display Settings"""
        """Start Catalog Settings"""
        #################################
        # catalog Settings
        #################################
        catalog_box = gtk.VBox()
        catalog_box.set_border_width(10)

        hbox = gtk.HBox()

        label = gtk.Label()
        label.set_markup(_('<b>Catalog Cache</b>'))

        hbox.pack_start(label, False, False)

        catalog_box.pack_start(hbox, False, False, 3)

        hbox = gtk.HBox()

        hbox.pack_start(gtk.Label("   "), False, False, 0)


        cb = gtk.CheckButton(_("Automatically clear local catalog when Ampache is updated"))
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
            if self.catalog_up_to_date:
                image.set_from_stock(gtk.STOCK_YES,gtk.ICON_SIZE_SMALL_TOOLBAR)
                label.set_text(_("Local catalog is up-to-date."))
            else:
                image.set_from_stock(gtk.STOCK_NO,gtk.ICON_SIZE_SMALL_TOOLBAR)
                label.set_text(_("Local catalog is older than Ampache catalog! To update the local catalog go to File -> Clear Local Cache."))

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
        label.set_markup(_('<b>Local Downloads</b>'))

        hbox.pack_start(label, False, False)

        download_box.pack_start(hbox, False, False, 3)

        hbox = gtk.HBox()

        label = gtk.Label(_("    Select where downloaded files should go."))

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
        label.set_markup(_('<b>Status Tray Icon</b>'))

        hbox.pack_start(label, False, False)

        trayicon_box.pack_start(hbox, False, False, 3)

        cb = gtk.CheckButton(_("Quit Viridian when window is closed"))
        cb.connect("toggled", self.toggle_quit_when_window_closed)
        cb.set_active(self.quit_when_window_closed)

        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label("   "), False, False, 0)

        button = gtk.RadioButton(None, _("Standard Tray Icon"))
        button.connect("toggled", self.trayicon_settings_toggled, "standard", cb)
        if self.tray_icon_to_display == 'standard':
            button.set_active(True)
        hbox.pack_start(button, True, True, 0)

        trayicon_box.pack_start(hbox, False, False, 2)

        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label("   "), False, False, 0)

        button = gtk.RadioButton(button, _("Unified Sound Icon ( Ubuntu 10.10 or higher )"))
        button.connect("toggled", self.trayicon_settings_toggled, "unified", cb)
        button.set_sensitive(False) # Ubuntu unified sound
        if self.tray_icon_to_display == 'unified':
            button.set_active(True)
        hbox.pack_start(button, True, True, 0)

        trayicon_box.pack_start(hbox, False, False, 2)

        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label("   "), False, False, 0)

        button = gtk.RadioButton(button, _("Disabled"))
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

        label = gtk.Label(_("Note: changes to the type of icon will take effect the next time this program is opened."))
        label.set_line_wrap(True)

        hbox.pack_start(label, False, False, 4)

        trayicon_box.pack_start(hbox, False, False, 5)
        """End Tray Icon Settings"""
        """Start Server Settings"""
        #################################
        # Server Settings
        #################################
        server_box = gtk.VBox(False, 0)
        server_box.set_border_width(10)

        hbox = gtk.HBox()

        label = gtk.Label()
        label.set_markup(_('<b>Server Settings</b>'))

        hbox.pack_start(label, False, False)

        server_box.pack_start(hbox, False, False, 3)

        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label("   "), False, False, 0)

        hbox.pack_start(gtk.Label(_("XML RPC Server: ")), False, False, 0)

        label = gtk.Label()
        image = gtk.Image()

        if self.xml_server.is_running:
            image.set_from_stock(gtk.STOCK_YES,gtk.ICON_SIZE_SMALL_TOOLBAR)
            label.set_text(_("Running. (port %d)") % self.xml_server.port)
        else:
            image.set_from_stock(gtk.STOCK_NO,gtk.ICON_SIZE_SMALL_TOOLBAR)
            label.set_text(_("Not Running."))

        hbox.pack_start(image, False, False, 5)
        hbox.pack_start(label, False, False, 0)

        server_box.pack_start(hbox, False, False, 2)

        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label("      "), False, False, 0)

        port = gtk.Entry()

        button = gtk.Button(_("Start"))
        button.connect("clicked", self.button_xml_server_clicked, 'start', label, image, port)
        #button.set_sensitive(False)
        hbox.pack_start(button, True, True, 0)

        button = gtk.Button(_("Stop"))
        button.connect("clicked", self.button_xml_server_clicked, 'stop', label, image, port)
        #button.set_sensitive(False)
        hbox.pack_start(button, True, True, 0)

        button = gtk.Button(_("Restart"))
        button.connect("clicked", self.button_xml_server_clicked, 'restart', label, image, port)
        #button.set_sensitive(False)
        hbox.pack_start(button, True, True, 0)

        hbox.pack_start(gtk.Label(_('Port: ')), False, False, 1)


        port.set_text(str(self.db_session.variable_get('xmlrpc_port', XML_RPC_PORT)))

        hbox.pack_start(port)

        server_box.pack_start(hbox, False, False, 2)

        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label("      "), False, False, 0)

        cb = gtk.CheckButton(_("Start XML RPC server when Viridan starts"))
        cb.connect("toggled", self.toggle_start_xml_rpc_server)
        start_xml_rpc_server = self.db_session.variable_get('enable_xmlrpc_server', False)
        cb.set_active(start_xml_rpc_server)

        hbox.pack_start(cb, False, False, 1)

        server_box.pack_start(hbox, False, False, 2)
        """End Server Settings"""
        """Start System Settings"""
        #################################
        # System Settings
        #################################
        system_box = gtk.VBox()
        system_box.set_border_width(10)

        hbox = gtk.HBox()

        label = gtk.Label()
        label.set_markup(_('<b>System</b>'))

        hbox.pack_start(label, False, False)

        system_box.pack_start(hbox, False, False, 3)

        hbox = gtk.HBox()

        hbox.pack_start(gtk.Label("   "), False, False, 0)

        label = gtk.Label(_("To delete all personal information (including your username, password, album-art, cached information, etc.) press this button. NOTE: This will delete all personal settings stored on this computer and Viridian will close itself.  When you reopen, it will be as though it is the first time you are running Viridian."))
        label.set_line_wrap(True)

        hbox.pack_start(label, False, False)

        system_box.pack_start(hbox, False, False, 2)

        hbox = gtk.HBox()

        hbox.pack_start(gtk.Label("       "), False, False, 0)

        cb = gtk.Button(_("Reset Everything"))
        cb.connect("clicked", self.button_reset_everything_clicked)

        hbox.pack_start(cb, False, False, 2)

        system_box.pack_start(hbox, False, False, 2)
        """End System Settings"""

        """End Notebook"""
        notebook.append_page(account_box,  gtk.Label(_("Account")))
        notebook.append_page(display_box,  gtk.Label(_("Display")))
        notebook.append_page(catalog_box,  gtk.Label(_("Catalog")))
        notebook.append_page(download_box, gtk.Label(_("Downloads")))
        notebook.append_page(trayicon_box, gtk.Label(_("Tray Icon")))
        notebook.append_page(server_box,   gtk.Label(_("Server")))
        notebook.append_page(system_box,   gtk.Label(_("System")))

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
        """Close the preferences window."""
        self.preferences_window.destroy()
        self.preferences_window = None

    def show_help(self, widget, data=None):
        """The Help pane"""
        #################################
        # Help Window
        #################################
        if hasattr(self, 'help_window'):
            if self.help_window != None:
                self.help_window.present()
                return True

        self.help_window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.help_window.set_transient_for(self.window)
        self.help_window.set_title(_("Viridian Help"))
        self.help_window.set_icon(self.images_pixbuf_viridian_simple)
        self.help_window.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        self.help_window.resize(350, 300)
        self.help_window.set_resizable(False)
        self.help_window.connect("delete_event", self.destroy_help)
        self.help_window.connect("destroy", self.destroy_help)

        vbox = gtk.VBox(False, 4)
        vbox.set_border_width(10)

        label = gtk.Label()
        label.set_markup(_('<span size="14000"><b>Viridian Help</b></span>'))
        vbox.pack_start(label, False, False, 1)

        hbox = gtk.HBox()
        label = gtk.Label(_("Home Page:"))
        link  = guifunctions.hyperlink('http://viridian.daveeddy.com')
        hbox.pack_start(label, False, False, 1)
        hbox.pack_start(link,  False, False, 2)
        vbox.pack_start(hbox,  False, False, 0)

        hbox = gtk.HBox()
        label = gtk.Label(_("Launchpad:"))
        link  = guifunctions.hyperlink('https://launchpad.net/viridianplayer')
        hbox.pack_start(label, False, False, 1)
        hbox.pack_start(link,  False, False, 2)
        vbox.pack_start(hbox,  False, False, 0)

        hbox = gtk.HBox()
        label = gtk.Label(_("FAQ:"))
        link  = guifunctions.hyperlink('https://answers.launchpad.net/viridianplayer/+faqs')
        hbox.pack_start(label, False, False, 1)
        hbox.pack_start(link,  False, False, 2)
        vbox.pack_start(hbox,  False, False, 0)

        hbox = gtk.HBox()
        label = gtk.Label(_("Bugs:"))
        link  = guifunctions.hyperlink('https://bugs.launchpad.net/viridianplayer')
        hbox.pack_start(label, False, False, 1)
        hbox.pack_start(link,  False, False, 2)
        vbox.pack_start(hbox,  False, False, 0)

        hbox = gtk.HBox()
        label = gtk.Label(_("Questions:"))
        link  = guifunctions.hyperlink('https://answers.launchpad.net/viridianplayer')
        hbox.pack_start(label, False, False, 1)
        hbox.pack_start(link,  False, False, 2)
        vbox.pack_start(hbox,  False, False, 0)

        self.help_window.add(vbox)
        self.help_window.show_all()

    def destroy_help(self, widget=None, data=None):
        self.help_window.destroy()
        self.help_window = None

    def show_playlist_select(self, type=None):
        """The playlist pane"""
        #################################
        # playlist select
        #################################
        if type != "Load" and type != "Save" and type != "Export":
            return True
        if hasattr(self, 'playlist_select_window'):
            if self.playlist_select_window != None:
                self.playlist_select_window.present()
                return True

        self.playlist_select_window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.playlist_select_window.set_transient_for(self.window)
        self.playlist_select_window.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        self.playlist_select_window.resize(490, 300)
        self.playlist_select_window.set_resizable(True)
        self.playlist_select_window.set_icon(self.images_pixbuf_viridian_simple)
        self.playlist_select_window.connect("delete_event", self.destroy_playlist)
        self.playlist_select_window.connect("destroy", self.destroy_playlist)
        self.playlist_select_window.set_title(type + " playlist")

        vbox = gtk.VBox()
        vbox.set_border_width(10)

        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label("Select a Playlist to " + type + "..."), False, False, 2)
        vbox.pack_start(hbox, False, False, 2)

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)


        # name, items, owner, type, id
        playlist_list_store = gtk.ListStore(str, int, str, str, int)
        tree_view = gtk.TreeView(playlist_list_store)
        tree_view.set_rules_hint(True)

        i = 0
        for column in (_("Name"), _("Songs"), _("Owner"), _("Type")):
            if column == _("Name"):
                renderer_text = gtk.CellRendererText()
                new_column = gtk.TreeViewColumn(column, renderer_text, markup=0)
            else:
                new_column = guifunctions.create_column(column, i)
            new_column.set_reorderable(True)
            new_column.set_resizable(True)
            new_column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
            if column == _("Name"):
                new_column.set_fixed_width(200)
            elif column == _("Songs"):
                new_column.set_fixed_width(70)
            elif column == _("Owner"):
                new_column.set_fixed_width(90)
            elif column == _("Type"):
                new_column.set_fixed_width(60)
            tree_view.append_column(new_column)
            i += 1


        scrolled_window.add(tree_view)

        vbox.pack_start(scrolled_window, True, True, 5)

        text_entry = gtk.Entry()
        text_entry.set_text('')
        if type == 'Save':
            hbox = gtk.HBox()
            hbox.pack_start(gtk.Label(_("Playlist Name: ")), False, False, 1)
            hbox.pack_start(text_entry, False, False, 2)
            vbox.pack_start(hbox, False, False, 2)

        bottom_bar = gtk.HBox()


        remove = gtk.Button(stock=gtk.STOCK_DELETE)
        remove.connect("clicked", self.button_delete_playlist_clicked, tree_view.get_selection(), type)

        close = gtk.Button(stock=gtk.STOCK_CLOSE)
        close.connect("clicked", self.destroy_playlist)

        button = gtk.Button(stock=gtk.STOCK_SAVE)
        if type == 'Load':
            button = gtk.Button(stock=gtk.STOCK_OPEN)
        elif type == 'Export':
            button = gtk.Button(_("Export as M3U..."))
        button.connect("clicked", self.button_load_or_save_playlist_clicked, tree_view.get_selection(), text_entry, type)

        bottom_bar.pack_start(remove, False, False, 2)
        bottom_bar.pack_end(button, False, False, 2)
        bottom_bar.pack_end(close, False, False, 2)

        vbox.pack_start(bottom_bar, False, False, 1)

        self.playlist_select_window.add(vbox)

        self.update_playlist_select(type, playlist_list_store)

        self.playlist_select_window.show_all()

    def update_playlist_select(self, type, playlist_list_store):
        """Refresh the contents of the playlist list store"""
        playlist_list_store.clear()
        if type == "Load": # load playlists window
            # get playlists from Ampache
            ampache_playlists = self.ampache_conn.get_playlists()
            if ampache_playlists == None:
                ampache_playlists = []
            print ampache_playlists
            playlist_list_store.append(['<b> - Ampache Playlists - </b>', len(ampache_playlists), '----', '----', -1])
            if len(ampache_playlists) == 0:
                playlist_list_store.append(['<i>-(None)-</i>', 0, '', '', -1])
            else:
                for playlist in ampache_playlists:
                    playlist_list_store.append([ helperfunctions.convert_string_to_html(playlist['name']), playlist['items'], playlist['owner'], playlist['type'], playlist['id']])
            # get playlists stored locally
        local_playlists = dbfunctions.get_playlists(self.db_session)
        playlist_list_store.append(['<b> - Local Playlists - </b>', len(local_playlists), '----', '----', -1])
        if len(local_playlists) == 0:
            playlist_list_store.append(['<i>-(None)-</i>', 0, '', '', -1])
        else:
            for playlist in local_playlists:
                playlist_list_store.append([ helperfunctions.convert_string_to_html(playlist['name']), len(playlist['songs']), getpass.getuser(), 'Local', -2])


    def destroy_playlist(self, widget=None, data=None):
        """Close the playlist window."""
        self.playlist_select_window.destroy()
        self.playlist_select_window = None

    def show_plugins_window(self, *args):
        """The Plugins Window"""
        #################################
        # The Plugins Window
        #################################
        if hasattr(self, 'plugins_window'):
            if self.plugins_window != None:
                self.plugins_window.present()
                return True

        self.plugins_window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.plugins_window.set_transient_for(self.window)
        self.plugins_window.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        self.plugins_window.resize(490, 300)
        self.plugins_window.set_resizable(True)
        self.plugins_window.set_icon(self.images_pixbuf_viridian_simple)
        self.plugins_window.connect("delete_event", self.destroy_plugins_window)
        self.plugins_window.connect("destroy", self.destroy_plugins_window)
        self.plugins_window.set_title(_("Viridian Plugins"))

        vbox = gtk.VBox()
        vbox.set_border_width(10)

        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label(_("Select a plugin.")), False, False, 2)
        vbox.pack_start(hbox, False, False, 2)

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        list_store = gtk.ListStore(gobject.TYPE_BOOLEAN, str, str, str)
        treeview = gtk.TreeView(list_store)

        bool_cell_renderer = gtk.CellRendererToggle()
        bool_cell_renderer.set_property('activatable', True)
        bool_cell_renderer.connect('toggled', self.toggle_plugin, list_store)
        bool_col = gtk.TreeViewColumn(_("Enabled"), bool_cell_renderer, active=0)
        treeview.append_column(bool_col)

        renderer_text = gtk.CellRendererText()
        name_column = gtk.TreeViewColumn(_("Name"), renderer_text, text=1)
        treeview.append_column(name_column)

        renderer_text = gtk.CellRendererText()
        desc_column = gtk.TreeViewColumn(_("Description"), renderer_text, text=2)
        treeview.append_column(desc_column)

        # Check for new plugins since launch
        self.plugins = {}
        new_plugins_list = self.__find_plugins(PLUGINS_DIR)
        for plugin in new_plugins_list:
            imported_plugin = self.__import_plugin(plugin)
            if imported_plugin != None:
                self.plugins[plugin] = imported_plugin

        for name, plugin in self.plugins.iteritems():
            enabled = False
            if name in self.enabled_plugins:
                enabled = True
            try:
                title       = plugin.title
                description = plugin.description
                author      = plugin.author
                list_store.append((enabled, title, description, name))
            except:
                print _("Error: plugin '%s' could not be loaded because it is missing a title, description, and author instance variable") % (name)


        scrolled_window.add(treeview)

        vbox.pack_start(scrolled_window, True, True, 5)

        bottom_bar = gtk.HBox()

        close = gtk.Button(stock=gtk.STOCK_CLOSE)
        close.connect("clicked", self.destroy_plugins_window)

        bottom_bar.pack_end(close, False, False, 2)

        vbox.pack_start(bottom_bar, False, False, 1)

        self.plugins_window.add(vbox)

        self.plugins_window.show_all()


    def destroy_plugins_window(self, *args):
        """Close the playlist window."""
        self.plugins_window.destroy()
        self.plugins_window = None

    #######################################
    # Status Icon
    #######################################
    def status_icon_activate(self, icon=None):
        """Bring the window back up when the user clicks the sys tray icon."""
        self.main_gui_toggle_hidden()


    def status_icon_popup_menu(self, icon, button, activate_time):
        """Create a menu when the user right clicks the sys tray icon."""
        menu = gtk.Menu()

        show_window = gtk.MenuItem(_("Show Window"))
        show_window.connect('activate', self.status_icon_activate)
        menu.append(show_window)

        ### Display Song Info is song is playing ###
        if self.audio_engine.get_state() != "stopped" and self.audio_engine.get_state() != None:
            menu.append(gtk.SeparatorMenuItem())
            np = gtk.MenuItem(_("- Now Playing -"))
            if self.audio_engine.get_state() == "paused":
                np = gtk.MenuItem(_("- Now Playing (paused) -"))
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

    def toggle_shuffle_songs(self, widget, data=None):
        """Toggle repeat songs."""
        self.audio_engine.set_shuffle_songs(widget.get_active())
        self.db_session.variable_set('shuffle_songs', widget.get_active())

    def toggle_display_notifications(self, widget, data=None):
        """Toggle displaying notify OSD notifications."""
        self.display_notifications = widget.get_active()
        self.db_session.variable_set('display_notifications', widget.get_active())

    def toggle_automatically_update(self, widget, data=None):
        """Toggle automatically updating the local cache."""
        self.automatically_update = widget.get_active()
        self.db_session.variable_set('automatically_update', widget.get_active())

    def toggle_alternate_row_colors(self, widget, data=None):
        """Toggle set rulse hint for the given treeview column."""
        self.tree_view_dict[data].set_rules_hint(widget.get_active())
        self.db_session.variable_set(data, widget.get_active())

    def toggle_quit_when_window_closed(self, widget, data=None):
        """Toggle to decide if the program quits or keeps running when the main window is closed."""
        self.quit_when_window_closed = widget.get_active()
        self.db_session.variable_set('quit_when_window_closed', widget.get_active())

    def toggle_start_xml_rpc_server(self, widget, data=None):
        """Toggle whether to start the XML server when Viridian opes."""
        self.db_session.variable_set('enable_xmlrpc_server', widget.get_active())

    def toggle_plugin(self, widget, path, model):
        """Toggle a plugin being active"""
        plugin_name = model[path][3]

        going_to = not model[path][0]
        if going_to == True:
            self.enabled_plugins.append(plugin_name)
        else:
            self.enabled_plugins.remove(plugin_name)
        # save the new list
        self.db_session.variable_set('enabled_plugins', self.enabled_plugins)

        # this line will tick or untick the checkmark
        model[path][0] = not model[path][0]

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
    # Combo Boxes
    #######################################
    def playlist_mode_changed(self, combobox):
        model = combobox.get_model()
        index = combobox.get_active()
        self.playlist_mode = index
        self.db_session.variable_set('playlist_mode', self.playlist_mode)
        return True

    #######################################
    # Initial Authentication
    #######################################
    def login_and_get_artists(self, data=None):
        """Authenticate and populate the artists."""
        self.stop_all_threads()
        self.__clear_all_list_stores()
        self.update_statusbar(_("Authenticating..."))
        # get the user inforamiton
        ampache  = self.ampache_conn.url
        username = self.ampache_conn.username
        password = self.ampache_conn.password
        print "--- Attempting to login to Ampache ---"
        print "Ampache  = %s" % ampache
        print "Username = %s" % username
        print "Password = " + len(password) * '*'
        # set the credentials and try to login
        self.__successfully_authed = None
        ################ Thread to authenticate (so the GUI doesn't lock) ############
        thread.start_new_thread(self.__authenticate, (None,))
        while self.__successfully_authed == None:
            self.refresh_gui()
        self.go_to_ampache_menu_item.set_sensitive(True)
        ##############################################################################
        if self.__successfully_authed: # auth successful
            self.update_statusbar("Authentication Successful.")
            print "Authentication Successful!"
            print "Authentication = %s" % self.ampache_conn.auth_data['auth']
            print "Number of artists = %d" % self.ampache_conn.auth_data['artists']

            db_time      = int(self.db_session.variable_get('catalog_update', -1))
            ampache_time = int(self.ampache_conn.get_last_update_time())

            if data == "changed":
                db_time = ampache_time
                self.db_session.variable_set('catalog_update', db_time)

            self.catalog_up_to_date = False
            if db_time >= ampache_time and ampache_time != -1:
                self.catalog_up_to_date = True

            if not self.catalog_up_to_date:
                # not up to date
                if data == "First" and self.automatically_update: # first time opening, update auto
                    dbfunctions.clear_cached_catalog(self.db_session)
                    self.db_session.variable_set('catalog_update', ampache_time)
                    self.catalog_up_to_date = True
                elif data == True or data == "First": # open a popup
                    if self.create_catalog_updated_dialog(): # user pressed update
                        dbfunctions.clear_cached_catalog(self.db_session)
                        self.db_session.variable_set('catalog_update', ampache_time)
                        self.catalog_up_to_date = True
                elif data == None: # clear_cache_button pressed
                    self.db_session.variable_set('catalog_update', ampache_time)
                    self.catalog_up_to_date = True

                #else: #do nothing, pull from cache

            # load the artists window with, you guessed it, artists
            self.update_statusbar(_("Pulling Artists..."))
            self.check_and_populate_artists()
            artists = dbfunctions.get_artist_dict(self.db_session)
            model = self.artist_list_store
            model.append([_("<b>All Artists (%d)</b>" % len(artists)), -1, ''])
            for artist_id in artists:
                artist_name = artists[artist_id]['name']
                custom_name = artists[artist_id]['custom_name']
                model.append([helperfunctions.convert_string_to_html(artist_name), artist_id, custom_name])
            # now pull all the albums.. this should cut down on precache time
            self.update_statusbar(_("Pulling Albums..."))
            self.check_and_populate_albums()
            self.albums = dbfunctions.get_album_dict(self.db_session)
            self.update_statusbar(_("Ready."))
            return True
        else: # auth failed
            error = self.__successfully_authed
            if not error:
                error = _("Unknown error, possibly an incorrect URL specified, or the server is not responding.")
            self.update_statusbar(_("Authentication Failed."))
            print error
            self.create_dialog_alert("error", _("Error Authenticating\n\n") + error, True)

            return False


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
        self.check_and_populate_albums(self.artist_id)
        if self.artist_id == -1: # all artists
            albums = self.albums
        else:
            albums = dbfunctions.get_album_dict(self.db_session, self.artist_id)

        self.update_statusbar("Loading: " + self.artist_name.replace('<b>', '').replace('</b>', ''))
        model.append([_("<b>All Albums (%d)</b>") % (len(albums)), -1, -1, 0])
        for album in albums:
            album_name     = albums[album]['name']
            album_year     = albums[album]['year']
            precise_rating = albums[album]['precise_rating']
            album_id       = album
            #self.update_statusbar(_("Fetching Album: ") + album_name)
            album_string = album_name + ' (' + str(album_year) + ')'
            if album_year == 0:
                album_string = album_name
            model.append([helperfunctions.convert_string_to_html(album_string), album_id, album_year, precise_rating])
        self.update_statusbar(self.artist_name.replace('<b>', '').replace('</b>', ''))


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

        self.continue_load_songs = False

        self.album_name = album_name
        self.album_id   = album_id

        song_list_store = self.song_list_store
        song_list_store.clear()

        if album_id == -1: # all albums
            self.continue_load_songs = True
            list = []
            for album in model:
                list.append(album[1])
            for album_id in list:
                if album_id != -1:
                    if self.continue_load_songs == False:
                        return False
                    if self.__add_songs_to_list_store(album_id):
                        self.update_statusbar(_("Fetching Album id: ") + str(album_id))
            self.update_statusbar(album_name.replace('<b>', '').replace('</b>', '') + " - " + self.artist_name.replace('<b>', '').replace('</b>', ''))
        else: # single album
            if self.__add_songs_to_list_store(album_id):
                self.update_statusbar(album_name + " - " + self.artist_name.replace('<b>', '').replace('</b>', ''))

    #######################################
    # Selection Methods (Double Click)
    #######################################
    def albums_on_activated(self, widget, row, col):
        """The function that runs when the user double-clicks an album."""

        model = widget.get_model()

        album_name = model[row][0]
        album_id   = model[row][1]

        if self.playlist_mode == 0: # replace mode
            # get all songs in the current songs menu and play them
            list = []
            for song in self.song_list_store:
                list.append(song[6])

            print "Sending this list of songs to player", list
            self.audio_engine.play_from_list_of_songs(list)
        else: # add mode
            for song in self.song_list_store:
                self.audio_engine.insert_into_playlist(song[6])
            self.update_playlist_window()

    def songs_on_activated(self, widget, row, col):
        """The function that runs when the user double-clicks a song."""
        model = widget.get_model()

        song_title = model[row][1]
        song_id    = model[row][6]

        if self.playlist_mode == 0: # replace mode
            list = []
            for song in model:
                list.append(song[6])

            song_num = row[0]
            print "Sending this list of songs to player", list
            self.audio_engine.play_from_list_of_songs(list, song_num)
        else: # add mode
            self.audio_engine.insert_into_playlist(song_id)
            self.update_playlist_window()

    def playlist_on_activated(self, widget, row, col):
        """The function that runs when the user double-clicks a song in the playlist."""
        song_num = row[0]
        self.audio_engine.change_song(song_num)

    def downloads_on_activated(self, widget, row, col):
        """The function that runs when the user double-clicks a song in the downloads window."""
        model = widget.get_model()
        full_path = model[row][2]
        self.gnome_open(os.path.dirname(full_path))

    #######################################
    # Selection Methods (right-click)
    #######################################
    def foreach(self, model, path, iter, data):
        """Helper for multi-select."""
        list = data[0]
        column = data[1]
        list.append(model.get_value(iter, column))

    def playlist_on_right_click(self, treeview, event, data=None):
        """The user right-clicked the playlist."""
        if event.button == 3:
            # check to see if there is multiple selections
            list = []
            self.tree_view_dict['playlist'].get_selection().selected_foreach(self.foreach, [list, 2])
            x = int(event.x)
            y = int(event.y)
            pthinfo = treeview.get_path_at_pos(x, y)
            if len(list) > 1: # multiple selected
                if pthinfo != None:
                    path, col, cellx, celly = pthinfo
                    # create popup
                    song_id = treeview.get_model()[path][2]
                    m = gtk.Menu()
                    i = gtk.MenuItem(_("Remove From Playlist"))
                    i.connect('activate', self.remove_from_playlist, song_id, treeview, list)
                    m.append(i)
                    m.append(gtk.SeparatorMenuItem())
                    i = gtk.MenuItem(_("Download Songs"))
                    i.connect('activate', self.download_songs_clicked, list)
                    m.append(i)
                    m.show_all()
                    m.popup(None, None, None, event.button, event.time, None)
                return True
            else: # single selected
                if pthinfo != None:
                    path, col, cellx, celly = pthinfo
                    # create popup
                    song_id = treeview.get_model()[path][2]
                    m = gtk.Menu()
                    i = gtk.MenuItem(_("Remove From Playlist"))
                    i.connect('activate', self.remove_from_playlist, song_id, treeview)
                    m.append(i)
                    m.append(gtk.SeparatorMenuItem())
                    i = gtk.MenuItem(_("Download Song"))
                    i.connect('activate', self.download_song_clicked, song_id)
                    m.append(i)
                    i = gtk.MenuItem(_("Copy URL to Clipboard"))
                    i.connect('activate', lambda y: self.copy_song_url_to_clipboard(song_id))
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
                i = gtk.MenuItem(_("Open Song"))
                i.connect('activate', lambda _: self.gnome_open(full_path))
                m.append(i)
                i = gtk.MenuItem(_("Open Containing Folder"))
                i.connect('activate', lambda _: self.gnome_open(os.path.dirname(full_path)))
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
                i = gtk.MenuItem(_("Add Album to Playlist"))
                i.connect('activate', self.add_album_to_playlist)
                m.append(i)
                m.append(gtk.SeparatorMenuItem())
                i = gtk.MenuItem(_("Download Album"))
                i.connect('activate', self.download_album_clicked)
                m.append(i)
                m.show_all()
                m.popup(None, None, None, event.button, event.time, None)

    def songs_on_right_click(self, treeview, event, data=None):
        if event.button == 3:
            x = int(event.x)
            y = int(event.y)
            pthinfo = treeview.get_path_at_pos(x, y)
            # check to see if there is multiple selections
            list = []
            self.tree_view_dict['songs'].get_selection().selected_foreach(self.foreach, [list, 6])
            if len(list) > 1: # multiple selected
                if pthinfo != None:
                    path, col, cellx, celly = pthinfo
                    # create popup
                    m = gtk.Menu()
                    i = gtk.MenuItem(_("Add Songs to Playlist"))
                    i.connect('activate', self.add_songs_to_playlist, list)
                    m.append(i)
                    m.append(gtk.SeparatorMenuItem())
                    i = gtk.MenuItem(_("Download Songs"))
                    i.connect('activate', self.download_songs_clicked, list)
                    m.append(i)
                    m.show_all()
                    m.popup(None, None, None, event.button, event.time, None)
                return True
            else: # single song
                if pthinfo != None:
                    path, col, cellx, celly = pthinfo
                    # create popup
                    song_id = treeview.get_model()[path][6]
                    m = gtk.Menu()
                    i = gtk.MenuItem(_("Add Song to Playlist"))
                    i.connect('activate', self.add_song_to_playlist, song_id)
                    m.append(i)
                    m.append(gtk.SeparatorMenuItem())
                    i = gtk.MenuItem(_("Download Song"))
                    i.connect('activate', self.download_song_clicked, song_id)
                    m.append(i)
                    i = gtk.MenuItem(_("Copy URL to Clipboard"))
                    i.connect('activate', lambda y: self.copy_song_url_to_clipboard(song_id))
                    m.append(i)
                    m.show_all()
                    m.popup(None, None, None, event.button, event.time, None)

    #######################################
    # Drag and Drop
    #######################################
    def on_playlist_drag(self, widget, context, data=None):
        """When the user changes the order of the playlist."""
        list = []
        i = 0
        cur_song_num = None
        for song in self.playlist_list_store: # iterate the rows
            song_id = song[2]
            list.append(song_id)
            if song[0] is self.images_pixbuf_playing: # this row has a now playing icon
                cur_song_num = i
            i += 1
        self.audio_engine.set_playlist(list)
        if cur_song_num != None: # song is playing
            self.audio_engine.set_current_song(cur_song_num)

    #######################################
    # Misc Selection Methods
    #######################################
    def on_time_elapsed_slider_change(self, slider):
        """When the user moves the seek bar."""
        seek_time_secs = slider.get_value()
        human_readable = helperfunctions.convert_seconds_to_human_readable(seek_time_secs)
        gobject.idle_add(self.time_seek_label.set_text, human_readable)
        if self.audio_engine.seek(seek_time_secs):
            print "Seek to %s successful" % human_readable
        else:
            print "Seek to %s failed!" % human_readable
        return True

    def on_time_elapsed_slider_change_value(self, slider, data1=None, data2=None):
        """When the user drags the slide bar but doesn't commit yet"""
        seek_time_secs = slider.get_value()
        gobject.idle_add(self.time_seek_label.set_text, helperfunctions.convert_seconds_to_human_readable(seek_time_secs))

    def on_volume_slider_change(self, range, scroll, value):
        """Change the volume."""
        self.audio_engine.set_volume(value)

    #######################################
    # Button Clicked Methods
    #######################################
    def button_save_preferences_clicked(self, widget, data=None):
        """When the save button is pressed in the preferences"""
        window   = data
        url      = self.ampache_text_entry.get_text()
        username = self.username_text_entry.get_text()
        password = self.password_text_entry.get_text()

        # check to see if any of the fields have been edited, if so, reauth with new credentials
        try:
            if url == self.ampache_conn.url and username == self.ampache_conn.username and password == self.ampache_conn.password:
                window.destroy()
                return True # haven't changed
        except:
            pass

        # if the code makes it this far, the credentials have been changed
        self.stop_all_threads()
        self.audio_engine.clear_playlist()
        self.clear_album_art()
        dbfunctions.clear_cached_catalog(self.db_session)
        self.ampache_conn.set_credentials(username, password, url) # credentials saved
        if self.ampache_conn.has_credentials: # credentials are NOT blank
            self.db_session.variable_set('credentials_username', username)
            self.db_session.variable_set('credentials_password', password)
            self.db_session.variable_set('credentials_url', url)
            self.update_statusbar(_("Saved Credentials"))
            print _("Credentials Saved")
            self.destroy_settings(window)
            self.login_and_get_artists("changed")
        else:
            self.update_statusbar(_("Couldn't save credentials!"))
            print _("[Error] Couldn't save credentials!")
            return False
        return True

    def button_cancel_preferences_clicked(self, widget, data=None):
        """Destroy the preferences window."""
        window = data
        self.destroy_settings(window)

    def button_open_downloads_file_chooser_clicked(self, widget, data=None):
        """Open file chooser for the downloads directory."""
        dialog = gtk.FileChooserDialog(_("Choose Folder..."),
                        None,
                        gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
                        (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                        gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        dialog.set_current_folder(os.path.expanduser("~"))
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

    def button_play_pause_clicked(self, widget=None, data=None):
        """The play/pause has been clicked."""
        state = self.audio_engine.get_state()
        if state == "stopped" or state == None:
            return False
        elif state == "playing":
            self.audio_engine.pause()
            self.play_pause_image.set_from_pixbuf(self.images_pixbuf_play)
            return "paused"
            #self.set_tray_icon(None)
        else:
            if self.audio_engine.play():
                self.play_pause_image.set_from_pixbuf(self.images_pixbuf_pause)
                #self.set_tray_icon(self.album_art_image.get_pixbuf())
                return "playing"


    def button_prev_clicked(self, widget=None, data=None):
        """Previous Track."""
        time_nanoseconds = self.audio_engine.query_position()
        if time_nanoseconds != -1:
            time_seconds = time_nanoseconds / 1000 / 1000 / 1000
            if time_seconds <= 5: # go back if time is less than 5 seconds
                return self.audio_engine.prev_track()
            else: # restart the song
                return self.audio_engine.restart()

        # failsafe
        return self.audio_engine.prev_track()

    def button_next_clicked(self, widget=None, data=None):
        """Next Track."""
        return self.audio_engine.next_track()

    #############
    # Playlists
    #############
    def button_save_playlist_clicked(self, widget, data=None):
        """The save playlist button was clicked."""
        if not self.audio_engine.get_playlist():
            self.create_dialog_alert("error", _("Cannot save empty playlist."), True)
            print _("Cannot save empty playlist")
            return False
        self.show_playlist_select('Save')
        return False

    def button_load_playlist_clicked(self, widget, data=None):
        """The load playlist button was clicked."""
        self.show_playlist_select('Load')
        return False

    def button_export_playlist_clicked(self, widget, data=None):
        self.show_playlist_select('Export')
        return False


    def button_load_or_save_playlist_clicked(self, widget, selection, text, type):
        """When the user wants to load or save a playlist from Ampache."""
        playlist_list_store, iter = selection.get_selected()
        text = text.get_text()
        if iter == None:
            playlist_id   = -1
            playlist_name = ''
        else:
            playlist_id   = playlist_list_store[iter][4]
            playlist_name = playlist_list_store[iter][0]
        list = []
        if type == 'Load': # Load playlist
            if iter == None: # nothing selected
                return True
            if playlist_id == -1: # text place holders
                return True
            if playlist_id == -2: # Local Playlists
                list = dbfunctions.get_playlist(self.db_session, playlist_name)
            else:
                playlist = self.ampache_conn.get_playlist_songs(playlist_id)
                if not playlist:
                    print "Error with playlist %d" % playlist_id
                    self.create_dialog_alert("error", _("Problem loading playlist.  Playlist ID = %d" % playlist_id), True)
                    return True
                for song in playlist:
                    list.append(song['song_id'])
            self.load_playlist(list)
            self.destroy_playlist()
        elif type == 'Save': # Save playlist
            if not self.audio_engine.get_playlist(): # playlist is empty
                self.create_dialog_alert("error", _("Cannot save empty playlist."), True)
                print _("Cannot save empty playlist.")
                return False
            if text == '': # no name for list was specified
                self.create_dialog_alert("error", _("Invalid Name."), True)
                return False
            if dbfunctions.get_playlist(self.db_session, text): # playlist exists
                answer = self.create_dialog_ok_or_close(_("Overwrite Playlist?"), _("A playlist by the name '%s' already exists, overwrite?" % text))
                if answer != "ok":
                    return False
            dbfunctions.set_playlist(self.db_session, text, self.audio_engine.get_playlist())
            self.destroy_playlist()
        elif type == 'Export': # Export Playlist
            if iter == None: # nothing selected
                return True
            if playlist_id == -1: # placeholders
                return True
            if playlist_id != -2: # not local playlists
                self.create_dialog_alert("error", _("Only exporting of local playlists is supported."), True)
                return False
            else: # ready to export
                list = dbfunctions.get_playlist(self.db_session, playlist_name)
                if not list:
                    self.create_dialog_alert("error", _("Cannot export empty playlist."), True)
                    return False
                chooser = gtk.FileChooserDialog(title="Save as...",action=gtk.FILE_CHOOSER_ACTION_SAVE,
                    buttons=(gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,gtk.STOCK_SAVE,gtk.RESPONSE_OK))
                chooser.set_current_folder(os.path.expanduser("~"))
                response = chooser.run()
                if response == gtk.RESPONSE_OK:
                    filename = chooser.get_filename()
                    if os.path.isfile(filename):
                        self.create_dialog_alert("error", _("File already exists."), True)
                        chooser.destroy()
                        return False

                    f = open(filename, 'w')
                    f.write("Playlist '%s' export from Viridian - %s\n\n" % (playlist_name, time.strftime("%A, %B %d, %Y at %I:%M%p")))
                    for song_id in list:
                        f.write(helperfunctions.convert_html_to_string(self.ampache_conn.get_song_url(song_id).rpartition('.')[0]))
                        f.write("\n")
                    f.close()
                    print "Exported playlist to %s" % (filename)
                    self.create_dialog_alert("info", _("Playlist %s written to %s." % (playlist_name, filename)), True)

                chooser.destroy()
            self.destroy_playlist()


    def button_delete_playlist_clicked(self, widget, selection, type):
        playlist_list_store, iter = selection.get_selected()
        if iter == None:
            return False
        playlist_id   = playlist_list_store[iter][4]
        playlist_name = playlist_list_store[iter][0]
        if playlist_id == -2: # Local Playlists
            answer = self.create_dialog_ok_or_close(_("Delete Playlist?"), _("Are you sure you want to delete the playlist '%s'?" % playlist_name))
            if answer != "ok":
                return False
            dbfunctions.remove_playlist(self.db_session, playlist_name)
            self.update_playlist_select(type, playlist_list_store)
        elif playlist_id != -1: # Ampache playlists
            self.create_dialog_alert('error', _("Cannot delete playlists that are on the Ampache server from Viridian."))

    #############
    # Cache
    #############
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
        dbfunctions.clear_cached_catalog(self.db_session)
        #self.audio_engine.stop()
        self.db_session.variable_set('current_playlist', self.audio_engine.get_playlist())
        self.login_and_get_artists()
        self.button_clear_cache_locked = False

    def button_clear_album_art_clicked(self, widget=None, data=None):
        """Clear local album art."""
        self.clear_album_art()
        self.update_statusbar(_("Album Art Cleared"))

    def button_reset_everything_clicked(self, widget=None, data=None):
        """Reset everything."""
        answer = self.create_dialog_ok_or_close(_("Reset Viridian"), _("Are you sure you want to delete all personal information stored with Viridian?"))
        if answer == "ok":
            self.reset_everything()
            gtk.main_quit()

    def button_pre_cache_info_clicked(self, widget=None, data=None):
        """Pre-cache all album and song info."""
        if self.ampache_conn.is_authenticated() == False:
            self.create_dialog_alert("warn", _("Not Authenticated"), True)
            return False
        try: # check to see if this function is running
            if self.button_pre_cache_locked == True:
                print "Already Running"
                self.create_dialog_alert("info", _("Pre-Cache already in progress."))
                return False
        except:
            pass
        answer = self.create_dialog_ok_or_close(_("Pre-Cache"), _("This will cache all of the artist, album, and song information (not the songs themselves) locally to make Viridian respond faster.\n\nThis process can take a long time depending on the size of your catalog.  Proceed?"))
        if answer != "ok":
            return False
        self.button_pre_cache_locked = True
        gobject.idle_add(self.__button_pre_cache_info_clicked)
        #thread.start_new_thread(self.__button_pre_cache_info_clicked, (None,))

    def __button_pre_cache_info_clicked(self, widget=None, data=None):
        self.pre_cache_continue = True # this will be set to false if this function should stop
        try:
            start_time = int(time.time())
            artists = dbfunctions.get_artist_ids(self.db_session)
            i = 0
            num_artists = len(artists)
            for artist_id in artists:
                i += 1
                if self.pre_cache_continue == False:
                    self.button_pre_cache_locked = False
                    return False
                self.check_and_populate_albums(artist_id)
                self.update_statusbar(_("Pulling all albums from artists: %d/%d" % (i, num_artists) ))
                #gobject.idle_add(self.update_statusbar, 1, "Pulling all albums from artists: %d/%d" % (i, num_artists) )
            self.update_statusbar(_("Finished pulling albums"))

            albums = dbfunctions.get_album_ids(self.db_session)
            i = 0
            num_albums = len(albums)
            for album_id in albums:
                i += 1
                if self.pre_cache_continue == False:
                    self.button_pre_cache_locked = False
                    return False
                self.check_and_populate_songs(album_id)
                self.update_statusbar(_("Pulling all songs from albums: %d/%d" % (i, num_albums) ) )

            end_time = int(time.time())
            time_taken = end_time - start_time
            time_taken = helperfunctions.convert_seconds_to_human_readable(time_taken)

            self.update_statusbar(_("Finished Pre Cache -- Time Taken: " + str(time_taken)))
            print "Finished Pre Cache -- Time Taken: " + str(time_taken)
        except Exception, detail:
            print "Error with pre-cache!", detail
            self.update_statusbar(_("Error with pre-cache!"))
            self.button_pre_cache_locked = False
            self.create_dialog_alert("error", _("Error with pre-cache!\n\n"+str(detail) ) )
            return False
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
        i = gtk.MenuItem(_("Open Image"))
        i.connect('activate', lambda x: self.gnome_open(self.current_album_art_file))
        m.append(i)
        i = gtk.MenuItem(_("Refresh Album Art"))
        i.connect('activate', self.__re_fetch_album_art)
        m.append(i)
        m.show_all()
        m.popup(None, None, None, event.button, event.time, None)
        return False

    ##################
    # XML Server Buttons
    ##################
    def button_xml_server_clicked(self, widget, action, label, image, port):
        """Start, stop or restart the xml server."""
        if self.xml_server.is_running: # xml server is running
            if action == "start":
                return False
        else:
            if action == "stop":
                return False
        if port.get_text().isdigit():
            self.db_session.variable_set('xmlrpc_port', int(port.get_text()))
        if action == "start":
            self.start_xml_server()
        elif action == "stop":
            self.stop_xml_server()
        elif action == "restart":
            self.restart_xml_server()

        # update the gui
        if self.xml_server.is_running:
            image.set_from_stock(gtk.STOCK_YES,gtk.ICON_SIZE_SMALL_TOOLBAR)
            label.set_text(_("Running. (port %d)" % self.xml_server.port))
        else:
            image.set_from_stock(gtk.STOCK_NO,gtk.ICON_SIZE_SMALL_TOOLBAR)
            label.set_text(_("Not Running."))


    #######################################
    # Dialogs
    #######################################
    def create_dialog_alert(self, dialog_type, message, ok=False):
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
        md.set_title('Viridian')
        md.set_icon(self.images_pixbuf_viridian_simple)
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
        md.set_icon(self.images_pixbuf_viridian_simple)
        md.show_all()
        #md.set_title('Viridian')
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
        about.set_icon(self.images_pixbuf_viridian_simple)
        about.set_version(VERSION_NUMBER)
        about.set_copyright("(c) Dave Eddy <dave@daveeddy.com>")
        about.set_comments(_("Viridian is a front-end for an Ampache Server (see http://ampache.org)"))
        about.set_website("http://viridian.daveeddy.com")
        about.set_authors(["Author:", "Dave Eddy <dave@daveeddy.com>", "http://www.daveeddy.com", "", "AudioEngine by:", "Michael Zeller <link@conquerthesound.com>", "http://conquerthesound.com"])
        about.set_artists(["Skye Sawyer <skyelauren.s@gmail.com>", "http://www.skyeillustration.com", "", "Media Icons by:", "http://mysitemyway.com", "http://ampache.org"])
        try: # try to set the logo
            about.set_logo(self.images_pixbuf_viridian_app)
        except:
            pass
        license = ""
        try: # try to read the license, and just paste the link if it fails
            for line in open(os.path.join(SCRIPT_PATH, os.path.join('doc', 'bsd.txt'))):
                license += line
        except:
            license = "BSD 3-Clause <http://www.opensource.org/licenses/BSD-3-Clause>"
        about.set_license(license)
        about.run()
        about.destroy()

    def create_catalog_updated_dialog(self):
        """Create a dialog to tell the user the cache has been updated."""
        answer = self.create_dialog_ok_or_close(_("Ampache Catalog Updated"), _("The Ampache catalog on the server is newer than the locally cached catalog on this computer.\nWould you like to update the local catalog by clearing the local cache?\n\n(You can also do this at anytime by going to File -> Clear Local Cache)."))
        if answer == "ok":
            return True
        return False


    #######################################
    # Audio Engine Callback
    #######################################
    def audioengine_song_changed(self, song_id):
        """The function that gets called when the AudioEngine changes songs."""
        if song_id != None:
            if dbfunctions.song_has_info(self.db_session, song_id):
                self.current_song_info = dbfunctions.get_single_song_dict(self.db_session, song_id)
            else:
                self.current_song_info = self.ampache_conn.get_song_info(song_id)
        thread.start_new_thread(self.__audioengine_song_changed, (song_id,))

    def __audioengine_song_changed(self, song_id):
        """The function that gets called when the AudioEngine changes songs."""
        THREAD_LOCK_B.acquire()
        self.update_playlist_window()
        #self.refresh_gui()
        if song_id == None: # nothing playing
            self.current_song_info = None
            self.play_pause_image.set_from_pixbuf(self.images_pixbuf_play)
            self.set_tray_tooltip('Viridian')
            self.window.set_title("Viridian")
            self.set_tray_icon(None)
            THREAD_LOCK_B.release()
            return False
        self.play_pause_image.set_from_pixbuf(self.images_pixbuf_pause)

        print self.current_song_info # DEBUG

        song_time   = self.current_song_info['song_time']
        self.time_elapsed_slider.set_range(0, song_time)
        self.time_total_label.set_text(helperfunctions.convert_seconds_to_human_readable(song_time))

        song_title  = self.current_song_info['song_title']
        artist_name = self.current_song_info['artist_name']
        album_name  = self.current_song_info['album_name']

        song_title_html  = helperfunctions.convert_string_to_html(song_title)
        artist_name_html = helperfunctions.convert_string_to_html(artist_name)
        album_name_html  = helperfunctions.convert_string_to_html(album_name)

        ### Update EVERYTHING to say the current artist, album, and song
        # make font size smaller if the title is long
        length = len(song_title_html)
        if length > 40:
            self.current_song_label.set_markup('<span size="9000"><b>'+song_title_html+'</b></span>')
        elif length > 20:
            self.current_song_label.set_markup('<span size="11000"><b>'+song_title_html+'</b></span>')
        else:
            self.current_song_label.set_markup('<span size="13000"><b>'+song_title_html+'</b></span>')
        self.current_artist_label.set_markup( '<span size="10000">'+artist_name_html+'</span>' )
        self.current_album_label.set_markup(  '<span size="10000">'+album_name_html+'</span>'  )

        ### Update the statusbar and tray icon ###
        self.set_tray_tooltip("Viridian :: " + song_title + ' - ' + artist_name + ' - ' + album_name)
        self.window.set_title("Viridian :: " + song_title + ' - ' + artist_name + ' - ' + album_name)
        self.update_statusbar(song_title + ' - ' + artist_name + ' - ' + album_name)

        ### Get the album Art ###
        album_id   = self.current_song_info['album_id']
        if not os.path.exists(ALBUM_ART_DIR):
            os.mkdir(ALBUM_ART_DIR)
        self.current_album_art_file = os.path.join(ALBUM_ART_DIR,  str(album_id))
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
        image_pixbuf = guifunctions.create_image_pixbuf(self.current_album_art_file, ALBUM_ART_SIZE)
        self.album_art_image.set_from_pixbuf(image_pixbuf)
        self.set_tray_icon(image_pixbuf)

        self.refresh_gui()

        ### Send notifications OSD ###
        self.notification(_("Now Playing"), song_title + ' - ' + artist_name + ' - ' + album_name, self.current_album_art_file)
        # rating stars
        stars = self.current_song_info['precise_rating']
        i = 0
        while i < 5:
            if stars > i:
                self.rating_stars_list[i].set_from_pixbuf(self.images_pixbuf_gold_star)
            else:
                self.rating_stars_list[i].set_from_pixbuf(self.images_pixbuf_gray_star)
            i += 1

        ### Alert the plugins! ###
        self._alert_plugins_of_song_change()
        THREAD_LOCK_B.release()


    def _alert_plugins_of_song_change(self, *args):
        """Fire off enabled plugins because the song has changed"""
        for name, plugin in self.plugins.iteritems():
            if name in self.enabled_plugins: # only fire off enabled plugins
                try:
                    print "Alerting plugin '%s' of song change" % (name)
                    plugin.on_song_change(self.current_song_info)
                    print "Plugin exited successfully"
                except:
                    print "Error with plugin '%s':\n+++++++ BEGIN STACK TRACE ++++++++" % (name)
                    traceback.print_exc() # DEBUG
                    print "++++++++ END STACK TRACE +++++++++"
                    pass

    def audioengine_error_callback(self, error_message):
        """Display the gstreamer error in the notification label."""
        self.update_statusbar(_("An error has occured."))
        self.create_dialog_alert('warn', _("""GStreamer has encountered an error, this is most likely caused by:
- gstreamer-plugins not being installed.
- Ampache not transcoding the file correctly.
- A lost or dropped connection to the server.

Message from GStreamer:
%s""" % error_message))



    #######################################
    # Convenience Functions
    #######################################

    ############
    # check database for info
    ############
    def check_and_populate_artists(self):
        """Returns an artist list by either grabbing from the DB or from Ampache."""
        if self.db_session.table_is_empty('artists'):
            artists = self.ampache_conn.get_artists()
            if artists == None:
                return False
            list = []
            for artist in artists:
                custom_artist_name = re.sub('^the |^a ', '', artist['artist_name'].lower())
                list.append([artist['artist_id'], artist['artist_name'], custom_artist_name])
            dbfunctions.populate_artists_table(self.db_session, list)

    def check_and_populate_albums(self, artist_id=-1):
        if artist_id == -1:
            if self.db_session.table_is_empty('albums'):
                albums = self.ampache_conn.get_albums()
                if albums == None:
                    return False
                list = []
                for album in albums:
                    list.append([album['artist_id'], album['album_id'], album['album_name'], album['album_year'], album['precise_rating']])
                dbfunctions.populate_full_albums_table(self.db_session, list)
        else:
            if dbfunctions.table_is_empty(self.db_session, 'albums', artist_id):
                albums = self.ampache_conn.get_albums_by_artist(artist_id)
                if albums == None:
                    return False
                list = []
                for album in albums:
                    list.append([artist_id, album['album_id'], album['album_name'], album['album_year'] , album['precise_rating']])
                dbfunctions.populate_albums_table(self.db_session, artist_id, list)

    def check_and_populate_songs(self, album_id):
        if dbfunctions.table_is_empty(self.db_session, 'songs', album_id):
            songs = self.ampache_conn.get_songs_by_album(album_id)
            if songs == None:
                return False
            list = []
            for song in songs:
                list.append([album_id, song['song_id'], song['song_title'], song['song_track'], song['song_time'], song['song_size'], song['artist_name'], song['album_name']])
            dbfunctions.populate_songs_table(self.db_session, album_id, list)


    ################
    # Random Helpers
    ################
    def gnome_open(self, uri):
        """Open with gnome-open."""
        if uri:
            os.popen("gnome-open '%s' &" % (uri))
        else:
            self.create_dialog_alert("warn", _("The file/URL specified is invalid."), True)

    def update_statusbar(self, text):
        """Update the status bar and run pending main_iteration() events."""
        try: # try to pop off any text already on the bar
            self.statusbar.pop(0)
        except:
            pass
        self.statusbar.push(0, text)
        self.refresh_gui()

    def notification(self, title, message=None, image=None):
        """Display OSD notifications if the user wants them and it's installed."""
        if PYNOTIFY_INSTALLED and self.display_notifications:
            if not message:
                message = title
                title = 'Viridian'
            if not image:
                image = IMAGES_DIR + 'ViridianApp.png'
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
                self.tray_icon.set_from_pixbuf(self.images_pixbuf_viridian_app)
            else:
                self.tray_icon.set_from_pixbuf(pixbuf)
            return True
        return False


    def stop_all_threads(self):
        """Stops all running threads."""
        self.pre_cache_continue  = False
        self.continue_load_songs = False

    def refresh_gui(self):
        """Refresh the GUI by calling gtk.main_iteration(). """
        while gtk.events_pending():
            gtk.main_iteration()

    def copy_text_to_clipboard(self, text):
        """Copies the content of 'text' to the clipboard"""
        c = gtk.Clipboard()
        c.set_text(text)

    def copy_song_url_to_clipboard(self, song_id):
        """Copies the song_id's URL to the clipboard"""
        self.copy_text_to_clipboard(self.ampache_conn.get_song_url(song_id))

    ####################
    # Playlist Functions
    ####################
    def update_playlist_window(self):
        """Updates the playlist window with the current playing songs."""
        gobject.idle_add(self.__update_playlist_window)

    def __update_playlist_window(self):
        cur_playlist = self.audio_engine.get_playlist()
        cur_song_num = self.audio_engine.get_current_song()
        list = []
        i = 0
        for song_id in cur_playlist:
            cur_song = {}
            if dbfunctions.song_has_info(self.db_session, song_id):
                cur_song = dbfunctions.get_playlist_song_dict(self.db_session, song_id)
            else:
                cur_song = self.ampache_conn.get_song_info(song_id)
            cur_string = cur_song['song_title'] + ' - ' + cur_song['artist_name'] + ' - ' + cur_song['album_name']
            cur_string = helperfunctions.convert_string_to_html(cur_string)
            now_playing = self.images_pixbuf_empty
            if i == cur_song_num:
                now_playing = self.images_pixbuf_playing
                cur_string = '<b>' + cur_string + '</b>'
            list.append([now_playing, cur_string, song_id])
            i += 1
            self.refresh_gui()
        self.playlist_list_store.clear()
        for string in list:
            self.playlist_list_store.append(string)
        return False

    def load_playlist(self, list):
        """Takes a list of song_ids and loads it into the audio engine."""
        self.audio_engine.clear_playlist()
        self.audio_engine.set_playlist(list)
        self.update_statusbar(_('Loading Playlist...'))
        i = 1
        print list
        for song in list:
            self.update_statusbar(_('Querying for song %d/%d in playlist') % (i, len(list)))
            if not dbfunctions.song_has_info(self.db_session, song):
                song = self.ampache_conn.get_song_info(song)
                self.check_and_populate_albums(song['artist_id'])
                self.check_and_populate_songs( song['album_id'])
            i += 1
        self.update_playlist_window()
        self.update_statusbar(_('Playlist loaded'))

    def add_album_to_playlist(self, widget):
        """Adds every song in the visible list store and adds it to the playlist."""
        for song in self.song_list_store:
            self.audio_engine.insert_into_playlist(song[6])
        self.update_playlist_window()
        return True

    def add_songs_to_playlist(self, widget, list):
        for song_id in list:
            self.add_song_to_playlist(widget, song_id)

    def add_song_to_playlist(self, widget, song_id):
        """Takes a song_id and adds it to the playlist."""
        self.audio_engine.insert_into_playlist(song_id)
        self.update_playlist_window()
        return True


    def remove_from_playlist(self, widget, song_id, treeview, list=None):
        """Remove a song from the current playlist."""
        if list != None:
            for song_id in list:
                self.remove_from_playlist(widget, song_id, treeview, None)
                #print self.audio_engine.get_current_song()
            return True
        else:
            if self.audio_engine.remove_from_playlist(song_id):
                self.update_playlist_window()
                return True
        return False

    ##################
    # XML Server
    ##################
    def start_xml_server(self):
        """Start the XML Server."""
        self.restart_xml_server()

    def restart_xml_server(self):
        """Restart the XML server."""
        self.stop_xml_server()
        time.sleep(1)
        xmlrpc_port = self.db_session.variable_get('xmlrpc_port', XML_RPC_PORT)
        self.current_xmlrpc_port = xmlrpc_port
        self.xml_server = XMLServer('', xmlrpc_port)

        ### Load the functions ###
        self.xml_server.register_function(self.button_next_clicked, 'next')
        self.xml_server.register_function(self.button_prev_clicked, 'prev')
        self.xml_server.register_function(self.button_play_pause_clicked, 'play_pause')
        self.xml_server.register_function(self.increment_volume, 'volume_up')
        self.xml_server.register_function(self.decrement_volume, 'volume_down')
        self.xml_server.register_function(self.set_volume, 'set_volume')
        self.xml_server.register_function(self.get_current_song, 'get_current_song')
        self.xml_server.register_function(self.audio_engine.get_state, 'get_state')
        self.xml_server.register_function(self.audio_engine.get_volume, 'get_volume')
        #self.xml_server.register_function(lambda : self.ampache_conn.get_album_art(self.current_song_info['album_id']), 'get_album_art')
        self.xml_server.serve_forever()

    def stop_xml_server(self):
        """Stop the XML Server."""
        try: self.xml_server.shutdown()
        except: pass

    ###################
    # Func for XML
    ###################
    def get_current_song(self, *args):
        """Get the current song info."""
        return self.current_song_info


    ###################
    # Volume modifiers
    ###################
    def increment_volume(self, *args):
        """Increment the volume by 5%."""
        cur_vol = self.audio_engine.get_volume()
        vol = cur_vol + 5
        return self.set_volume(vol)

    def decrement_volume(self, *args):
        """Decrement the volume by 5%."""
        cur_vol = self.audio_engine.get_volume()
        vol = cur_vol - 5
        return self.set_volume(vol)

    def set_volume(self, vol, *args):
        """Set the volume, assumes the value is 0<vol<100."""
        if vol >= 100:
            vol = 100
        elif vol <= 0:
            vol = 0
        self.volume_slider.set_value(vol)
        self.audio_engine.set_volume(vol)
        return self.audio_engine.get_volume()

    #######################################
    # Download Songs / Albums
    #######################################
    def download_songs_clicked(self, widget, list):
        """The user is downloading multiple songs from the playlist."""
        if not os.path.exists(self.downloads_directory):
            self.create_dialog_alert("warn", _("The folder %s does not exist.  You can change the folder in Preferences.") % (self.downloads_directory), True)
            return False
        if self.show_downloads_checkbox.active == False:
            self.side_panel.show()
            self.downloads_window.show()
            self.show_downloads_checkbox.set_active(True)
        for song_id in list:
            self.download_song_clicked(widget, song_id, False)

    def download_album_clicked(self, widget):
        """The user cliked download album."""
        # check to see if the downloads directory exists
        if not os.path.exists(self.downloads_directory):
            self.create_dialog_alert("warn", _("The folder %s does not exist.  You can change the folder in Preferences.") % (self.downloads_directory), True)
            return False
        if self.show_downloads_checkbox.active == False:
            self.side_panel.show()
            self.downloads_window.show()
            self.show_downloads_checkbox.set_active(True)
        for song in self.song_list_store:
            self.download_song_clicked(widget, song[6], False)

    def download_song_clicked(self, widget, song_id, show_panel=True):
        """The user clicked download song."""
        # check to see if the downloads directory exists
        if not os.path.exists(self.downloads_directory):
            self.create_dialog_alert("warn", _("The folder %s does not exist.  You can change the folder in Preferences.") % (self.downloads_directory), True)
            return False
        if show_panel and self.show_downloads_checkbox.active == False:
            self.side_panel.show()
            self.downloads_window.show()
            self.show_downloads_checkbox.set_active(True)
        song_url = self.ampache_conn.get_song_url(song_id)
        m = re.search('name=.*\.[a-zA-Z0-9]+', song_url)
        song_string = helperfunctions.convert_html_to_string(m.group(0).replace('name=/',''))
        full_file = os.path.join(self.downloads_directory, song_string)
        self.downloads_list_store.append([song_string, 0, full_file])
        iter1 = self.downloads_list_store.get_iter(len(self.downloads_list_store) - 1)
        thread.start_new_thread(self.download_song, (song_url, full_file, iter1))

    def download_song(self, url, dst, iter1):
        THREAD_LOCK.acquire()
        print "get url '%s' to '%s'" % (url, dst)
        urllib.urlretrieve(url, dst,
                lambda nb, bs, fs, url=url: self._reporthook(nb,bs,fs,url,iter1))
        self.notification(_("Download Complete"), os.path.basename(url).replace('%20',' ').replace('%27', "'"))
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
    # Resets
    #######################################
    def clear_album_art(self):
        """Clear local album art."""
        if os.path.exists(ALBUM_ART_DIR):
            print "+++ Checking for album art +++"
            for root, dirs, files in os.walk(ALBUM_ART_DIR):
                for name in files:
                    print "Deleting ", os.path.join(root, name)
                    os.remove(os.path.join(root, name))

    def reset_everything(self):
        """Delete all private/personal data from the users system."""
        self.stop_all_threads()
        try:
            shutil.rmtree(VIRIDIAN_DIR)
            os.rmdir(VIRIDIAN_DIR)
        except:
            pass


    #######################################
    # Threads
    #######################################
    def query_position(self, data=None):
        """Thread that updates the label and the seek/slider."""
        self.time_seek_label.set_text(" ")
        new_time_nanoseconds = self.audio_engine.query_position()
        if new_time_nanoseconds != -1:
            new_time_seconds = new_time_nanoseconds / 1000 / 1000 / 1000
            new_time_human_readable = helperfunctions.convert_seconds_to_human_readable(new_time_seconds)
            for signal in self.time_elapsed_signals:
                self.time_elapsed_slider.handler_block(signal)
            self.time_elapsed_slider.set_value(new_time_seconds)
            for signal in self.time_elapsed_signals:
                self.time_elapsed_slider.handler_unblock(signal)
            self.time_elapsed_label.set_text(new_time_human_readable)
        return True

    def keep_session_active(self, data=None):
        """Thread to keep the session active when a song is paused (DOESN'T WORK YET)."""
        if self.audio_engine.get_state() == 'paused':
            self.ampache_conn.ping()
        return True


    #######################################
    # Private Methods
    #######################################

    #################
    # Internal Helper Functions
    #################
    def __authenticate(self, data=None):
        self.__successfully_authed = self.ampache_conn.authenticate()
        return True

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
        self.update_statusbar(_("Re-Fetching album art..."))
        if not os.path.exists(ALBUM_ART_DIR):
            os.mkdir(ALBUM_ART_DIR)
        try: # attempt to get the current playing songs album art
            album_id   = self.current_song_info['album_id']
            art_file   = os.path.join(ALBUM_ART_DIR, str(album_id))
            album_art  = self.ampache_conn.get_album_art(album_id)
            response   = urllib2.urlopen(album_art)
            f = open(art_file, 'w')
            f.write(response.read())
            f.close()
        except: # cache was cleared or something and it fails...
            self.update_statusbar(_("Re-Fetching album art... Failed!"))
            print "Failed!"
            self.button_album_art_locked = False
            return False
        image_pixbuf = guifunctions.create_image_pixbuf(art_file, ALBUM_ART_SIZE)
        self.album_art_image.set_from_pixbuf(image_pixbuf)
        self.set_tray_icon(image_pixbuf)
        print "Done!"
        self.update_statusbar(_("Re-Fetching album art... Success!"))
        self.button_album_art_locked = False
        return True

    def __add_songs_to_list_store(self, album_id):
        """Takes an album_id, and adds all of that albums songs to the GUI."""
        self.check_and_populate_songs(album_id)
        songs = dbfunctions.get_song_dict(self.db_session, album_id)
        model = self.song_list_store

        if not songs:
            print "Error pulling ", album_id
            self.update_statusbar(_("Error with album -- Check Ampache -- Album ID = %d" % album_id))
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
            song_size = helperfunctions.convert_filesize_to_human_readable(float(song_size))

            model.append([song_track, song_title, artist_name, album_name, song_time, song_size, song_id])
        return True

    def __find_plugins(self, plugin_dir):
        """ Taken From http://www.luckydonkey.com/2008/01/02/python-style-plugins-made-easy/ """
        plugins_list = []
        for root, dirs, files in os.walk(plugin_dir):
            for name in files:
                if name.endswith(".py") and not name.startswith("__"):
                    plugins_list.append(name.rsplit('.', 1)[0])
        return plugins_list

    def __import_plugin(self, plugin_name):
        """Import the given plugin"""
        sys.path.append(PLUGINS_DIR)
        try:
            module = __import__(plugin_name)
            plugin = module.__init__()
        except:
            plugin = None
        sys.path.remove(PLUGINS_DIR)
        return plugin


