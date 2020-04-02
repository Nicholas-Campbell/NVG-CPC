/* Procedure used by triggers to validate data being entered into the nvg
   table */

DROP PROCEDURE IF EXISTS validate_nvg_data;

DELIMITER //
CREATE PROCEDURE validate_nvg_data(IN original_title VARCHAR(255),
	IN publication_type_id TINYINT UNSIGNED,
	IN publisher_code VARCHAR(16),
	IN barcode VARCHAR(13),
	IN dl_code VARCHAR(26),
	IN memory_required SMALLINT UNSIGNED,
	IN cheat_mode VARCHAR(50),
	IN protection VARCHAR(255),
	IN run_command VARCHAR(1000),
	IN company VARCHAR(255),
	IN protected VARCHAR(50)
)
BEGIN
	-- Set default file_id.diz version to 2.00; note that this procedure
	-- cannot accurately determine the file_id.diz version in use, as this
	-- would also require author information from the nvg_file_authors table
	DECLARE file_id_diz_version DECIMAL(3,2) DEFAULT 2.00;

	IF original_title IS NOT NULL AND original_title != ''
	OR publication_type_id IS NOT NULL
	OR (publisher_code IS NOT NULL AND publisher_code != '')
	OR memory_required IS NOT NULL
	OR (protection IS NOT NULL AND protection != '')
	OR (run_command IS NOT NULL AND run_command != '')
	THEN
		SET file_id_diz_version := 3.00;
	END IF;

	-- Check fields used in version 3.10
	IF (barcode IS NOT NULL AND barcode != '')
	OR (dl_code IS NOT NULL AND dl_code != '')
	THEN
		SET file_id_diz_version := 3.10;
	END IF;

	-- Check deprecated fields in versions 3.00 and above (COMPANY and
	-- PROTECTED); if any of these are detected, there is an inconsistency
	-- in the data, so generate an error
	IF file_id_diz_version >= 3.00
	THEN
		IF (company IS NOT NULL AND company != '')
		OR (protected IS NOT NULL AND protected != '')
		THEN
			SIGNAL SQLSTATE '45000' SET message_text =
				'\'company\' and \'protected\' columns are deprecated in file_id.diz versions 3.00 onwards';
		ELSEIF (cheat_mode IS NOT NULL AND cheat_mode != '')
		AND (publication_type_id NOT IN
			(SELECT type_id FROM nvg_publication_type_ids
				WHERE type_desc = 'Crack'
				OR type_desc = 'Crack with modifications'))
		THEN
			SIGNAL SQLSTATE '45000' SET message_text =
				'\'cheat_mode\' column can only be defined in file_id.diz versions 3.00 onwards if publication type has been set to \'Crack\' or \'Crack with modifications\'';
		-- Only certain values are permitted in the memory_required column
		ELSEIF memory_required NOT IN(64,128,256) THEN
			SIGNAL SQLSTATE '45000' SET message_text = 'Invalid value in memory_required column; the only valid values are 64, 128 and 256';
		END IF;
	END IF;

END //
DELIMITER ;


/* Trigger to validate data being inserted into the nvg table */

DROP TRIGGER IF EXISTS validate_nvg_data_bi;

DELIMITER //
CREATE TRIGGER validate_nvg_data_bi
BEFORE INSERT ON nvg FOR EACH ROW
BEGIN
	CALL validate_nvg_data(
		NEW.original_title,
		NEW.publication_type_id,
		NEW.publisher_code,
		NEW.barcode,
		NEW.dl_code,
		NEW.memory_required,
		NEW.cheat_mode,
		NEW.protection,
		NEW.run_command,
		NEW.company,
		NEW.protected
	);
END //
DELIMITER ;


/* Trigger to validate data being updated in the nvg table */

DROP TRIGGER IF EXISTS validate_nvg_data_bu;

DELIMITER //
CREATE TRIGGER validate_nvg_data_bu
BEFORE UPDATE ON nvg FOR EACH ROW
BEGIN
	CALL validate_nvg_data(
		NEW.original_title,
		NEW.publication_type_id,
		NEW.publisher_code,
		NEW.barcode,
		NEW.dl_code,
		NEW.memory_required,
		NEW.cheat_mode,
		NEW.protection,
		NEW.run_command,
		NEW.company,
		NEW.protected
	);
END //
DELIMITER ;


/* Trigger to detect if updating an alias in the nvg_author_ids table will
   result in a circular reference */

DROP TRIGGER IF EXISTS validate_author_id_data_bu;

DELIMITER //
CREATE TRIGGER validate_author_id_data_bu
BEFORE UPDATE ON nvg_author_ids FOR EACH ROW
BEGIN
	DECLARE author_id_param SMALLINT UNSIGNED DEFAULT NEW.alias_of_author_id;
	DECLARE end_author_id SMALLINT UNSIGNED DEFAULT NEW.author_id;
	DECLARE author_id_result SMALLINT UNSIGNED;
	DECLARE error_message VARCHAR(128);

	-- Traverse the tree of author alias ID numbers, starting with the
	-- specified alias ID (alias_of_author_id), until either the specified
	-- author ID number (author_id) is found, or the top of the tree is
	-- reached
	REPEAT
		SELECT alias_of_author_id FROM nvg_author_ids
		WHERE author_id = author_id_param
		INTO author_id_result;
		SET author_id_param := author_id_result;
	UNTIL author_id_result = end_author_id OR author_id_result IS NULL
	END REPEAT;

	-- If the specified author ID number was found, then there is a
	-- circular reference
	IF author_id_result = end_author_id THEN
		SET error_message := CONCAT('Circular reference detected between author IDs ',
			NEW.author_id, ' and ', NEW.alias_of_author_id);
		SIGNAL SQLSTATE '45000' SET message_text = error_message;
	END IF;
END //
DELIMITER ;


/* Trigger to check if file_id.diz version 2.00 is being used when inserting
   new author information in nvg_file_authors table

   There should not be any need to add a BEFORE UPDATE trigger because
   another trigger for the nvg table prevents deprecated columns from being
   updated if author information is present */

DROP TRIGGER IF EXISTS validate_nvg_file_authors_data_bi;
DELIMITER //
CREATE TRIGGER validate_nvg_file_authors_data_bi
BEFORE INSERT ON nvg_file_authors FOR EACH ROW
BEGIN
	DECLARE file_id_diz_version DECIMAL(3,2);
	DECLARE error_message VARCHAR(128);
	DECLARE max_author_index SMALLINT UNSIGNED;

	-- Author information can only be added if the file_id.diz version is 3.00
	-- or greater
	SET file_id_diz_version := get_file_id_diz_version(NEW.filepath_id);
	IF file_id_diz_version < 3.00 THEN
		SET error_message := CONCAT('Unable to insert author information for filepath ID ',
			NEW.filepath_id, '; file_id.diz version ', file_id_diz_version, ' is in use');
		SIGNAL SQLSTATE '45000' SET message_text = error_message;

	-- If no author index is specified, get the maximum index value of the
	-- existing author type and increase it by 1
	ELSEIF NEW.author_index IS NULL THEN
		SET NEW.author_index = 
			(SELECT MAX(author_index) FROM nvg_file_authors
			WHERE filepath_id = NEW.filepath_id
			AND author_type = NEW.author_type) + 1;
	END IF;
END //
DELIMITER ;


/* Procedure used by triggers to validate language codes being entered into the
   nvg_language_codes table

   The IETF language code must consist of a primary language subtag (two
   letters) and an optional region subtag (two letters); if both subtags
   are used, then they must be separated by a hyphen

   For more details, visit the URLs below:
   https://tools.ietf.org/html/rfc5646
   https://en.wikipedia.org/wiki/IETF_language_tag */

DROP PROCEDURE IF EXISTS validate_language_code;

DELIMITER //
CREATE PROCEDURE validate_language_code(INOUT language_code VARCHAR(5))
BEGIN
	DECLARE error_message VARCHAR(128);

	-- Confirm that the language code is in the correct format using a
	-- regular expression
	IF language_code REGEXP '^[a-z]{2}(-[A-Z]{2})?+$' = 0 THEN
		SET error_message := CONCAT('\'', language_code, '\' is not a valid IETF language code for use in the nvg_language_codes table');
		SIGNAL SQLSTATE '45000' SET message_text = error_message;
	END IF;

	-- Convert the subtags to their correct case; the primary language subtag
	-- should be in lower case, and the region subtag should be in upper case

	-- If only the primary language subtag is specified, then the language code
	-- will be 2 characters in length
	IF LENGTH(language_code) = 2 THEN
		SET language_code = LOWER(language_code);
	-- If both the primary language subtag and the region subtag are specified,
	-- then the language code will be 5 characters in length
	ELSEIF LENGTH(language_code) = 5 THEN
		SET language_code = CONCAT(LOWER(SUBSTRING(language_code, 1, 2)),
			'-', UPPER(SUBSTRING(language_code, 4, 2)));
	END IF;
END //
DELIMITER ;


/* Trigger to validate language codes being inserted into the languages
   table */

DROP TRIGGER IF EXISTS validate_language_code_bi;

DELIMITER //
CREATE TRIGGER validate_language_code_bi
BEFORE INSERT ON nvg_language_codes FOR EACH ROW
BEGIN
	CALL validate_language_code(NEW.language_code);
END //
DELIMITER ;


/* Trigger to validate language codes being updated in the languages
   table */

DROP TRIGGER IF EXISTS validate_language_code_bu;

DELIMITER //
CREATE TRIGGER validate_language_code_bu
BEFORE UPDATE ON nvg_language_codes FOR EACH ROW
BEGIN
	CALL validate_language_code(NEW.language_code);
END //
DELIMITER ;
