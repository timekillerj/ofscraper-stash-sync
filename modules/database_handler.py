import sqlite3
import logging
import os
import glob

class DatabaseHandler:
    def __init__(self, data_path):
        self.data_path = data_path
        self.conn = None
        self.cursor = None

    def find_database_files(self):
        databases = []
        logging.debug(f'Finding database files at {self.data_path}')
        search_path = os.path.join(self.data_path, "**", "user_data.db")
        path_databases = glob.glob(search_path, recursive=True)
        databases = databases + path_databases
        logging.debug(f'Databases: {str(databases)}')
        return databases

    def connect(self, database):
        try:
            self.conn = sqlite3.connect(database)
            self.cursor = self.conn.cursor()
            logging.debug(f"Connected to database: {database}")
        except sqlite3.Error as e:
            logging.error(f"Error connecting to database: {e}")
            self.conn = None
            self.cursor = None

    def execute(self, query, params=None):
        if self.cursor:
            try:
                if params:
                    self.cursor.execute(query, params)
                else:
                    self.cursor.execute(query)
                return self.cursor
            except sqlite3.Error as e:
                logging.error(f"Error executing query: {e}")
                return None
        return None

    def fetchone(self):
        if self.cursor:
            return self.cursor.fetchone()
        return None

    def fetchall(self):
        if self.cursor:
            return self.cursor.fetchall()
        return None

    def close(self):
        if self.conn:
            self.conn.close()
            logging.info(f"Disconnected from database: {self.db_path}")
            self.conn = None
            self.cursor = None