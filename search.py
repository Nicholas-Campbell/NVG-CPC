"""Search the dictionary of filepaths containing information about the Amstrad
CPC software archive on the NVG FTP site (located at
<ftp://ftp.nvg.ntnu.no/pub/cpc/>).
"""

# (C) Nicholas Campbell 2018
# Last update: 21/01/2018

from nvg.csv import read_nvg_csv_file

# Initialise variables used by functions and main program

search_fields = ['COMPANY', 'PUBLISHER', 'RE-RELEASED BY', 'DEVELOPER',
	'AUTHOR', 'DESIGNER', 'ARTIST', 'MUSICIAN']
_SEARCH_FIELD_ASCII_SUFFIX = '_A'	# Suffix to add to ASCII versions of search
									# fields
# Map used for converting certain non-ASCII characters to their ASCII
# equivalents in remove_diacritics_from_string() functions
_ascii_translation_table = str.maketrans(
		'\xA0'							# non-breaking space
		+ '\xC0\xC1\xC2\xC3\xC4\xC5'	# A
		+ '\xC7'						# C
		+ '\xC8\xC9\xCA\xCB'			# E
		+ '\xCC\xCD\xCE\xCF'			# I
		+ '\xD1'						# N
		+ '\xD2\xD3\xD4\xD5\xD6\xD8'	# O
		+ '\xD9\xDA\xDB\xDC'			# U
		+ '\xDD'						# Y
		+ '\xE0\xE1\xE2\xE3\xE4\xE5'	# a
		+ '\xE7'						# c
		+ '\xE8\xE9\xEA\xEB'			# e
		+ '\xEC\xED\xEE\xEF'			# i
		+ '\xF1'						# n
		+ '\xF2\xF3\xF4\xF5\xF6\xF8'	# o
		+ '\xF9\xFA\xFB\xFC'			# u
		+ '\xFD\xFF'					# y
		, ' '
		+ 'AAAAAA' + 'C' + 'EEEE' + 'IIII' + 'N' + 'OOOOOO' + 'UUUU' + 'Y'
		+ 'aaaaaa' + 'c' + 'eeee' + 'iiii' + 'n' + 'oooooo' + 'uuuu' + 'yy')


# Functions

def remove_diacritics_from_string(string):
	"""Remove certain non-ASCII characters from a string and convert them into
their ASCII equivalents.

The string is assumed to be encoded in Latin-1 (ISO-8859-1), which is the
encoding that is used in the 00_table.csv file in the Amstrad CPC software
archive on NVG.

Parameters:
string: The string to convert.

Returns:
An ASCII-encoded string."""

	new_str = string.translate(_ascii_translation_table)

	# Replace some single characters with more than one character
	for (char_to_replace, replacement_seq) in (
		[('\xC6', 'AE'), ('\xE6', 'ae'), ('\xDF', 'ss'),
		 ('\xDE', 'TH'), ('\xFE', 'th')]):
		new_str = new_str.replace(char_to_replace, replacement_seq)
	return new_str


def convert_nvg_file_data_to_ascii(fields_to_convert):
	"""Iterate the dictionary of filepaths containing information about the Amstrad
CPC software archive on NVG. If any of the specified fields contain certain
non-ASCII characters, add a new field which contains the ASCII equivalent of
the value of that field.

Parameters:
fields_to_convert: A list of fields whose values will be converted to ASCII.

Returns: Nothing.
"""

	for file in file_data:
		for field in fields_to_convert:
			try:
				str_ascii = file_data[file][field].encode(encoding='ascii', errors='strict')
			except KeyError:
				pass
			except UnicodeError:
				file_data[file][field + _SEARCH_FIELD_ASCII_SUFFIX] = remove_diacritics_from_string(
					file_data[file][field])


def search_nvg_filepaths(search_term):
	"""Search the dictionary of filepaths containing information about the files
on the Amstrad CPC software archive on NVG.

Parameters:
search_term: The string to search for.

Returns:
An ordered list of filepaths that match the specified search term."""

	search_results = []
	for file in file_data:
		if search_term.lower() in file:
			search_results.append(file)

	return sorted(search_results)


def search_nvg_file_data(search_term, ascii_search=False):
	"""Iterate the dictionary of filepaths containing information about the Amstrad
CPC software archive on NVG, and search certain fields.

When using ASCII mode, the dictionary of filepaths must have already been
modified using the convert_nvg_file_data_to_ascii() function.

Parameters:
search_term: The string to search for.
ascii_search: True if ASCII mode should be used (i.e. any letters containing
diacritics will match to their non-diacritical (ASCII) equivalents), False
if letters containing diacritics must be matched exactly. Default value is
False.

Returns:
A dictionary of filepaths, with each value consisting of a dictionary of
fields that were matched and a list of the strings that were matched.
"""

	# Search selected fields and store the results in a dictionary
	search_results = {}

	for file in file_data:
		for field in search_fields:
			# Check if the specified search field has been defined for the
			# current filepath
			if field in file_data[file]:
				# The information in the specified fields is comma-delimited
				name_list = file_data[file][field].split(sep = ',')
				if (ascii_search == True and
					(field + _SEARCH_FIELD_ASCII_SUFFIX) in file_data[file]):
					name_list_ascii = file_data[file][field + _SEARCH_FIELD_ASCII_SUFFIX].split(sep = ',')
				else:
					name_list_ascii = []

				for index in range(len(name_list)):
					# Remove excess space at the beginning and end of each
					# entry
					name = name_list[index].strip()
					if ascii_search == True and len(name_list_ascii) > 0:
						search_term_found = (search_term in name_list_ascii[index].upper())
					else:
						search_term_found = (search_term in name.upper())
					if search_term_found:
						if file not in search_results:
							search_results[file] = {}
							search_results[file][field] = [name]
						else:
							if field not in search_results[file]:
								search_results[file][field] = [name]
							else:
								search_results[file][field].append(name)

	return search_results


# ------------
# Main program
# ------------

# Initialise variables, dictionaries and lists
nvg_csv_filename = r'00_table.csv'
file_data = read_nvg_csv_file(nvg_csv_filename)

# Iterate the dictionary of NVG file data and add ASCII equivalents of fields
# containing certain non-ASCII characters
convert_nvg_file_data_to_ascii(search_fields)

search_term = None
while search_term != '':
	# Input a string to search for
	search_term = input('Enter search term: ')
	# Remove excess whitespace from the search term and convert it to upper
	# case
	search_term = ' '.join(search_term.split()).upper()
	# If no search term is entered, then exit the loop
	if search_term == '':
		break
	else:
		print()

		# Test if the string contains only ASCII characters; if it does, then
		# use ASCII mode when searching
		search_term_is_ascii = True
		try:
			search_term.encode(encoding='ascii', errors='strict')
		except UnicodeError:
			search_term_is_ascii = False

		# Search filepaths for the specified search term
		search_results = search_nvg_filepaths(search_term)

		# If any filepaths containing the specified search term were found,
		# list all matches
		results_found = len(search_results)
		if results_found:
			# Display the number of results found
			format_layout = '{:<35s} {:<43s}'
			if results_found == 1:
				print('1 file was found:\n')
			else:
				print(str(results_found) + ' files were found:\n')

			# List the matches found
			print(format_layout.format('Filepath', 'Title'))
			print('-'*35 + ' ' + '-'*43)

			for file in search_results:
				print(file[0:36].ljust(35) + ' ', end = '')
				if 'TITLE' in file_data[file]:
					print(file_data[file]['TITLE'][0:43])
				else:
					print()
		else:
			print('No files were found.')

		# Search selected fields for the specified search term 
		print()
		search_results = search_nvg_file_data(search_term, search_term_is_ascii)

		# If any names containing the specified search term were found,
		# display the results

		# Some entries may appear to be duplicates; this is because different
		# filepaths may contain different versions of the same program, which
		# will have the same title and author(s)
		titles_found = len(search_results)
		if titles_found:
			format_layout = '{:<40s} {:<23s} {:<14s}'

			# Calculate the overall number of results that were found by
			# examining how many results were found for each field in each
			# filepath; some fields may have more than one result containing
			# the specified search term
			results_found = 0
			for file in search_results:
				for field in search_results[file]:
					results_found += len(search_results[file][field])

			# Display the number of results and titles that were found
			if results_found == 1:
				print('1 result was', end = '')
			else:
				print(str(results_found) + ' results were', end = '')
			print(' found in ', end = '')
			if titles_found == 1:
				print('1 title', end = '')
			else:
				print(str(titles_found) + ' titles', end = '')				
			print(':\n\n' + format_layout.format('Title', 'Name', 'Field'))
			print('-'*40 + ' ' + '-'*23 + ' ' + '-'*14)

			# List the matches found, ordered by title
			for file in sorted(search_results, key=lambda f: str(file_data[f]['TITLE'].lower())):
				for field in search_fields:
					if field in search_results[file]:
						for name in search_results[file][field]:
							print(format_layout.format(file_data[file]['TITLE'][0:40],
								name[0:23], field))
			print()
