#!/usr/bin/python
import requests
import argparse
import os

JSON_URL = 'http://www.reddit.com/r/earthporn.json?limit=100'
HEADERS = {'User-Agent': 'script by /u/blissbero'}


def load_images(count):
    """
    Download images from /r/earthporn

    :param count: number of images to download from subreddit
    :returns: dict where keys are ids of threads and values are raw data
    """
    earthporn_json = requests.get(JSON_URL, headers=HEADERS).json()
    threads_with_images = []

    for thread in earthporn_json['data']['children']:
        if not thread['data']['stickied']:
            threads_with_images.append(thread)

    images = {}

    for thread in threads_with_images[:count]:
        images[thread['data']['id']] = requests.get(thread['data']['preview']['images'][0]['source']['url'],
                                                    stream=True).raw.read()

    return images


def save_images(images, dir):
    """
    Save images to folder
    :param images: dict where keys are titles and values are raw image data
    :param folder: directory for images
    """

    if not os.path.exists(dir):
        os.makedirs(dir)

    for title, data in images.items():
        with open(os.path.join(dir, title) + '.jpg', 'wb') as img_file:
            img_file.write(data)


def main(count, dest):
    save_images(load_images(count), dest)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Download images from http://www.reddit.com/r/earthporn')
    parser.add_argument('count', help='number of images (max = 100)', type=int)
    parser.add_argument('dest', help='destination directory', type=str)
    args = parser.parse_args()
    main(args.count, args.dest)
