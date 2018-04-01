# NVG-CPC

## Usage and examples

### Python

Currently this repository contains two Python modules:

* `nvg.csv` - read a locally stored copy of the `00_table.csv` file on NVG and store the data in a dictionary
* `nvg.fileid` - read the `file_id.diz` files that contain data about the ZIP files on NVG

An example Python 3 script named `search.py` is also included, which enables you to search the list of ZIP files on NVG and demonstrates how to use the `nvg.csv` module.

To use the modules in your own scripts, copy the `nvg` directory and its contents to your working directory and include the following lines in your script:

```python
import nvg.csv
import nvg.fileid
```

To read the data from the CSV file into a dictionary named `nvg_file_data`, include the following lines (replacing `nvg_csv_filepath` with the location of the `00_table.csv` file on your own computer):

```python
nvg_csv_filepath = r'00_table.csv'
nvg_file_data = nvg.csv.read_nvg_csv_file(nvg_csv_filepath)
```

The dictionary stores the list of ZIP files on NVG as keys, and the data for each file is also stored as a dictionary, with the keys being the names of each field in the `file_id.diz` file. The example below displays the data for the game *Roland on the Ropes*, with the fields being displayed in random order:

```python
for field, value in nvg_file_data['games/arcade/rolanrop.zip'].items():
	print(field + ': ' + str(value))
```

The `nvg.csv` module contains a list named `csv_field_names`, which contains the names of the fields in the same order as the columns in the `00_table.csv` file. You can use this list to display the fields in order:

```python
filepath = 'games/arcade/rolanrop.zip'
for field in nvg.csv.csv_field_names:
	if field in nvg_file_data[filepath].keys():
		print(field + ': ' + str(nvg_file_data[filepath][field]))
```

Each ZIP file on NVG should include a file named `file_id.diz`, which is intended to contain data about the ZIP file. To read the data in this file, use the `read_file_id_diz` function in the `nvg.fileid` module. The example below assumes that you have saved a copy of the ZIP file for *Roland on the Ropes* in the same directory as your script:

```python
file_data = nvg.fileid.read_file_id_diz('rolanrop.zip')
print(file_data)
```

If you want to view the contents of the `file_id.diz` file without processing it, use the `print_file_id_diz` function in the `nvg.fileid` module:

```python
nvg.fileid.print_file_id_diz('rolanrop.zip')
```

### SQL

A Python 3 script named `sql.py` is included, which reads a locally stored copy of the `00_table.csv` file on NVG and creates a database containing the information in this file. Much of this information is converted to and stored as ID numbers in separate tables, to enable more efficient storage and faster searching.

In order to use `sql.py`, the [PyMySQL](https://pymysql.readthedocs.io/en/latest/) package must be installed. It also uses the `nvg.csv` module described in the **Python** section above.

The file `create_stored_routines.sql` contains various stored functions and procedures that can be used to retrieve information from the database and process it in your own applications.

#### Stored functions

##### `concat_author_names(INT UNSIGNED filepath_id, VARCHAR(14) author_type)`

Return a string containing the names of all the authors of the specified type that are associated with the specified filepath ID number, separated by commas.

For example, if the game *Auf Wiedersehen Monty* has a filepath ID number of 1221, the following query will return a string containing the names of all the authors, in the same order that they appear in the `file_id.diz` file:

```sql
SELECT concat_author_names(1221, 'AUTHOR');
```
```
+-------------------------------------------------------------------------+
| concat_author_names(1221, 'AUTHOR')                                     |
+-------------------------------------------------------------------------+
| Pete Harrap, Shaun Hollingworth, Chris Kerry, Colin Dooley, Greg Holmes |
+-------------------------------------------------------------------------+
1 row in set (0.00 sec)
```

The following query will return a string containing the names of the artists (the people who drew the graphics that are used in the game):

```sql
SELECT concat_author_names(1221, 'ARTIST');
```
```
+-------------------------------------+
| concat_author_names(1221, 'ARTIST') |
+-------------------------------------+
| Steve Kerry, Terry Lloyd            |
+-------------------------------------+
1 row in set (0.00 sec)
```

##### `concat_language_descs(INT UNSIGNED filepath_id)`

Return a string containing the names of all the languages that are associated with the specified filepath ID number, separated by commas and in alphabetical order.

For example, the game *2112 AD* displays in-game text in four languages. If it has a filepath ID number of 285, the following query will return a string containing the names of the languages used:

```sql
SELECT concat_language_descs(285);
```
```
+----------------------------------+
| concat_language_descs(285)       |
+----------------------------------+
| English, French, German, Spanish |
+----------------------------------+
1 row in set (0.00 sec)
```

##### `concat_title_aliases(INT UNSIGNED filepath_id)`

Return a string containing all the aliases of the specified filepath ID number (i.e. titles other than that which is specified in the `title` column), separated by semi-colons.

For example, the game *Last Ninja 2* is also known by several other names. If it has a filepath ID number of 430, the following query will return a string containing all the other names by which it is known:

```sql
SELECT concat_title_aliases(430);
```
```
+-----------------------------------------------------------------------+
| concat_title_aliases(430)                                             |
+-----------------------------------------------------------------------+
| Last Ninja 2, The; Last Ninja 2: Back with a Vengeance; Last Ninja II |
+-----------------------------------------------------------------------+
1 row in set (0.00 sec)
```

##### `get_file_id_diz(INT UNSIGNED filepath_id)`

Create and return the `file_id.diz` file that is used by ZIP files in the NVG Amstrad CPC software archive.

For example, if the game *Roland on the Ropes* has a filepath ID number of 2369, the following query will return a string which will look something like the result below:

```sql
SELECT get_file_id_diz(2369);
```
```
    ** AMSTRAD CPC SOFTWARE AT FTP.NVG.NTNU.NO : file_id.diz FILE V 3.00 **
-------------------------------------------------------------------------------
TITLE:           Roland on the Ropes
YEAR:            1984
PUBLISHER:       Amsoft
PUBLICATION:     Crack
CRACKER:         Nich
DEVELOPER:       Indescomp
AUTHOR:          Paco Menéndez, Fernando Rada, Camilo Cela, Carlos Granados
LANGUAGE:        English
MEMORY REQUIRED: 64K
TYPE:            Arcade game
SUBTYPE:         Maze exploration/shoot-'em-up
TITLE SCREEN:    Yes
CHEAT MODE:      Yes
RUN COMMAND:     RUN"ROLANDRO"
UPLOADED:        14/10/2002 by Nicholas Campbell
-------------------------------------------------------------------------------
```

##### `get_file_id_diz_version(INT UNSIGNED filepath_id)`

Return the version number of the `file_id.diz` file that is used by ZIP files in the NVG Amstrad CPC software archive, as a `DECIMAL(3,2)` data type (i.e. 3 digits, with 2 of those digits following the decimal point).

This function is intended for internal use in generating `file_id.diz` files (using the `get_file_id_diz` function described above) and validating data that is added to the database (using various triggers).

In the example shown above for the `get_file_id_diz` function, the following query returns `3.00` as the version number:

```sql
SELECT get_file_id_diz_version(2369);
```
```
+-------------------------------+
| get_file_id_diz_version(2369) |
+-------------------------------+
| 3.00                          |
+-------------------------------+
1 row in set (0.00 sec)
```

##### `get_language_desc(VARCHAR(5) language_tag)`

Return the name of the language associated with the specified [IETF language tag](https://tools.ietf.org/html/rfc5646). Currently the length of the tag is restricted to a maximum of 5 characters, which is sufficient to store a primary language subtag (2 characters) and a region subtag (2 characters).

For example, the IETF language tag for the English language is 'en':

```sql
SELECT get_language_desc('en');
```
```
+-------------------------+
| get_language_desc('en') |
+-------------------------+
| English                 |
+-------------------------+
1 row in set (0.00 sec)
```

##### `get_uploaded_string(INT UNSIGNED filepath_id)`

Return a string combining the upload date and the name(s) of the people who uploaded the specified filepath ID number.

In the example shown above for the `get_file_id_diz` function, the query below returns the string used in the `UPLOADED` field of the `file_id.diz` file for *Roland on the Ropes*:

```sql
SELECT get_uploaded_string(2369);
```
```
+---------------------------------+
| get_uploaded_string(2369)       |
+---------------------------------+
| 14/10/2002 by Nicholas Campbell |
+---------------------------------+
1 row in set (0.00 sec)
```

#### Stored procedures

##### `get_aliases_of_author_id(SMALLINT UNSIGNED author_id)`

Select the specified author ID number and all the author ID numbers which are aliases of the specified author ID number.

##### `get_author_ids(INT UNSIGNED filepath_id)`

Select all the author ID numbers, and their types, that are associated with the specified filepath ID number.

##### `get_author_names(INT UNSIGNED filepath_id)`

Select all the author ID numbers, and their names and types, that are associated with the specified filepath ID number.

##### `get_filepath_ids_by_author(SMALLINT UNSIGNED author_id)`

Select all the filepath ID numbers that are associated with the specified author ID number.

##### `get_file_info(INT UNSIGNED filepath_id)`

Select all information stored in the database about the specified filepath ID number. Author names are selected instead of ID numbers.

##### `get_titles_by_author(SMALLINT UNSIGNED author_id)`

Select all the titles that are associated with the specified author ID number.

##### `search_authors(VARCHAR(255) search_term)`

Select all the author ID numbers, names and types that match the specified search term, using standard SQL pattern matching syntax (i.e. `_` matches a single character, and `%` matches zero or more characters).

For example, to search for all authors whose names contain the term `Oliver`, use the following query:

```sql
CALL search_authors('%oliver%');
```
```
+-----------+---------------------+--------------------+-------------+
| author_id | author_name         | alias_of_author_id | author_type |
+-----------+---------------------+--------------------+-------------+
|       132 | Andrew Oliver       |               NULL | ARTIST      |
|       132 | Andrew Oliver       |               NULL | DESIGNER    |
|       132 | Andrew Oliver       |               NULL | AUTHOR      |
|       326 | Carlos Oliver       |               NULL | AUTHOR      |
|       468 | César Ivorra Oliver |               NULL | AUTHOR      |
|       926 | Ian Oliver          |               NULL | AUTHOR      |
|      1616 | Oliver Goodman      |               NULL | AUTHOR      |
|      1617 | Oliver Mayer        |               NULL | MUSICIAN    |
|      1749 | Philip Oliver       |               NULL | AUTHOR      |
|      1749 | Philip Oliver       |               NULL | ARTIST      |
|      1749 | Philip Oliver       |               NULL | DESIGNER    |
|      2201 | The Oliver Twins    |               NULL | DEVELOPER   |
|      2201 | The Oliver Twins    |               NULL | DESIGNER    |
+-----------+---------------------+--------------------+-------------+
13 rows in set (0.01 sec)
```

Note that the same author ID and name may appear more than once in the set of results; there is one row for each author type. In the above example, both Andrew Oliver and Philip Oliver appear three times &ndash; once as an author, once as an artist, and once as a designer.

##### `search_filepaths(VARCHAR(260) search_term)`

Select all the filepath ID numbers and filepaths that match the specified search term.

For example, the following query selects all filepaths containing the term `ghost`:

```sql
CALL search_filepaths('%ghost%');
```
```
+-------------+---------------------------+
| filepath_id | filepath                  |
+-------------+---------------------------+
|        1723 | games/arcade/ghostb.zip   |
|        1724 | games/arcade/ghostbu2.zip |
|        1725 | games/arcade/ghostgob.zip |
|        1726 | games/arcade/ghosthun.zip |
|        1727 | games/arcade/ghostsca.zip |
|        1728 | games/arcade/ghoststr.zip |
|        4618 | utils/cpc/ghostwri.zip    |
+-------------+---------------------------+
7 rows in set (0.01 sec)
```

##### `search_titles(VARCHAR(255) search_term)`

Select all the filepath ID numbers and titles that match the specified search term, and also specify if a title is an alias.

For example, the following query selects all filepaths where the title contains the term `ghost`:

```sql
CALL search_filepaths('%ghost%');
```
```
+-------------+-----------------------------------------------+----------+
| filepath_id | title                                         | is_alias |
+-------------+-----------------------------------------------+----------+
|         979 | SCAPEGHOST                                    |        0 |
|        1354 | Bubble Ghost                                  |        0 |
|        1723 | GHOSTBUSTERS                                  |        0 |
|        1724 | Ghostbusters II                               |        0 |
|        1725 | Ghosts'n Goblins                              |        0 |
|        1725 | Ghosts 'n' Goblins                            |        1 |
|        1726 | Ghost Hunters                                 |        0 |
|        1727 | GHOSTS (CASCADE)                              |        0 |
|        1728 | GHOSTS (THOMAS REISEPATT)                     |        0 |
|        1729 | Ghouls 'n' Ghosts                             |        0 |
|        1729 | Ghouls 'n Ghosts                              |        1 |
|        1927 | Knight Ghost                                  |        0 |
|        2151 | Olli and Lissa: The Ghost of Shilmoore Castle |        1 |
|        2308 | Real Ghostbusters, The                        |        0 |
|        4618 | GHOST-WRITER                                  |        0 |
+-------------+-----------------------------------------------+----------+
15 rows in set (0.01 sec)
```

Note that the same filepath ID may appear more than once in the set of results. This procedure searches the title of each filepath (the `title` column in the `nvg` table, or the `TITLE` field in the `file_id.diz` file) and all the aliases by which it is also known (the `title` column in the `nvg_title_aliases` table, or the `ALSO KNOWN AS` field in the `file_id.diz` file).

In the above example, *Ghosts'n Goblins* and *Ghouls 'n' Ghosts* both appear twice, because their aliases also contain the term `ghost`. Also note how *Olli and Lissa: The Ghost of Shilmoore Castle* is included in the results; it is an alias of the title *Olli and Lissa*, but as *Olli and Lissa* does not contain the term `ghost`, it is not included in the set of results.

##### `validate_nvg_data(VARCHAR(255) original_title, TINYINT UNSIGNED publication_type_id, VARCHAR(16) publisher_code, VARCHAR(13) barcode, VARCHAR(26) dl_code, SMALLINT UNSIGNED memory_required, VARCHAR(50) cheat_mode, VARCHAR(255) protection, VARCHAR(1000) run_command, VARCHAR(255) company, VARCHAR(50) protected)`

Used internally by triggers to test if information being inserted or updated into the `nvg` table is valid.
