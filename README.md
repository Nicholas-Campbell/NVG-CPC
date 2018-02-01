# NVG-CPC
A set of scripts for reading and using data about files on the NVG Amstrad CPC software archive, located at
ftp://ftp.nvg.ntnu.no/pub/cpc/ .

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
* The names of the authors who programmed it
* The command to type in order to run the program
* The date it was uploaded to NVG, and who uploaded it
* Any other relevant comments

## Files

Currently this repository only contains one Python module (`nvg.csv`). This module contains a single function named
`read_nvg_csv_file` that reads a locally stored copy of the `00_table.csv` file on NVG and stores the data in a dictionary
which can be used by your own scripts.

An example Python 3 script named `search.py` is also included, which enables you to search the list of ZIP files on NVG and
demonstrates how to use the `nvg.csv` module.

## Usage

To use the module in your own Python scripts, copy the `nvg` directory and its contents to your working directory and include the following line in your script:

```python
from nvg.csv import read_nvg_csv_file
```

To read the data from the CSV file into a dictionary named `nvg_file_data`, include the following lines (replacing `nvg_csv_filepath` with the location of the `00_table.csv` file on your own computer):

```python
nvg_csv_filepath = r'00_table.csv'
nvg_file_data = read_nvg_csv_file(nvg_csv_filepath)
```

The dictionary stores the list of ZIP files on NVG as keys, and the data for each file is also stored as a dictionary, with the keys being the names of each field in the `file_id.diz` file. The example below displays the data for the game *Roland on the Ropes*, with the fields being displayed in no particular order:

```python
for field, value in nvg_file_data['games/arcade/rolanrop.zip'].items():
	print(field + ': ' + str(value))
```

The module contains a list named `csv_field_names`, which contains the names of the fields in the same order as the columns in the `00_table.csv` file. You can use this list to display the fields in order:

```python
filepath = 'games/arcade/rolanrop.zip'
for field in nvg.csv.csv_field_names:
	if field in nvg_file_data[filepath].keys():
		print(field + ': ' + str(nvg_file_data[filepath][field]))
```
