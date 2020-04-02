# Module containing a function to read the CSV file used by the Amstrad CPC
# software archive on NVG, which contains the information stored in the
# file_id.diz file within each ZIP file in the archive
#
# This file can be downloaded from the archive at the URL below:
# <ftp://ftp.nvg.ntnu.no/pub/cpc/00_table.csv>
#
# Initial version by Nicholas Campbell 2018-01-06
# Last update: 2020-04-02

import csv	# Intended to import Python's built-in CSV module
from os import path
import re
import sys

# Initialise variables used by functions

csv_field_names = ['Action','File Path','Size','TITLE',
	'COMPANY','YEAR','LANGUAGE','TYPE','SUBTYPE','TITLE SCREEN','CHEAT MODE',
	'PROTECTED','PROBLEMS','Upload Date','Uploader','COMMENTS',

	'ALSO KNOWN AS','ORIGINAL TITLE','PUBLISHER','RE-RELEASED BY',
	'PUBLICATION','PUBLISHER CODE','BARCODE','DL CODE','CRACKER','DEVELOPER',
	'AUTHOR','DESIGNER','ARTIST','MUSICIAN','MEMORY REQUIRED','PROTECTION',
	'RUN COMMAND']
file_id_diz_filename = 'file_id.diz'

# Functions

def read_nvg_csv_file(csv_filename):
	"""Read a CSV file in the format that is used by the Amstrad CPC software
archive on the NVG FTP site at <ftp://ftp.nvg.ntnu.no/pub/cpc/>.

The CSV file is assumed to be encoded in Latin-1 (ISO-8859-1).

Parameters:
csv_filename: The filepath of the CSV file.

Returns:
A dictionary containing filepaths as the keys, and a dictionary of field names
(e.g. 'TITLE', 'YEAR', 'PUBLISHER', 'AUTHOR') as the values."""

	file_data = {}

	line = 0
	with open(csv_filename, newline='', encoding='utf-8') as csv_file:
		csv_file_reader = csv.reader(csv_file, dialect='excel', delimiter=',')

		# Skip the first line of the CSV file, which contains the field names
		next(csv_file_reader)
		line += 1

		# Read all the remaining lines in the CSV file one at a time
		for row in csv_file_reader:
			# Initialise the dictionary for the specified filepath
			filename = row[1].strip()
			file_data[filename] = {}
			# Get the size of the file
			file_data[filename]['Size'] = int(row[2])

			# Get all the remaining details, ignoring the 'Action' column
			for column in range(3,len(csv_field_names)):
				if row[column] != '':
					file_data[filename][csv_field_names[column]] = row[column].strip()
			line += 1

	return file_data


def read_cpcpower_csv_file(csv_filename):
	"""Read a CSV file that lists filepaths on the NVG FTP site at
<ftp://ftp.nvg.ntnu.no/pub/cpc/> and their corresponding ID numbers on the
CPC-POWER web site at <http://www.cpc-power.com/>.

If the ID number column is blank, it means that the ID number associated with
the file is unknown; this is converted to a value of None.

If the ID number column is 0, it means that the file has no entry on CPC-POWER.

Parameters:
csv_filename: The filepath of the CSV file.

Returns:
A dictionary containing filepaths as the keys, and the CPCSOFTS/CPC-POWER ID
numbers as the values."""

	cpcpower_data = {}

	line = 0
	with open(csv_filename, newline='', encoding='utf-8') as csv_file:
		csv_file_reader = csv.reader(csv_file, dialect='excel', delimiter=',')

		# Skip the first line of the CSV file, which contains the field names
		next(csv_file_reader)
		line += 1

		# Read all the remaining lines in the CSV file one at a time
		for row in csv_file_reader:
			# Get the filepath, which acts as the key
			filepath = row[0].strip()

			# Get the CPCSOFTS ID, which acts as the value

			cpcsofts_id_str = row[1].strip()
			try:
				if cpcsofts_id_str == '':
					cpcpower_data[filepath] = None
				else:
					cpcsofts_id = int(cpcsofts_id_str)
					if cpcsofts_id < 0:
						raise ValueError
					else:
						cpcpower_data[filepath] = cpcsofts_id
			except ValueError:
				print(('Invalid CPCSOFTS ID number for file {0} in {1}. The ID '
					+ 'number will be set to None.').format(filepath,
					csv_filename), file=sys.stderr)
				cpcpower_data[filepath] = None

	return cpcpower_data
