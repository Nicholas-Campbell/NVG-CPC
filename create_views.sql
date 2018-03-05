/* Views for NVG database */


DROP VIEW IF EXISTS nvg_view;

CREATE VIEW nvg_view
	(filepath_id, filepath, title, company, year, language, type, subtype,
	title_screen, cheat_mode, protected, problems, upload_date, uploader,
	comments, also_known_as, original_title, publisher, rereleased_by,
	publication, publisher_code, barcode, dl_code, cracker, developer, author,
	designer, artist, musician) AS
	SELECT filepath_id, filepath, title, company, YEAR(year),

	-- Convert language codes to names (e.g. 'en' -> 'English')
	concat_language_descs(filepath_id) language,

	-- Convert file type ID numbers to their corresponding descriptions
	(SELECT t.type_desc FROM nvg_type_ids t WHERE n.type_id = t.type_id),

	subtype, title_screen, cheat_mode, protected, problems, upload_date,
	uploader, comments,

	-- Combine aliases of titles into a comma-separated string
	concat_title_aliases(filepath_id) also_known_as,

	original_title,

	-- Convert publisher and re-release ID numbers to their corresponding
	-- names
	concat_author_names(filepath_id, 'PUBLISHER') publisher,
	concat_author_names(filepath_id, 'RE-RELEASED BY') rereleased_by,

	-- Convert publication type ID numbers to their corresponding descriptions
	(SELECT type_desc FROM nvg_publication_type_ids p
		WHERE n.publication_type_id = p.type_id) publication,

	publisher_code, barcode, dl_code,

	-- Convert author ID numbers to comma-separated strings 
	concat_author_names(filepath_id, 'CRACKER') cracker,
	concat_author_names(filepath_id, 'DEVELOPER') developer,
	concat_author_names(filepath_id, 'AUTHOR') author,
	concat_author_names(filepath_id, 'DESIGNER') designer,
	concat_author_names(filepath_id, 'ARTIST') artist,
	concat_author_names(filepath_id, 'MUSICIAN') musician
	FROM nvg n
	ORDER BY filepath_id;
