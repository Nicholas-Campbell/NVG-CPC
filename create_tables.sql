/* Create tables for the NVG database */

/* Program type ID numbers and descriptions (e.g. 'Emulator', 'Arcade game',
   'Board game', 'Other program', 'Utility') */

CREATE TABLE nvg_type_ids (
	type_id TINYINT UNSIGNED AUTO_INCREMENT,
	type_desc VARCHAR(255) NOT NULL,
	UNIQUE INDEX (type_desc),
	PRIMARY KEY (type_id)
);

/* Publication type ID numbers and descriptions (e.g. 'Commercial', 'Crack',
   'Freeware', 'Public domain', 'Type-in') */

CREATE TABLE nvg_publication_type_ids (
	type_id TINYINT UNSIGNED AUTO_INCREMENT,
	type_desc VARCHAR(255) NOT NULL,
	UNIQUE INDEX (type_desc),
	PRIMARY KEY (type_id)
);

/* IETF language codes and descriptions (e.g. 'en' = 'English', 'fr' =
   'French', 'es' = 'Spanish', 'de' = 'German') */

CREATE TABLE nvg_language_codes (
	language_code VARCHAR(5) NOT NULL,
	language_desc VARCHAR(30) NOT NULL,
	UNIQUE INDEX (language_desc),
	PRIMARY KEY (language_code)
);

/* The main table for storing information about files on the NVG FTP server

   Each file has a unique ID number, which makes searching the database much
   quicker than using the filepath as a primary key */

CREATE TABLE nvg (
	filepath_id INT UNSIGNED AUTO_INCREMENT,
	filepath VARCHAR(260) CHARACTER SET ascii NOT NULL,
	file_size INT UNSIGNED NOT NULL,
	cpcsofts_id SMALLINT UNSIGNED,
	title VARCHAR(255),
	company VARCHAR(255),
	year DATE,
	languages SET('ar','ca','da','de','el','en','en-US','es','fr','ga','it',
		'nl','pt-BR','sv'),
	type_id TINYINT UNSIGNED,
	subtype VARCHAR(255),
	title_screen VARCHAR(50),
	cheat_mode VARCHAR(50),
	protected VARCHAR(50),
	problems VARCHAR(255),
	upload_date DATE,
	uploader VARCHAR(255),
	comments VARCHAR(1000) DEFAULT '',
	original_title VARCHAR(255),
	publication_type_id TINYINT UNSIGNED,
	publisher_code VARCHAR(16),
	barcode VARCHAR(13),
	dl_code VARCHAR(26),
	memory_required SMALLINT UNSIGNED,
	protection VARCHAR(255),
	run_command VARCHAR(1000),
	PRIMARY KEY (filepath_id),
	UNIQUE INDEX (filepath),
	CONSTRAINT FOREIGN KEY fk_type_id (type_id)
		REFERENCES nvg_type_ids (type_id)
		ON UPDATE CASCADE,
	CONSTRAINT FOREIGN KEY fk_publication_type_id (publication_type_id)
		REFERENCES nvg_publication_type_ids (type_id)
		ON UPDATE CASCADE
);

/* Aliases of titles

   Using ON DELETE CASCADE on the fk_filepath_id ensures that deleting a
   filepath from the `nvg` table also deletes any references to it in this
   table */

CREATE TABLE nvg_title_aliases (
	filepath_id INT UNSIGNED,
	title VARCHAR(255),
	PRIMARY KEY (filepath_id, title),
	CONSTRAINT FOREIGN KEY fk_filepath_id (filepath_id)
		REFERENCES nvg (filepath_id)
		ON DELETE CASCADE ON UPDATE CASCADE
);

/* Author ID numbers and names

   Author ID numbers should not be permitted to be modified, because ON UPDATE
   CASCADE does not work in the InnoDB engine if it needs to update a foreign
   key reference in the same table (which is the case for the
   `alias_of_author_id` column */

CREATE TABLE nvg_author_ids (
	author_id SMALLINT UNSIGNED AUTO_INCREMENT,
	author_name VARCHAR(255) NOT NULL,
	alias_of_author_id SMALLINT UNSIGNED,
	PRIMARY KEY (author_id),
	CONSTRAINT FOREIGN KEY fk_alias_of_author (alias_of_author_id)
		REFERENCES nvg_author_ids (author_id)
);

/* ID numbers of authors and the files that they are associated with */

CREATE TABLE nvg_file_authors (
	filepath_id INT UNSIGNED,
	author_id SMALLINT UNSIGNED,
	author_type ENUM ('PUBLISHER','RE-RELEASED BY','CRACKER','DEVELOPER',
		'AUTHOR','DESIGNER','ARTIST','MUSICIAN'),
	author_index SMALLINT UNSIGNED,
	PRIMARY KEY (filepath_id, author_id, author_type),
	UNIQUE INDEX (filepath_id, author_type, author_index),
	CONSTRAINT FOREIGN KEY fk_fa_filepath_id (filepath_id)
		REFERENCES nvg (filepath_id)
		ON DELETE CASCADE ON UPDATE CASCADE,
	CONSTRAINT FOREIGN KEY fk_fa_author_id (author_id)
		REFERENCES nvg_author_ids (author_id)
);
