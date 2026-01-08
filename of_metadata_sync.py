import logging
import os

import argparse
import configparser

from modules.database_handler import DatabaseHandler
from modules.stash_api_handler import StashAPIHandler
from modules.media_handler import MediaHandler


parser = argparse.ArgumentParser(description="A tool to sync OFScraper metadata to Stash")
parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose (debugging) output")
parser.add_argument("-c", "--config", dest="config_path", help="Path to config file", required=True)

args = parser.parse_args()


if args.verbose:
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info('============= Debug Logging Enabled =============')
else:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def main(config_path):
    config = configparser.ConfigParser()
    config.read(config_path)
    # TODO: Validate config

    # Initialize handlers
    db_handler = DatabaseHandler(config['Paths']['data_path'])
    stash_handler = StashAPIHandler(
        config['Stash']['api_key'],
        config['Stash']['scheme'],
        config['Stash']['host'],
        config['Stash']['port']
    )
    if not stash_handler.stash:
        logging.error("Failed to connect to Stash API. Exiting.")
        return

    media_handler = MediaHandler()

    # Get OnlyFans studio_id
    of_studio_id = stash_handler.get_of_studio_id()
    logging.debug(f'OnlyFans studio id: {of_studio_id}')
    if not of_studio_id:
        logging.error('Failed to get studio id for "OnlyFans". Exiting.')
        return


    # Get sqlite database files
    # OFScraper creates a sqlite file for each model, so we have to search the data path
    databases = db_handler.find_database_files()

    for database in databases:
        db_handler.connect(database)
        
        if not db_handler.conn:
            logging.error("Failed to connect to database. Exiting.")
            return

        # Get usernames
        # Should just b one profile, but it's a table so we assume more than one
        profiles = db_handler.execute("SELECT user_id, username FROM profiles").fetchall()

        for profile in profiles:
            user_id = profile[0]
            username = profile[1]
            logging.info(f'Username: {username}, UserId: {user_id}')

            # Get unorganized images and scenes
            # We do this in a single query to cache the results for efficiency
            images = stash_handler.get_unorganized_of_model_images(username)
            logging.debug(f'Images: {images}')
            images_dict = {}
            for image in images:
                for visual_file in image['visual_files']:
                    # We use the base filename as the key because this will be the unique 
                    # identifier we use from the OF scrape
                    images_dict[visual_file['basename']] = image['id']
            logging.info(f'Found {len(images_dict)} images')

            scenes = stash_handler.get_unorganized_of_model_scenes(username)
            scenes_dict = {}
            logging.debug(f'Scenes: {scenes}')
            for scene in scenes:
                for file in scene['files']:
                    # We use the base filename as the key because this will be the unique 
                    # identifier we use from the OF scrape
                    scenes_dict[os.path.basename(file['path'])] = scene['id']
            logging.info(f'Found {len(scenes_dict)} scenes')

            # Get Stash performer
            performers = stash_handler.get_stash_performers_by_name(username)
            logging.debug(f"Found {len(performers)} matching performers")

            if not performers:
                # No Stash performer found for OF Model
                logging.error(f"No performers found with name or alias {username}")
                if config['Stash']['stop_on_missing_performer'] == 'True':
                    # config say we stop here
                    return
                else:
                    # config says skip and go to next user
                    # TODO: Consider creating performer
                    continue

            if len(performers) > 1 and config['Stash']['multiple_performers_ok'] != 'True':
                # Found multiple matches for the OF Model, and config says that's not ok
                logging.error(f'Multiiple performers found for {username}.')
                if config['Stash']['stop_on_missing_performer'] == 'True':
                    # if missing performers aren't ok, neither is too many performers
                    return
                else:
                    # Skip and go to the next
                    continue

            performer_ids = [p['id'] for p in performers]

            media_dict = images_dict | scenes_dict

            for media_item in media_dict.items():
                media_handler.update_media(db_handler, stash_handler, profile, media_item,performer_ids, of_studio_id)

    db_handler.close()

if __name__ == "__main__":
    main(args.config_path)