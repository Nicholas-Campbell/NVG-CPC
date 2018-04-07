"""Set up a MySQL database containing information about files on the Amstrad CPC
software archive on NVG.

The CSV file containing this information can be downloaded from the archive at
the following URL:
<ftp://ftp.nvg.ntnu.no/pub/cpc/00_table.csv>
"""

# by Nicholas Campbell 2017-2018
# Last update: 2018-04-02

import argparse
import csv
import datetime
import ftplib
import getopt
import getpass
import nvg.csv
import os
import pymysql as sql
import re
import socket
import sys
import tempfile
import warnings


# --------------------------------------------
# Initialise variables, dictionaries and lists
# --------------------------------------------

# Data relating to CSV files from the NVG archive
nvg_csv_filename = r'00_table.csv'
author_aliases_csv_filename = r'author_aliases.csv'
file_data = {}

author_field_list = ['PUBLISHER','RE-RELEASED BY','CRACKER','DEVELOPER',
	'AUTHOR','DESIGNER','ARTIST','MUSICIAN']
author_set_def = ','.join([repr(type) for type in author_field_list])

# Permitted values for the MEMORY REQUIRED field in the main CSV file
memory_required_valid_values = [64, 128, 256]

# Database filenames
db_trigger_source_file = 'create_triggers.sql'
db_stored_routine_source_file = 'create_stored_routines.sql'
db_view_source_file = 'create_views.sql'

# Get the list of IETF language codes in alphabetical order and store
# them in a comma-delimited string for use in defining the main table later
# on
language_codes_dict = {
	'Catalan': 'ca', 'Danish': 'da', 'Dutch': 'nl', 'English': 'en',
	'English (American)': 'en-US', 'French': 'fr', 'German': 'de',
	'Greek': 'el', 'Irish': 'ga', 'Italian': 'it',
	'Portuguese (Brazilian)': 'pt-BR', 'Spanish': 'es', 'Swedish' : 'sv'
}
language_codes_list = []
for language, code in sorted(language_codes_dict.items()):
	language_codes_list.append(code)
language_codes_list.sort(key=str.lower)
language_set_def = ','.join([repr(code) for code in language_codes_list])
del language_codes_list


# Display a help message

def _print_help():
	"""Display the help message associated with this program.
"""
	indent = ' '*22
	print('Usage: {0} [OPTIONS] [database]\n'.format(sys.argv[0]))
	print('The following options can be used:')
	print('  -?, --help          Display this help message and exit.')
	print('  --build             Rebuild the entire database.')
	print('  -D, --database=name Database to use.')
	print('  --ftp-download      Download CSV files from the NVG FTP '
		+ 'site\n'
		+ indent + '(ftp://ftp.nvg.ntnu.no/pub/cpc/) instead of using '
		+ 'locally\n'
		+ indent + 'stored files.')
	print('  -h, --host=name     Connect to host.')
	print('  -p, --password=name Password to use when connecting to host. If '
		+ 'no password\n'
		+ indent + 'is specified then the program will ask for the user to\n'
		+ indent + 'input it.')
	print('  -s, --silent        Be more silent. Don\'t print any information '
		+ 'about what\n'
		+ indent + 'changes were made to the database.')
	print('  -u, --user=name     Username to use when connecting to host. If '
		+ 'no username\n'
		+ indent + 'is specified then the current login username will be\n'
		+ indent + 'used.')


def download_file_from_ftp_host(ftp_host, dir, filepath, file_transfer_mode):
	"""Download a file from an FTP site.

Parameters:
ftp_host: An ftplib.FTP object representing a connection to an FTP site. A
    connection must be established and the user must be logged on.
dir: The directory to download the specified files to.
filepath: The path of the file to download from the FTP site.
mode: The file transfer mode to use ('a' = ASCII, 'b' or 'i' = image (binary)).

Returns:
Nothing.
"""
	# Convert the file transfer mode to lower case, and if it is not a valid
	# mode, raise an exception
	file_transfer_mode = file_transfer_mode.lower()
	if file_transfer_mode not in ['a', 'b', 'i']:
		raise ValueError

	# Check that the directory to download to exists; if it doesn't,
	# create the directories
	(file_dir, filename) = os.path.split(filepath)
	download_dir = os.path.join(dir, file_dir).replace('\\','/')
	download_filepath = os.path.join(dir, filepath)
	if not os.path.exists(download_dir):
		os.makedirs(download_dir)

	# Download the file to the specified directory
	if file_transfer_mode == 'a':
		file_handle = open(download_filepath, 'w', encoding='latin-1')
		ftp_host.retrlines('RETR ' + filepath,
			lambda file: file_handle.write(file + '\n'))
	elif file_transfer_mode in ['b', 'i']:
		file_handle = open(download_filepath, 'wb')
		ftp_host.retrbinary('RETR ' + filepath,
			lambda file: file_handle.write(file))
	file_handle.close()


# Set up the database and create tables, triggers, procedures, functions and
# views

def _setup_db(db_name):
	# Convert backticks in arguments to double backticks so they can be used
	# in queries
	db_name_escaped = db_name.replace('`', '``')

	# Delete the database if it exists, and suppress any warning messages that
	# are displayed (e.g. the database doesn't exist)
	#
	# To set up the database, the following privileges need to be granted to
	# the relevant user:
	# CREATE, DROP, REFERENCES, ALTER ROUTINE, CREATE ROUTINE, TRIGGER, INSERT

	cursor = connection.cursor()
	try:
		warnings.simplefilter('ignore')

		# The queries below cannot be parameterised
		cursor.execute('DROP DATABASE IF EXISTS `{0}`'.format(db_name_escaped))
		cursor.execute('CREATE DATABASE `{0}`'.format(db_name_escaped))
		cursor.execute('USE `{0}`'.format(db_name_escaped))
		print('Using database {0}.'.format(db_name))
		warnings.simplefilter('default')
	except sql.OperationalError as db_error:
		print(('Unable to set up database {0} on host {1}. Please check with '
			+ 'your database administrator that you have the appropriate '
			+ 'privileges to create, drop and set up databases.').format(
			db_name, db_hostname))
		connection.close()
		quit()

	# Create tables
	try:
		cursor = connection.cursor()
		connection.begin()
		table_name = 'nvg_type_ids'
		print('Creating table ' + table_name + '...')
		query = ('CREATE TABLE ' + table_name + '\n'
		'(type_id TINYINT UNSIGNED AUTO_INCREMENT,\n'
		'type_desc VARCHAR(255) NOT NULL,\n'
		'PRIMARY KEY (type_id)'
		')')
		cursor.execute(query)

		table_name = 'nvg_publication_type_ids'
		print('Creating table ' + table_name + '...')
		query = ('CREATE TABLE ' + table_name + '\n'
		'(type_id TINYINT UNSIGNED AUTO_INCREMENT,\n'
		'type_desc VARCHAR(255) NOT NULL,\n'
		'PRIMARY KEY (type_id)'
		')')
		cursor.execute(query)

		table_name = 'nvg_language_codes'
		print('Creating table ' + table_name + '...')
		query = ('CREATE TABLE ' + table_name + '\n'
		'(language_code VARCHAR(5) NOT NULL,\n'
		'language_desc VARCHAR(30) NOT NULL,\n'
		'PRIMARY KEY (language_code)'
		')')
		cursor.execute(query)

		table_name = 'nvg'
		print('Creating table ' + table_name + '...')
		query = ('CREATE TABLE ' + table_name + '\n'
		'(filepath_id INT UNSIGNED AUTO_INCREMENT,\n'
		'filepath VARCHAR(260) CHARACTER SET ascii NOT NULL,\n'
		'file_size INT UNSIGNED NOT NULL,\n'
		'title VARCHAR(255),\n'
		'company VARCHAR(255),\n'
		'year DATE,\n'
		'language SET(' + language_set_def + '),\n'
		'type_id TINYINT UNSIGNED,\n'
		'subtype VARCHAR(255),\n'
		'title_screen VARCHAR(50),\n'
		'cheat_mode VARCHAR(50),\n'
		'protected VARCHAR(50),\n'
		'problems VARCHAR(255),\n'
		'upload_date DATE,\n'
		'uploader VARCHAR(255),\n'
		"comments VARCHAR(1000) DEFAULT '',\n"
		'original_title VARCHAR(255),\n'
		'publication_type_id TINYINT UNSIGNED,\n'
		'publisher_code VARCHAR(16),\n'
		'barcode VARCHAR(13),\n'
		'dl_code VARCHAR(26),\n'
		'memory_required SMALLINT UNSIGNED,\n'
		'protection VARCHAR(255),\n'
		'run_command VARCHAR(1000),\n'
		'PRIMARY KEY (filepath_id),\n'
		'UNIQUE INDEX (filepath),\n'
		'CONSTRAINT FOREIGN KEY fk_type_id (type_id) REFERENCES nvg_type_ids (type_id),\n'
		'CONSTRAINT FOREIGN KEY fk_publication_type_id (publication_type_id) REFERENCES nvg_publication_type_ids (type_id)\n'
		')')
		cursor.execute(query)

		table_name = 'nvg_title_aliases'
		print('Creating table ' + table_name + '...')
		query = ('CREATE TABLE ' + table_name + '\n'
		'(filepath_id INT UNSIGNED,\n'
		'title VARCHAR(255),\n'
		'PRIMARY KEY (filepath_id, title),\n'
		'CONSTRAINT FOREIGN KEY fk_filepath_id (filepath_id) REFERENCES nvg (filepath_id)\n'
		')')
		cursor.execute(query)

		table_name = 'nvg_author_ids'
		print('Creating table ' + table_name + '...')
		query = ('CREATE TABLE ' + table_name + '\n'
		'(author_id SMALLINT UNSIGNED AUTO_INCREMENT,\n'
		'author_name VARCHAR(255) NOT NULL,\n'
		'alias_of_author_id SMALLINT UNSIGNED,\n'
		'PRIMARY KEY (author_id),\n'
		'CONSTRAINT FOREIGN KEY fk_alias_of_author (alias_of_author_id) REFERENCES nvg_author_ids (author_id)\n'
		')')
		cursor.execute(query)

		table_name = 'nvg_file_authors'
		print('Creating table ' + table_name + '...')
		query = ('CREATE TABLE ' + table_name + '\n'
		'(filepath_id INT UNSIGNED,\n'
		'author_id SMALLINT UNSIGNED,\n'
		'author_type ENUM (' + author_set_def + '),\n'
		'author_index SMALLINT UNSIGNED,\n'
		'PRIMARY KEY (filepath_id, author_id, author_type),\n'
		'UNIQUE INDEX (filepath_id, author_type, author_index),\n'
		'CONSTRAINT FOREIGN KEY fk_fa_filepath_id (filepath_id) REFERENCES nvg (filepath_id),\n'
		'CONSTRAINT FOREIGN KEY fk_fa_author_id (author_id) REFERENCES nvg_author_ids (author_id)'
		')')
		cursor.execute(query)
		connection.commit()
	except sql.OperationalError as db_error:
		print(('Unable to create table {0}. The following error was '
			+ 'encountered:').format(table_name))
		print('Error code: ' + str(db_error.args[0]))
		print('Error message: ' + db_error.args[1])
		connection.close()
		quit()

	# Set up the triggers, stored procedures, functions and views by running
	# MySQL directly and processing the SQL files
	db_command_base = ('mysql -h {0} -D {1} -u {2} --password={3}').format(
		db_hostname, db_name, db_username, db_password)

	# Triggers
	print('Reading triggers from source file {0}...'.format(
		db_trigger_source_file))
	db_command = (db_command_base + ' < {0}').format(db_trigger_source_file)
	if os.system(db_command) != 0:
		print(('Unable to create triggers for database {0} on host {1}. '
			+ 'Please check that the PATH environment variable is set '
			+ 'correctly, or check with your database administrator that you '
			+ 'have the appropriate privileges to create and alter '
			+ 'triggers.').format(db_name, db_hostname))
		connection.close()
		quit()

	# Stored procedures and functions
	print(('Reading stored procedures and functions from source file '
		+ '{0}...').format(db_stored_routine_source_file))
	db_command = (db_command_base + ' < {0}').format(
		db_stored_routine_source_file)
	if os.system(db_command) != 0:
		print(('Unable to create stored procedures and functions for database '
			+ '{0} on host {1}. Please check that the PATH environment '
			+ 'variable is set correctly, or check with your database '
			+ 'administrator that you have the appropriate privileges to '
			+ 'create and alter stored procedures and functions.').format(
			db_name, db_hostname))
		connection.close()
		quit()

	# Views
	print(('Reading views from source file {0}...').format(db_view_source_file))
	db_command = (db_command_base + ' < {0}').format(db_view_source_file)
	if os.system(db_command) != 0:
		print(('Unable to create views for database {0} '
			+ 'on host {1}. Please check that the PATH environment variable '
			+ 'is set correctly, or check with your database administrator '
			+ 'that you have the appropriate privileges to create and alter '
			+ 'views.').format(db_name, db_hostname))
		connection.close()
		quit()


# Read the CSV file containing the list of author aliases
#
# Each line in this file consists of two columns; the first contains the
# alias, and the second contains the author's actual name. These are added to
# a dictionary

def read_author_aliases_csv_file(csv_filename):
	"""Read a CSV file containing a list of author names and aliases associated with
them.

The CSV file is assumed to be encoded in Latin-1 (ISO-8859-1).

Parameters:
csv_filename: The filepath of the CSV file.

Returns:
A dictionary containing aliases as the keys, and the author name each one is
associated with as the values.
"""
	author_aliases_dict = {}
	line = 0

	try:
		csv_file = open(csv_filename, newline='')
		csv_file_reader = csv.reader(csv_file, dialect='excel', delimiter=',')

		# Skip the first line of the CSV file, which contains the field names
		next(csv_file_reader)
		line += 1

		# Read all the remaining lines in the CSV file one at a time
		for row in csv_file_reader:
			alias_name = row[0].strip()
			author_name = row[1].strip()
			author_aliases_dict[alias_name] = author_name

			line += 1
		csv_file.close()
	except FileNotFoundError as file_error:
		print(('Unable to locate {0}. No information about author aliases '
			+ 'will be added or updated.').format(author_aliases_csv_filename),
			file=sys.stderr)
	finally:
		return author_aliases_dict


# Create a dictionary containing entries from a list of field names, sort
# the dictionary in alphabetical order, and assign ID numbers to each entry

# The value of each field name could have more than one entry, so a delimiter
# needs to be specified as well (usually a comma)

def create_id_dict(field_list, delimiter=','):
	dict = {}

	for filepath in file_data:
		for field in field_list:
			try:
				names = file_data[filepath][field]

				split_pub = names.split(sep=delimiter)
				for name in split_pub:
					dict[name.strip()] = 0
			except KeyError:
				pass

	id_num = 1
	for name in sorted(dict, key=str.lower):
		dict[name] = id_num
		id_num += 1

	return dict


def build_dict_from_table(table, key_column, value_column):
	"""Retrieve data from a table in the database and create a dictionary of key-value
pairs from it.

Parameters:
table: The name of the table to select data from.
key_column: The name of the column to use as the key in the dictionary.
value_column: The name of the column to use as the values for each key in the
    dictionary.

Returns:
A dictionary containing key-value pairs obtained from the specified table and
columns.
"""
	cursor = connection.cursor()
	dict = {}

	# Convert backticks in arguments to double backticks so they can be used
	# in the query below
	table = table.replace('`', '``')
	key_column = key_column.replace('`', '``')
	value_column = value_column.replace('`', '``')

	query = 'SELECT `{0}`, `{1}` FROM `{2}`'.format(key_column, value_column,
		table)
	rows = cursor.execute(query)
	if rows > 0:
		for i in range(0,rows):
			row = cursor.fetchone()
			dict[row[0]] = row[1]

	cursor.close()
	return(dict)

# Retrieve all the existing author information from the database

def get_existing_author_ids():
	cursor = connection.cursor()
	author_ids_dict = {}

	query = ('SELECT author_name, author_id, alias_of_author_id FROM '
		+ 'nvg_author_ids')
	rows = cursor.execute(query)
	if rows > 0:
		for i in range(0,rows):
			row = cursor.fetchone()
			if row[0] not in author_ids_dict:
				author_ids_dict[row[0]] = {}
				author_ids_dict[row[0]]['ID'] = row[1]
				if row[2]:
					author_ids_dict[row[0]]['Alias ID'] = row[2]

	cursor.close()
	return author_ids_dict

# Retrieve all the existing filepaths and their ID numbers from the database

def get_existing_filepath_ids():
	return build_dict_from_table('nvg', 'filepath', 'filepath_id')

# Retrieve all the existing publication types and their ID numbers from the
# database

def get_existing_publication_type_ids():
	return build_dict_from_table('nvg_publication_type_ids', 'type_desc',
		'type_id')

# Retrieve all the existing filepath author information from the database

def get_existing_filepath_id_author_info():
	cursor = connection.cursor()
	filepath_author_info = {}

	query = ('SELECT filepath_id, author_id, author_type, author_index '
		+ 'FROM nvg_file_authors '
		+ 'ORDER BY filepath_id, author_type, author_index')
	rows = cursor.execute(query)
	if rows > 0:
		for i in range(0,rows):
			row = cursor.fetchone()
			filepath_id = row[0]
			author_type = row[2]
			# If no authors have been defined yet for this filepath ID, then
			# create a new dictionary to store the author information
			if filepath_id not in filepath_author_info:
				filepath_author_info[filepath_id] = {}
			# The ID numbers of each author type are stored in an ordered list
			if author_type not in filepath_author_info[filepath_id]:
				filepath_author_info[filepath_id][author_type] = []

			filepath_author_info[filepath_id][author_type].append(row[1])

	cursor.close()
	return filepath_author_info

# Retrieve all the existing filepath types and their ID numbers from the
# database

def get_existing_type_ids():
	return build_dict_from_table('nvg_type_ids', 'type_desc', 'type_id')


# Create a list of author names and aliases to add to the database, by
# searching all the author-like fields in the file data (e.g. PUBLISHER,
# DEVELOPER, AUTHOR) and the dictionary of author aliases

def _get_authors_to_add():
	authors_to_add = []
	for filepath in file_data:
		for field in author_field_list:
			if field in file_data[filepath]:
				names = file_data[filepath][field]
				
				# The values of each field are comma-delimited
				author_names_split = names.split(sep=',')
				for name in author_names_split:
					name = name.strip()
					# If the author name is not already on the database, add it
					# to a list of author names to add to the database
					if (name not in author_ids_dict and
						name not in authors_to_add):
						authors_to_add.append(name)

	# Add aliases and names in the author aliases CSV file to the list of
	# authors to add to the database
	for alias, name in author_aliases_dict.items():
		if alias not in author_ids_dict and alias not in authors_to_add:
			authors_to_add.append(alias)
		if name not in author_ids_dict and name not in authors_to_add:
			authors_to_add.append(name)

	return authors_to_add


# Retrieve all the existing title aliases from the database

def get_existing_title_aliases():
	cursor = connection.cursor()
	title_aliases_info = {}

	query = ('SELECT filepath_id, title '
		+ 'FROM nvg_title_aliases '
		+ 'ORDER BY filepath_id, title')
	rows = cursor.execute(query)
	if rows > 0:
		for i in range(0,rows):
			row = cursor.fetchone()
			filepath_id = row[0]
			title_alias = row[1]
			# If no aliases have been defined yet for this filepath ID, then
			# create a new dictionary to store the title aliases
			if filepath_id not in title_aliases_info:
				title_aliases_info[filepath_id] = [title_alias]
			# The aliases of each filepath ID are stored in an ordered list
			else:
				title_aliases_info[filepath_id].append(title_alias)

	cursor.close()
	return title_aliases_info


def insert_language_codes(language_codes_dict):
	"""Insert a dictionary of IETF language tags and their descriptions into the table
of language codes on the database.

Parameters:
language_codes_dict: A dictionary containing IETF language tags as the keys
(e.g. 'en', 'en-US', 'es', 'fr') and the descriptions of the languages as their
values (e.g. 'English', 'English (American)', 'Spanish', 'French').

Returns:
Nothing.
"""
	cursor = connection.cursor()
	query = 'INSERT INTO nvg_language_codes VALUES (%s, %s)'
	connection.begin()
	for (language, code) in sorted(language_codes_dict.items()):
		cursor.execute(query, (code, language))
	connection.commit()
	cursor.close()


def insert_publication_type_ids(publication_type_ids_dict):
	"""Insert a dictionary of publication types and their ID numbers into the table of
publication types on the database.

Parameters:
publication_type_ids_dict: A dictionary containing publication types as the
keys, and their corresponding ID numbers as the values (e.g. 'Commercial': 1,
'Crack': 2, 'Freeware': 3).

Returns:
Nothing.
"""
	query = 'INSERT INTO nvg_publication_type_ids VALUES (%s, %s)'
	cursor = connection.cursor()
	connection.begin()
	for type in sorted(publication_type_ids_dict):
		cursor.execute(query, (publication_type_ids_dict[type], type))
	connection.commit()
	cursor.close()


def insert_type_ids(type_ids_dict):
	"""Insert a dictionary of filepath types and their ID numbers into the table of
filepath types on the database.

Parameters:
type_ids_dict: A dictionary containing filepath types as the keys, and their
corresponding ID numbers as the values (e.g. 'Arcade game': 1, 'Board game': 2,
'Cartridge game': 3).

Returns:
Nothing.
"""
	query = 'INSERT INTO nvg_type_ids VALUES (%s, %s)'
	cursor = connection.cursor()
	connection.begin()
	for type in sorted(type_ids_dict):
		cursor.execute(query, (type_ids_dict[type], type))
	connection.commit()
	cursor.close()


def insert_authors(authors_to_add):
	"""Insert a list of authors into the table of author names on the database. ID
numbers are assigned by the database and the names are added to the database in
alphabetical order.

Parameters:
authors_to_add: A list containing the names of the authors to add.

Returns:
author_ids_dict: A dictionary containing the author names that were added as
the keys, and their ID numbers as the values.
"""
	author_ids_dict = {}
	cursor = connection.cursor()
	connection.begin()
	for author_name in sorted(authors_to_add, key=str.lower):
		# Insert the new author name into the table of authors
		query = ('INSERT INTO nvg_author_ids'
			+ ' (author_name, alias_of_author_id) VALUES (%s, NULL)')
		cursor.execute(query, (author_name.strip()))

		# Get the ID number of the new author
		query = 'SELECT LAST_INSERT_ID()'
		cursor.execute(query)
		author_id = cursor.fetchone()[0]

		# Add the author name and his/her ID number to the local dictionary
		# of author information
		author_ids_dict[author_name] = {}
		author_ids_dict[author_name]['ID'] = author_id

	connection.commit()
	return author_ids_dict

def delete_filepaths_from_db():
	# Search the list of filepaths in the main CSV file that aren't already in
	# the database

	filepaths_to_delete = []
	for filepath in existing_filepath_ids:
		if filepath not in file_data:
			filepaths_to_delete.append(
				(filepath, existing_filepath_ids[filepath]))

	# If there are no filepaths to delete, then return
	if len(filepaths_to_delete) == 0:
		return 0
	else:
		# Sort the list of filepaths to delete
		filepaths_to_delete.sort(key=lambda x: x[0])

		# Build a string containing the ID numbers of the filepaths to delete,
		# separated by commas and in numerical order (although it isn't really
		# necessary to sort the list)
		filepath_ids_to_delete_set = ','.join(str(value) for (key, value) in
			filepaths_to_delete)

		# Create a query string containing the list of filepath ID numbers

		# Normally the method used below is discouraged due to the potential
		# for SQL injection, but the list of filepath ID numbers should consist
		# entirely of integers so there shouldn't be a problem?
		try:
			connection.begin()
			for table_name in ['nvg_file_authors', 'nvg_title_aliases', 'nvg']:
				query = ('DELETE FROM {0} WHERE filepath_id IN ({1})'.format(
					table_name, filepath_ids_to_delete_set))
				cursor.execute(query)
				connection.commit()

			# Display the list of filepaths that were deleted
			for (filepath, filepath_id) in filepaths_to_delete:
				print('Deleted {0} (ID {1}).'.format(filepath,
					filepath_id))

			# Return the number of filepaths that were deleted
			return len(filepaths_to_delete)

		except sql.OperationalError as db_error:
			print(('Unable to delete rows from table {0}. The following error '
				+ 'was encountered:').format(table_name))
			print('Error code: ' + str(db_error.args[0]))
			print('Error message: ' + db_error.args[1])
			connection.close()
			quit()


# ------------
# Main program
# ------------

# Parse command line arguments
#
# The allowed options are intentionally similar to those used by MySQL

db_hostname = 'localhost'
db_name = 'cpc'
db_username = getpass.getuser()
db_password = None
db_name_set_in_options = False	# Has the name of the database been set in the
								# command-line options?
build_db_flag = False			# Does the database need to be rebuilt?
silent_output = False			# Silent output mode

ftp_hostname = 'ftp.nvg.ntnu.no'
ftp_nvg_csv_filepath = 'pub/cpc/00_table.csv'
download_files_from_ftp_host = False

try:
	optlist, args = getopt.getopt(sys.argv[1:], '?D:h:u:p:s',
		['help', 'database=', 'host=', 'user=', 'password=', 'silent',
		'build', 'ftp-download'])
	# If more than one database name is supplied, then print the help message
	# and quit
	if len(args) > 1:
		_print_help()
		quit()
	else:
		for (option, value) in optlist:
			# Print the help message and quit
			if option in ['-?', '--help']:
				_print_help()
				quit()

			# Database connection options
			elif option in ['-D', '--database']:
				db_name = value
				db_name_set_in_options = True
			elif option in ['-h', '--host']:
				db_hostname = value
			elif option in ['-u', '--user']:
				db_username = value
			elif option in ['-p', '--password']:
				db_password = value
			elif option in ['-s', '--silent']:
				silent_output = True
			elif option == '--build':
				build_db_flag = True
			elif option == '--ftp-download':
				download_files_from_ftp_host = True

		# Check if more than one database has been specified (i.e. by using
		# -D or --database, as well as specifying the name of the database as
		# the last argument)
		if args:
			if db_name_set_in_options and args[0] != db_name:
				raise getopt.GetoptError('more than one database specified')
			else:
				db_name = args[0]
except getopt.GetoptError as argument_parse_error:
	print('Error while parsing options: ' + argument_parse_error.msg,
		file=sys.stderr)
	quit()

# If no password is supplied in the command line options, ask for one
if db_password == None:
	db_password = getpass.getpass(prompt = 'Enter password: ')


# ------------------------------
# Read and process the CSV files
# ------------------------------

# If author_aliases file isn't found, aliases will be removed from database!
# Prevent this from happening!

file_data = {}

# If the FTP download option has been selected, then download the relevant
# files from the NVG FTP site
if download_files_from_ftp_host:
	# Connect and log on to the FTP host
	try:
		print('Connecting to {0}...'.format(ftp_hostname))
		ftp = ftplib.FTP(ftp_hostname)
		ftp.login(user='anonymous', passwd='anonymous@nvg.ntnu.no')
	# socket.gaierror exception is raised if it is not possible to connect
	# to the FTP host
	except socket.gaierror:
		print('Unable to connect to FTP host {0}.'.format(ftp_hostname),
			file=sys.stderr)
		quit()
	# ftplib.error_perm exception is raised if it is not possible to log on
	# to the FTP host; the reply is also included
	except ftplib.error_perm as ftp_error:
		print(('Unable to log on to FTP host {0}. The following error was '
			+ 'encountered: ').format(ftp_hostname), file=sys.stderr)
		print(ftp_error)
		quit()

	# Create a temporary directory to download files to
	temp_dir = tempfile.TemporaryDirectory()

	# Download files from the FTP host
	file_list = [ftp_nvg_csv_filepath]
	for file_to_download in file_list:
		try:
			print('Downloading {0} from {1}...'.format(file_to_download,
				ftp_hostname))
			download_file_from_ftp_host(ftp, temp_dir.name,
				file_to_download, 'b')
		except ftplib.error_perm as ftp_error:
			print(('Unable to download {0} from {1}. The following error '
				+ 'occurred:').format(file_to_download, ftp_hostname),
				file=sys.stderr)
			print(ftp_error, file=sys.stderr)

	# Close the FTP connection
	ftp.quit()

# Read the main CSV file
try:
	if download_files_from_ftp_host:
		nvg_csv_filename = os.path.join(temp_dir.name,
			ftp_nvg_csv_filepath).replace('\\','/')
	print('Reading {0}...'.format(nvg_csv_filename))

	file_data = nvg.csv.read_nvg_csv_file(nvg_csv_filename)
# If the main CSV file is missing, then print an error message and quit
except FileNotFoundError:
	print('Unable to read {0}.'.format(nvg_csv_filename))
	if download_files_from_ftp_host:
		temp_dir.cleanup()
	quit()

# Read the CSV file containing the list of author aliases
print('Reading list of author aliases in {0}...'.format(
	author_aliases_csv_filename))
author_aliases_dict = read_author_aliases_csv_file(
	author_aliases_csv_filename)

# If a temporary directory was created earlier, delete the directory and
# its contents
if download_files_from_ftp_host:
	temp_dir.cleanup()

# Some file types are incorrectly formatted, so they need to be corrected
type_correction_dict = {'Games compilation': 'Compilation',
	'Sport game': 'Sports game', 'Util': 'Utility', 'UTILITY': 'Utility',
	'Utilities': 'Utility'}

for filepath in file_data:
	for type_, corrected_type in type_correction_dict.items():
		try:
			if file_data[filepath]['TYPE'] == type_:
				file_data[filepath]['TYPE'] = corrected_type
		except KeyError:
			pass
del type_correction_dict

# Create dictionaries containing ID numbers of file types (e.g. Arcade game,
# Compilation, Utility) and publication types (e.g. Commercial, Freeware,
# Type-in)

type_ids_dict = create_id_dict(['TYPE'])
publication_type_ids_dict = create_id_dict(['PUBLICATION'])


# -----------------------------
# Connect to the MySQL database
# -----------------------------

connection = None
try:
	print()
	print('Connecting to host {0}...'.format(db_hostname))
	connection = sql.connect(host = db_hostname, user = db_username,
		password = db_password, charset = 'utf8')
except sql.OperationalError as db_error:
	print(('Unable to connect to database host {0} using username {1}. Please '
		+ 'check that you have specified the correct host name, user name '
		+ 'and/or password.').format(db_hostname, db_username),
		file=sys.stderr)
	quit()

cursor = connection.cursor()


# ---------------------------------------
# Create tables for storing data from NVG
# ---------------------------------------

# If the build flag is not set, try to select the specified database; if it
# doesn't exist, then set the build flag so that it will be built
if build_db_flag == False:
	try:
		query = 'USE `{0}`'.format(db_name.replace('`', '``'))
		cursor = connection.cursor()
		cursor.execute(query)
	except sql.InternalError as db_error:
		print(('Database {0} does not exist on host {1}, so it will be '
			+ 'built.').format(db_name, db_hostname), file=sys.stderr)
		# If an InternalError is raised, it should mean that the database
		# doesn't exist, so it will need to be built
		build_db_flag = True

# If the build flag is set, then set up all the tables, procedures, functions
# and views
if build_db_flag == True:
	_setup_db(db_name)

	# Create dictionaries containing ID numbers of file types (e.g. Arcade
	# game, Compilation, Utility) and publication types (e.g. Commercial,
	# Freeware, Type-in)
	create_id_dict(type_ids_dict, ['TYPE'])
	create_id_dict(publication_type_ids_dict, ['PUBLICATION'])

# If the build flag is not set, then get the existing data from the database
# and create lists of filepaths that need to be removed and added
else:
	try:
		# Retrieve ID numbers of data that is already on the database
		existing_filepath_ids = get_existing_filepath_ids()
		publication_type_ids_dict = get_existing_publication_type_ids()
		type_ids_dict = get_existing_type_ids()
		existing_title_aliases_dict = get_existing_title_aliases()

		# Retrieve filepath author information
		existing_filepath_id_author_info = \
			get_existing_filepath_id_author_info()
	except sql.OperationalError as db_error:
		print(('Unable to retrieve data from database {0}. The following '
			'error was encountered:').format(db_name), file=sys.stderr)
		print('Error code: ' + str(db_error.args[0]), file=sys.stderr)
		print('Error message: ' + db_error.args[1], file=sys.stderr)

	# Delete filepaths from the database that aren't in the main CSV file
	# (00_table.csv)
	delete_filepaths_from_db()

	# Iterate the list of filepaths that are already on the database, and add
	# their ID numbers to the dictionary of filepaths in the main CSV file
	for filepath in sorted(file_data):
		if filepath in existing_filepath_ids:
			file_data[filepath]['ID'] = existing_filepath_ids[filepath]

# Get the existing list of author IDs from the database, if the build flag is
# not set
if build_db_flag == True:
	author_ids_dict = {}
else:
	try:
		author_ids_dict = get_existing_author_ids()
	except sql.OperationalError as db_error:
		print(('Unable to retrieve list of author ID numbers from database '
			+ '{0}. The following error was encountered:').format(db_name),
			file=sys.stderr)
		print('Error code: ' + str(db_error.args[0]), file=sys.stderr)
		print('Error message: ' + db_error.args[1], file=sys.stderr)
		connection.close()
		quit()

# Get a list of author names that need to be added to the database
authors_to_add = _get_authors_to_add()


# -------------------------
# Populate tables with data
# -------------------------

# If the build flag is set, insert data into the tables containing the type ID
# numbers, publication type ID numbers and language codes; if the build flag is
# not set, assume that all of the data has already been added to the database
message_insert_rows = 'Inserting rows into table {0}...'

if build_db_flag == True:
	try:
		# List of file types (nvg_type_ids)
		table_name = 'nvg_type_ids'
		print(message_insert_rows.format(table_name))
		insert_type_ids(type_ids_dict)

		# List of publication types (nvg_publication_type_ids)
		table_name = 'nvg_publication_type_ids'
		print(message_insert_rows.format(table_name))
		insert_publication_type_ids(publication_type_ids_dict)

		# List of language codes
		table_name = 'nvg_language_codes'
		print(message_insert_rows.format(table_name))
		insert_language_codes(language_codes_dict)

	except sql.OperationalError as db_error:
		print(('Unable to insert rows into table {0}. The following error was '
			+ 'encountered:').format(table_name), file=sys.stderr)
		print('Error code: ' + str(db_error.args[0]), file=sys.stderr)
		print('Error message: ' + db_error.args[1], file=sys.stderr)
		connection.close()
		quit()

# Add new authors and aliases to the database and get the ID numbers that are
# assigned to them after they are added
if authors_to_add:
	print('Assigning ID numbers to new authors...')
	table_name = 'nvg_author_ids'
	try:
		authors_added = insert_authors(authors_to_add)
	except sql.OperationalError as db_error:
		print(('Unable to insert authors into table {0}. The '
			+ 'following error was encountered:').format(table_name),
			file=sys.stderr)
		print('Error code: ' + str(db_error.args[0]), file=sys.stderr)
		print('Error message: ' + db_error.args[1], file=sys.stderr)
		connection.close()
		quit()

	# Update the dictionary of author IDs with the author names and IDs that
	# have been added to the database
	author_ids_dict.update(authors_added)

	# Print the author names and ID numbers that were added, if silent mode is
	# not enabled
	if silent_output == False:
		for name in sorted(authors_added,
			key=lambda name: authors_added[name]['ID']):
			print('Added author {0} (ID {1}).'.format(name,
				authors_added[name]['ID']))


# Update the alias ID numbers associated with authors, but only if the
# author aliases CSV file is available

# Create a dictionary of author names to update, with the values being the
# previous alias ID number associated with the author name
author_aliases_to_update = {}

if author_aliases_dict:
	for author_name in author_ids_dict:
		if 'Alias ID' in author_ids_dict[author_name]:
			current_alias_of_author_id = \
				author_ids_dict[author_name]['Alias ID']
		else:
			current_alias_of_author_id = None

		# If an author is not in the list of author aliases, and the author
		# name is an alias of another name (i.e. there is an alias ID number
		# assigned), delete the alias ID and add the author name to the list
		# of authors to update
		if (author_name not in author_aliases_dict and
			current_alias_of_author_id):
			author_aliases_to_update[author_name] = current_alias_of_author_id
			del author_ids_dict[author_name]['Alias ID']

		# If an author is in the list of author aliases, and there is no alias
		# ID set or the alias ID currently on the database is different to
		# what is in the list of author aliases, then update the alias ID and
		# add the author name to the list of authors to update
		elif author_name in author_aliases_dict:
			new_alias_of_author_id = \
				author_ids_dict[author_aliases_dict[author_name]]['ID']
			if ('Alias ID' not in author_ids_dict[author_name] or
				new_alias_of_author_id != current_alias_of_author_id):
				author_aliases_to_update[author_name] = current_alias_of_author_id
				author_ids_dict[author_name]['Alias ID'] = new_alias_of_author_id

	# Update the database with the new author alias information
	table_name = 'nvg_author_ids'
	print('Updating author aliases...')
	query_base = 'UPDATE {0} SET alias_of_author_id = '.format(table_name)
	message_list = []

	try:
		connection.begin()
		for author_name in sorted(author_aliases_to_update, key=str.lower):
			query = query_base
			params = []

			# The author to update no longer has an alias
			if 'Alias ID' not in author_ids_dict[author_name]:
				query += 'NULL'
				prev_alias_of_author_id = author_aliases_to_update[author_name]
				for author_name2 in author_ids_dict:
					if (author_ids_dict[author_name2]['ID'] ==
						prev_alias_of_author_id):
						message_list.append(('Removed {0} (ID {1}) as an '
							+ 'alias of {2} (ID {3}).').format(author_name,
							author_ids_dict[author_name]['ID'], author_name2,
							author_ids_dict[author_name2]['ID']))

			# The author to update has a new alias
			else:
				query += '%s'
				params.append(author_ids_dict[author_name]['Alias ID'])
				message_list.append(('Added {0} (ID {1}) as an alias of {2} '
					+ '(ID {3}).').format(author_name,
					str(author_ids_dict[author_name]['ID']),
					author_aliases_dict[author_name],
					str(author_ids_dict[author_aliases_dict[author_name]]['ID'])))

			query += ' WHERE author_id = %s'
			params.append(author_ids_dict[author_name]['ID'])

			# Update the relevant row in the table of author names
			try:
				cursor.execute(query, params)
			except sql.OperationalError as db_error:
				connection.rollback()
				print(('Unable to update author name {0} in table {1}. The '
					+ 'following error was encountered:').format(author_name,
					table_name), file=sys.stderr)
				print('Error code: ' + str(db_error.args[0]), file=sys.stderr)
				print('Error message: ' + db_error.args[1], file=sys.stderr)
				connection.close()
				quit()

		# Commit all the updates to the table of author names
		connection.commit()

		# Print a list of author aliases that were added and removed
		if silent_output == False:
			if message_list:
				print('\n'.join(message_list))
	except sql.OperationalError as db_error:
		print(('Unable to insert author {0} into table {1}. The following '
			+ 'error was encountered:').format(author_name, table_name),
			file=sys.stderr)
		print('Error code: ' + str(db_error.args[0]), file=sys.stderr)
		print('Error message: ' + db_error.args[1], file=sys.stderr)
		connection.close()
		quit()

# ----------------------------------------------------------------------------
# Convert information in the CSV file data to the corresponding ID numbers and
# codes
# ----------------------------------------------------------------------------

print('Converting data read from {0} to ID numbers...'.format(
	nvg_csv_filename))
for filepath in sorted(file_data):
	# Create a dictionary containing aliases of titles taken from the ALSO
	# KNOWN AS field; the keys are filepaths which have aliases, and the
	# values are lists containing each alias
	title_aliases_list = []
	try:
		# The ALSO KNOWN AS field is semicolon-delimited, as some aliases
		# may contain commas in their names
		for title in file_data[filepath]['ALSO KNOWN AS'].split(sep=';'):
			title_aliases_list.append(title.strip())
		file_data[filepath]['ALSO KNOWN AS'] = sorted(title_aliases_list,
			key=str.lower)
	except KeyError:
		pass

	# Convert the TYPE and PUBLICATION fields for each filepath to their
	# corresponding ID numbers
	try:
		file_data[filepath]['TYPE'] = type_ids_dict[file_data[filepath]['TYPE']]
	except KeyError:
		pass

	try:
		file_data[filepath]['PUBLICATION'] = \
			publication_type_ids_dict[file_data[filepath]['PUBLICATION']]
	except KeyError:
		pass

	# Convert the LANGUAGE field for each filepath to a list containing the
	# corresponding IETF codes for each language
	try:
		language_id_list = []

		# The LANGUAGE field is comma-delimited
		for language in file_data[filepath]['LANGUAGE'].split(sep=','):
			language = language.strip()
			try:
				language_id_list.append(language_codes_dict[language])
			# Ignore any languages for which codes have not been defined
			except KeyError:
				pass

		if language_id_list:
			file_data[filepath]['LANGUAGE'] = language_id_list
		# If no language codes have been defined for this filepath, then
		# delete the LANGUAGE field
		else:
			del file_data[filepath]['LANGUAGE']
	except KeyError:
		pass

	# Examine the fields from SUBTYPE to PROBLEMS
	
	# Version 2.00 of the file_id.diz file uses '-' in some fields to
	# represent 'not applicable'; delete these values from the file data
	for column in range(7, 13):
		try:
			if file_data[filepath][nvg.csv.csv_field_names[column]] == '-':
				del file_data[filepath][nvg.csv.csv_field_names[column]]
		except KeyError:
			pass

	# Examine the Upload Date field and check that the date is valid
	try:
		upload_date = file_data[filepath]['Upload Date'].strip()

		# If the upload date consists of a question mark, then don't perform
		# any checks, but also don't print a warning message
		if upload_date == '?':
			del file_data[filepath]['Upload Date']
		else:
			# Check that the date is in the format dd/mm/yyyy
			match = re.fullmatch('([0-9]{2})/([0-9]{2})/([0-9]{4})',
				upload_date)
			if match and datetime.date(int(match.group(3)),
				int(match.group(2)), int(match.group(1))):
				pass
			else:
				raise ValueError
	except KeyError:
		pass

	# If the upload date is not in the format dd/mm/yyyy, print a warning
	# message
	except ValueError:
		del file_data[filepath]['Upload Date']
		print(('Upload Date field in {0} (ID {1}) does not contain a valid '
			+ 'date in the format dd/mm/yyyy, so it will be set to '
			+ 'NULL.').format(filepath,
			file_data[filepath]['ID']), file=sys.stderr)

	# Examine the Uploader and COMMENTS field; the string '?' is used to
	# represent an unknown uploader, or no comments, so delete these values
	# from the file data
	for column in ['Uploader', 'COMMENTS']:
		try:
			if file_data[filepath][column] == '?':
				del file_data[filepath][column]
		except KeyError:
			pass

	# Convert the MEMORY REQUIRED field to an integer
	try:
		match = re.fullmatch('^([0-9]+)K',
			file_data[filepath]['MEMORY REQUIRED'])
		valid_memory_required_value = False

		# The only valid values permitted for the MEMORY REQUIRED field are
		# 64, 128 and 256
		if match:
			memory_required = int(match.group(1))
			if memory_required in memory_required_valid_values:
				file_data[filepath]['MEMORY REQUIRED'] = memory_required
				valid_memory_required_value = True

		if valid_memory_required_value == False:
			print(('MEMORY REQUIRED field in {0} (ID {1}) does not contain a '
				+ 'valid value, so it will be set to NULL.').format(filepath,
				file_data[filepath]['ID']), file=sys.stderr)
			del file_data[filepath]['MEMORY REQUIRED']
	except KeyError:
		pass

	# Convert names of authors to their corresponding ID numbers, by examining
	# all the author-like fields (e.g. PUBLISHER, DEVELOPER, AUTHOR)
	for field in author_field_list:
		if field in file_data[filepath]:
			author_id_list = []
			names = file_data[filepath][field]

			# The values of each field are comma-delimited
			author_names_split = names.split(sep=',')
			for name in author_names_split:
				name = name.strip()
				try:
					author_id_list.append(author_ids_dict[name]['ID'])
				except KeyError:
					print(('No ID number defined for author {0} in filepath '
						'{1}.').format(name, filepath), file=sys.stderr)
					quit()

			file_data[filepath][field] = author_id_list


# ----------------------------------
# Resume populating tables with data
# ----------------------------------

# Update information about existing filepaths on the database

table_name = 'nvg'
message_list = []
query_base = ('UPDATE ' + table_name
	+ ' SET filepath = %s, file_size = %s, title = %s, company = %s, '
	+ 'year = '
	)
update_message_displayed = False

try:
	connection.begin()
	for filepath in sorted(file_data):
		# If a filepath needs to be updated, it will have an ID number
		# assigned to it
		if 'ID' in file_data[filepath]:
			# Display the message about updating rows, but only once
			if update_message_displayed == False:
				print('Updating filepaths in table {0}...'.format(table_name))
				update_message_displayed = True

			# Set the initial query string
			query = query_base

			# Set the year of release by converting it to an integer; if the
			# conversion fails, set it to None (NULL in MySQL)
			try:
				year = int(file_data[filepath]['YEAR'])
				query += "STR_TO_DATE(%s,'%%Y')"
			except (KeyError, ValueError):
				year = None
				query += '%s'

			# Convert the list of languages to a comma-separated string
			try:
				languages = ','.join(file_data[filepath]['LANGUAGE'])
			except KeyError:
				languages = None
			query += ', language = %s, '

			query += ('type_id = %s, subtype = %s, title_screen = %s, '
				+ 'cheat_mode = %s, protected = %s, problems = %s, '
				+ 'upload_date = ')

			# Check if the upload date matches the format dd/mm/yyyy; if it
			# does not, set it to None (NULL in MySQL)
			try:
				upload_date = file_data[filepath]['Upload Date']
				if (re.fullmatch('[0-9]{2}/[0-9]{2}/\d{4}', upload_date)):
					query += "STR_TO_DATE(%s,'%%d/%%m/%%Y')"
				else:
					raise ValueError
			except (KeyError, ValueError):
				upload_date = None
				query += '%s'

			query += (', uploader = %s, comments = %s, original_title = %s, '
				+ 'publication_type_id = %s, publisher_code = %s, '
				+ 'barcode = %s, dl_code = %s, memory_required = %s, '
				+ 'protection = %s, run_command = %s'
				)

			query += ' WHERE filepath_id = %s'

			# Update the filepath
			cursor.execute(query, (filepath,
				file_data[filepath]['Size'],
				file_data[filepath].get('TITLE', None),
				file_data[filepath].get('COMPANY', None),
				year, languages,
				file_data[filepath].get('TYPE', None),
				file_data[filepath].get('SUBTYPE', None),
				file_data[filepath].get('TITLE SCREEN', None),
				file_data[filepath].get('CHEAT MODE', None),
				file_data[filepath].get('PROTECTED', None),
				file_data[filepath].get('PROBLEMS', None),
				upload_date,
				file_data[filepath].get('Uploader', None),
				file_data[filepath].get('COMMENTS', ''),
				file_data[filepath].get('ORIGINAL TITLE', None),
				file_data[filepath].get('PUBLICATION', None),
				file_data[filepath].get('PUBLISHER CODE', None),
				file_data[filepath].get('BARCODE', None),
				file_data[filepath].get('DL CODE', None),
				file_data[filepath].get('MEMORY REQUIRED', None),
				file_data[filepath].get('PROTECTION', None),
				file_data[filepath].get('RUN COMMAND', None),
				str(file_data[filepath]['ID'])
				))

	connection.commit()
	if silent_output == False:
		if(message_list):
			print('\n'.join(message_list))

except (sql.OperationalError, sql.InternalError) as db_error:
	print(('Unable to updates rows in table {0}. The following error was '
		+ 'encountered:').format(table_name), file=sys.stderr)
	print('Error code: ' + str(db_error.args[0]), file=sys.stderr)
	print('Error message: ' + db_error.args[1], file=sys.stderr)
	connection.close()
	quit()

# Insert new filepaths into the database
query_base = ('INSERT INTO ' + table_name + ' (filepath, file_size, '
	+ 'title, company, year, language, type_id, subtype, title_screen, '
	+ 'cheat_mode, protected, problems, upload_date, uploader, comments, '
	+ 'original_title, publication_type_id, publisher_code, barcode, '
	+ 'dl_code, memory_required, protection, run_command) '
	+ 'VALUES (%s, %s, %s, %s, ')
insert_message_displayed = False

try:
	connection.begin()
	for filepath in sorted(file_data):
		# If a filepath needs to be added to the database, it won't have an
		# ID number assigned to it
		if 'ID' not in file_data[filepath]:
			# Display the message about inserting rows, but only once
			if insert_message_displayed == False:
				print('Inserting filepaths into table {0}...'.format(
					table_name))
				insert_message_displayed = True

			# Set the initial query string
			query = query_base

			# Set the year of release by converting it to an integer; if the
			# conversion fails, set it to None (NULL in MySQL)
			try:
				year = int(file_data[filepath]['YEAR'])
				query += "STR_TO_DATE(%s,'%%Y')"
			except (KeyError, ValueError):
				year = None
				query += '%s'

			# Convert the list of languages to a comma-separated string
			try:
				languages = ','.join(file_data[filepath]['LANGUAGE'])
			except KeyError:
				languages = None
			query += ', %s, '

			query += '%s, %s, %s, %s, %s, %s, '

			# Check if the upload date matches the format dd/mm/yyyy; if it
			# does not, set it to None (NULL in MySQL)
			try:
				upload_date = file_data[filepath]['Upload Date']
				if (re.fullmatch('\d{2}/\d{2}/\d{4}', upload_date)):
					query += "STR_TO_DATE(%s,'%%d/%%m/%%Y')"
				else:
					raise ValueError
			except (KeyError, ValueError):
				upload_date = None
				query += '%s'

			query += ', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'

			# Insert the new filepath into the table
			cursor.execute(query, (
				filepath,
				file_data[filepath]['Size'],
				file_data[filepath].get('TITLE', None),
				file_data[filepath].get('COMPANY', None),
				year, languages,
				file_data[filepath].get('TYPE', None),
				file_data[filepath].get('SUBTYPE', None),
				file_data[filepath].get('TITLE SCREEN', None),
				file_data[filepath].get('CHEAT MODE', None),
				file_data[filepath].get('PROTECTED', None),
				file_data[filepath].get('PROBLEMS', None),
				upload_date,
				file_data[filepath].get('Uploader', None),
				file_data[filepath].get('COMMENTS', ''),
				file_data[filepath].get('ORIGINAL TITLE', None),
				file_data[filepath].get('PUBLICATION', None),
				file_data[filepath].get('PUBLISHER CODE', None),
				file_data[filepath].get('BARCODE', None),
				file_data[filepath].get('DL CODE', None),
				file_data[filepath].get('MEMORY REQUIRED', None),
				file_data[filepath].get('PROTECTION', None),
				file_data[filepath].get('RUN COMMAND', None))
			)

			# Get the ID number of the new filepath
			query = 'SELECT LAST_INSERT_ID()'
			cursor.execute(query)
			filepath_id = cursor.fetchone()[0]
			file_data[filepath]['ID'] = filepath_id
			message_list.append('Added {0} (ID {1}).'.format(filepath,
				filepath_id))

	connection.commit()
	if silent_output == False:
		if(message_list):
			print('\n'.join(message_list))

except (sql.OperationalError, sql.InternalError) as db_error:
	print(('Unable to insert rows into table {0}. The following error was '
		+ 'encountered:').format(table_name), file=sys.stderr)
	print('Error code: ' + str(db_error.args[0]), file=sys.stderr)
	print('Error message: ' + db_error.args[1], file=sys.stderr)
	connection.close()
	quit()

# Insert author information, associating authors with filepaths
table_name = 'nvg_file_authors'
delete_query = ('DELETE FROM ' + table_name
	+ ' WHERE filepath_id = %s AND author_type = %s')
insert_query = ('INSERT INTO ' + table_name + ' (filepath_id, author_id, '
	+ 'author_type, author_index) VALUES (%s, %s, %s, %s)')
message_list = []

try:
	connection.begin()

	# If the build flag is set, there is no need to check the existing
	# author information in the database
	if build_db_flag == True:
		print('Inserting author information into table {0}...'.format(
			table_name))
		for filepath in sorted(file_data):
			filepath_id = file_data[filepath]['ID']
			author_info_updated = 0

			# Iterate through each author type (e.g. PUBLISHER, DEVELOPER,
			# AUTHOR)
			for field in author_field_list:
				# If there is any information for the specified author type
				# in the main CSV file, then add it to the database
				if field in file_data[filepath]:
					for index in range(len(file_data[filepath][field])):
						cursor.execute(insert_query, (filepath_id,
							file_data[filepath][field][index], field, index))
					author_info_updated |= 1

			if author_info_updated:
				message_list.append(('Added author information for {0} (ID '
					+ '{1}).').format(filepath, filepath_id))
		
	# If the build flag is not set, then compare the existing author
	# information for each filepath in the main CSV file with what is already
	# in the database
	else:
		print('Updating author information in table {0}...'.format(
			table_name))

		for filepath in sorted(file_data):
			filepath_id = file_data[filepath]['ID']
			author_info_updated = 0

			# Iterate through each author type (e.g. PUBLISHER, DEVELOPER,
			# AUTHOR)
			for field in author_field_list:
				author_info_in_csv_file = False
				author_info_in_db = False
				issue_delete_query = False
				issue_insert_query = False

				# Is there any author information in the main CSV file?
				if field in file_data[filepath]:
					author_info_in_csv_file = True
				# Is there any author information already in the database?
				if (filepath_id in existing_filepath_id_author_info and
					field in existing_filepath_id_author_info[filepath_id]):
					author_info_in_db = True

				# If there is author information in the CSV file but not the
				# database, it needs to be added to the database
				if (author_info_in_csv_file == True and
					author_info_in_db == False):
					issue_insert_query = True
					author_info_updated |= 1
				# If there is author information in the database but not the
				# CSV file, it needs to be deleted from the database
				elif (author_info_in_csv_file == False and
					author_info_in_db == True):
					issue_delete_query = True
					author_info_updated |= 2
				# If there is author information in both the CSV file and the
				# database, compare them; if they are different, the
				# information in the database needs to be updated
				elif (author_info_in_csv_file == True and
					author_info_in_db == True and
					file_data[filepath][field] != existing_filepath_id_author_info[filepath_id][field]):
					issue_delete_query = True
					issue_insert_query = True
					author_info_updated |= 3

				# Issue DELETE and INSERT queries as necessary
				if issue_delete_query:
					cursor.execute(delete_query, (filepath_id, field))
				if issue_insert_query:
					for index in range(len(file_data[filepath][field])):
						cursor.execute(insert_query, (filepath_id,
							file_data[filepath][field][index], field, index))

			# If the author information on the database has been modified,
			# display a message to state this

			# The status of author_info_updated is as follows:
			# 1 = information added to database
			# 2 = information deleted from database
			# 3 = information added to and deleted from database
			if author_info_updated:
				message_base = ''
				if author_info_updated == 1:
					message_base = 'Added'
				elif author_info_updated in (2, 3):
					message_base = 'Updated'
				message_list.append(message_base + (' author information '
					+ 'for {0} (ID {1}).'.format(filepath, filepath_id)))

	connection.commit()
	if silent_output == False:
		if(message_list):
			print('\n'.join(message_list))

except (sql.OperationalError, sql.InternalError) as db_error:
	print(('Unable to insert rows into table {0}. The following error was '
		+ 'encountered:').format(table_name), file=sys.stderr)
	print('Error code: ' + str(db_error.args[0]), file=sys.stderr)
	print('Error message: ' + db_error.args[1], file=sys.stderr)
	connection.close()
	quit()

# Insert aliases of titles
table_name = 'nvg_title_aliases'
delete_query = ('DELETE FROM ' + table_name + ' WHERE filepath_id = %s')
insert_query = ('INSERT INTO ' + table_name + ' VALUES (%s, %s)')
message_list = []

try:
	connection.begin()

	# If the build flag is set, there is no need to check the existing title
	# alias information in the database
	if build_db_flag == True:
		print('Inserting title aliases into table {0}...'.format(table_name))
		for filepath in sorted(file_data):
			filepath_id = file_data[filepath]['ID']

			if 'ALSO KNOWN AS' in file_data[filepath]:
				for title in file_data[filepath]['ALSO KNOWN AS']:
					cursor.execute(insert_query, (filepath_id, title))
				message_list.append(('Added title aliases for {0} '
					+ '(ID {1}).').format(filepath, filepath_id))

	# If the build flag is not set, then compare the existing title alias
	# information for each filepath in the main CSV file with what is already
	# in the database
	else:
		print('Updating title alias information in table {0}...'.format(
			table_name))

		for filepath in sorted(file_data):
			filepath_id = file_data[filepath]['ID']
			title_alias_info_in_csv_file = False
			title_alias_info_in_db = False
			issue_delete_query = False
			issue_insert_query = False
			title_alias_info_updated = 0

			# Is there any title alias information in the main CSV file?
			if 'ALSO KNOWN AS' in file_data[filepath]:
				title_alias_info_in_csv_file = True
			# Is there any title alias information already in the database?
			if (filepath_id in existing_title_aliases_dict):
				title_alias_info_in_db = True

			# If there is title alias information in the CSV file but not the
			# database, it needs to be added to the database
			if (title_alias_info_in_csv_file == True and
				title_alias_info_in_db == False):
				issue_insert_query = True
				title_alias_info_updated |= 1
			# If there is title alias information in the database but not the
			# CSV file, it needs to be deleted from the database
			elif (title_alias_info_in_csv_file == False and
				title_alias_info_in_db == True):
				issue_delete_query = True
				title_alias_info_updated |= 2
			# If there is title alias information in both the CSV file and the
			# database, compare them; if they are different, the information
			# in the database needs to be updated
			elif (title_alias_info_in_csv_file == True and
				title_alias_info_in_db == True and
				set(file_data[filepath]['ALSO KNOWN AS']) !=
				set(existing_title_aliases_dict[filepath_id])):
				issue_delete_query = True
				issue_insert_query = True
				title_alias_info_updated |= 3

			# Issue DELETE and INSERT queries as necessary
			if issue_delete_query:
				cursor.execute(delete_query, (filepath_id))
			if issue_insert_query:
				for title_alias in file_data[filepath]['ALSO KNOWN AS']:
					cursor.execute(insert_query, (filepath_id, title_alias))

			# If the author information on the database has been modified,
			# display a message to state this

			# The status of title_alias_info_updated is as follows:
			# 1 = information added to database
			# 2 = information deleted from database
			# 3 = information added to and deleted from database
			if title_alias_info_updated:
				message_base = ''
				if title_alias_info_updated == 1:
					message_base = 'Added'
				elif title_alias_info_updated in (2, 3):
					message_base = 'Updated'
				message_list.append(message_base + (' title alias information '
					+ 'for {0} (ID {1}).'.format(filepath, filepath_id)))

	connection.commit()
	if silent_output == False:
		if(message_list):
			print('\n'.join(message_list))

except (sql.OperationalError, sql.InternalError) as db_error:
	print(('Unable to insert rows into table {0}. The following error was '
		+ 'encountered:').format(table_name), file=sys.stderr)
	print('Error code: ' + str(db_error.args[0]), file=sys.stderr)
	print('Error message: ' + db_error.args[1], file=sys.stderr)
	connection.close()
	quit()

# Everything has been set up, so close the connection
connection.close()
