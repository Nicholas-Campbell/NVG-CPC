"""Set up a MySQL database containing information about files on the Amstrad CPC
software archive on NVG.

The CSV file containing this information can be downloaded from the archive at
the following URL:
<ftp://ftp.nvg.ntnu.no/pub/cpc/00_table.csv>
"""

# by Nicholas Campbell 2017-2018
# Last update: 2018-03-05

import argparse
import csv
import getopt
import getpass
import nvg.csv
import os
import pymysql as sql
import re
import sys
import warnings

# --------------------------------------------
# Initialise variables, dictionaries and lists
# --------------------------------------------

# Data relating to CSV files from the NVG archive
nvg_csv_filename = r'00_table.csv'
author_aliases_csv_filename = r'author_aliases.csv'
file_data = {}
csv_field_name = ['Action','File Path','Size','TITLE',
	'COMPANY','YEAR','LANGUAGE','TYPE','SUBTYPE','TITLE SCREEN','CHEAT MODE',
	'PROTECTED','PROBLEMS','Upload Date','Uploader','COMMENTS',

	'ALSO KNOWN AS','ORIGINAL TITLE','PUBLISHER','RE-RELEASED BY',
	'PUBLICATION','PUBLISHER CODE','BARCODE','DL CODE','CRACKER','DEVELOPER',
	'AUTHOR','DESIGNER','ARTIST','MUSICIAN','MEMORY REQUIRED','PROTECTION',
	'RUN COMMAND']
max_field_length = [0] * len(csv_field_name)

author_field_list = ['PUBLISHER','RE-RELEASED BY','CRACKER','DEVELOPER',
	'AUTHOR','DESIGNER','ARTIST','MUSICIAN']
author_set_def = ','.join([repr(type) for type in author_field_list])

# Database connections and filenames
db_name = 'cpc'
db_trigger_source_file = 'create_triggers.sql'
db_stored_routine_source_file = 'create_stored_routines.sql'
db_view_source_file = 'create_views.sql'

# Get the list of IETF language codes in alphabetical order and store
# them in a comma-delimited string for use in defining the main table later
# on
language_code_dict = {
	'Catalan': 'ca', 'Danish': 'da', 'Dutch': 'nl', 'English': 'en',
	'English (American)': 'en-US', 'French': 'fr', 'German': 'de',
	'Greek': 'el', 'Irish': 'ga', 'Italian': 'it',
	'Portuguese (Brazilian)': 'pt-BR', 'Spanish': 'es', 'Swedish' : 'sv'
}
language_code_list = []
for language, code in sorted(language_code_dict.items()):
	language_code_list.append(code)
language_code_list.sort(key=str.lower)
language_set_def = ','.join([repr(code) for code in language_code_list])
del language_code_list


# Create a dictionary containing entries from a list of field names, sort
# the dictionary in alphabetical order, and assign ID numbers to each entry

# The value of each field name could have more than one entry, so a delimiter
# needs to be specified as well (usually a comma)

def create_id_dict(dict, field_list, delimiter=','):
	for filepath in file_data:
		for field in field_list:
			try:
				name = file_data[filepath][field]

				split_pub = name.split(sep=delimiter)
				for name in split_pub:
					dict[name.strip()] = 0
			except KeyError:
				pass

	id_num = 1
	for name in sorted(dict, key = str.lower):
		dict[name] = id_num
		id_num += 1

# Display a help message

def print_help():
	indent = ' '*22
	print('Usage: {0} [OPTIONS]\n'.format(sys.argv[0]))
	print('The following options can be used:')
	print('  -?, --help          Display this help message and exit.')
	print('  -h, --host=name     Connect to host.')
	print('  -p, --password=name Password to use when connecting to host. If '
		+ 'no password\n'
		+ indent + 'is specified then the program will ask for the user to\n'
		+ indent + 'input it.')
	print('  -u, --user=name     Username to use when connecting to host. If '
		+ 'no username\n'
		+ indent + 'is specified then the current login username will be\n'
		+ indent + 'used.')


# ------------
# Main program
# ------------

# Parse command line arguments
#
# The allowed options are intentionally similar to those used by MySQL

db_hostname = 'localhost'
db_username = getpass.getuser()
db_password = None

try:
	optlist, args = getopt.getopt(sys.argv[1:], '?h:u:p:',
		['help', 'host=', 'user=', 'password='])
	for (option, value) in optlist:
		# Print the help message and quit
		if option in ['-?', '--help']:
			print_help()
			quit()

		# Database connection options
		elif option in ['-h', '--host']:
			db_hostname = value
		elif option in ['-u', '--user']:
			db_username = value
		elif option in ['-p', '--password']:
			db_password = value
except getopt.GetoptError as argument_parse_error:
	print('Error while parsing options: ' + argument_parse_error.msg)
	quit()

# If no password is supplied in the command line options, ask for one
if db_password == None:
	db_password = getpass.getpass(prompt = 'Enter password: ')


# ------------------------------
# Read and process the CSV files
# ------------------------------

print('Reading ' + nvg_csv_filename + '...')
file_data = nvg.csv.read_nvg_csv_file(nvg_csv_filename)

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
type_id_dict = {}

# Create dictionaries containing ID numbers of file types (e.g. Arcade game,
# Compilation, Utility) and publication types (e.g. Commercial, Freeware,
# Type-in)

create_id_dict(type_id_dict, ['TYPE'])
del type_correction_dict

publication_type_id_dict = {}
create_id_dict(publication_type_id_dict, ['PUBLICATION'])

# Iterate through each entry in the file data

filepath_id = 1
title_alias_dict = {}
for filepath in sorted(file_data):
	# Assign a unique ID number to each file
	file_data[filepath]['ID'] = filepath_id

	# Create a dictionary containing aliases of titles taken from the ALSO
	# KNOWN AS field; the keys are filepaths which have aliases, and the
	# values are lists containing each alias
	title_alias_list = []
	try:
		# The ALSO KNOWN AS field is semicolon-delimited, as some aliases
		# may contain commas in their names
		for title in file_data[filepath]['ALSO KNOWN AS'].split(sep=';'):
			title = title.strip()
			title_alias_list.append(title)
		title_alias_dict[filepath] = title_alias_list
	except KeyError:
		pass

	# Convert the TYPE and PUBLICATION fields for each filepath to their
	# corresponding ID numbers
	try:
		file_data[filepath]['TYPE'] = type_id_dict[file_data[filepath]['TYPE']]
	except KeyError:
		pass

	try:
		file_data[filepath]['PUBLICATION'] = \
			publication_type_id_dict[file_data[filepath]['PUBLICATION']]
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
				language_id_list.append(language_code_dict[language])
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
			if file_data[filepath][csv_field_name[column]] == '-':
				del file_data[filepath][csv_field_name[column]]
		except KeyError:
			pass
	
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
		match = re.fullmatch('^(\d+)K',
			file_data[filepath]['MEMORY REQUIRED'])
		if match:
			file_data[filepath]['MEMORY REQUIRED'] = int(match.group(1))
		else:
			del file_data[filepath]['MEMORY REQUIRED']
	except KeyError:
		pass

	filepath_id += 1

# Convert author-like fields in the file data (e.g. PUBLISHER, DEVELOPER,
# AUTHOR) to a list containing the ID numbers of the publisher(s)
author_id_dict = {}
for filepath in file_data:
	for field in author_field_list:
		try:
			name = file_data[filepath][field]
			
			# Assume that the values of each field are comma-delimited
			split_pub = name.split(sep=',')
			for name in split_pub:
				author_id_dict[name.strip()] = {}
		except KeyError:
			pass

# Read the CSV file containing the list of author aliases
#
# Each line in this file consists of two columns; the first contains the
# alias, and the second contains the author's actual name. These are added to
# a dictionary
author_aliases_dict = {}
line = 0
print('Reading list of author aliases in {0}...'.format(
	author_aliases_csv_filename))
try:
	csv_file = open(author_aliases_csv_filename, newline='')
	csv_file_reader = csv.reader(csv_file, dialect='excel', delimiter=',')

	# Skip the first line of the CSV file, which contains the field names
	next(csv_file_reader)
	line += 1

	# Read all the remaining lines in the CSV file one at a time
	for row in csv_file_reader:
		author_aliases_dict[row[0]] = row[1]

		line += 1
	csv_file.close()
except FileNotFoundError as file_error:
	print(('Unable to locate {0}. No information about author aliases will be '
		+ 'added!').format(author_aliases_csv_filename),
		file=sys.stderr)

# Add aliases and names in the author aliases CSV file to the main list of
# authors
print('Adding aliases to list of authors...')
for alias, name in author_aliases_dict.items():
	if alias not in author_id_dict:
		author_id_dict[alias] = {}
	if name not in author_id_dict:
		author_id_dict[name] = {}

# Assign ID numbers to all authors
id_num = 1
print('Assigning ID numbers to authors...')
for name in sorted(author_id_dict, key = str.lower):
	author_id_dict[name]['ID'] = id_num
	id_num += 1

# Replace aliases of author names with their ID numbers
print('Replacing author alias names with ID numbers...')
for name in sorted(author_aliases_dict, key = str.lower):
	alias = author_aliases_dict[name]
	author_id_dict[name]['Alias ID'] = author_id_dict[alias]['ID']

# Convert details in author-like fields (e.g. PUBLISHER, DEVELOPER, AUTHOR)
# to lists of their corresponding ID numbers
print('Converting author information to ID numbers...')
for filepath in file_data:
	author_id_list = {}
	for field in author_field_list:
		try:
			author_id_list = []

			# All author-like fields are comma-delimited
			for name in file_data[filepath][field].split(sep=','):
				name = name.strip()
				author_id_list.append(author_id_dict[name]['ID'])
			if len(author_id_list) > 0:
				file_data[filepath][field] = author_id_list

		except KeyError:
			pass


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
		+ 'and/or password.').format(db_hostname, db_username))
	quit()

# Delete the database if it exists, and suppress any warning messages that
# are displayed (e.g. the database doesn't exist)
#
# To set up the database, the following privileges need to be granted to the
# relevant user:
# CREATE, DROP, REFERENCES, ALTER ROUTINE, CREATE ROUTINE, TRIGGER, INSERT

cursor = connection.cursor()
try:
	warnings.simplefilter('ignore')

	# MySQL doesn't like enclosing database names in quotes, which means that
	# the statements below cannot be parameterised; could this potentially
	# lead to SQL injection attacks?
	cursor.execute('DROP DATABASE IF EXISTS ' + db_name)
	cursor.execute('CREATE DATABASE ' + db_name)
	cursor.execute('USE ' + db_name)
	warnings.simplefilter('default')
except sql.OperationalError as db_error:
	print(('Unable to set up database {0} on host {1}. Please check with your '
		+ 'database administrator that you have the appropriate privileges to '
		+ 'create, drop and set up databases.').format(db_name, db_hostname))
	connection.close()
	quit()


# ---------------------------------------
# Create tables for storing data from NVG
# ---------------------------------------

try:
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
except sql.OperationalError as db_error:
	print(('Unable to create table {0}. The following error was '
		+ 'encountered:').format(table_name))
	print('Error code: ' + str(db_error.args[0]))
	print('Error message: ' + db_error.args[1])
	connection.close()
	quit()

# Set up the triggers, stored procedures, functions and views by running MySQL
# directly and processing the SQL files
db_command_base = ('mysql -h {0} -u {1} --password={2} {3}').format(
	db_hostname, db_username, db_password, db_name)

# Triggers
print('Reading triggers from source file {0}...'.format(db_trigger_source_file))
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
db_command = (db_command_base + ' < {0}').format(db_stored_routine_source_file)
if os.system(db_command) != 0:
	print(('Unable to create stored procedures and functions for database {0} '
		+ 'on host {1}. Please check that the PATH environment variable is '
		+ 'set correctly, or check with your database administrator that you '
		+ 'have the appropriate privileges to create and alter stored '
		+ 'procedures and functions.').format(db_name, db_hostname))
	connection.close()
	quit()

# Views
print(('Reading views from source file {0}...').format(db_view_source_file))
db_command = (db_command_base + ' < {0}').format(db_view_source_file)
if os.system(db_command) != 0:
	print(('Unable to create views for database {0} '
		+ 'on host {1}. Please check that the PATH environment variable is '
		+ 'set correctly, or check with your database administrator that you '
		+ 'have the appropriate privileges to create and alter views.').format(
		db_name, db_hostname))
	connection.close()
	quit()


# -----------------------------
# Populate the tables with data
# -----------------------------

try:
	message_insert_rows = 'Inserting rows into table {0}...'

	# List of file types (nvg_type_ids)
	table_name = 'nvg_type_ids'
	print(message_insert_rows.format(table_name))
	query = 'INSERT INTO ' + table_name + ' VALUES (%s, %s)'
	connection.begin()
	for type in sorted(type_id_dict):
		cursor.execute(query, (type_id_dict[type], type))
	connection.commit()

	# List of publication types (nvg_publication_type_ids)
	table_name = 'nvg_publication_type_ids'
	print(message_insert_rows.format(table_name))
	query = 'INSERT INTO ' + table_name + ' VALUES (%s, %s)'
	connection.begin()
	for type in sorted(publication_type_id_dict):
		cursor.execute(query, (publication_type_id_dict[type], type))
	connection.commit()

	# List of language codes
	table_name = 'nvg_language_codes'
	print(message_insert_rows.format(table_name))
	query = 'INSERT INTO ' + table_name + ' VALUES (%s, %s)'
	connection.begin()
	for language, code in sorted(language_code_dict.items()):
		cursor.execute(query, (code, language))
	connection.commit()

	# List of developer names and IDs (nvg_author_ids)
	table_name = 'nvg_author_ids'
	print(message_insert_rows.format(table_name))
	query = 'INSERT INTO ' + table_name + ' VALUES (%s, %s, NULL)'
	connection.begin()
	for author in sorted(author_id_dict):
		cursor.execute(query, (author_id_dict[author]['ID'], author))
	connection.commit()
except sql.OperationalError as db_error:
	print(('Unable to insert rows into table {0}. The following error was '
		+ 'encountered:').format(table_name))
	print('Error code: ' + str(db_error.args[0]))
	print('Error message: ' + db_error.args[1])
	connection.close()
	quit()

# Add author alias IDs to the table of authors; this can only be done after
# all the author IDs have been added to the database
if author_aliases_dict:
	try:
		table_name = 'nvg_author_ids'
		print('Adding author alias IDs to {0}...'.format(table_name))
		query = ('UPDATE nvg_author_ids\n'
		'SET alias_of_author_id = %s WHERE author_id = %s')
		connection.begin()
		for author in sorted(author_id_dict):
			if 'Alias ID' in author_id_dict[author]:
				cursor.execute(query, (author_id_dict[author]['Alias ID'],
					author_id_dict[author]['ID']))
		connection.commit()
	except sql.OperationalError as db_error:
		print(('Unable to add author aliases to {0}. The following error was '
			+ 'encountered:').format(table_name))
		print('Error code: ' + str(db_error.args[0]))
		print('Error message: ' + db_error.args[1])
		connection.close()
		quit()

try:
	# Main table (nvg)
	table_name = 'nvg'
	print(message_insert_rows.format(table_name))
	connection.begin()
	for filepath in sorted(file_data):
		# Set the initial query string
		query = ('INSERT INTO ' + table_name + ' (filepath_id, filepath, '
			'file_size, title, company, year, language, type_id, subtype, '
			'title_screen, cheat_mode, protected, problems, upload_date, uploader, '
			'comments, original_title, publication_type_id, publisher_code, '
			'barcode, dl_code, memory_required, protection, run_command) '
			'VALUES (%s, %s, %s, %s, %s, ')

		# Set the year; if the year is defined as '19??', it will be converted
		# to None (NULL in MySQL)
		try:
			year = int(file_data[filepath]['YEAR'])
			query += "STR_TO_DATE(%s,'%%Y')"
		except (KeyError, ValueError):
			year = None
			query += "%s"
		
		# Set the languages
		query += ', %s, '
		try:
			languages = ','.join(file_data[filepath]['LANGUAGE'])
		except KeyError:
			languages = None

		query += '%s, %s, %s, %s, %s, %s, '
		
		# Set the upload date and the name of the uploader
		try:
			upload_date = file_data[filepath]['Upload Date']
			if (re.fullmatch('\d{2}/\d{2}/\d{4}', upload_date)):
				query += "STR_TO_DATE(%s,'%%d/%%m/%%Y'), "
			else:
				raise ValueError
		except (KeyError, ValueError):
			upload_date = None
			query += '%s, '
		
		query += '%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'
		cursor.execute(query, (
			file_data[filepath]['ID'],
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

	# Insert author IDs; this sorts the authors by name in a case-insensitive
	# manner
	table_name = 'nvg_file_authors'
	print(message_insert_rows.format(table_name))
	query = ('INSERT INTO ' + table_name + ' (filepath_id, author_id, '
	'author_type, author_index) VALUES (%s, %s, %s, %s)')
	connection.begin()
	for filepath in sorted(file_data):
		for field in sorted(author_field_list, key = str.lower):
			try:
				for index in range(len(file_data[filepath][field])):
					cursor.execute(query, (file_data[filepath]['ID'],
						file_data[filepath][field][index], field, index))
			except KeyError:
				pass
	connection.commit()

	# Title aliases table (nvg_title_aliases)
	table_name = 'nvg_title_aliases'
	print(message_insert_rows.format(table_name))
	query = ('INSERT INTO ' + table_name + ' (filepath_id, title) '
		+ 'VALUES (%s, %s)')
	connection.begin()
	for filepath in sorted(title_alias_dict):
		for index in range(len(title_alias_dict[filepath])):
			cursor.execute(query, (file_data[filepath]['ID'],
				title_alias_dict[filepath][index]))
	connection.commit()
except sql.OperationalError:
	print(('Unable to insert rows into table {0}. The following error was '
		+ 'encountered:').format(table_name))
	print('Error code: ' + str(db_error.args[0]))
	print('Error message: ' + db_error.args[1])
	connection.close()
	quit()

# Everything has been set up, so close the connection
connection.close()
