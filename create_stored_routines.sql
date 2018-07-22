/* Procedure to select author ID numbers and types associated with a
   specified file ID number */

DROP PROCEDURE IF EXISTS get_author_ids;

DELIMITER //
CREATE PROCEDURE get_author_ids(IN filepath_id_param INT UNSIGNED)
BEGIN
	SELECT author_id, author_type, author_index FROM nvg_file_authors
	WHERE filepath_id = filepath_id_param
	ORDER BY author_type, author_index;
END //
DELIMITER ;


/* Procedure to search the table of author aliases, build a tree containing
   all aliases associated with the specified author ID number, store the
   tree in a temporary table (nvg_author_ids_temp) and select the set of
   author IDs

   The temporary table is not deleted on exit, in order to allow it to be
   used by other programs */

DROP PROCEDURE IF EXISTS get_aliases_of_author_id;

DELIMITER //
CREATE PROCEDURE get_aliases_of_author_id(IN author_id_param SMALLINT UNSIGNED)
BEGIN
	DECLARE author_id_result SMALLINT UNSIGNED;
	DECLARE tree_depth_var TINYINT UNSIGNED DEFAULT 0;
	DECLARE all_rows_read BOOLEAN;
	DECLARE result_count SMALLINT UNSIGNED;

	DECLARE cur1 CURSOR FOR
		SELECT author_id FROM nvg_author_ids
			WHERE alias_of_author_id IN (
				SELECT author_id FROM nvg_author_ids_temp
				WHERE tree_depth = tree_depth_var
			);
	DECLARE CONTINUE HANDLER FOR NOT FOUND
		SET all_rows_read := TRUE;

	-- Create a temporary table to store results in; it is also used for
	-- the recursive search of author alias ID numbers
	DROP TEMPORARY TABLE IF EXISTS nvg_author_ids_temp;
	CREATE TEMPORARY TABLE nvg_author_ids_temp
		(author_id SMALLINT UNSIGNED,
		tree_depth TINYINT UNSIGNED);

	-- Find the top of the tree of author alias ID numbers
	SET author_id_result := author_id_param;
	find_top_of_tree_loop: LOOP
		SELECT alias_of_author_id FROM nvg_author_ids
			WHERE author_id = author_id_param
			INTO author_id_result;
		IF author_id_result IS NULL THEN leave find_top_of_tree_loop;
		ELSE SET author_id_param := author_id_result;
		END IF;
	END LOOP find_top_of_tree_loop;

	-- Add the root node to the temporary table and start traversing the
	-- tree from the root node
	INSERT INTO nvg_author_ids_temp VALUES (author_id_param, tree_depth_var);
	REPEAT
		SET result_count := 0;
		SET all_rows_read := FALSE;
		OPEN cur1;
		add_aliases_to_tree_loop: LOOP
			-- Get all aliases of nodes at the specified tree depth; if no
			-- more nodes are found, then the entire tree has been
			-- traversed
			FETCH cur1 INTO author_id_result;
			IF all_rows_read = TRUE THEN leave add_aliases_to_tree_loop;
			END IF;

			-- Insert the results into the temporary table
			SET result_count := result_count + 1;
			INSERT INTO nvg_author_ids_temp VALUES
				(author_id_result, tree_depth_var + 1);
		END LOOP;
		CLOSE cur1;
		SET tree_depth_var := tree_depth_var + 1;
	UNTIL result_count = 0
	END REPEAT;

	SELECT author_id FROM nvg_author_ids_temp
	ORDER BY author_id;

END //
DELIMITER ;


/* Procedure to select author ID numbers, names and types associated with a
   specified file ID number */

DROP PROCEDURE IF EXISTS get_author_names;

DELIMITER //
CREATE PROCEDURE get_author_names(IN filepath_id_param INT UNSIGNED)
BEGIN
	SELECT a.author_id, a.author_name, fa.author_type, fa.author_index FROM nvg_file_authors fa
	INNER JOIN nvg_author_ids a
	USING (author_id)
	WHERE filepath_id = filepath_id_param
	ORDER BY author_type, author_index;
END //
DELIMITER ;


/* Procedure to select filepaths associated with a specified author ID
   number */

DROP PROCEDURE IF EXISTS get_filepath_ids_by_author;

DELIMITER //
CREATE PROCEDURE get_filepath_ids_by_author(IN author_id_param SMALLINT UNSIGNED)
BEGIN
	SELECT filepath_id, author_type FROM nvg_file_authors
	WHERE author_id = author_id_param;
END //
DELIMITER ;


/* Function to return a concatenated string containing the names of all
   authors of a specified type that are associated with a specified filepath
   
   The names are separated by commas */

DROP FUNCTION IF EXISTS concat_author_names;
DELIMITER //
CREATE FUNCTION concat_author_names(filepath_id_param INT UNSIGNED, author_type_param VARCHAR(14))
	RETURNS VARCHAR(1000)
BEGIN
	RETURN (
		SELECT GROUP_CONCAT(a.author_name SEPARATOR ', ')
		FROM nvg_file_authors fa INNER JOIN nvg_author_ids a
		USING (author_id)
		WHERE filepath_id = filepath_id_param AND author_type = author_type_param
		ORDER BY fa.author_index
	);
END //
DELIMITER ;


/* Function to return a concatenated string containing all title aliases of a
   specified file ID number

   If there are no aliases associated with the specified file ID number, then
   return an empty string
   
   The names are separated by semicolons */

DROP FUNCTION IF EXISTS concat_title_aliases;

DELIMITER //
CREATE FUNCTION concat_title_aliases(filepath_id_param INT UNSIGNED)
	RETURNS VARCHAR(1000)
BEGIN
	RETURN (
		SELECT GROUP_CONCAT(title SEPARATOR '; ') FROM nvg_title_aliases
		WHERE filepath_id = filepath_id_param
		ORDER BY title
	);
END //
DELIMITER ;


/* Procedure to select all information about a specified file ID number */

DROP PROCEDURE IF EXISTS get_file_info;

DELIMITER //
CREATE PROCEDURE get_file_info(IN filepath_id_param INT UNSIGNED)
BEGIN
	SELECT filepath, file_size, cpcsofts_id, title, company,
	YEAR(year) AS year, languages, type_id, subtype, title_screen, cheat_mode,
	protected, problems, upload_date, uploader, comments,
	concat_title_aliases(filepath_id_param) AS title_aliases, original_title,
	concat_author_names(filepath_id_param, 'PUBLISHER') AS publisher,
	concat_author_names(filepath_id_param, 'RE-RELEASED BY') AS rereleased_by,
	publication_type_id, publisher_code, barcode, dl_code,
	concat_author_names(filepath_id_param, 'CRACKER') AS cracker,
	concat_author_names(filepath_id_param, 'DEVELOPER') AS developer,
	concat_author_names(filepath_id_param, 'AUTHOR') AS author,
	concat_author_names(filepath_id_param, 'DESIGNER') AS designer,
	concat_author_names(filepath_id_param, 'ARTIST') AS artist,
	concat_author_names(filepath_id_param, 'MUSICIAN') AS musician,
	memory_required, protection, run_command
	FROM nvg
	WHERE filepath_id = filepath_id_param;
END //

DELIMITER ;


/* Function to return the UPLOADED field of a specified file ID number

   The string combines the upload_date and uploader columns */

DROP FUNCTION IF EXISTS get_uploaded_string;

DELIMITER //
CREATE FUNCTION get_uploaded_string(filepath_id_param INT UNSIGNED)
	RETURNS VARCHAR(269)
BEGIN
	DECLARE upload_date_var DATETIME;
	DECLARE uploader_var VARCHAR(255);
	DECLARE upload_str VARCHAR(269) DEFAULT '';

	SELECT upload_date, uploader FROM nvg
		WHERE filepath_id = filepath_id_param
		INTO upload_date_var, uploader_var;

	IF upload_date_var IS NULL THEN
		SET upload_str := CONCAT(upload_str, '?');
	ELSE
		SET upload_str := CONCAT(upload_str,
			DATE_FORMAT(upload_date_var, '%d/%m/%Y'));
	END IF;

	SET upload_str := CONCAT(upload_str, ' by ');

	IF uploader_var IS NULL OR uploader_var = '' THEN
		SET upload_str := CONCAT(upload_str, '?');
	ELSE
		SET upload_str := CONCAT(upload_str, uploader_var);
	END IF;

	RETURN upload_str;
END //
DELIMITER ;


/* Prodecure to select all file ID numbers, titles and author types that are
   associated with a specified author ID */

DROP PROCEDURE IF EXISTS get_titles_by_author;

DELIMITER //
CREATE PROCEDURE get_titles_by_author(IN author_id_param SMALLINT UNSIGNED)
BEGIN
	SELECT fa.filepath_id, n.title, fa.author_type FROM nvg_file_authors fa
	INNER JOIN nvg n
	USING (filepath_id)
	WHERE author_id = author_id_param
	ORDER BY title;
END //
DELIMITER ;


/* Procedure to select all file ID numbers and filepaths that match a
   specified search term */

DROP PROCEDURE IF EXISTS search_filepaths;

DELIMITER //
CREATE PROCEDURE search_filepaths(IN search_term_param VARCHAR(260))
BEGIN
	SELECT filepath_id, filepath FROM nvg
	WHERE filepath LIKE search_term_param
	ORDER BY filepath;
END //
DELIMITER ;


/* Procedure to select all file ID numbers and titles that match a specified
   search term

   A column called is_alias is returned as a boolean, which states whether
   the string in the title column is an alias or not */

DROP PROCEDURE IF EXISTS search_titles;

DELIMITER //
CREATE PROCEDURE search_titles(IN search_term_param VARCHAR(255))
BEGIN
	SELECT filepath_id, title, FALSE is_alias FROM nvg
	WHERE title LIKE search_term_param
	UNION ALL
	SELECT filepath_id, title, TRUE is_alias FROM nvg_title_aliases
	WHERE title LIKE search_term_param	
	ORDER BY filepath_id, is_alias, title;
END //
DELIMITER ;


/* Procedure to select all author ID numbers and names that match a specified
   search term */

DROP PROCEDURE IF EXISTS search_authors;

DELIMITER //
CREATE PROCEDURE search_authors(IN search_term_param VARCHAR(255))
BEGIN
	SELECT DISTINCT a.author_id, a.author_name, a.alias_of_author_id, fa.author_type FROM nvg_author_ids a
	LEFT JOIN nvg_file_authors fa
	USING (author_id)
	WHERE a.author_name LIKE search_term_param
	ORDER BY a.author_name, a.author_id;
END //
DELIMITER ;


/* Function to return the description associated with a language code */

DROP FUNCTION IF EXISTS get_language_desc;

DELIMITER //
CREATE FUNCTION get_language_desc(language_code_param VARCHAR(5))
	RETURNS VARCHAR(30)
BEGIN
	RETURN (SELECT language_desc FROM nvg_language_codes
		WHERE language_code = language_code_param);
END //
DELIMITER ;


/* Function to return a concatenated string containing descriptions of all
   the languages associated with a specified file ID number, sorted in
   alphabetical order (e.g. "English, French, German, Spanish")
   
   The names are separated by commas */

DROP FUNCTION IF EXISTS concat_language_descs;

DELIMITER //
CREATE FUNCTION concat_language_descs(filepath_id_param INT UNSIGNED)
	RETURNS VARCHAR(100)
BEGIN
	DECLARE language_code_str VARCHAR(5);
	DECLARE language_desc_str VARCHAR(30);
	DECLARE filepath_languages VARCHAR(50);
	DECLARE language_str VARCHAR(100) DEFAULT '';
	DECLARE all_rows_read BOOLEAN DEFAULT FALSE;
	DECLARE cur1 CURSOR FOR
		SELECT language_code, language_desc FROM nvg_language_codes
		ORDER BY language_desc;
	DECLARE CONTINUE HANDLER FOR NOT FOUND
		SET all_rows_read := TRUE;

	-- Get the set of language codes used by the specified file ID number
	SELECT languages FROM nvg WHERE filepath_id = filepath_id_param
		INTO filepath_languages;

	-- Read each language code from the language codes table one at a time
	OPEN cur1;
	get_lang_loop: LOOP
		FETCH cur1 INTO language_code_str, language_desc_str;
		IF all_rows_read = TRUE THEN LEAVE get_lang_loop;
		END IF;

		-- If this language code is used by the specified file ID number
		-- then add it to the string containing the names of the languages
		-- used
		IF FIND_IN_SET(language_code_str, filepath_languages) THEN
			IF language_str = '' THEN
				SET language_str := language_desc_str;
			ELSE
				SET language_str := CONCAT(language_str, ', ', language_desc_str);
			END IF;
		END IF;
	END LOOP get_lang_loop;
	CLOSE cur1;

	IF language_str = '' THEN RETURN NULL;
	ELSE RETURN language_str;
	END IF;
END //
DELIMITER ;


/* Function to determine the version number of the information entered for
   a specified file ID number */

DROP FUNCTION IF EXISTS get_file_id_diz_version;

DELIMITER //
CREATE FUNCTION get_file_id_diz_version(filepath_id_param INT UNSIGNED)
	RETURNS DECIMAL(3,2)
BEGIN
	-- Set default file_id.diz version to 2.00
	DECLARE file_id_diz_version DECIMAL(3,2) DEFAULT 2.00;
	DECLARE original_title_var VARCHAR(255);
	DECLARE publication_type_id_var TINYINT UNSIGNED;
	DECLARE publisher_code_var VARCHAR(16);
	DECLARE barcode_var VARCHAR(13);
	DECLARE dl_code_var VARCHAR(26);
	DECLARE memory_required_var SMALLINT UNSIGNED;
	DECLARE company_var VARCHAR(255);
	DECLARE protected_var VARCHAR(255);
	DECLARE protection_var VARCHAR(255);
	DECLARE run_command_var VARCHAR(1000);

	SELECT company, original_title, publication_type_id, publisher_code,
	barcode, dl_code, memory_required, protected, protection, run_command
	FROM nvg
	WHERE filepath_id = filepath_id_param
	INTO company_var, original_title_var, publication_type_id_var,
	publisher_code_var, barcode_var, dl_code_var, memory_required_var,
	protected_var, protection_var, run_command_var;

	-- Check fields used in version 3.00
	-- Do any aliases exist (i.e. ALSO KNOWN AS field is defined)?
	IF (SELECT COUNT(filepath_id) FROM nvg_title_aliases
		WHERE filepath_id = filepath_id_param) > 0
	-- Is the ORIGINAL TITLE field defined?
	OR (original_title_var IS NOT NULL AND original_title_var != '')
	-- Does any author information exist (e.g. PUBLISHER, RE-RELEASED BY,
	-- DEVELOPER, AUTHOR, DESIGNER, ARTIST, MUSICIAN, CRACKER)?
	OR (SELECT COUNT(filepath_id) FROM nvg_file_authors
		WHERE filepath_id = filepath_id_param) > 0
	-- Are the PUBLICATION and/or PUBLISHER CODE fields defined?
	OR publication_type_id_var IS NOT NULL
	OR (publisher_code_var IS NOT NULL AND publisher_code_var != '')
	-- Is the MEMORY REQUIRED field defined?
	OR memory_required_var IS NOT NULL
	-- Are the PROTECTION and RUN COMMAND fields defined?
	OR (protection_var IS NOT NULL AND protection_var != '')
	OR (run_command_var IS NOT NULL AND run_command_var != '')
	THEN
		SET file_id_diz_version := 3.00;
	END IF;

	-- Check fields used in version 3.10
	IF (SELECT COUNT(filepath_id) FROM nvg_file_authors
		WHERE filepath_id = filepath_id_param
		AND author_type = 'DESIGNER') > 0
	OR (barcode_var IS NOT NULL AND barcode_var != '')
	OR (dl_code_var IS NOT NULL AND dl_code_var != '')
	THEN
		SET file_id_diz_version := 3.10;
	END IF;

	-- Check deprecated fields in versions 3.00 and above (COMPANY and
	-- PROTECTED); if any of these are detected, there is an inconsistency
	-- in the data, so set the file_id.diz version to NULL
	IF file_id_diz_version >= 3.00 THEN
		IF (company_var IS NOT NULL AND company_var != '')
		OR (protected_var IS NOT NULL AND protected_var != '')
		THEN
			SET file_id_diz_version = NULL;
		END IF;
	END IF;

	RETURN file_id_diz_version;
END //
DELIMITER ;


/* Function to create the file_id.diz file associated with a specified
   file ID number */

DROP FUNCTION IF EXISTS get_file_id_diz;

DELIMITER //
CREATE FUNCTION get_file_id_diz(filepath_id_param INT UNSIGNED)
	RETURNS VARCHAR(2500)
BEGIN
	DECLARE file_id_diz_str VARCHAR(2500) DEFAULT '';
	DECLARE file_id_diz_version DECIMAL(3,2);
	DECLARE filepath_var VARCHAR(260);
	DECLARE title_var VARCHAR(255);
	DECLARE title_aliases_var VARCHAR(1000);
	DECLARE original_title_var VARCHAR(255);
	DECLARE year_var DATE;
	DECLARE publisher_var VARCHAR(1000);
	DECLARE publication_type_id_var TINYINT;
	DECLARE publisher_code_var VARCHAR(16);
	DECLARE barcode_var VARCHAR(13);
	DECLARE dl_code_var VARCHAR(26);
	DECLARE cracker_var VARCHAR(1000);
	DECLARE developer_var VARCHAR(1000);
	DECLARE author_var VARCHAR(1000);
	DECLARE designer_var VARCHAR(1000);
	DECLARE artist_var VARCHAR(1000);
	DECLARE musician_var VARCHAR(1000);
	DECLARE languages_var VARCHAR(100);
	DECLARE memory_required_var SMALLINT UNSIGNED;
	DECLARE rereleased_by_var VARCHAR(1000);
	DECLARE company_var VARCHAR(255);
	DECLARE type_id_var TINYINT UNSIGNED;
	DECLARE subtype_var VARCHAR(255);
	DECLARE title_screen_var VARCHAR(50);
	DECLARE cheat_mode_var VARCHAR(50);
	DECLARE protected_var VARCHAR(255);
	DECLARE problems_var VARCHAR(255);
	DECLARE upload_date_var DATETIME;
	DECLARE uploader_var VARCHAR(255);
	DECLARE comments_var VARCHAR(1000);
	DECLARE protection_var VARCHAR(255);
	DECLARE run_command_var VARCHAR(1000);

	SELECT filepath, title, company, year, type_id, subtype, original_title,
		publication_type_id, publisher_code, barcode, dl_code,
		memory_required, title_screen, cheat_mode, protected, problems,
		upload_date, uploader, comments, protection, run_command
	FROM nvg
	WHERE filepath_id = filepath_id_param
	INTO filepath_var, title_var, company_var, year_var, type_id_var, subtype_var,
		original_title_var,
		publication_type_id_var, publisher_code_var, barcode_var,
		dl_code_var, memory_required_var, title_screen_var,
		cheat_mode_var, protected_var, problems_var, upload_date_var,
		uploader_var, comments_var, protection_var, run_command_var;

	SET languages_var := concat_language_descs(filepath_id_param);

	-- Get the file_id.diz version number
	SET file_id_diz_version = get_file_id_diz_version(filepath_id_param);

	-- Build first line of file_id.diz
	IF file_id_diz_version >= 3.00 THEN
		SET file_id_diz_str := '    ';
	END IF;

	SET file_id_diz_str := CONCAT(file_id_diz_str, '** AMSTRAD ');
	
	IF SUBSTRING(filepath_var, 1, 4) = 'pcw/' THEN
		SET file_id_diz_str := CONCAT(file_id_diz_str, 'PCW');
	ELSE
		SET file_id_diz_str := CONCAT(file_id_diz_str, 'CPC');
	END IF;
	
	SET file_id_diz_str := CONCAT(file_id_diz_str, ' SOFTWARE AT FTP.NVG.NTNU.NO : file_id.diz FILE V ');

	IF file_id_diz_version >= 3.00 THEN
		SELECT concat_title_aliases(filepath_id_param)
			INTO title_aliases_var;
		SELECT concat_author_names(filepath_id_param, 'PUBLISHER')
			INTO publisher_var;
		SELECT concat_author_names(filepath_id_param, 'RE-RELEASED BY')
			INTO rereleased_by_var;
		SELECT concat_author_names(filepath_id_param, 'CRACKER')
			INTO cracker_var;
		SELECT concat_author_names(filepath_id_param, 'DEVELOPER')
			INTO developer_var;
		SELECT concat_author_names(filepath_id_param, 'AUTHOR')
			INTO author_var;
		SELECT concat_author_names(filepath_id_param, 'DESIGNER')
			INTO designer_var;
		SELECT concat_author_names(filepath_id_param, 'ARTIST')
			INTO artist_var;
		SELECT concat_author_names(filepath_id_param, 'MUSICIAN')
			INTO musician_var;
	END IF;

	SET file_id_diz_str := CONCAT(file_id_diz_str, file_id_diz_version,
		' **\n');

	-- Version 2.00
	IF file_id_diz_version < 3.00 THEN
		SET file_id_diz_str := CONCAT(file_id_diz_str, REPEAT('-', 71), '\n');

		IF title_var IS NOT NULL AND title_var != '' THEN
			SET file_id_diz_str := CONCAT(file_id_diz_str,
				'TITLE:        ', title_var, '\n');
		END IF;

		SET file_id_diz_str := CONCAT(file_id_diz_str, 'COMPANY:      ');
		IF company_var IS NULL OR company_var = '' THEN
			SET file_id_diz_str = CONCAT(file_id_diz_str, '?\n');
		ELSE
			SET file_id_diz_str := CONCAT(file_id_diz_str, company_var, '\n');
		END IF;

		IF year_var IS NULL THEN
			SET file_id_diz_str := CONCAT(file_id_diz_str, 'YEAR:         19??\n');
		ELSE
			SET file_id_diz_str := CONCAT(file_id_diz_str, 'YEAR:         ',
				YEAR(year_var), '\n');
		END IF;

		SET file_id_diz_str := CONCAT(file_id_diz_str, 'LANGUAGE:     ',
			concat_language_descs(filepath_id_param), '\n');
		
		SET file_id_diz_str = CONCAT(file_id_diz_str, 'TYPE:         ');
		IF type_id_var IS NULL THEN
			SET file_id_diz_str := CONCAT(file_id_diz_str, '?\n');
		ELSE
			SET file_id_diz_str := CONCAT(file_id_diz_str,
			(SELECT type_desc FROM nvg_type_ids WHERE type_id = type_id_var), '\n');
		END IF;

		SET file_id_diz_str := CONCAT(file_id_diz_str, 'SUBTYPE:      ');
		IF subtype_var IS NULL OR subtype_var = '' THEN
			SET file_id_diz_str = CONCAT(file_id_diz_str, '?\n');
		ELSE
			SET file_id_diz_str := CONCAT(file_id_diz_str, subtype_var, '\n');
		END IF;

		SET file_id_diz_str := CONCAT(file_id_diz_str, 'TITLE SCREEN: ');
		IF title_screen_var IS NULL OR title_screen_var = '' THEN
			SET file_id_diz_str = CONCAT(file_id_diz_str, '-\n');
		ELSE
			SET file_id_diz_str := CONCAT(file_id_diz_str, title_screen_var, '\n');
		END IF;

		SET file_id_diz_str := CONCAT(file_id_diz_str, 'CHEAT MODE:   ');
		IF cheat_mode_var IS NULL OR cheat_mode_var = '' THEN
			SET file_id_diz_str = CONCAT(file_id_diz_str, '-\n');
		ELSE
			SET file_id_diz_str := CONCAT(file_id_diz_str, cheat_mode_var, '\n');
		END IF;

		SET file_id_diz_str := CONCAT(file_id_diz_str, 'PROTECTED:    ');
		IF protected_var IS NULL OR protected_var = '' THEN
			SET file_id_diz_str = CONCAT(file_id_diz_str, '-\n');
		ELSE
			SET file_id_diz_str := CONCAT(file_id_diz_str, protected_var, '\n');
		END IF;

		SET file_id_diz_str := CONCAT(file_id_diz_str, 'PROBLEMS:     ');
		IF problems_var IS NULL OR problems_var = '' THEN
			SET file_id_diz_str = CONCAT(file_id_diz_str, '-\n');
		ELSE
			SET file_id_diz_str := CONCAT(file_id_diz_str, problems_var, '\n');
		END IF;

		SET file_id_diz_str := CONCAT(file_id_diz_str, 'UPLOADED:     ',
			get_uploaded_string(filepath_id_param), '\n');

		SET file_id_diz_str := CONCAT(file_id_diz_str, 'COMMENTS:     ');
		IF comments_var IS NULL OR comments_var = '' THEN
			SET file_id_diz_str = CONCAT(file_id_diz_str, '?\n');
		ELSE
			SET file_id_diz_str := CONCAT(file_id_diz_str, comments_var, '\n');
		END IF;

		SET file_id_diz_str := CONCAT(file_id_diz_str, REPEAT('-', 71), '\n');
	ELSE

	-- Version 3.00 and above
		SET file_id_diz_str := CONCAT(file_id_diz_str, REPEAT('-', 79), '\n');

		IF title_var IS NOT NULL AND title_var != '' THEN
			SET file_id_diz_str := CONCAT(file_id_diz_str,
				'TITLE:           ', title_var, '\n');
		END IF;

		IF title_aliases_var != '' THEN
			SET file_id_diz_str := CONCAT(file_id_diz_str, 'ALSO KNOWN AS:   ',
				title_aliases_var, '\n');
		END IF;

		IF original_title_var IS NOT NULL and original_title_var != '' THEN
			SET file_id_diz_str := CONCAT(file_id_diz_str, 'ORIGINAL TITLE:  ',
				original_title_var, '\n');
		END IF;

		IF year_var IS NOT NULL THEN
			SET file_id_diz_str := CONCAT(file_id_diz_str, 'YEAR:            ',
				YEAR(year_var), '\n');
		END IF;

		IF publisher_var != '' THEN
			SET file_id_diz_str := CONCAT(file_id_diz_str, 'PUBLISHER:       ',
				publisher_var, '\n');
		END IF;

		IF rereleased_by_var != '' THEN
			SET file_id_diz_str := CONCAT(file_id_diz_str, 'RE-RELEASED BY:  ',
				rereleased_by_var, '\n');
		END IF;

		IF publication_type_id_var IS NOT NULL THEN
			SET file_id_diz_str := CONCAT(file_id_diz_str, 'PUBLICATION:     ',
				(SELECT type_desc FROM nvg_publication_type_ids WHERE type_id = publication_type_id_var), '\n');
		END IF;

		IF publisher_code_var IS NOT NULL AND publisher_code_var != '' THEN
			SET file_id_diz_str := CONCAT(file_id_diz_str, 'PUBLISHER CODE:  ',
				publisher_code_var, '\n');
		END IF;

		IF barcode_var IS NOT NULL AND barcode_var != '' THEN
			SET file_id_diz_str := CONCAT(file_id_diz_str, 'BARCODE:         ',
				barcode_var, '\n');
		END IF;

		IF dl_code_var IS NOT NULL AND dl_code_var != '' THEN
			SET file_id_diz_str := CONCAT(file_id_diz_str, 'DL CODE:         ',
				dl_code_var, '\n');
		END IF;

		IF cracker_var IS NOT NULL THEN
			SET file_id_diz_str := CONCAT(file_id_diz_str, 'CRACKER:         ',
				cracker_var, '\n');
		END IF;

		IF developer_var IS NOT NULL THEN
			SET file_id_diz_str := CONCAT(file_id_diz_str, 'DEVELOPER:       ',
				developer_var, '\n');
		END IF;

		IF author_var IS NOT NULL THEN
			SET file_id_diz_str := CONCAT(file_id_diz_str, 'AUTHOR:          ',
				author_var, '\n');
		END IF;

		IF designer_var IS NOT NULL THEN
			SET file_id_diz_str := CONCAT(file_id_diz_str, 'DESIGNER:        ',
				designer_var, '\n');
		END IF;

		IF artist_var IS NOT NULL THEN
			SET file_id_diz_str := CONCAT(file_id_diz_str, 'ARTIST:          ',
				artist_var, '\n');
		END IF;

		IF musician_var IS NOT NULL THEN
			SET file_id_diz_str := CONCAT(file_id_diz_str, 'MUSICIAN:        ',
				musician_var, '\n');
		END IF;

		IF languages_var IS NOT NULL THEN
			SET file_id_diz_str := CONCAT(file_id_diz_str, 'LANGUAGE:        ',
				languages_var, '\n');
		END IF;

		IF memory_required_var IS NOT NULL THEN
			SET file_id_diz_str := CONCAT(file_id_diz_str, 'MEMORY REQUIRED: ',
				memory_required_var, 'K\n');
		END IF;

		IF type_id_var IS NOT NULL THEN
			SET file_id_diz_str := CONCAT(file_id_diz_str, 'TYPE:            ',
				(SELECT type_desc FROM nvg_type_ids WHERE type_id = type_id_var), '\n');
		END IF;

		IF subtype_var IS NOT NULL AND subtype_var != '' THEN
			SET file_id_diz_str := CONCAT(file_id_diz_str, 'SUBTYPE:         ',
				subtype_var, '\n');
		END IF;

		IF title_screen_var IS NOT NULL AND title_screen_var != '' THEN
			SET file_id_diz_str := CONCAT(file_id_diz_str, 'TITLE SCREEN:    ',
				title_screen_var, '\n');
		END IF;

		IF cheat_mode_var IS NOT NULL AND cheat_mode_var != '' THEN
			SET file_id_diz_str := CONCAT(file_id_diz_str, 'CHEAT MODE:      ',
				cheat_mode_var, '\n');
		END IF;

		IF protection_var IS NOT NULL AND protection_var != '' THEN
			SET file_id_diz_str := CONCAT(file_id_diz_str, 'PROTECTION:      ',
				protection_var, '\n');
		END IF;

		IF problems_var IS NOT NULL AND problems_var != '' THEN
			SET file_id_diz_str := CONCAT(file_id_diz_str, 'PROBLEMS:        ',
				problems_var, '\n');
		END IF;

		IF run_command_var IS NOT NULL AND run_command_var != '' THEN
			SET file_id_diz_str := CONCAT(file_id_diz_str, 'RUN COMMAND:     ',
				run_command_var, '\n');
		END IF;

		SET file_id_diz_str := CONCAT(file_id_diz_str, 'UPLOADED:        ',
			get_uploaded_string(filepath_id_param), '\n');

		IF comments_var IS NOT NULL AND comments_var != '' THEN
			SET file_id_diz_str := CONCAT(file_id_diz_str, 'COMMENTS:        ',
				comments_var, '\n');
		END IF;

		SET file_id_diz_str := CONCAT(file_id_diz_str, REPEAT('-', 79), '\n');

	END IF;

	RETURN file_id_diz_str;
END //
DELIMITER ;
