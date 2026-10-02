-- Token-lean interviews: a distilled brief replaces the full JD in every turn,
-- the summarizer becomes incremental, and resumes carry a short digest.
alter table interviews add column brief text;
alter table interviews add column summarized_through_turn int not null default 0;
alter table resumes add column digest text;
