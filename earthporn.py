#!/usr/bin/env python3
# coding=utf-8

import argparse
import logging.config
import os
import re
import string
import sys
import urllib
from collections import namedtuple
from itertools import filterfalse
from pathlib import Path

import requests
import yaml

logger = logging.getLogger('earthporn')

Resolution = namedtuple('Resolution', 'w,h')

JSON_URL = 'https://www.reddit.com/r/earthporn/hot.json?limit={}'
HEADERS = {'User-Agent': 'script by /u/blissbero'}
VALID_CHARS = frozenset("-_.()%s%s" % (string.ascii_letters, string.digits))
PREFIX = 'DOWN-'
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


def get_filepath(destdir, title, suffix):
    short_title = title if len(title) <= MAX_FILENAME_LENGTH else (
            title[:MAX_FILENAME_LENGTH // 2] + '...' +
            title[-MAX_FILENAME_LENGTH // 2:])
    return Path(
            os.path.join(destdir, PREFIX + safe_filename(short_title)) + suffix
    )


def keep_image(title, res_):
    w, h = res_.w, res_.h
    tw, th = TARGET_RESOLUTION.w, TARGET_RESOLUTION.h

    if tw - w > 4 * ACCEPTABLE_DIFFERENCE:
        # Smaller width, landscape
        logger.debug('rejecting %22r: width (%d) < target (%d)', title, w, tw)
        return False
    elif th - h > 4 * ACCEPTABLE_DIFFERENCE:
        # Smaller height, landscape
        logger.debug('rejecting %22r: height (%d) < target (%d)', title, h, th)
        return False
    elif w >= tw:
        # Greater width if landscape
        logger.debug('keeping %22r: width (%d) > target (%d)', title, w, tw)
        return True

    if h > w:
        # Portrait
        # ~ # Reject
        # ~ return False
        # Flip the coordinates
        w, h = h, w
        tw, th = th, tw
        logger.debug('%22r is a portrait (%dx%d) image', title, w, h)

    if tw * th - w * h < ACCEPTABLE_DIFFERENCE ** 2:
        # Greater width, landscape, overall higher resolution
        logger.debug(
            'rejecting %22r: resolution (%dx%d = %d) > target (%dx%d = %d)',
            title, w, h, w * h, tw, th, tw * th)
        return False

    if tw / th - w / h > ACCEPTABLE_DIFFERENCE / 200.0:
        logger.debug(
            'rejecting %22r: aspect ratio (%dx%d = %.3f) > '
            'target (%dx%d = %.3f)',
            title, w, h, w / h, tw, th, tw / th)
        return False

    logger.debug('keeping %22r: seems fine (%dx%d)', title, w, h)
    return True


def filtered_images(children, count, minscore):
    """
    :param children:
    :param count:
    :param minscore: Minimum required score to qualify.
    :return:
    """
    total = 0
    for thread in children:
        if total >= count:
            break
        title = thread['data']['title']
        if thread['data']['stickied']:
            continue
        score = thread['data']['score']
        if score < minscore:
            logger.debug('rejecting %22r: insufficient score %d',
                         title, score)
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


def load_images(count, minscore):
    """
    Download images from /r/earthporn

    :param count: number of images to download from subreddit
    :param minscore: Minimum required score to qualify.
    :returns: dict where keys are ids of threads and values are raw data
    """
    url = JSON_URL.format(count)
    logger.info("Getting url %r with count %d", url, count)
    earthporn_json = requests.get(url, headers=HEADERS).json()

    for thread, source_image in filtered_images(
            earthporn_json['data']['children'], count, minscore):
        title = thread['data']['title']
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
        # Kludge for
        # https://www.reddit.com/r/bugs/comments/4zpqks/uri_signature_match_failed/
        data = data.replace('&amp;', '&')
        save_image(title, data, destdir)


def save_image(title, url, destdir):
    suffix = os.path.splitext(urllib.parse.urlsplit(url).path)[1]
    path = get_filepath(destdir, title, suffix)
    if path.exists():
        logger.debug('skipping %22r: already acquired', title)
        return
    logger.info("Saving image %r to %s", title, path)
    data = requests.get(url, stream=True).raw.read()
    with path.open('wb') as img_file:
        img_file.write(data)
    with open(get_filepath(destdir, title, '.txt'), 'w') as info:
        info.write('Title:\t{}\nFile:\t{}\nURL:\t{}\n'.format(title, path, url))


def keep_at_most(dest, count):
    all_files = Path(dest).glob(PREFIX + '*')
    images = filterfalse(lambda p: p.match('*.txt'), all_files)
    oldest_images = sorted(images, key=lambda p: p.stat().st_mtime,
                           reverse=True)[count:]
    for f_ in oldest_images:
        dirname, basename = os.path.split(f_)
        for target in Path(dirname).glob(os.path.splitext(basename)[0] + '.*'):
            logger.info("Deleting file %s", target)
            try:
                f_.unlink()
            except OSError:
                logger.exception("Failed to delete %s", f_)


def main(count, minscore, dest, keepcount):
    """
    :param count:
    :param minscore:
        Minimum required score to qualify.
    :param dest:
    :param keepcount:
    """
    dest = os.path.expanduser(dest)
    save_images(load_images(count, minscore), dest)
    if keepcount and keepcount > count:
        keep_at_most(dest, keepcount)


if __name__ == '__main__':
    # Configure logging
    with open('logging.yaml', 'r') as f:
        logging.config.dictConfig(yaml.load(f))

    # start with internal default configuration
    config = {
        'count': 10,
        'dest': '~/Pictures',
        'keepcount': None,
        'minscore': 10000,
        'resolution': '1920x1080',
    }
    # update those defaults using the configuration file
    try:
        with open('earthporn.yaml', 'r') as f:
            config.update(yaml.load(f))
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
    parser.add_argument('--minscore', '-m',
                        help='minimum required score',
                        type=int, default=config.get('minscore'))
    parser.add_argument('--resolution', '-r',
                        help='resolution of the display, to filter out images '
                             'that do not look good',
                        type=str, default=config.get('resolution'))
    args = parser.parse_args()

    if args.keepcount and args.keepcount <= args.count:
        parser.error('keepcount, if set, must be greater than count')

    logging.debug('Starting with config: %r', args)

    res = args.resolution
    if res:
        TARGET_RESOLUTION = Resolution(*map(int, res.split('x')))
    main(args.count, args.minscore, args.dest, args.keepcount)
    logging.debug('Done.')
    sys.exit(0)
