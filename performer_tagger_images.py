#!/usr/bin/env python

import logging
import json
import re

import stashapi.log as log
from stashapi.stashapp import StashInterface

logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)

stash_api_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1aWQiOiJ0aW1la2lsbGVyIiwiaWF0IjoxNjk2NTM3NjYxLCJzdWIiOiJBUElLZXkifQ.I-bG5CTZWW9UaESZ-UX9vwxtIr1TWa9L-64U_vTAQZU"
of_studio=319
performer_tagged=2143
max_per_page=500
missing_performer_file = 'missing_performers_images.txt'

stash = StashInterface({
    "scheme": "http",
    "host":"10.0.30.8",
    "port": "9999",
    "ApiKey": stash_api_key,
    "logger": log
})


def of_images_with_at():
    f={
        "studios": {"value": [of_studio], "excludes": [], "modifier": "INCLUDES", "depth": 0},
        "title": {"value": "@", "modifier": "INCLUDES"},
    }
    images = get_images(f)
    return images

def of_images_with_tagged_performer(performer):
    f={
        "studios": {"value": [of_studio], "excludes": [], "modifier": "INCLUDES", "depth": 0},
        "title": {"value": f"@{performer}", "modifier": "INCLUDES"},
    }
    images = get_images(f)
    return images

def get_images(f):
    done = False
    all_images = []
    page = 1
    while not done:
        logging.debug(f'Page: {page}')
        images = stash.find_images(
            f=f,
            filter={
                "per_page": max_per_page,
                "page": page
            }

        )
        logging.debug(f'Images: {len(images)}')
        all_images = all_images + images

        if len(images) < max_per_page:
            logging.debug('Done')
            done = True
        else:
            done=True
            logging.debug('Not Done')
            page+=1
    return all_images

def parse_text_for_performers(text):
    mentions = re.findall(r'@\w+[.]?\w+', text)
    return mentions

def get_performer_ids_by_name(name):
    # performers by name
    performers = stash.find_performers(
        f={
            "name": {"value": name, "modifier": "EQUALS"},
        }
    )

    # performers by alias
    alias_performers = stash.find_performers(
        f={
            "aliases": {"value": name, "modifier": "INCLUDES"},
        }
    )
    # merge the two
    all_performers = performers + alias_performers
    performer_ids = []
    performer_matched = False
    # loop through them and look for an exact match.
    # We add all exact matches because an OF account can have multiple performers.
    for performer in all_performers:
        if performer['name'].lower() == name.lower():
            performer_matched = True
        for alias in performer['alias_list']:
            if alias.lower() == name.lower():
                performer_matched = True
        if performer_matched:
            performer_ids.append(performer['id'])
    return performer_ids

def init_missing_log():
    with open(missing_performer_file, 'w') as file:
        file.write('')

def log_missing_performer(performer):
    with open(missing_performer_file, 'a') as file:
        file.write(f'{performer}\n')


if __name__ == "__main__":
    logging.debug('Initializing log file')
    init_missing_log()

    logging.info('Getting Images with tagged performers')
    # First look for images containing the '@' symbol and not tagged as done
    images = of_images_with_at()

    logging.info('Parsing text for tagged performers')
    # Get tagged performers from image text
    all_tagged_performers = []
    for image in images:
        title = image['title']
        details = image['details']
        for text in [title,details]:
            tagged_performers = parse_text_for_performers(text)
            for performer in tagged_performers:
                performer = performer.lower()
                if performer not in all_tagged_performers:
                    all_tagged_performers.append(performer)
    logging.debug(f'Found performers: {str(all_tagged_performers)}')
    
    # Loop tagged performers
    for tagged_performer in all_tagged_performers:
        # Strip '@' from name
        tagged_performer = tagged_performer.lstrip('@')

        # Look for performer with exact match name or alias
        performer_ids = get_performer_ids_by_name(tagged_performer)

        if not performer_ids:
            logging.debug(f'Performer not found {tagged_performer}')
            log_missing_performer(tagged_performer)
            continue

        # Performer id(s) found, bulk update all images with this performer tagged
        logging.info(f'Updating images for {tagged_performer}')
        images = of_images_with_tagged_performer(tagged_performer)

        # Bulk update images
        results = stash.update_images({
            "ids": [i["id"] for i in images],
            "performer_ids": {
                "ids": performer_ids,
                "mode": "ADD"
            }
        })
        logging.info(f'Updated {len(results)} records')