# NVG-CPC
A set of scripts for reading and using data about files on the NVG Amstrad CPC software archive, located at
ftp://ftp.nvg.ntnu.no/pub/cpc/ .

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
