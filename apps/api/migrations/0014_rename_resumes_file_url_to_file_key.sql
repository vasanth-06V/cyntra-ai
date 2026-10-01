-- The column stores an R2 object key, not a real browsable URL (the bucket
-- is private) -- "file_url" was a misleading name left over from the
-- original schema draft, corrected before the table ever held real data.
alter table resumes rename column file_url to file_key;
