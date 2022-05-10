# NVG-CPC

A set of Python 3 and SQL scripts for reading and using data about files on the NVG Amstrad CPC software FTP archive, located at https://ftp.nvg.ntnu.no/pub/cpc/ .

More information about the Amstrad CPC range of computers is available at [Wikipedia](https://en.wikipedia.org/wiki/Amstrad_CPC).

## Introduction

The NVG Amstrad CPC software archive (hereafter abbreviated to **NVG**) is one of the oldest archives of Amstrad CPC software on the Internet, and it has been around since the mid-1990s.

The most useful source of data about the files on NVG is a CSV file located in the root directory named `00_table.csv`, which can be downloaded at https://ftp.nvg.ntnu.no/pub/cpc/00_table.csv . A plain text file named `00_index_full.txt`, which is also located in the root directory of the archive and contains most of this information in a more human-readable format, is also available and can be downloaded at https://ftp.nvg.ntnu.no/pub/cpc/00_index_full.txt .

Both of these files contain data about ZIP files that are stored on NVG. Each ZIP file on NVG should include a file named `file_id.diz`, which is intended to contain data about the file, such as:

* Its title
* The year it was released
* The software house that published it
* The names of the author(s) who programmed it
* The command to type in order to run the program
* The date it was uploaded to NVG, and who uploaded it
* Any other relevant comments

For example, here are the contents of a ZIP file containing the game *Flying Shark*:

```
    ** AMSTRAD CPC SOFTWARE AT FTP.NVG.NTNU.NO : file_id.diz FILE V 3.10 **
-------------------------------------------------------------------------------
TITLE:           Flying Shark
YEAR:            1989
PUBLISHER:       Firebird
PUBLICATION:     Crack
CRACKER:         CNGSoft
DEVELOPER:       Graftgold
AUTHOR:          Steve Turner
DESIGNER:        Dominic Robinson
ARTIST:          John Cumming
MUSICIAN:        Steve Turner
LANGUAGE:        English
MEMORY REQUIRED: 64K
TYPE:            Arcade game
SUBTYPE:         Plane shoot-'em-up
TITLE SCREEN:    Yes
CHEAT MODE:      Yes
RUN COMMAND:     RUN"FLYING"
UPLOADED:        17/12/2013 by Nicholas Campbell & CNGSoft
COMMENTS:        Press SPACE on the title screen to start the game.
-------------------------------------------------------------------------------
```

## Usage

### Building a MySQL database

The `sql.py` Python script uses the [MySQL](https://www.mysql.com/) or [MariaDB](https://mariadb.org/) database servers. The [PyMySQL](https://pymysql.readthedocs.io/en/latest/) package also needs to be installed to enable this script to connect to the database.

To set up and build the database on `localhost`, use the command below:

```
python3 sql.py -u username -D cpc
```

where `username` is the username to use when connecting to the MySQL host, and `cpc` is the name of the database to use. 

The script creates and updates a MySQL database that contains data about the ZIP files that are stored on NVG, based on information from some CSV files on NVG, which are located at the following URLs:

* `00_table.csv`: https://ftp.nvg.ntnu.no/pub/cpc/00_table.csv
* `author_aliases.csv`: https://ftp.nvg.ntnu.no/pub/cpc/author_aliases.csv
* `cpcpower.csv`: https://ftp.nvg.ntnu.no/pub/cpc/cpcpower.csv

By default, the script will download these files from NVG each time it is run. However, it can also use copies of these files that are stored locally in the same directory as the script. If you wish to use locally stored copies, you can use the `--read-local-files` option:

```
python3 sql.py -u username -D cpc --read-local-files
```

When the database is built, the following tables are created:

* `nvg`: The main table, containing filepaths and their associated ID numbers, and information about them (other than author and publisher information, which is stored in the `nvg_file_authors` table)
* `nvg_author_ids`: ID numbers of authors, and links to alternative names by which certain authors are also known
* `nvg_file_authors`: Associates author ID numbers with programs, and states their role(s) (e.g. AUTHOR, ARTIST, MUSICIAN, PUBLISHER)
* `nvg_language_codes`: Languages used in files (e.g. English, French, German, Spanish), and their corresponding [IETF language tags](https://en.wikipedia.org/wiki/IETF_language_tag) (e.g. 'en', 'fr', 'de', 'es')
* `nvg_publication_type_ids`: ID numbers of publication types of programs that are stored on NVG (e.g. commercial, freeware, public domain, type-in listing)
* `nvg_title_aliases`: Alternative names by which certain programs are also known
* `nvg_type_ids`: ID numbers of categories of programs that are stored on NVG (e.g. arcade game, board game, emulator, utility)

### Updating the database

Once the database has been built, it can be updated by using the same command, i.e.:

```
python3 sql.py -u username -D cpc
```

The script will output messages detailing what data has been inserted and deleted. If you prefer these messages not to be displayed, you can use the `-s` or `--silent` options:

```
python3 sql.py -u username -D cpc -s
```

More information about the command-line options that can be used is available by using either of the commands below:

```
python3 sql.py -?
python3 sql.py --help
```

### Retrieving information from the database

The database is set up with stored procedures and functions that can be used to search the database and retrieve information. Please see the [USAGE.md](USAGE.md) file for further information.
