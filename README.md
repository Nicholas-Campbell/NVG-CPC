# NVG-CPC
A set of Python and SQL scripts for reading and using data about files on the NVG Amstrad CPC software FTP archive, located at ftp://ftp.nvg.ntnu.no/pub/cpc/ .

More information about the Amstrad CPC range of computers is available at [Wikipedia](https://en.wikipedia.org/wiki/Amstrad_CPC).

## Introduction

The NVG Amstrad CPC software archive (hereafter abbreviated to **NVG**) is one of the oldest archives of Amstrad CPC software
on the Internet, and it has been around since the mid-1990s.

The most useful source of data about the files on NVG is a CSV file located in the root directory named `00_table.csv`, which can
be downloaded at ftp://ftp.nvg.ntnu.no/pub/cpc/00_table.csv . A plain text file named `00_index_full.txt`, which is also located
in the root directory of the archive and contains most of this information in a more human-readable format, is also available and
can be downloaded at ftp://ftp.nvg.ntnu.no/pub/cpc/00_index_full.txt .

Both of these files contain data about ZIP files that are stored on NVG. Each ZIP file on NVG should include a file named
`file_id.diz`, which is intended to contain data about the file, such as:

* Its title
* The year it was released
* The software house that published it
* The names of the author(s) who programmed it
* The command to type in order to run the program
* The date it was uploaded to NVG, and who uploaded it
* Any other relevant comments

## Usage

### Setting up and updating the database

The `sql.py` Python script uses the [MySQL](https://www.mysql.com/) or [MariaDB](https://mariadb.org/) database servers. The [PyMySQL](https://pymysql.readthedocs.io/en/latest/) package also needs to be installed to enable this script to connect to the database.

The script creates and updates a MySQL database of data about the files on NVG, based on information from the `00_table.csv` and `cpcpower.csv` files on NVG, which can be downloaded from the following URLs:

* `00_table.csv`: ftp://ftp.nvg.ntnu.no/pub/cpc/00_table.csv
* `cpcpower.csv`: ftp://ftp.nvg.ntnu.no/pub/cpc/cpcpower.csv

By default, the script uses a local copy of this file that is stored in the same directory as this script.

To set up and build the database on `localhost`, use the command below:

```
python sql.py -u username -D cpc
```

where `username` is the username to use when connecting to the MySQL host, and `cpc` is the name of the database to use.

It you wish to download the relevant CSV files from NVG itself rather than storing copies of them locally, you can use the `--ftp-download` option, e.g.:

```
python sql.py -u username -D cpc --ftp-download
```

Information about further command-line options is available by using the command below:

```
python sql.py -?
```

### Reading data from the database

The database is set up with stored procedures and functions that can be used to search the database and retrieve information. Please see the `USAGE.md` file for further information.
