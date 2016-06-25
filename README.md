# Usage
```
usage: earthporn.py [-h] [--count COUNT] [--dest DEST] [--keepcount KEEPCOUNT]
                    [--resolution RESOLUTION]

Download images from http://www.reddit.com/r/earthporn

optional arguments:
  -h, --help            show this help message and exit
  --count COUNT, -c COUNT
                        number of images (max = 100)
  --dest DEST, -d DEST  destination directory
  --keepcount KEEPCOUNT, -k KEEPCOUNT
                        number of images to keep in the directory (> count)
  --resolution RESOLUTION, -r RESOLUTION
                        resolution of the display, to filter out images that
                        do not look good
```

Or using config files (see below).

The XML file is a scheduled task for windows 10 that you can import
manually or by running the `install.bat` script.

There are two yaml config files that you can customize.

In `earthporn.yaml`, the `dest` property is the directory to which the
files will be downloaded. You can set that as the source of your 
wallpaper slideshow in the Windows 10 settings, and you'll have the
top `count` images of /r/earthporn downloaded periodically (with maximum
of `keepcount` images at once in the `dest` directory.

In `logging.yaml`, you can configure the logging if you want to see what
is happening or why some pictures are showing up and not others.
