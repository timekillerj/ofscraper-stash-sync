# OFScraper/Stash Metadata Sync Tool
This project unites the work of [OF-Scraper](https://github.com/datawhores/OF-Scraper) and [StashApp](https://github.com/stashapp/stash) by merging the metadata scraped by OF-Scraper into the StashApp database. 

## What metadata is merged?
 * Title/Details: Onlyfans text can be very long. Script attempts to turn this into a reasonable Title and Details
 * Date: OnlyFans "posted at" date is used
 * Studio: Hardcoded to 'OnlyFans'. You must have a studio 'OnlyFans' (case insensitive) in your Stash database
 * Studio Code: OnlyFans Media ID is used
 * URLs: Link to original file on OF
 * Performers: Original posting model as well as any models @mentioned in the post text are added to the stash media record. For this to work the OF username must match exactly either the Stash performer name or one of the performer's aliases.
 * Organized: Set to true once processed. This prevents processing already processed media.

## Installation and Use
This script can be run directly or through a docker image

### Direct Execution
1. Clone this directory
```
git clone https://github.com/timekillerj/ofscraper-stash-sync
```
2. Move into cloned directory
```
cd ofscraper-stash-sync
```
3. (Optional but recommended) Install and activate a virtual environment
```
python3 -m venv .venv
source .venv/bin/activate
```
4. Install dependancies
```
pip install -r requirements.txt
```
5. Copy and edit config.ini.sample
```
cp config.ini.sample config.ini
vi config.ini
```
6. Run the code
```
python of_metadata_sync.py -c config.ini
```

### Docker Execution
TBD
