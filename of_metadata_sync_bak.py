#!/usr/bin/env python

import logging
import re
import json
import sys
import os
import sqlite3
import glob
from datetime import datetime

import stashapi.log as log
from stashapi.stashapp import StashInterface

logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)

spinner_chars = ['|', '/', '-', '\\']
spinner = iter(spinner_chars)

of_studio_id = '319'
of_tag_id = '1216'
paid_tag = '2137'

#config_prefix = "/mnt/Adult/appdata"
config_prefix = "/home/jdonahue/appdata"


ofscraper_configpaths = [
    f"{config_prefix}/of-scraper/ofscraper/main_profile/.data/",
    f"{config_prefix}/of-scraper/ofscraper/mdlaskowski_profile/.data/"
]
stash_api_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1aWQiOiJ0aW1la2lsbGVyIiwiaWF0IjoxNjk2NTM3NjYxLCJzdWIiOiJBUElLZXkifQ.I-bG5CTZWW9UaESZ-UX9vwxtIr1TWa9L-64U_vTAQZU"

stash = StashInterface({
    "scheme": "http",
    "host":"10.0.30.8",
    "port": "9999",
    "ApiKey": stash_api_key,
    "logger": log
})

import pdb
pdb.set_trace()

def find_database_files(directories=ofscraper_configpaths):
    logging.debug(f'Finding databases')
    databases = []
    for directory in directories:
        logging.debug(f'...searching {directory}')
        search_path = os.path.join(directory, "**", "user_data.db")
        path_databases = glob.glob(search_path, recursive=True)
        databases = databases + path_databases
    logging.debug(f'Databases: {str(databases)}')
    return databases

def remove_html_tags_regex(text):
    text.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    clean = re.compile(r'<[^>]+>')
    return clean.sub('', text)


def truncate_at_space(text, max_length=255):
    if len(text) <= max_length:
        return text
    
    truncated_text = text[:max_length]
    last_space_index = truncated_text.rfind(' ')
    
    if last_space_index != -1:
        return truncated_text[:last_space_index]
    else:
        # No space found within the max_length, so return the full max_length slice
        return truncated_text

def update_media(cur, user_id, filename, stash_media_id):
    cur.execute('''
        SELECT media_id, post_id, link, filename, api_type, media_type, posted_at FROM medias WHERE model_id = ? AND filename = ?
    ''', (user_id, filename))
    media_row = cur.fetchone()
    if not media_row:
        print_spinner()
        return
    media_id = media_row[0]
    post_id = media_row[1]
    link = media_row[2]
    filename = media_row[3]
    api_type = media_row[4]
    media_type = media_row[5]
    posted_at = media_row[6]
    logging.debug(media_row)
    posted_at_dt = dt = datetime.fromisoformat(posted_at)
    posted_at_formatted = posted_at_dt.strftime("%Y-%m-%d")

    post_tables = ['posts','stories','messages','stories']

    for table in post_tables:
        cur.execute(f'''
            SELECT text FROM {table} where post_id = ?
        ''', (post_id, ))
        metadata_row = cur.fetchone()
        if metadata_row:
            text = metadata_row[0]
            break

    if not text:
        text = f"{api_type}: {posted_at_formatted}"
    text = remove_html_tags_regex(text)
    description = ""

    if len(text) > 255:
        description = text
        text = truncate_at_space(text)
        
    logging.debug(text, description)

    input = {
        "id": stash_media_id,
        "title": text,
        "code": media_id,
        "date": posted_at_formatted,
        "studio_id": of_studio_id,
        "performer_ids": performer_ids,
        "details": description,
        "tag_ids": tag_ids,
        "organized": True
    }
    if link:
        input["urls"] = [link]

    logging.debug(input)
    # Find media in stash
    logging.debug(f"FILE: {filename}")
    if media_type == 'Videos':
        stash.update_scene(input)
        logging.info(f"Updated: Scene {media_id}: {text}")
    elif media_type == 'Images':
        stash.update_image(input)
        logging.info(f"Updated: Image {media_id}: {text}")
    return

def print_spinner():
    global spinner
    char = next(spinner)
    sys.stdout.write(char)
    sys.stdout.flush()
    sys.stdout.write('\b')
    if char == '\\':
        spinner = iter(spinner_chars)


if __name__ == "__main__":
    tag_ids = [of_tag_id]
    # Open sqlite db
    for sqlite_db in find_database_files():
        logging.debug(f"Database File: {sqlite_db}")
        con = sqlite3.connect(sqlite_db)
        cur = con.cursor()

        # Get usernames
        cur.execute('''
            SELECT user_id, username from profiles
        ''')
        rows = cur.fetchall()
        for row in rows:
            user_id = row[0]
            username = row[1]
            logging.info(f'Username: {username}, UserId: {user_id}')

            # Get unorganized images
            logging.info('Getting Images')
            images = stash.find_images(
                f={
                    "path": {"value": username, "modifier": "INCLUDES"},
                    "organized": False
                }
            )
            images_dict = {}
            logging.debug(images)

            for image in images:
                for visual_file in image['visual_files']:
                    images_dict[visual_file['basename']] = image['id']
            logging.info(f"Found {len(images_dict)} images")

            # Get unorganized scenes
            logging.info('Getting scenes')
            scenes = stash.find_scenes(
                f={
                    "path": {"value": username, "modifier": "INCLUDES"},
                    "organized": False
                }
            )
            
            scenes_dict = {}
            logging.debug(scenes)
            for scene in scenes:
                for file in scene['files']:
                    scenes_dict[os.path.basename(file['path'])] = scene['id']
            logging.info(f"Found {len(scenes_dict)} scenes")

            if not images_dict and not scenes_dict:
                logging.info('No Images, no scenes, skipping')
                # Nothing to do!
                continue

            # Get Stash performer
            performers = stash.find_performers(
                f={
                    "name": {"value": username, "modifier": "EQUALS"},
                }
            )
                
            alias_performers = stash.find_performers(
                f={
                    "aliases": {"value": username, "modifier": "INCLUDES"},
                }
            )
            all_performers = performers + alias_performers
            # TODO username verification logic
            performer_ids = []
            performer_matched = False
            for performer in all_performers:
                # First make sure they are an OF model
                tag_matched = False
                for tag in performer['tags']:
                    if tag['name'] == 'OnlyFans':
                        tag_matched = True
                if not tag_matched:
                    continue

                if performer['name'].lower() == username.lower():
                    performer_matched = True

                for alias in performer['alias_list']:
                    if alias.lower() == username.lower():
                        performer_matched = True
                if performer_matched:
                    performer_ids.append(performer['id'])
            logging.debug(performer_ids)
            logging.info(f"Found {len(performer_ids)} performers")

            # If no performer, stop
            if not performer_ids:
                logging.error(f"No performers found with alias {username}")
                sys.exit(1)

            media_dict = images_dict | scenes_dict
            for filename, media_id in media_dict.items():
                update_media(cur, user_id, filename, media_id)

        con.close()
