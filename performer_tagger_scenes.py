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
missing_performer_file = 'missing_performers.txt'

stash = StashInterface({
    "scheme": "http",
    "host":"10.0.30.8",
    "port": "9999",
    "ApiKey": stash_api_key,
    "logger": log
})


def of_scenes_with_at():
    f={
        "studios": {"value": [of_studio], "excludes": [], "modifier": "INCLUDES", "depth": 0},
        "title": {"value": "@", "modifier": "INCLUDES"},
    }
    scenes = get_scenes(f)
    return scenes

def of_scenes_with_tagged_performer(performer):
    f={
        "studios": {"value": [of_studio], "excludes": [], "modifier": "INCLUDES", "depth": 0},
        "title": {"value": f"@{performer}", "modifier": "INCLUDES"},
    }
    scenes = get_scenes(f)
    return scenes

def get_scenes(f):
    done = False
    all_scenes = []
    page = 1
    while not done:
        logging.debug(f'Page: {page}')
        scenes = stash.find_scenes(
            f=f,
            filter={
                "per_page": max_per_page,
                "page": page
            }

        )
        logging.debug(f'Scenes: {len(scenes)}')
        all_scenes = all_scenes + scenes

        if len(scenes) < max_per_page:
            logging.debug('Done')
            done = True
        else:
            done=True
            logging.debug('Not Done')
            page+=1
    return all_scenes

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

    logging.info('Getting Scenes with tagged performers')
    # First look for scenes containing the '@' symbol and not tagged as done
    scenes = of_scenes_with_at()

    logging.info('Parsing text for tagged performers')
    # Get tagged performers from scene text
    all_tagged_performers = []
    for scene in scenes:
        title = scene['title']
        details = scene['details']
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

        # Performer id(s) found, bulk update all scenes with this performer tagged
        logging.info(f'Updating scenes for {tagged_performer}')
        scenes = of_scenes_with_tagged_performer(tagged_performer)
        # Get scene ids
        #scene_ids = []
        #for scene in scenes:
        #    scene_ids.append(scene['id'])

        # Bulk update scenes
        results = stash.update_scenes({
            "ids": [s["id"] for s in scenes],
            "performer_ids": {
                "ids": performer_ids,
                "mode": "ADD"
            }
        })
        logging.info(f'Updated {len(results)} records')