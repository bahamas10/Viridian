#!/usr/bin/env python
	
# example radiobuttons.py

import pygtk
pygtk.require('2.0')
import gtk

class RadioButtons:
	def callback(self, widget, data=None, cb=None):
		if widget.get_active():
	  		if data == "disabled":
				cb.set_active(False)
				cb.set_sensitive(False)
			elif data == "unified":
				cb.set_sensitive(True)
			elif data == "tray":
				cb.set_sensitive(True)


	def close_application(self, widget, event, data=None):
		gtk.main_quit()
		return False

	def __init__(self):
		self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
  
		self.window.connect("delete_event", self.close_application)

		self.window.set_title("radio buttons")
		self.window.set_border_width(0)

		box1 = gtk.VBox(False, 0)
		self.window.add(box1)
		box1.show()

		box2 = gtk.VBox(False, 10)
		box2.set_border_width(10)
		box1.pack_start(box2, True, True, 0)
		box2.show()

		cb = gtk.CheckButton("Quit Viridian when window is closed")

		button = gtk.RadioButton(None, "Standard Tray Icon")
		button.connect("toggled", self.callback, "tray", cb)
		box2.pack_start(button, True, True, 0)
		button.show()

		button = gtk.RadioButton(button, "Unified Sound Icon ( >= Ubuntu 10.10 )")
		button.connect("toggled", self.callback, "unified", cb)
		button.set_active(True)
		box2.pack_start(button, True, True, 0)
		button.show()

		button = gtk.RadioButton(button, "Disabled")
		button.connect("toggled", self.callback, "disabled", cb)
		box2.pack_start(button, True, True, 0)
		button.show()

		box2.pack_start(cb, True, True, 0)
		cb.show()

		separator = gtk.HSeparator()
		box1.pack_start(separator, False, True, 0)
		separator.show()

		box2 = gtk.VBox(False, 10)
		box2.set_border_width(10)
		box1.pack_start(box2, False, True, 0)
		box2.show()

		button = gtk.Button("close")
		button.connect_object("clicked", self.close_application, self.window,
							  None)
		box2.pack_start(button, True, True, 0)
		button.set_flags(gtk.CAN_DEFAULT)
		button.grab_default()
		button.show()
		self.window.show()

def main():
	gtk.main()
	return 0		

if __name__ == "__main__":
	RadioButtons()
	main()
