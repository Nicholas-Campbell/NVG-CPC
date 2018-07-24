"""Set up a MySQL database containing information about files on the Amstrad CPC
software archive on NVG.

The CSV file containing this information can be downloaded from the archive at
the following URL:
<ftp://ftp.nvg.ntnu.no/pub/cpc/00_table.csv>
"""

# by Nicholas Campbell 2017-2018
# Last update: 2018-07-22

import csv
import datetime
import ftplib
import getopt
import getpass
import nvg.csv
import nvg.database
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
cpcpower_csv_filename = r'cpcpower.csv'

author_field_list = ['PUBLISHER','RE-RELEASED BY','CRACKER','DEVELOPER',
	'AUTHOR','DESIGNER','ARTIST','MUSICIAN']
author_set_def = ','.join([repr(type) for type in author_field_list])

# Permitted values for the MEMORY REQUIRED field in the main CSV file
memory_required_valid_values = [64, 128, 256]

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


def _print_help():
	"""Display the help message associated with this program.
"""
	indent = ' '*22
	print('Usage: {0} [OPTIONS] [database]\n'.format(sys.argv[0]))
	print('The following options can be used:')
	print('  -?, --help          Display this help message and exit.')
	print('  --build             Rebuild the entire database.')
	print('  -D, --database=name Database to use.')
	print('  --ftp-download      Download CSV files from the NVG FTP site\n'
		+ indent + '(ftp://ftp.nvg.ntnu.no/pub/cpc/) instead of using '
		+ 'locally\n'
		+ indent + 'stored files.')
	print('  -h, --host=name     Connect to host.')
	print('  -p, --password=name Password to use when connecting to host.')
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
    connection must already be established and the user must be logged on.
dir: The directory to download the specified file to.
filepath: The path of the file to download from the FTP site.
file_transfer_mode: The file transfer mode to use ('a' = ASCII, 'b' or 'i' =
    image (binary)).

Returns:
Nothing.
"""
	# Convert the file transfer mode to lower case, and if it is not a valid
	# mode, raise an exception
	file_transfer_mode = file_transfer_mode.lower()
	if file_transfer_mode not in ['a', 'b', 'i']:
		raise ValueError

	# Check that the directory to download to exists; if it doesn't, then
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


def read_author_aliases_csv_file(csv_filename):
	"""Read a CSV file containing a list of author names and aliases associated with
them.

Each line of the CSV file consists of two columns; the first contains the
alias, and the second contains the author's actual name. The file is assumed
to be encoded in Latin-1 (ISO-8859-1).

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
	cursor = db.connection.cursor()
	dict = {}

	# Convert backticks in arguments to double backticks so they can be used
	# in the query below
	table = table.replace('`', '``')
	key_column = key_column.replace('`', '``')
	value_column = value_column.replace('`', '``')

	db_name_escaped = db_name.replace('`', '``')
	query = 'USE `{0}`'.format(db_name_escaped)
	cursor.execute(query)
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
	cursor = db.connection.cursor()
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

# Retrieve all the existing filepath author information from the database

def get_existing_filepath_id_author_info():
	cursor = db.connection.cursor()
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
	cursor = db.connection.cursor()
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


# ------------
# Main program
# ------------

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
ftp_cpcpower_csv_filepath = 'pub/cpc/cpcpower.csv'
download_files_from_ftp_host_flag = False


# Parse command line arguments
#
# The allowed options are intentionally similar to those used by MySQL

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
				download_files_from_ftp_host_flag = True

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

file_data = {}		# Dictionary for storing information about files on NVG
cpcpower_data = {}	# Dictionary for storing CPCSOFTS ID numbers of files on
					# NVG

# If the FTP download option has been selected, then download the relevant
# files from the NVG FTP site
if download_files_from_ftp_host_flag:
	# Connect and log on to the FTP host
	try:
		print('Connecting to {0}...'.format(ftp_hostname))
		ftp = ftplib.FTP(ftp_hostname)
		ftp.login(user='anonymous', passwd='anonymous@nvg.ntnu.no')
	# socket.gaierror exception is raised if it is not possible to connect
	# to the FTP host
	except (socket.gaierror, TimeoutError):
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
	file_list = [ftp_nvg_csv_filepath, ftp_cpcpower_csv_filepath]
	for file_to_download in file_list:
		try:
			print('Downloading {0} from {1}...'.format(file_to_download,
				ftp_hostname))
			download_file_from_ftp_host(ftp, temp_dir.name,
				file_to_download, 'a')
		except ftplib.error_perm as ftp_error:
			print(('Unable to download {0} from {1}. The following error '
				+ 'occurred:').format(file_to_download, ftp_hostname),
				file=sys.stderr)
			print(ftp_error, file=sys.stderr)

	# Close the FTP connection
	ftp.quit()

# Read the main CSV file
try:
	if download_files_from_ftp_host_flag:
		nvg_csv_filename = os.path.join(temp_dir.name,
			ftp_nvg_csv_filepath).replace('\\','/')
	print('Reading {0}...'.format(nvg_csv_filename))
	file_data = nvg.csv.read_nvg_csv_file(nvg_csv_filename)
# If the main CSV file is missing, then print an error message and quit
except FileNotFoundError:
	print('Unable to read {0}.'.format(nvg_csv_filename))
	if download_files_from_ftp_host_flag:
		temp_dir.cleanup()
	quit()

# Read the CSV file containing the list of author aliases
print('Reading list of author aliases in {0}...'.format(
	author_aliases_csv_filename))
author_aliases_dict = read_author_aliases_csv_file(
	author_aliases_csv_filename)

# Read the CSV file containing the list of CPCSOFTS ID numbers associated with
# files on NVG
try:
	if download_files_from_ftp_host_flag:
		cpcpower_csv_filename = os.path.join(temp_dir.name,
			ftp_cpcpower_csv_filepath).replace('\\','/')
	print('Reading list of CPCSOFTS ID numbers in {0}...'.format(
		cpcpower_csv_filename))
	cpcpower_data = nvg.csv.read_cpcpower_csv_file(cpcpower_csv_filename)
# If the CSV file is missing, then print an error message; however, the
# database can still be maintained without it
except FileNotFoundError:
	print(('Unable to read {0}. CPCSOFTS ID numbers will not be added or '
		+ 'updated.').format(cpcpower_csv_filename))
# If a temporary directory was created earlier, delete the directory and
# its contents
finally:
	if download_files_from_ftp_host_flag:
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

# Check if any of the filepaths in the main CSV file are not included in
# the CPC-POWER CSV file
if cpcpower_data:
	for filepath in file_data:
		if filepath not in cpcpower_data:
			print(('{0} is listed in {1} but is not listed in '
				+ '{2}.').format(filepath, nvg_csv_filename,
				cpcpower_csv_filename), file=sys.stderr)

	# Now check if any of the ZIP files listed in the CPC-POWER CSV file
	# are not included in the main CSV file
	for filepath in cpcpower_data:
		if filepath[-4:].lower() == '.zip':
			if filepath not in file_data:
				print(('{0} is listed in {1} but is not listed in '
					+ '{2}.').format(filepath, cpcpower_csv_filename,
					nvg_csv_filename), file=sys.stderr)


# -----------------------------
# Connect to the MySQL database
# -----------------------------

db = None
try:
	print()
	print('Connecting to host {0}...'.format(db_hostname))
	db = nvg.database.Database(db_hostname, db_name, db_username, db_password)
	db.connect(use_database=False)
except (sql.OperationalError, sql.InternalError) as db_error:
	print(('Unable to connect to database host {0} using username {1}. Please '
		+ 'check that you have specified the correct host name, user name '
		+ 'and/or password.').format(db_hostname, db_username),
		file=sys.stderr)
	quit()

# ---------------------------------------
# Create tables for storing data from NVG
# ---------------------------------------

# If the build flag is not set, check that the specified database exists on
# the server; if it doesn't exist, then set the build flag so that it will be
# built
if build_db_flag == False:
	query = 'SHOW DATABASES LIKE %s'
	cursor = db.connection.cursor()

	cursor.execute(query, (db_name))
	row = cursor.fetchone()
	if row == None:
		print(('Database {0} does not exist on host {1}, so it will be '
			+ 'built.').format(db_name, db_hostname), file=sys.stderr)
		build_db_flag = True

# If the build flag is set, then set up all the tables, triggers, functions,
# procedures and views
if build_db_flag == True:
	db.build()

	# Create dictionaries containing ID numbers of file types (e.g. Arcade
	# game, Compilation, Utility) and publication types (e.g. Commercial,
	# Freeware, Type-in)
	type_ids_dict = create_id_dict(['TYPE'])
	publication_type_ids_dict = create_id_dict(['PUBLICATION'])

# If the build flag is not set, then get the existing data from the database
# and create lists of filepaths that need to be removed and added
else:
	try:
		# Retrieve ID numbers of data that is already on the database
		existing_filepath_ids = get_existing_filepath_ids()
		publication_type_ids_dict = db.get_publication_types()
		type_ids_dict = db.get_file_types()
		existing_title_aliases_dict = get_existing_title_aliases()

		# Retrieve filepath author information
		existing_filepath_id_author_info = \
			get_existing_filepath_id_author_info()
	except sql.OperationalError as db_error:
		print(('Unable to retrieve data from database {0}. The following '
			'error was encountered:').format(db_name), file=sys.stderr)
		print('Error code: ' + str(db_error.args[0]), file=sys.stderr)
		print('Error message: ' + db_error.args[1], file=sys.stderr)
		db.disconnect()
		quit()

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
		author_ids_dict = db.get_authors()
	except sql.OperationalError as db_error:
		print(('Unable to retrieve list of author ID numbers from database '
			+ '{0}. The following error was encountered:').format(db_name),
			file=sys.stderr)
		print('Error code: ' + str(db_error.args[0]), file=sys.stderr)
		print('Error message: ' + db_error.args[1], file=sys.stderr)
		db.disconnect()
		quit()

# Get a list of author names that need to be added to the database
authors_to_add = _get_authors_to_add()

# -------------------------
# Populate tables with data
# -------------------------

# If the build flag is set, insert data into the tables containing the type ID
# numbers, publication type ID numbers and language codes; if the build flag
# is not set, assume that all of the data has already been added to the
# database
message_insert_rows = 'Inserting rows into table {0}...'

if build_db_flag == True:
	try:
		db.connection.begin()

		# List of file types (nvg_type_ids)
		if silent_output == False:
			print(message_insert_rows.format(nvg.database.file_type_ids_table))
		for type_desc, type_id in sorted(type_ids_dict.items(),
			key=lambda x: x[1]):
			db.insert_file_type(type_desc, type_id, commit=False)

		# List of publication types (nvg_publication_type_ids)
		if silent_output == False:
			print(message_insert_rows.format(
				nvg.database.publication_type_ids_table))
		for type_desc, type_id in sorted(publication_type_ids_dict.items(),
			key=lambda x: x[1]):
			db.insert_publication_type(type_desc, type_id, commit=False)

		# List of language codes
		if silent_output == False:
			print(message_insert_rows.format(
				nvg.database.language_codes_table))
		for language, code in sorted(language_codes_dict.items(),
			key=lambda x: x[1]):
			db.insert_language(language, code, commit=False)

		db.connection.commit()
	except sql.OperationalError as db_error:
		print(('Unable to insert rows into table {0}. The following error was '
			+ 'encountered:').format(table_name), file=sys.stderr)
		print('Error code: ' + str(db_error.args[0]), file=sys.stderr)
		print('Error message: ' + db_error.args[1], file=sys.stderr)
		db.disconnect()
		quit()

# Add new authors and aliases to the database and get the ID numbers that are
# assigned to them after they are added
if authors_to_add:
	print('Assigning ID numbers to new authors...')
	authors_added = {}

	try:
		db.connection.begin()

		# Sort the list of author names alphabetically
		for author in sorted(authors_to_add, key=str.lower):
			# Don't add any alias ID number cross-references yet; do this
			# later when all the new author ID numbers have been assigned
			author_id = db.insert_author(author, None, None, commit=False)
			authors_added[author] = {}
			authors_added[author]['ID'] = author_id

		db.connection.commit()
	except sql.OperationalError as db_error:
		print(('Unable to insert authors into table {0}. The '
			+ 'following error was encountered:').format(table_name),
			file=sys.stderr)
		print('Error code: ' + str(db_error.args[0]), file=sys.stderr)
		print('Error message: ' + db_error.args[1], file=sys.stderr)
		db.disconnect()
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
# author aliases CSV file is available (i.e. the dictionary of author aliases
# contains entries)

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
		# already assigned to it), delete the alias ID and add the author name
		# to the list of authors to update
		if ((author_name not in author_aliases_dict) and
			current_alias_of_author_id):
			author_aliases_to_update[author_name] = current_alias_of_author_id
			new_alias_of_author_id = None
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
				author_aliases_to_update[author_name] = \
					current_alias_of_author_id
				author_ids_dict[author_name]['Alias ID'] = \
					new_alias_of_author_id

	# Update the database with the new author alias information
	print('Updating author aliases...')
	message_list = []

	try:
		db.connection.begin()
		for author_name in sorted(author_aliases_to_update, key=str.lower):
			params = []
			new_alias_of_author_id = None

			# The author to update no longer has an alias
			if 'Alias ID' not in author_ids_dict[author_name]:
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
				new_alias_of_author_id = \
					author_ids_dict[author_name]['Alias ID']
				message_list.append(('Added {0} (ID {1}) as an alias of {2} '
					+ '(ID {3}).').format(author_name,
					author_ids_dict[author_name]['ID'],
					author_aliases_dict[author_name],
					author_ids_dict[author_aliases_dict[author_name]]['ID']))

			# Update the relevant row in the table of author names
			try:
				db.update_author(author_ids_dict[author_name]['ID'],
					author_name, new_alias_of_author_id, commit=False)
			except sql.OperationalError as db_error:
				db.connection.rollback()
				print(('Unable to update author name {0} in table {1}. The '
					+ 'following error was encountered:').format(author_name,
					table_name), file=sys.stderr)
				print('Error code: ' + str(db_error.args[0]), file=sys.stderr)
				print('Error message: ' + db_error.args[1], file=sys.stderr)
				db.disconnect()
				quit()

		# Commit all the updates to the table of author names
		db.connection.commit()

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
		db.disconnect()
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

	# Convert the YEAR field to an integer
	if 'YEAR' in file_data[filepath]:
		try:
			file_data[filepath]['YEAR'] = int(file_data[filepath]['YEAR'])
		except ValueError:
			del file_data[filepath]['YEAR']

	# Convert the TYPE and PUBLICATION fields for each filepath to their
	# corresponding ID numbers
	try:
		file_data[filepath]['TYPE'] = \
			type_ids_dict[file_data[filepath]['TYPE']]
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
			+ 'NULL.').format(filepath, file_data[filepath]['ID']),
			file=sys.stderr)

	# Examine the Uploader and COMMENTS field; the string '?' is used to
	# represent an unknown uploader, or no comments, so delete these values
	# from the file data
	for column in ['Uploader', 'COMMENTS']:
		if ((column in file_data[filepath]) and
			(file_data[filepath][column] == '?')):
			del file_data[filepath][column]

	# Convert the MEMORY REQUIRED field to an integer
	if 'MEMORY REQUIRED' in file_data[filepath]:
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
update_message_displayed = False

try:
	db.connection.begin()
	for filepath in sorted(file_data):
		# If a filepath needs to be updated, it will have an ID number
		# assigned to it
		if 'ID' in file_data[filepath]:
			# Display the message about updating rows, but only once
			if update_message_displayed == False:
				print('Updating filepaths in table {0}...'.format(table_name))
				update_message_displayed = True

			if cpcpower_data:
				cpcsofts_id = cpcpower_data.get(filepath)
				if cpcsofts_id == 0:
					cpcsofts_id = None
			else:
				cpcsofts_id = None

			# Update the filepath
			db.update_filepath(file_data[filepath]['ID'],
				file_size=file_data[filepath]['Size'],
				cpcsofts_id=cpcsofts_id,
				title=file_data[filepath].get('TITLE'),
				company=file_data[filepath].get('COMPANY'),
				year=file_data[filepath].get('YEAR'),
				languages=file_data[filepath].get('LANGUAGE'),
				type_id=file_data[filepath].get('TYPE'),
				subtype=file_data[filepath].get('SUBTYPE'),
				title_screen=file_data[filepath].get('TITLE SCREEN'),
				cheat_mode=file_data[filepath].get('CHEAT MODE'),
				protected=file_data[filepath].get('PROTECTED'),
				problems=file_data[filepath].get('PROBLEMS'),
				upload_date=file_data[filepath].get('Upload Date'),
				uploader=file_data[filepath].get('Uploader'),
				comments=file_data[filepath].get('COMMENTS'),
				original_title=file_data[filepath].get('ORIGINAL TITLE'),
				publication_type_id=file_data[filepath].get('PUBLICATION'),
				publisher_code=file_data[filepath].get('PUBLISHER CODE'),
				barcode=file_data[filepath].get('BARCODE'),
				dl_code=file_data[filepath].get('DL CODE'),
				memory_required=file_data[filepath].get('MEMORY REQUIRED'),
				commit=False
			)

	db.connection.commit()

except (sql.OperationalError, sql.InternalError) as db_error:
	print(('Unable to update rows in table {0}. The following error was '
		+ 'encountered:').format(table_name), file=sys.stderr)
	print('Error code: ' + str(db_error.args[0]), file=sys.stderr)
	print('Error message: ' + db_error.args[1], file=sys.stderr)
	db.disconnect()
	quit()

# If the build flag is not set, then delete filepaths from the database that
# aren't in the main CSV file
if build_db_flag == False:
	try:
		db.connection.begin()
		for filepath in existing_filepath_ids:
			if filepath not in file_data:
				id = existing_filepath_ids[filepath]
				db.delete_filepath(id, commit=False)
				message_list.append('Deleted {0} (ID {1}).'.format(
					filepath, id))

		db.connection.commit()
		if silent_output == False:
			if(message_list):
				print('\n'.join(message_list))
	except sql.OperationalError as db_error:
		print(('Unable to delete rows from table {0}. The following error '
			+ 'was encountered:').format(table_name))
		print('Error code: ' + str(db_error.args[0]))
		print('Error message: ' + db_error.args[1])
		db.disconnect()
		quit()

# Insert new filepaths into the database

message_list = []
insert_message_displayed = False

try:
	db.connection.begin()
	for filepath in sorted(file_data):
		# If a filepath needs to be added to the database, it won't have an
		# ID number assigned to it
		if 'ID' not in file_data[filepath]:
			# Display the message about inserting rows, but only once
			if insert_message_displayed == False:
				print('Inserting filepaths into table {0}...'.format(
					table_name))
				insert_message_displayed = True

			if cpcpower_data:
				cpcsofts_id = cpcpower_data.get(filepath)
				if cpcsofts_id == 0:
					cpcsofts_id = None
			else:
				cpcsofts_id = None

			# Insert the new filepath into the table
			filepath_id = db.insert_filepath(
				filepath,
				file_size=file_data[filepath]['Size'],
				cpcsofts_id=cpcsofts_id,
				title=file_data[filepath].get('TITLE'),
				company=file_data[filepath].get('COMPANY'),
				year=file_data[filepath].get('YEAR'),
				languages=file_data[filepath].get('LANGUAGE'),
				type_id=file_data[filepath].get('TYPE'),
				subtype=file_data[filepath].get('SUBTYPE'),
				title_screen=file_data[filepath].get('TITLE SCREEN'),
				cheat_mode=file_data[filepath].get('CHEAT MODE'),
				protected=file_data[filepath].get('PROTECTED'),
				problems=file_data[filepath].get('PROBLEMS'),
				upload_date=file_data[filepath].get('Upload Date'),
				uploader=file_data[filepath].get('Uploader'),
				comments=file_data[filepath].get('COMMENTS'),
				original_title=file_data[filepath].get('ORIGINAL TITLE'),
				publication_type_id=file_data[filepath].get('PUBLICATION'),
				publisher_code=file_data[filepath].get('PUBLISHER CODE'),
				barcode=file_data[filepath].get('BARCODE'),
				dl_code=file_data[filepath].get('DL CODE'),
				memory_required=file_data[filepath].get('MEMORY REQUIRED'),
				commit=False
			)
			file_data[filepath]['ID'] = filepath_id
			message_list.append('Added {0} (ID {1}).'.format(filepath,
				filepath_id))

	db.connection.commit()
	if silent_output == False:
		if(message_list):
			print('\n'.join(message_list))

except (sql.OperationalError, sql.InternalError) as db_error:
	print(('Unable to insert rows into table {0}. The following error was '
		+ 'encountered:').format(table_name), file=sys.stderr)
	print('Error code: ' + str(db_error.args[0]), file=sys.stderr)
	print('Error message: ' + db_error.args[1], file=sys.stderr)
	db.disconnect()
	quit()

# Insert author information, associating authors with filepaths
table_name = 'nvg_file_authors'
message_list = []

try:
	db.connection.begin()

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
						db.insert_filepath_author(filepath_id,
							file_data[filepath][field][index], field, index,
							commit=False)
					author_info_updated |= 1

			if author_info_updated:
				message_list.append(('Added author information for {0} (ID '
					+ '{1}).').format(filepath, filepath_id))

		db.connection.commit()
		
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
					db.delete_filepath_author(filepath_id,
						author_type=field, commit=False)
				if issue_insert_query:
					for index in range(len(file_data[filepath][field])):
						db.insert_filepath_author(filepath_id,
							file_data[filepath][field][index], field, index,
							commit=False)

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

	db.connection.commit()
	if silent_output == False:
		if(message_list):
			print('\n'.join(message_list))

except (sql.OperationalError, sql.InternalError) as db_error:
	print(('Unable to insert rows into table {0}. The following error was '
		+ 'encountered:').format(table_name), file=sys.stderr)
	print('Error code: ' + str(db_error.args[0]), file=sys.stderr)
	print('Error message: ' + db_error.args[1], file=sys.stderr)
	db.disconnect()
	quit()

# Insert aliases of titles
table_name = 'nvg_title_aliases'
message_list = []

try:
	db.connection.begin()

	# If the build flag is set, there is no need to check the existing title
	# alias information in the database
	if build_db_flag == True:
		print('Inserting title aliases into table {0}...'.format(table_name))
		for filepath in sorted(file_data):
			filepath_id = file_data[filepath]['ID']

			if 'ALSO KNOWN AS' in file_data[filepath]:
				for title_alias in file_data[filepath]['ALSO KNOWN AS']:
					db.insert_title_alias(filepath_id, title_alias,
						commit=False)
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
				db.delete_title_aliases(filepath_id, commit=False)
			if issue_insert_query:
				for title_alias in file_data[filepath]['ALSO KNOWN AS']:
					db.insert_title_alias(filepath_id, title_alias,
						commit=False)

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

	db.connection.commit()
	if silent_output == False:
		if(message_list):
			print('\n'.join(message_list))

except (sql.OperationalError, sql.InternalError) as db_error:
	print(('Unable to insert rows into table {0}. The following error was '
		+ 'encountered:').format(table_name), file=sys.stderr)
	print('Error code: ' + str(db_error.args[0]), file=sys.stderr)
	print('Error message: ' + db_error.args[1], file=sys.stderr)
	db.disconnect()
	quit()

# Everything has been set up, so close the connection
db.disconnect()
