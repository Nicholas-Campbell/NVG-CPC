"""Module containing functions for using file_id.diz files that are stored
within ZIP files on the Amstrad CPC software archive on the NVG FTP site
(located at <ftp://ftp.nvg.ntnu.no/pub/cpc/>).
"""

# (C) Nicholas Campbell 2018
# First version: 21/01/2018
# Last update: 04/02/2018

from os import path
import datetime
import re
import tempfile
import warnings
import zipfile

# Initialise variables used by functions and main program

file_id_diz_filename = 'file_id.diz'

valid_file_id_diz_versions = ['2.00', '3.00', '3.10']
# Dictionary of valid field names that can be used and the version numbers in
# which they were introduced
valid_field_names = {
  'TITLE': 2.00, 'COMPANY': 2.00, 'YEAR': 2.00, 'LANGUAGE': 2.00,
  'TYPE': 2.00, 'SUBTYPE': 2.00, 'TITLE SCREEN': 2.00,
  'CHEAT MODE': 2.00, 'PROTECTED': 2.00, 'PROBLEMS': 2.00,
  'UPLOADED': 2.00, 'COMMENTS': 2.00,

  'ALSO KNOWN AS': 3.00, 'ORIGINAL TITLE': 3.00, 'PUBLISHER': 3.00,
  'RE-RELEASED BY': 3.00, 'PUBLICATION': 3.00, 'PUBLISHER CODE': 3.00,
  'CRACKER': 3.00, 'DEVELOPER': 3.00, 'AUTHOR': 3.00, 'ARTIST': 3.00,
  'MUSICIAN': 3.00, 'MEMORY REQUIRED': 3.00, 'PROTECTION': 3.00,
  'RUN COMMAND': 3.00,

  'DESIGNER': 3.10, 'BARCODE': 3.10, 'DL CODE': 3.10
};
# Dictionary of deprecated field names and the version numbers from which they
# are considered deprecated
deprecated_field_names = {
  'COMPANY': 3.00, 'PROTECTED': 3.00
};
# Field names that must be included in each file_id.diz version
mandatory_field_names = {
	'2.00': ['TITLE', 'COMPANY', 'YEAR', 'LANGUAGE', 'TYPE', 'SUBTYPE',
		'TITLE SCREEN', 'CHEAT MODE', 'PROTECTED', 'PROBLEMS', 'UPLOADED',
		'COMMENTS'],

	'3.00': ['TITLE', 'UPLOADED'],

	'3.10': ['TITLE', 'UPLOADED']
};

# Compiled regular expression for identifying the first line of a file_id.diz
# file
file_id_header_regex = re.compile('\s*\*\* AMSTRAD (CPC|PCW) SOFTWARE AT FTP\.NVG\.(UNIT|NTNU)\.NO : file_id.diz FILE V ([0-9]\.[0-9]{2}) \*\*[\s\n]*')
# Compiled regular expression for validating the UPLOADED field in a
# file_id.diz file
uploaded_field_regex = re.compile('(\?|[0-9]{2}\/[0-9]{2}\/[0-9]{4})\s+by\s+(.+)[\s\n]*')


# Functions

def read_file_id_diz(zip_filepath):
	"""Open a ZIP file and read the contents of the file_id.diz file within the
archive, in the format used by the Amstrad CPC software archive on the NVG FTP
site at <ftp://ftp.nvg.ntnu.no/pub/cpc/>.

Parameters:
zip_filepath: The filepath of the ZIP file.

Returns:
A dictionary containing field names as the keys (e.g. TITLE, YEAR, UPLOADED,
COMMENTS)."""

	file_data = {}

	with tempfile.TemporaryDirectory() as temp_dir:
		with zipfile.ZipFile(zip_filepath, 'r') as zip_file:
			files = zip_file.namelist()

			# If there is no file named file_id.diz within the ZIP file, then
			# raise an exception
			if file_id_diz_filename in files:
				zip_file.extract(file_id_diz_filename, temp_dir)
			else:
				raise FileNotFoundError('There is no file named '
					+ file_id_diz_filename + ' in the archive '
					+ zip_filepath)

			field_format = '{:16s} {:s}'
			# Read the file_id.diz file in the temporary directory
			with open(path.join(temp_dir, file_id_diz_filename), 'r', encoding='latin-1') as file_id_diz_handle:
				line_num = 0
				file_id_diz_version_str = ''
				file_id_diz_version = 0.00

				for line in file_id_diz_handle:
					# Read the first line of the file_id.diz file and get the
					# version number; if this line does not match a particular
					# format, generate a warning and do not continue
					line = line.strip()
					if line_num == 0:
						regex_match = re.match('^\s*\*\* AMSTRAD (CPC|PCW) SOFTWARE AT FTP\.NVG\.(UNIT|NTNU)\.NO : file_id.diz FILE V ([0-9]\.[0-9]{2}) \*\*\s*$', line)
						if regex_match:
							# Convert the version number to a float
							file_id_diz_version_str = regex_match.group(3)
							file_id_diz_version = float(file_id_diz_version_str)

							# Check if the version number specified is valid;
							# if it is not, generate a warning and do not
							# continue
							if file_id_diz_version_str not in valid_file_id_diz_versions:
								warning_message = ('{:.2f} is an invalid '
									+ 'version number in {:s} in {:s}').format(
									file_id_diz_version, file_id_diz_filename,
									zip_filepath)
								warnings.warn(warning_message)
								return
						else:
							warning_message = ('{:s} in {:s} is in an '
								+ 'unsuitable format').format(
								file_id_diz_filename, zip_filepath)
							warnings.warn(warning_message)
							return

					# Read the remaining lines, and look for any lines
					# containing colons
					colon_index = line.find(':')
					if colon_index != -1 and line_num > 0:
						field_name = line[0:colon_index].strip()
						field_value = line[(colon_index+1):len(line)].strip()

						# Before file_id.diz version 3.00 was introduced, the
						# CSV file used semi-colons to separate fields on each
						# line. Therefore, in file_id.diz versions before 3.00,
						# semi-colons are not allowed within values; if any are
						# found, generate a warning and replace them with
						# spaces
						if round(file_id_diz_version,2) < 3.00 and ';' in field_value:
							warning_message = ('Value of {:s} field in {:s} in '
								+ '{:s} contains semi-colons').format(
								field_name, file_id_diz_filename, zip_filepath)
							warnings.warn(warning_message)
							field_value = field_value.replace(';', ' ')

						# Check if the field name is in the list of valid
						# field names
						if field_name not in valid_field_names:
							warning_message = ('Invalid field {:s} in {:s} in '
								+ '{:s}').format(field_name,
								file_id_diz_filename, zip_filepath)
							warnings.warn(warning_message)

						# Check if the field name is valid for the version
						# number of this file_id.diz file
						elif round(float(file_id_diz_version),2) < valid_field_names[field_name]:
							warning_message = ('{:s} field is invalid in {:s} '
								+ 'version {:.2f} in {:s}').format(field_name,
								file_id_diz_filename, file_id_diz_version,
								zip_filepath)
							warnings.warn(warning_message)

						# Check if the field is deprecated for the version
						# number of this file_id.diz file
						elif (field_name in deprecated_field_names and
							round(float(file_id_diz_version),2) >= deprecated_field_names[field_name]):
							warning_message = ('{:s} field is deprecated in '
								+ '{:s} version {:.2f} in {:s}').format(
								field_name, file_id_diz_filename,
								file_id_diz_version, zip_filepath)
							warnings.warn(warning_message)

						# Try to convert the YEAR field (year of release) to
						# an integer
						elif field_name == 'YEAR':
							try:
								year = int(field_value)
							except ValueError:
								year = None
							finally:
								file_data['YEAR'] = year

						# The field is valid, so add it to the file data
						else:
							file_data[field_name] = field_value

					line_num += 1

				# All the fields have been read

				# Check that no field names have blank values; if a field is
				# blank, then generate a warning
				for field_name in file_data:
					if file_data[field_name] == '':
						warning_message = ('{:s} field is blank in {:s} in '
							+ '{:s}').format(field_name, file_id_diz_filename,
							zip_filepath)
						warnings.warn(warning_message)

				# Check field names that must be included; if a field is
				# missing, then generate a warning
				if file_id_diz_version_str in mandatory_field_names:
					for field_name in mandatory_field_names[file_id_diz_version_str]:
						if field_name not in file_data:
							warning_message = ('{:s} field is missing in {:s} '
								+ 'in {:s}').format(field_name,
								file_id_diz_filename, zip_filepath)
							warnings.warn(warning_message)

				# Check that the UPLOADED field is correctly formatted; if it
				# is not, generate a warning
				regex_match = re.match(uploaded_field_regex, file_data['UPLOADED'])
				if regex_match:
					# Split the UPLOADED field into two new fields named
					# 'Upload Date' and 'Uploader'
					if regex_match.group(1) == '?':
						file_data['Upload Date'] = None

					# If a date is specified in the UPLOADED field, attempt to
					# convert it to a date object; if the date is invalid,
					# generate a warning
					else:
						upload_date_day = int(regex_match.group(1)[0:2])
						upload_date_month = int(regex_match.group(1)[3:5])
						upload_date_year = int(regex_match.group(1)[6:10])
						try:
							file_data['Upload Date'] = (datetime.date(
								upload_date_year, upload_date_month, upload_date_day))
						except ValueError:
							file_data['Upload Date'] = None
							warning_message = ('Invalid date in UPLOADED '
								+ 'field in {:s} in {:s}').format(
								file_id_diz_filename, zip_filepath)
							warnings.warn(warning_message)

					file_data['Uploader'] = regex_match.group(2)
				else:
					warning_message = ('UPLOADED field in {:s} in {:s} is in '
						+ 'an unsuitable format').format(file_id_diz_filename,
						zip_filepath)
					warnings.warn(warning_message)

	return file_data


def print_file_id_diz(zip_filepath):
	"""Read a ZIP file and print the contents of the file_id.diz file within
the archive, if it exists, to standard output.

Parameters:
zip_filepath: The filepath of the ZIP file.

Returns:
Nothing.

Raises:
FileNotFoundError: Either the ZIP file was not found, or there is no file
named file_id.diz within the ZIP file."""

	with tempfile.TemporaryDirectory() as temp_dir:
		with zipfile.ZipFile(zip_filepath, 'r') as zip_file:
			files = zip_file.namelist()

			# If there is no file named file_id.diz within the ZIP file, then
			# raise an exception
			if file_id_diz_filename in files:
				zip_file.extract(file_id_diz_filename, temp_dir)
			else:
				raise FileNotFoundError('There is no file named '
					+ file_id_diz_filename + ' in the archive ' + zip_filepath)

			# Read the file_id.diz file in the temporary directory
			with open(path.join(temp_dir, file_id_diz_filename), 'r',
				encoding='latin-1') as file_id_diz_handle:
				for line in file_id_diz_handle:
					print(line.strip('\n'))


# Script to test functions used in this module

if __name__ == '__main__':
	zip_filename = input('Enter filepath of ZIP file: ').strip()

	print('Reading data from {:s} in {:s}...'.format(
		file_id_diz_filename, zip_filename))
	file_data = read_file_id_diz(zip_filename)
	print(file_data)
	print()
	print_file_id_diz(zip_filename)
