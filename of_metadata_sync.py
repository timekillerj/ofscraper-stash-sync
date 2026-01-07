import logging

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

    # Initialize handlers
    db_handler = DatabaseHandler(config['Paths']['data_path'])
    stash_handler = StashAPIHandler(
        config['Stash']['api_key'],
        config['Stash']['scheme'],
        config['Stash']['host'],
        config['Stash']['port']
    )
    media_handler = MediaHandler()

    if not stash_handler.stash:
        logging.error("Failed to connect to Stash API. Exiting.")
        return

    # Get sqlite database files
    # OFScraper creates a sqlite file for each model, so we have to search the data path
    databases = db_handler.find_database_files()

    for database in databases:
        db_handler.connect(database)
        
        if not db_handler.conn:
            logging.error("Failed to connect to database. Exiting.")
            return

        # Get OnlyFans studio_id
        of_studio_id = stash_handler.get_of_studio_id()
        logging.debug(f'OnlyFans studio id: {of_studio_id}')
        if not of_studio_id:
            logging.error('Failed to get studio id for "OnlyFans". Exiting.')
            return

        # Get Onlyfans tag id
        #of_tag_id = stash_handler.get_of_tag_id()
        #logging.debug(f'OnlyFans tag id: {of_tag_id}')
        #if not of_tag_id:
        #    logging.error("Failed to get tag with name 'OnlyFans'. Exiting.")
        #    return

        # Get usernames
        profiles = db_handler.execute("SELECT user_id, username FROM profiles").fetchall()

        for profile in profiles:
            user_id = profile[0]
            username = profile[1]
            logging.info(f'Username: {username}, UserId: {user_id}')

            # Get unorganized images and scenes
            # We do this in a single query to cache the results
            images = stash_handler.get_unorganized_of_model_images(username)
            logging.debug(f'Images: {images}')
            images_dict = {}
            for image in images:
                for visual_file in image['visual_files']:
                    images_dict[visual_file['basename']] = image['id']
            logging.info(f'Found {len(images_dict)} images')

            scenes = stash_handler.get_unorganized_of_model_scenes(username)
            scenes_dict = {}
            logging.debug(f'Scenes: {scenes}')
            for scene in scenes:
                for file in scene['files']:
                    scenes_dict[os.path.basename(file['path'])] = scene['id']
            logging.info(f'Found {len(scenes_dict)} scenes')

            # Get Stash performer
            performers = stash_handler.get_stash_performers_by_name(username)
            logging.debug(f"Found {len(performers)} matching performers")

            if not performers:
                logging.error(f"No performers found with name or alias {username}")
                continue
            performer_ids = [p['id'] for p in performers]

            media_dict = {'images': images_dict, 'scenes': scenes_dict}

            for media_type, media_list in media_dict.items():
                for media_item in media_list.items():
                    media_handler.update_media(db_handler, profile, media_item,performer_ids, of_studio_id)

    db_handler.close()

if __name__ == "__main__":
    main(args.config_path)