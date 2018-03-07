#!/usr/bin/env python3
# coding=utf-8

import argparse
import logging.config
import os
import re
import string
import sys
from collections import namedtuple
from pathlib import Path

import requests
import yaml

logger = logging.getLogger('earthporn')

Resolution = namedtuple('Resolution', 'w,h')

JSON_URL = 'https://www.reddit.com/r/earthporn/hot.json?limit=100'
HEADERS = {'User-Agent': 'script by /u/blissbero'}
VALID_CHARS = frozenset("-_.()%s%s" % (string.ascii_letters, string.digits))
PREFIX = PREFIX_GLOB = 'DOWN-'
SUFFIX = SUFFIX_GLOB = '.jpg'
TARGET_RESOLUTION = Resolution(1920, 1080)
ACCEPTABLE_DIFFERENCE = 90
MAX_FILENAME_LENGTH = 30

# From Reddit Enhancement Suite
FLICKR_RE = re.compile(
    '^https?://(?:\w+\.)?flickr\.com/(?:.+)/(\d{10,})(?:/|$)'
)


def safe_filename(title):
    return ''.join(
        c for c in title.replace(' ', '_') if c in VALID_CHARS).strip(' _.-()')


def get_filepath(destdir, title):
    filename = os.path.join(destdir, PREFIX + safe_filename(title)) + SUFFIX
    rpath = Path(filename)
    rdir = Path(destdir)
    assert rdir == rpath.parent
    return rpath


def keep_image(title, res_):
    w, h = res_.w, res_.h
    tw, th = TARGET_RESOLUTION.w, TARGET_RESOLUTION.h

    if tw - w > 4 * ACCEPTABLE_DIFFERENCE:
        # Smaller width, landscape
        logger.debug('{%22r} Rejecting: width (%d) < target (%d) ',
                     title, w, tw)
        return False
    elif th - h > 4 * ACCEPTABLE_DIFFERENCE:
        # Smaller height, landscape
        logger.debug('{%22r} Rejecting: height (%d) < target (%d) ',
                     title, h, th)
        return False
    elif w >= tw:
        # Greater width if landscape
        logger.debug('{%22r} Keeping: width (%d) > target (%d) ', title, w, tw)
        return True

    if h > w:
        # Portrait
        # ~ # Reject
        # ~ return False
        # Flip the coordinates
        w, h = h, w
        tw, th = th, tw
        logger.debug('{%22r} Portrait image -> (%dx%d)', title, w, h)

    if tw * th - w * h < ACCEPTABLE_DIFFERENCE ** 2:
        # Greater width, landscape, overall higher resolution
        logger.debug(
            '{%22r} Rejecting: resolution (%dx%d = %d) > target (%dx%d = %d) ',
            title, w, h, w * h, tw, th, tw * th)
        return False

    if tw / th - w / h > ACCEPTABLE_DIFFERENCE / 200.0:
        logger.debug(
            '{%22r} Rejecting: aspect ratio (%dx%d = %.3f) > '
            'target (%dx%d = %.3f) ',
            title, w, h, w / h, tw, th, tw / th)
        return False

    logger.debug('{%22r} Keeping: seems fine (%dx%d)', title, w, h)
    return True


def filtered_images(children, count):
    total = 0
    for thread in children:
        if total >= count:
            break
        if thread['data']['stickied']:
            continue

        try:
            if thread['data']['domain'] == 'flickr.com' and FLICKR_RE.match(
                    thread['data']['url']):
                embed = requests.get('https://noembed.com/embed', params={
                    'url': thread['data']['url']
                }).json()
                source_image = {
                    'url': embed['media_url'],
                    'width': int(embed['width']),
                    'height': int(embed['height']),
                }
            else:
                source_image = thread['data']['preview']['images'][0]['source']
            res_ = Resolution(source_image['width'], source_image['height'])
        except (KeyError, IndexError):
            # No image
            continue
        except (ValueError, TypeError):
            # Probably the integers of width and height
            continue
        else:
            if not keep_image(thread['data']['title'], res_):
                continue
        yield thread, source_image
        total += 1


def load_images(count):
    """
    Download images from /r/earthporn

    :param count: number of images to download from subreddit
    :returns: dict where keys are ids of threads and values are raw data
    """
    logger.info("Getting url %r with count %d", JSON_URL, count)
    earthporn_json = requests.get(JSON_URL, headers=HEADERS).json()

    for thread, source_image in filtered_images(
            earthporn_json['data']['children'], count):
        title = thread['data']['title']
        if len(title) > MAX_FILENAME_LENGTH:
            title = title[:MAX_FILENAME_LENGTH // 2] + '...' + \
                    title[-MAX_FILENAME_LENGTH // 2:]
        title = '{}_{}'.format(thread['data']['id'], title)
        yield (title, source_image['url'])


def save_images(images, destdir):
    """
    Save images to directory
    :param images: dict where keys are titles and values are raw image data
    :param destdir: directory for images
    """

    if not os.path.isdir(destdir):
        os.makedirs(destdir)

    for title, data in images:
        save_image(title, data, destdir)


def save_image(title, url, destdir):
    path = get_filepath(destdir, title)
    logger.info("Saving image %r to %s", title, path)
    if path.exists():
        logger.debug("Already saved. Skipping...")
        path.touch()
        return
    data = requests.get(url, stream=True).raw.read()
    with path.open('wb') as img_file:
        img_file.write(data)


def keep_at_most(dest, count):
    rdir = Path(dest)
    for f_ in sorted(rdir.glob(PREFIX_GLOB + '*' + SUFFIX_GLOB),
                     key=lambda p: p.stat().st_mtime, reverse=True)[count:]:
        logger.info("Deleting image %s", f_)
        try:
            f_.unlink()
        except OSError:
            logger.exception("Failed to delete %s", f_)


def main(count, dest, keepcount):
    save_images(load_images(count), dest)
    if keepcount and keepcount > 0 and keepcount > count:
        keep_at_most(dest, keepcount)


if __name__ == '__main__':
    # Configure logging
    with open('logging.yaml', 'r') as f:
        logging.config.dictConfig(yaml.load(f))

    # Load configuration file
    config = {
        'count': 10,
        'dest': '~/Pictures',
        'keepcount': -1,
        'resolution': '1920x1080',
    }
    try:
        with open('earthporn.yaml', 'r') as f:
            config = yaml.load(f)
    except FileNotFoundError:
        logging.warning('Config file earthporn.yaml not found')

    parser = argparse.ArgumentParser(
        description='Download images from http://www.reddit.com/r/earthporn')
    parser.add_argument('--count', '-c', help='number of images (max = 100)',
                        type=int, default=config.get('count'))
    parser.add_argument('--dest', '-d', help='destination directory', type=str,
                        default=config.get('dest'))
    parser.add_argument('--keepcount', '-k',
                        help='number of images to keep in the directory (> '
                             'count)',
                        type=int, default=config.get('keepcount'))
    parser.add_argument('--resolution', '-r',
                        help='resolution of the display, to filter out images '
                             'that do not look good',
                        type=str, default=config.get('resolution'))
    args = parser.parse_args()

    logging.debug('Starting with config: %r', args)

    res = args.resolution
    if res:
        TARGET_RESOLUTION = Resolution(*map(int, res.split('x')))
    main(args.count, args.dest, args.keepcount)
    logging.debug('Done.')
    sys.exit(0)
