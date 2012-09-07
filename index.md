---
layout: default
---

Viridan
=======

<img src="/static/img/ViridianApp.png" style="float: right;" />

> Viridian is an Ampache Client that displays all of your media from your Ampache
> server in a simple and convenient way that makes choosing and streaming music
> an easy task.

Some of the highlighted features of Viridian:

- Create and save custom playlists in Viridian
- Export playlists created in Viridian to be imported into Ampache
- Download songs/albums from Ampache directly from Viridian
- Viridian caches and displays album art from Ampache in Viridian
- Notify osd messages when a song changes or a song finishes downloading
- Silent re-authentications to Ampache (if your session expires for whatever reason)
- Close Viridian and have it continue running as a status icon
- Seek/scrub songs being streamed
- XMLRPC server for communicating with Viridian
- Open source.  Feel confident in the code you execute.

---

- [Screenshots](#screenshots)
- [Download](#download)
- [License](#license)

Screenshots
-----------

### Load and Save playlists with Viridian

![viridian](/static/img/Viridian-Playlist.png)

### Viridian

![viridian](/static/img/viridian_alone.png)

### Set Viridian to get the newest changes from Ampache

![viridian](/static/img/viridian_catalog_settings.png)

### Download songs from Viridian

![viridian](/static/img/viridian_download_songs.png)

### Viridian tray icon

![viridian](/static/img/viridian_icon.png)

### Control Viridian from the status icon

![viridian](/static/img/viridian_icon_settings.png)

### Open downloads from Viridian

![viridian](/static/img/viridian_open_downloads.png)

### Open album art with Viridian

![viridian](/static/img/viridian_open_image.png)

### OSD Notify with Viridian

![viridian](/static/img/viridian_osd.png)

Download
--------

#### Ubuntu 11.04 (or higher)

    sudo aptitude install viridian

#### Other

Check below for links to the latest releases

### Latest Release

Version 1.2-Release (1/7/2010):

[https://launchpad.net/viridianplayer/trunk/1.2-release](https://launchpad.net/viridianplayer/trunk/1.2-release)

Note: Viridian is for Linux/Unix only. It might be possible to run it on
Windows/Mac if you can get python/pygtk running on them.

Older versions can be downloaded from the launchpad project site on Launchpad.

### Dependencies

Viridian depends on gstreamer to stream the music from the server.  This means
that it relies on gstreamer to have the proper codecs to understand how to play
each file Ampache might have.  If you are on a fresh install of Ubuntu, you
will need to download gstreamer plugins for Viridian to work as expected.
Viridian was written and tested on Python 2.6.

#### Ubuntu 10.10

Install the mp3 extras when you install the OS, or find them in the software center.

#### Ubuntu 10.04

1. Go to Applications -> Ubuntu Software Center
2. Search for `gstreamer`
3. Install `gstreamer extra plugins`
4. Install `GStreamer plugins for aac, xvid, mpeg2, faad`
   (optional: do this if your music file types vary, and may include iTunes m4a or aac files)

License
-------

BSD 3-clause license
