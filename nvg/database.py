# (C) Nicholas Campbell 2018-2019
# Last update: 2019-08-26

import os
import pymysql as sql
import re
import sys
import warnings

# Path to execute the MySQL command

mysql_filepath = 'mysql'

# Names of tables in the database server

file_info_table = 'nvg'
author_ids_table = 'nvg_author_ids'
file_authors_table = 'nvg_file_authors'
file_type_ids_table = 'nvg_type_ids'
language_codes_table = 'nvg_language_codes'
publication_type_ids_table = 'nvg_publication_type_ids'
title_aliases_table = 'nvg_title_aliases'

# Names of columns in the file information table on the database server; this
# is used by routines for inserting new filepaths and updating existing
# filepaths

valid_column_keywords = ['filepath', 'file_size', 'cpcsofts_id', 'title',
	'company', 'year', 'languages', 'type_id', 'subtype',
	'title_screen', 'cheat_mode', 'protected', 'problems',
	'upload_date', 'uploader', 'comments', 'original_title',
	'publication_type_id', 'publisher_code', 'barcode', 'dl_code',
	'memory_required', 'run_command', 'protection']

# Strings used to form error messages when raising exceptions

db_error_message_path = ('check that the PATH environment variable is set '
	+ 'correctly')
db_error_message_admin = ('check with your database administrator that you '
	+ 'have the appropriate privileges to ')

def _escape_table_name(table_name):
	"""Replace backticks in a table name with double backticks so that it can be used
safely in SQL statements.
"""
	return table_name.replace('`', '``')


def _validate_author_ids(id, alias_of_id):
	"""Check that the specified author ID numbers are valid. If they are not, then
raise appropriate exceptions.

Parameters:
id (int): The author ID number.
alias_of_id (int): A cross-reference to another author ID number, indicating
    that the variable id is an alias of another author.

Returns:
True if both author ID numbers are valid.
"""
	if id is not None:
		if not (isinstance(id, int)):
			raise TypeError('Author ID number must be an integer')
		elif id not in range(0,65536):
			raise ValueError('Author ID number must be between 0 and '
				+ '65535')
	if alias_of_id is not None:
		if not (isinstance(alias_of_id, int)):
			raise TypeError('Author alias ID number must be an integer')
		elif alias_of_id not in range(1,65536):
			raise ValueError('Author alias ID number must be between 1 '
				+ 'and 65535')
	return True


class Database():
	connection = None
	db_hostname = None
	db_name = None
	db_username = None
	db_password = None

	# Local caches for storing file and publication type ID numbers and their
	# descriptions; these are used when inserting information about a file
	file_types_cache = {}
	publication_types_cache = {}

	def __init__(self, db_hostname, db_name, db_username,
		db_password):
		"""Create a new NVG database object.
"""
		self.db_hostname = db_hostname
		self.db_name = db_name
		self.db_username = db_username
		self.db_password = db_password


	def connect(self, use_database=True):
		"""Connect to the NVG database if no existing connection is open.

Parameters:
use_database (bool, optional): If False, do not select any database. This is
    useful if the database has not been set up yet on the server. The default
	is True.
"""
		# Confirm that there is no existing connection to the database before
		# trying to open another connection
		if (self.connection == None) or (self.connection.open == False):
			self.connection = sql.connect(host = self.db_hostname,
				user = self.db_username, password = self.db_password,
				charset = 'utf8', autocommit = False)
			if use_database:
				self.connection.select_db(self.db_name)


	def disconnect(self):
		"""Disconnect from the NVG database.
"""
		if (self.connection != None) and (self.connection.open):
			self.connection.close()


	def _select_last_insert_id(self):
		"""Get the ID number of the most recently inserted row where the value of a
column is generated automatically using AUTO_INCREMENT.
"""
		cursor = self.connection.cursor()
		query = 'SELECT LAST_INSERT_ID()'
		cursor.execute(query)
		insert_id = cursor.fetchone()[0]
		cursor.close()
		return insert_id


	def build(self, silent_output=False):
		"""Set up the tables, triggers, stored routines and views that are used by the
NVG database.

For the setting up to be successful, the user must have been granted the
following privileges:
CREATE, DROP, REFERENCES, ALTER ROUTINE, CREATE ROUTINE, TRIGGER, CREATE VIEW,
SELECT

Parameters:
silent_output (bool): If True, then be more silent and don't print any
    information about what changes were made to the database.

Returns:
Nothing.
"""
		db_command_base = (mysql_filepath
			+ ' -h {0} -u {1} --password={2}').format(self.db_hostname,
			self.db_username, self.db_password)
		db_tables_source_file = 'create_tables.sql'
		db_triggers_source_file = 'create_triggers.sql'
		db_stored_routines_source_file = 'create_stored_routines.sql'
		db_views_source_file = 'create_views.sql'
		db_name_escaped = _escape_table_name(self.db_name)

		# Connect to the database
		self.connect()
		cursor = self.connection.cursor()

		# Set up the database; this also drops (deletes) any existing copy
		# of the database on the server, so BE CAREFUL!
		try:
			warnings.simplefilter('ignore')

			# The queries below cannot be parameterised
			cursor.execute('DROP DATABASE IF EXISTS `{0}`'.format(
				db_name_escaped))
			cursor.execute('CREATE DATABASE `{0}`'.format(db_name_escaped))
			cursor.execute('USE `{0}`'.format(db_name_escaped))
			cursor.close()
			if silent_output == False:
				print('Using database {0}.'.format(self.db_name))
			warnings.simplefilter('default')
		except sql.OperationalError as db_error:
			print(('Unable to set up database {0} on host {1}. Please '
				+ db_error_message_admin + 'create, drop and set up '
				+ 'databases.').format(self.db_name, self.db_hostname),
				file=sys.stderr)
			self.disconnect()
			quit()

		# Read external files containing SQL commands for setting up tables,
		# triggers, stored routines and views

		# Create tables
		if silent_output == False:
			print('Reading table creation commands from source file '
				+ '{0}...'.format(db_tables_source_file))
		db_command = (db_command_base + ' -D {0} < {1}').format(
			self.db_name, db_tables_source_file)
		if os.system(db_command) != 0:
			print(('Unable to create tables for database {0} on host {1}. '
				+ 'Please ' + db_error_message_path + ', or '
				+ db_error_message_admin + 'create tables.').format(
				self.db_name, self.db_hostname), file=sys.stderr)
			self.disconnect()
			quit()

		# Create triggers
		if silent_output == False:
			print('Reading trigger creation commands from source file '
				+ '{0}...'.format(db_triggers_source_file))
			db_command = (db_command_base + ' -D {0} < {1}').format(
				self.db_name, db_triggers_source_file)
			if os.system(db_command) != 0:
				print(('Unable to create triggers for database {0} on host '
					+ '{1}. Please ' + db_error_message_path + ', or '
					+ db_error_message_admin + 'create triggers.').format(
					self.db_name, self.db_hostname), file=sys.stderr)
				self.disconnect()
				quit()

		# Create stored functions and procedures
		if silent_output == False:
			print('Reading stored routine creation commands from source file '
				+ '{0}...'.format(db_stored_routines_source_file))
			db_command = (db_command_base + ' -D {0} < {1}').format(
				self.db_name, db_stored_routines_source_file)
			if os.system(db_command) != 0:
				print(('Unable to create stored routines for database {0} '
					+ 'on host {1}. Please ' + db_error_message_path + ', or '
					+ db_error_message_admin + 'create triggers.').format(
					self.db_name, self.db_hostname), file=sys.stderr)
				self.disconnect()
				quit()

		# Create views
		if silent_output == False:
			print('Reading view creation commands from source file '
				+ '{0}...'.format(db_views_source_file))
			db_command = (db_command_base + ' -D {0} < {1}').format(
				self.db_name, db_views_source_file)
			if os.system(db_command) != 0:
				print(('Unable to create views for database {0} on host {1}. '
					+ 'Please ' + db_error_message_path + ', or '
					+ db_error_message_admin + 'create triggers.').format(
					self.db_name, self.db_hostname), file=sys.stderr)
				self.disconnect()
				quit()


	def insert_author(self, name, id, alias_of_id=None, commit=True):
		_validate_author_ids(id, alias_of_id)

		# Connect to the database
		self.connect()
		cursor = self.connection.cursor()
		if commit == True:
			self.connection.begin()

		# Insert the author name, ID number and alias ID number
		# cross-reference
		query = ('INSERT INTO `{0}` (author_id, author_name, '
			+ 'alias_of_author_id) '
			+ 'VALUES (%s, %s, %s)').format(
			_escape_table_name(author_ids_table))
		assert (id is None) or (id in range(0,65536))
		assert (alias_of_id is None) or (alias_of_id in range(1,65536))
		cursor.execute(query, (id, name, alias_of_id))
		if commit == True:
			self.connection.commit()

		# If no ID number was specified, get the value of the ID number that
		# the database assigned
		if (id is None) or (id == 0):
			id = self._select_last_insert_id()

		cursor.close()
		assert id in range(1,65536)
		return id


	def update_author(self, id, name, alias_of_id=None, commit=True):
		_validate_author_ids(id, alias_of_id)

		# Connect to the database
		self.connect()
		cursor = self.connection.cursor()
		if commit == True:
			self.connection.begin()

		# Update the author name, ID number and alias cross-reference ID
		# number
		query = ('UPDATE `{0}` '
			+ 'SET author_name = %s, alias_of_author_id = %s '
			+ 'WHERE author_id = %s').format(
			_escape_table_name(author_ids_table))
		assert id in range(1,65536)
		assert alias_of_id in range(1,65536)
		rows_updated = cursor.execute(query, (name, alias_of_id, id))
		if commit == True:
			self.connection.commit()

		# If the specified author ID number is not in the database, then
		# the number of rows that were updated is zero
		cursor.close()
		assert rows_updated in range(0,2)
		if rows_updated:
			return True
		else:
			return False


	def insert_filepath_author(self, filepath_id, author_id, author_type,
		author_index, commit=True):
		"""Add author information about a filepath to the NVG database.

Parameters:
filepath_id (int): The ID number of the filepath to link the author to.
author_id (int): The ID number of the author to associate with the specified
    filepath.
author_type (str): The type of author (e.g. 'PUBLISHER', 'AUTHOR', 'DESIGNER',
    'ARTIST', 'MUSICIAN', 'CRACKER').
author_index (int): The position of the author in the list of authors. When
    retrieving author information from the database, the determines the order
	in which the author names are listed.
commit (bool, optional): If True, the insertion of the file type will be
    committed immediately. The default is True.

Returns:
Nothing.
"""
		author_field_list = ['PUBLISHER','RE-RELEASED BY','CRACKER',
			'DEVELOPER','AUTHOR','DESIGNER','ARTIST','MUSICIAN']

		# Connect to the database
		self.connect()
		cursor = self.connection.cursor()
		if commit == True:
			self.connection.begin()

		# Insert the filepath and author ID numbers, author type and index
		query = ('INSERT INTO `{0}` (filepath_id, author_id, author_type, '
			+ 'author_index) VALUES (%s, %s, %s, %s)').format(
			_escape_table_name(file_authors_table))
		assert (filepath_id is None) or (filepath_id in range(1,4294967296))
		assert (author_id is None) or (author_id in range(1,65536))
		assert (author_index is None) or (author_index in range(0,65536))
		cursor.execute(query, (filepath_id, author_id, author_type,
			author_index))
		if commit == True:
			self.connection.commit()

		cursor.close()


	def delete_filepath_author(self, filepath_id, author_id=None,
		author_type=None, commit=True):
		"""Delete author information about a filepath from the NVG database. An author ID
number and/or author type can also be specified in order to delete only some
entries.

Parameters:
filepath_id (int): The ID number of the filepath for which author information
    is to be deleted.
author_id (int, optional): The ID number of the author to delete.
author_type (str, optional): The type of author (e.g. 'PUBLISHER', 'AUTHOR',
    'DESIGNER', 'ARTIST', 'MUSICIAN', 'CRACKER').
author_index (int): The position of the author in the list of authors. When
    retrieving author information from the database, the determines the order
	in which the author names are listed.
commit (bool, optional): If True, the insertion of the file type will be
    committed immediately. The default is True.

Returns:
bool: True if the author information was updated successfully; False if no
	filepath with the specified ID number exists, or there is no author
	information to update.
"""
		author_field_list = ['PUBLISHER','RE-RELEASED BY','CRACKER',
			'DEVELOPER','AUTHOR','DESIGNER','ARTIST','MUSICIAN']

		# Connect to the database
		self.connect()
		cursor = self.connection.cursor()
		if commit == True:
			self.connection.begin()

		# Delete author(s) associated with the specified filepath ID number
		query = 'DELETE FROM `{0}` WHERE filepath_id = %s'.format(
			_escape_table_name(file_authors_table))
		query_params = [filepath_id]
		if author_id is not None:
			query += ' AND author_id = %s'
			query_params.append(author_id)
		if author_type is not None:
			query += ' AND author_type = %s'
			query_params.append(author_type)

		assert (filepath_id is None) or (filepath_id in range(1,4294967296))
		assert (author_id is None) or (author_id in range(1,65536))
		rows_deleted = cursor.execute(query, query_params)
		if commit == True:
			self.connection.commit()

		# If the specified filepath ID number is not in the database, then
		# the number of rows that were updated is zero
		cursor.close()
		if rows_deleted:
			return True
		else:
			return False

		cursor.close()


	def insert_file_type(self, description, id=None, commit=True):
		"""Insert a file type into the NVG database.

Parameters:
type_desc (str): A description of the file type (e.g. 'Arcade game', 'Board
    game', 'Emulator', 'Other program', 'Utility').
type_id (int, optional): The ID number of the file type (0-255). If it is 0 or
    None, the database will use the next available value as the ID number.
commit (bool, optional): If True, the insertion of the file type will be
    committed immediately. The default is True.

Returns:
int: The ID number of the file type that was inserted.
"""
		if id is not None:
			if not (isinstance(id, int)):
				raise TypeError('File type ID number must be an integer')
			elif id not in range(0,256):
				raise ValueError('File type ID number must be between 0 and '
					+ '255')

		# Connect to the database
		self.connect()
		cursor = self.connection.cursor()
		if commit == True:
			self.connection.begin()

		# Insert the file type ID number and its description
		query = ('INSERT INTO `{0}` (type_id, type_desc) '
			+ 'VALUES (%s, %s)').format(
			_escape_table_name(file_type_ids_table))
		assert (id is None) or (id in range(0,256))
		cursor.execute(query, (id, description))
		if commit == True:
			self.connection.commit()

		# If no ID number was specified, get the value of the ID number that
		# the database assigned
		if (id is None) or (id == 0):
			id = self._select_last_insert_id()

		cursor.close()
		assert id in range(1,256)
		return id


	def insert_filepath(self, filepath, file_size, id=None, commit=True,
		**keywords):
		"""Insert a filepath and associated information about this file into the NVG
database.

Parameters:
filepath (str): The filepath (e.g. 'games/arcade/rolanrop.zip',
    'utils/cpm.zip').
file_size (int): The size of the file in bytes.
id (int, optional): The ID number to assign to the filepath. If it is 0 or
    None, the database will use the next available value as the ID number.
commit (bool, optional): If True, the insertion of the filepath will be
    committed immediately. The default is True.
keywords (dict, optional): A dictionary of values associated with this
    filepath. The keys are the column names used in the database, and the
	values are the values to insert with the filepath.

Returns:
int: The ID number of the filepath that was inserted.
"""
		# Check that all the keywords supplied are valid; if not, raise an
		# exception
		for keyword in keywords:
			if (keyword not in valid_column_keywords or keyword in
				['filepath', 'file_size']):
				raise TypeError('insert_filepath() got an unexpected keyword '
					+ 'argument ' + repr(keyword))

		# Connect to the database
		self.connect()
		cursor = self.connection.cursor()
		if commit == True:
			self.connection.begin()

		# The list of languages needs to be sent to the database server as a
		# string with comma-separated values
		languages_str = None
		if keywords.get('languages') is not None:
			languages = keywords['languages']
			if isinstance(languages, str):
				languages_str = languages
			elif isinstance(languages, (list, tuple)):
				languages_str = ','.join(languages)

		# If the file and/or publication types are specified as strings (e.g.
		# 'Arcade game', 'Commercial') instead of integers, then convert the
		# string to its corresponding ID number by looking up a dictionary
		# containing a local copy of the relevant type
		for type_tuple in [
			('type_id', self.file_types_cache, self.get_file_types,
				self.get_file_type_id),
			('publication_type_id', self.publication_types_cache,
				self.get_publication_types, self.get_publication_type_id)
			]:
			keyword = type_tuple[0]
			cache = type_tuple[1]
			if keywords.get(keyword) is not None:
				# If the type ID is a string, then get its corresponding ID
				# number (if there is one)
				if isinstance(keywords[keyword], str):
					# If the local copy of type descriptions is empty, then get
					# all the valid ID numbers and their descriptions from the
					# database
					if len(cache) == 0:
						cache = type_tuple[2]()

					# Look up the description in the local copy
					description = keywords[keyword]
					if (description in cache):
						keywords[keyword] = cache[description]

					# If the description is not in the local copy, then look
					# it up in the database; if it has an ID number, then use
					# it
					else:
						type_id = type_tuple[3](description)
						if type_id is not None:
							cache[description] = type_id
							keywords[keyword] = type_id

		# Build an SQL query string that will be sent to the database server
		query = ('INSERT INTO `{0}` (filepath_id, filepath, '
			+ 'file_size').format(_escape_table_name(file_info_table))
		query_values = '%s, %s, %s'
		query_params = [id, filepath, file_size]

		# Iterate through the list of keywords supplied to the function; each
		# keyword represents a column name
		if keywords:
			for keyword in valid_column_keywords:
				if keyword in keywords:
					query += ', ' + keyword

					# The values of the `year` and `upload_date` columns need
					# to be converted to dates when they are passed to the
					# database server
					query_values += ', '
					if keyword == 'year':
						query_values += "STR_TO_DATE(%s,'%%Y')"
					elif keyword == 'upload_date':
						query_values += "STR_TO_DATE(%s,'%%d/%%m/%%Y')"
					else:
						query_values += '%s'

					# Pass the string containing the comma-separated list of
					# language codes to the database server (e.g. 'en,es,fr'),
					# not the list of language descriptions (e.g. ['English',
					# 'Spanish', 'French'])
					if keyword == 'languages':
						query_params.append(languages_str)
					else:
						query_params.append(keywords[keyword])

		query += ') VALUES (' + query_values +')'

		assert (id is None) or (id in range(0,4294967296))
		assert file_size >= 0
		cursor.execute(query, query_params)
		if commit == True:
			self.connection.commit()

		# If no ID number was specified, get the value of the ID number that
		# the database assigned
		if (id is None) or (id == 0):
			id = self._select_last_insert_id()

		cursor.close()
		assert id in range(1,4294967296)
		return id


	def update_filepath(self, id, commit=True, **keywords):
		"""Update a filepath and associated information about this file in the NVG
database.

Parameters:
id (int): The ID number of the filepath to be updated.
keywords (dict, optional): A dictionary of values associated with this
    filepath. The keys are the column names used in the database, and the
	values are the values to insert with the filepath.

Returns:
bool: True if the filepath was updated successfully; False if no filepath with
    the specified ID number exists, or there were column names passed to the
	function (which means there was nothing to update).
"""
		# If there are no columns to update, then return
		if len(keywords) == 0:
			return False
		else:
			# Check that all the keywords supplied are valid; if not, raise an
			# exception
			for keyword in keywords:
				if keyword not in valid_column_keywords:
					raise TypeError('update_filepath() got an unexpected '
						+ 'keyword argument ' + repr(keyword))

		# Connect to the database
		self.connect()
		cursor = self.connection.cursor()
		if commit == True:
			self.connection.begin()

		# The list of languages needs to be sent to the database server as a
		# string with comma-separated values
		languages_str = None
		if keywords.get('languages') is not None:
			languages = keywords['languages']
			if isinstance(languages, str):
				languages_str = languages
			elif isinstance(languages, (list, tuple)):
				languages_str = ','.join(languages)

		# Build an SQL query string that will be sent to the database server
		query = ('UPDATE `{0}` SET ').format(
			_escape_table_name(file_info_table))
		query_values = ''
		query_params = []

		# Iterate through the list of keywords supplied to the function; each
		# keyword represents a column name
		if keywords:
			for keyword in valid_column_keywords:
				if keyword in keywords:
					if query_values:
						query_values += ', '
					query_values += keyword + ' = '

					# The values of the `year` and `upload_date` columns need
					# to be converted to dates when they are passed to the
					# database server
					if keyword == 'year':
						query_values += "STR_TO_DATE(%s,'%%Y')"
					elif keyword == 'upload_date':
						query_values += "STR_TO_DATE(%s,'%%d/%%m/%%Y')"
					else:
						query_values += '%s'

					# Pass the string containing the comma-separated list of
					# language codes to the database server (e.g. 'en,es,fr'),
					# not the list of language descriptions (e.g. ['English',
					# 'Spanish', 'French'])
					if keyword == 'languages':
						query_params.append(languages_str)
					else:
						query_params.append(keywords[keyword])

		query += query_values + ' WHERE filepath_id = {0}'.format(id)

		assert (id in range(0,4294967296))
		rows_updated = cursor.execute(query, query_params)
		if commit == True:
			self.connection.commit()

		# If the specified filepath ID number is not in the database, then
		# the number of rows that were updated is zero
		cursor.close()
		assert rows_updated in range(0,2)
		if rows_updated:
			return True
		else:
			return False


	def delete_filepath(self, id, commit=True):
		if id is not None:
			if not (isinstance(id, int)):
				raise TypeError('Filepath ID number must be an integer')
			elif id not in range(1,4294967296):
				raise ValueError('File type ID number must be between 0 and '
					+ '4294967295')

		# Connect to the database
		self.connect()
		cursor = self.connection.cursor()
		if commit == True:
			self.connection.begin()

		query = ('DELETE FROM `{0}` WHERE filepath_id = %s'.format(
			_escape_table_name(file_info_table)))		
		rows_deleted = cursor.execute(query, (id))
		if commit == True:
			self.connection.commit()

		cursor.close()
		if rows_deleted:
			return True
		else:
			return False


	def insert_title_alias(self, filepath_id, title_alias, commit=True):
		# Connect to the database
		self.connect()
		cursor = self.connection.cursor()
		if commit == True:
			self.connection.begin()

		query = ('INSERT INTO `{0}` (filepath_id, title) '
			+ 'VALUES (%s, %s)').format(
			_escape_table_name(title_aliases_table))
		cursor.execute(query, (filepath_id, title_alias))

		if commit == True:
			self.connection.commit()

		cursor.close()


	def delete_title_aliases(self, filepath_id, commit=True):
		# Connect to the database
		self.connect()
		cursor = self.connection.cursor()
		if commit == True:
			self.connection.begin()

		query = 'DELETE FROM `{0}` WHERE filepath_id = %s'.format(
			_escape_table_name(title_aliases_table))
		rows_deleted = cursor.execute(query, (filepath_id))

		if commit == True:
			self.connection.commit()

		# If the specified filepath ID number is not in the database, or
		# there are no title aliases associated with the filepath, then the
		# number of rows that were updated is zero
		cursor.close()
		if rows_deleted:
			return True
		else:
			return False


	def _get_languages_column_set(self):
		"""Get the set of IETF language tags that are defined in the languages column of
the file information table.

Returns:
list: A list containing the set of IETF language tags, or None if the column is
    not defined using the SET type (e.g. it is defined using the VARCHAR type
    instead).
"""
		# Generate a query to retrieve the elements of the set in the languages
		# column from the information_schemas.columns table
		query = ('SELECT COLUMN_TYPE FROM `information_schema`.`columns` '.format(
			_escape_table_name(language_codes_table))
			+ 'WHERE table_schema = %s AND table_name = %s '
			+ "AND column_name = 'languages'")
		cursor = self.connection.cursor()

		# Get the set as a string; it will be in a format like
		# "set('de','en','es','fr')" if it is defined using the SET type
		cursor.execute(query, (self.db_name, file_info_table))
		row = cursor.fetchone()
		match = re.fullmatch('set\((.*)\)', row[0], re.IGNORECASE)

		# If the language column is defined as a set, then convert the elements
		# of the set to a list by splitting the string and removing the
		# surrounding single quotes from each element
		if match:
			languages_column_set_list = match.group(1).split(sep=',')
			for i in range(0,len(languages_column_set_list)):
				languages_column_set_list[i] = \
					languages_column_set_list[i][
						1:len(languages_column_set_list[i])-1]
			return languages_column_set_list
		else:
			return None


	def insert_language(self, name, code):
		"""Insert a language name and its corresponding IETF language tag into the NVG
database.

Currently, the NVG database only allows a maximum length of 5 characters for
the IETF language tag. This can accommodate a 2-letter ISO 639-1 language
code (e.g. 'en', 'fr', 'es'), a hyphen, and a 2-letter ISO 3166 country code
(e.g. 'GB', 'US', 'FR', 'ES').

Parameters:
name (str): The name of the language (e.g. 'English', 'English (American)',
    'French', 'Spanish').
code (str): The IETF language tag that is associated with the specified
    language (e.g. 'en', 'en-US', 'fr', 'es').

Returns:
str: The IETF language tag that was inserted.
"""
		# Connect to the database
		self.connect()
		cursor = self.connection.cursor()
		self.connection.begin()

		# Check if the IETF language tag is already defined in the languages
		# column of the file information table; if it is not, then attempt to
		# add it to the set

		# The ALTER TABLE command always causes an implicit commit before
		# execution, so it should be executed first; if it fails, then the
		# language name and code won't be inserted into the nvg_language_codes
		# table
		languages_column_set_list = self._get_languages_column_set()

		if (languages_column_set_list is not None and
			code not in languages_column_set_list):
			languages_column_set_list.append(code)
			query = ('ALTER TABLE `{0}` '.format(
				_escape_table_name(file_info_table))
				+ 'MODIFY languages SET('
				+ ','.join(("'" + code + "'")
					for code in sorted(languages_column_set_list))
				+ ')'
				)
			try:
				cursor.execute(query)
			except sql.InternalError as db_error:
				self.connection.rollback()

				# MySQL allows a maximum of 64 members in columns defined with
				# the SET type; attempting to add any more members than this
				# results in an error
				if db_error.args[0] == 1097:
					error_message = ("Unable to insert language code {0} into "
						+ "column 'languages' in table '{1}'; a maximum of 64 "
						+ "language codes can be defined").format(
						repr(code), language_codes_table)
					raise sql.DataError(1097, error_message)

		# Insert the language description and IETF language tag into the table
		# of language codes
		query = ('INSERT INTO `{0}` (language_code, language_desc) '
			+ 'VALUES (%s, %s)').format(
			_escape_table_name(language_codes_table))
		cursor.execute(query, (code, name))

		self.connection.commit()

		return code


	def update_language(self, name, code, commit=True):
		"""Update an IETF language tag with a new name in the NVG database.

Parameters:
name (str): The new name of the language (e.g. 'English', 'English (American)',
    'French', 'Spanish').
code (str): The IETF language tag that is associated with the specified
    language (e.g. 'en', 'en-US', 'fr', 'es').

Returns:
bool: True if the IETF language tag was updated, False if the IETF language tag
    does not exist in the database.
"""
		# Connect to the database
		self.connect()
		cursor = self.connection.cursor()
		if commit == True:
			self.connection.begin()

		# Update the IETF language tag with its new name
		query = ('UPDATE `{0}` SET language_desc = %s '
			+ 'WHERE language_code = %s').format(
			_escape_table_name(language_codes_table))
		rows_updated = cursor.execute(query, (name, code))
		if commit == True:
			self.connection.commit()

		# Return True or False depending on whether or not the IETF language
		# tag exists in the table
		if rows_updated:
			return True
		else:
			return False


	def delete_language(self, code):
		"""Delete a language name and its corresponding IETF language tag from the NVG
database.

Parameters:
code (str): The IETF language tag to delete (e.g. 'en', 'en-US', 'fr', 'es').

Returns:
bool: True if the IETF language tag was deleted, False if the IETF language tag
    does not exist in the database.
"""
		# Connect to the database
		self.connect()
		cursor = self.connection.cursor()
		self.connection.begin()

		# Attempt to remove the IETF language tag from the set of elements in
		# the languages column of the file information table

		# The ALTER TABLE command always causes an implicit commit before
		# execution, so it should be executed first; if it fails, then the
		# language name and code won't be deleted from the nvg_language_codes
		# table
		languages_column_set_list = self._get_languages_column_set()

		if (languages_column_set_list is not None and
			code in languages_column_set_list):
			languages_column_set_list.remove(code)
			query = ('ALTER TABLE `{0}` '.format(
				_escape_table_name(file_info_table))
				+ 'MODIFY languages SET('
				+ ','.join(("'" + code + "'")
					for code in sorted(languages_column_set_list))
				+ ')'
				)
			try:
				cursor.execute(query)
			except sql.DataError as db_error:
				self.connection.rollback()
				if db_error.args[0] == 1265:
					error_message = ("Unable to delete language code {0} from "
						+ "column 'languages' in table '{1}' because at least "
						+ 'one row uses this language code').format(repr(code),
						language_codes_table)
					raise sql.DataError(1265, error_message)

		# Delete the IETF language tag from the table of language codes
		query = 'DELETE FROM `{0}` WHERE language_code = %s'.format(
			_escape_table_name(language_codes_table))
		rows_deleted = cursor.execute(query, (code))

		self.connection.commit()

		# Return True or False depending on whether or not the IETF language
		# tag exists in the table
		if rows_deleted:
			return True
		else:
			return False


	def insert_publication_type(self, description, id=None, commit=True):
		"""Insert a publication type into the NVG database.

Parameters:
type_desc (str): A description of the publication type (e.g. 'Commercial',
    'Freeware', 'Type-in').
type_id (int, optional): The ID number of the publication type (0-255). If it
    is 0 or None, the database will use the next available value as the ID
    number.
commit (bool, optional): If True, the insertion of the publication type will
    be committed immediately. The default is True.

Returns:
int: The ID number of the publication type that was inserted.
"""
		if id is not None:
			if not (isinstance(id, int)):
				raise TypeError('Publication type ID number must be an '
					+ 'integer')
			elif id not in range(0,256):
				raise ValueError('Publication type ID number must be between '
					+ '0 and 255')

		# Connect to the database
		self.connect()
		cursor = self.connection.cursor()
		if commit == True:
			self.connection.begin()

		query = ('INSERT INTO `{0}` (type_id, type_desc) '
			+ 'VALUES (%s, %s)').format(
			_escape_table_name(publication_type_ids_table))
		cursor.execute(query, (id, description))
		if commit == True:
			self.connection.commit()

		# If no ID number was specified, get the value of the ID number that
		# the database assigned
		if (id is None) or (id == 0):
			id = self._select_last_insert_id()

		cursor.close()
		return id


	def _get_dict(self, db_table, key_column, value_column):
		"""Generate a dictionary by retrieving key and columns from a table in the
NVG database.

Parameters:
db_table (str): The name of the table in the database.
key_column (str): The column in the table that will contain the keys in the
    dictionary.
value_column (str): The column in the table that will contain the values in
    the dictionary.

Returns:
dict: A dictionary containing the specified keys and values.
"""
		# Convert backticks in arguments to double backticks so they can
		# be used in queries
		key_column_escaped = key_column.replace('`', '``')
		value_column_escaped = value_column.replace('`', '``')

		# Connect to the database
		self.connect()
		cursor = self.connection.cursor()

		# Select all the rows from the specified table
		query = ('SELECT `{0}`, `{1}` FROM `{2}`').format(key_column_escaped,
			value_column_escaped, _escape_table_name(db_table))
		rows = cursor.execute(query)

		dict = {}
		if rows > 0:
			for i in range(0,rows):
				row = cursor.fetchone()
				dict[row[0]] = row[1]

		cursor.close()
		return dict


	def _get_value(self, db_table, key_column, value_column, search_term):
		# Convert backticks in arguments to double backticks so they can
		# be used in queries
		key_column_escaped = key_column.replace('`', '``')
		value_column_escaped = value_column.replace('`', '``')

		self.connect()
		cursor = self.connection.cursor()

		# Select the first row from the specified table that matches the
		# search term
		query = ('SELECT `{0}` FROM `{1}` WHERE `{2}` LIKE %s'.
			format(value_column_escaped, _escape_table_name(db_table),
				key_column_escaped))
		rows = cursor.execute(query, (search_term))

		id = None
		if rows > 0:
			id = cursor.fetchone()[0]

		cursor.close()
		return id


	def get_file_type_id(self, description):
		"""Get the ID number of a file type from the NVG database that matches the
specified description.

Parameters:
description (str): The file type description.

Returns:
int: The ID number of the file type, or None if no file type matching the
    description was found."""
		return self._get_value(file_type_ids_table, 'type_desc', 'type_id',
			description)


	def get_file_types(self):
		"""Retrieve a dictionary of file types and their corresponding ID numbers from
the NVG database.

Returns:
A dictionary containing file type descriptions as the keys, and their ID
numbers as the values.
"""
		return self._get_dict(file_type_ids_table, 'type_desc', 'type_id')


	def get_publication_type_id(self, description):
		"""Get the ID number of a publication type from the NVG database that matches the
specified description.

Parameters:
description (str): The publication type description.

Returns:
int: The ID number of the publication type, or None if no publication type
    matching the description was found."""
		return self._get_value(publication_type_ids_table, 'type_desc',
			'type_id', description)


	def get_publication_types(self):
		"""Retrieve a dictionary of publication types and their corresponding ID numbers
from the NVG database.

Returns:
A dictionary containing publication type descriptions as the keys, and their
ID numbers as the values.
"""
		return self._get_dict(publication_type_ids_table, 'type_desc',
			'type_id')


	def get_authors(self):
		"""Retrieve a dictionary of author names and their corresponding ID numbers and
cross-references to aliases from the NVG database.

Returns:
A dictionary containing author names as the keys; the values are also
dictionaries which contain the author's ID number ('ID') and, if the name is
an alias of another author name, the ID number of the actual name.
"""
		# Connect to the database
		self.connect()
		cursor = self.connection.cursor()

		query = ('SELECT author_name, author_id, alias_of_author_id FROM '
			+ '`{0}`').format(_escape_table_name(author_ids_table))
		rows = cursor.execute(query)

		# Select all the rows from the table of authors
		authors_dict = {}
		if rows > 0:
			for i in range(0,rows):
				row = cursor.fetchone()
				author_name = row[0]

				# Add the name, ID number and cross-references to aliases
				# (if applicable) to the dictionary
				authors_dict[author_name] = {}
				authors_dict[author_name]['ID'] = row[1]
				if row[2]:
					authors_dict[author_name]['Alias ID'] = row[2]

		cursor.close()
		return authors_dict


	def get_languages(self):
		"""Retrieve a dictionary of languages and their corresponding IETF language tags
from the NVG database.

Returns:
A dictionary containing language descriptions as the keys, and their IETF
language tags as the values (e.g. 'English': 'en',
'English (American)': 'en-us', 'French': 'fr', 'Spanish': 'es').
"""
		# Connect to the database
		self.connect()
		cursor = self.connection.cursor()

		query = ('SELECT language_desc, language_code FROM '
			+ '`{0}`').format(_escape_table_name(language_codes_table))
		rows = cursor.execute(query)

		languages_dict = {}
		if rows > 0:
			for i in range(0,rows):
				row = cursor.fetchone()
				languages_dict[row[0]] = row[1]

		cursor.close()
		return languages_dict
