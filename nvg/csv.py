# Module containing a function to read the CSV file used by the Amstrad CPC
# software archive on NVG, which contains the information stored in the
# file_id.diz file within each ZIP file in the archive
#
# This file can be downloaded from the archive at the URL below:
# <ftp://ftp.nvg.ntnu.no/pub/cpc/00_table.csv>
#
# Initial version by Nicholas Campbell 2018-01-06
# Last update: 2018-01-21

import csv	# Intended to import Python's built-in CSV module
from os import path
import re

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
	with open(csv_filename, newline='', encoding='latin-1') as csv_file:
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


# Script to test functions used in this module

if __name__ == '__main__':
	csv_filename = input('Enter filepath of CSV file: ').strip()

	file_data = read_nvg_csv_file(csv_filename)
	filepath = None
	while filepath != '':
		filepath = input('Enter filepath to search for: ').strip()
		if filepath == '':
			break

		if filepath in file_data:
			for field in csv_field_names:
				if field in file_data[filepath]:
					print(field + ': ' + str(file_data[filepath][field]))
		else:
			print(filepath + ' does not exist in NVG file data.')
		print()
