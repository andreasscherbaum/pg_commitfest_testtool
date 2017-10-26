
\set ON_ERROR_STOP


-- which type of patches are available
CREATE TABLE "public"."commitfest_patch_type" (
    id                       SERIAL                  NOT NULL PRIMARY KEY,
    name                     TEXT                    NOT NULL UNIQUE
);
INSERT INTO "public"."commitfest_patch_type"
            (name)
     VALUES ('message-id'), ('patch'), ('pull request');



-- all PostgreSQL versions
-- the 'active' flag can be used to schedule tests for all active versions at once
-- see the demo query at the end of the file
-- the idea is that we ask the patch submitter if this is a new feature
-- (only tested against head) or a bugfix (tested against all active versions)
-- the 'active_by_default' can be used in the web interface to make this decision
CREATE TABLE "public"."commitfest_test_pg_versions" (
    id                       SERIAL                  NOT NULL PRIMARY KEY,
    name                     TEXT                    NOT NULL UNIQUE,
    branch_name_prefix         TEXT                    NOT NULL UNIQUE,
    active                   BOOLEAN                 NOT NULL,
    active_by_default        BOOLEAN                 NOT NULL
);
INSERT INTO "public"."commitfest_test_pg_versions"
            (name, branch_name_prefix, active, active_by_default)
     VALUES ('master', 'master', true, true),
            ('10.0', 'REL_10', true, false),
            ('9.6', 'REL9_6', true, false),
            ('9.5', 'REL9_5', true, false),
            ('9.4', 'REL9_4', true, false),
            ('9.3', 'REL9_3', true, false),
            ('9.2', 'REL9_2', true, false),
            ('9.1', 'REL9_1', true, false),
            ('9.0', 'REL9_0', true, false),
            ('8.4', 'REL8_4', false),
            ('8.3', 'REL8_3', false),
            ('8.2', 'REL8_2', false),
            ('8.1', 'REL8_1', false),
            ('8.0', 'REL8_0', false),
            ('7.4', 'REL7_4', false),
            ('7.3', 'REL7_3', false),
            ('7.2', 'REL7_2', false),
            ('7.1', 'REL7_1', false),
            ('7.0', 'REL7_0', false);


-- all supported platforms
-- the 'active' flag can be used to schedule tests for all active platforms at once
-- see the demo query at the end of the file
CREATE TABLE "public"."commitfest_test_platforms" (
    id                       SERIAL                  NOT NULL PRIMARY KEY,
    name                     TEXT                    NOT NULL UNIQUE,
    active                   BOOLEAN                 NOT NULL
);
INSERT INTO "public"."commitfest_test_platforms"
            (name, active)
     VALUES ('linux', true),
            ('windows', false),
            ('osx', false),
            ('freebds', false),
            ('netbsd', false),
            ('openbsd', false);



-- a patch or patch set can appear multiple times for the same PG version, or platforms, if it is re-tested
-- this table is basically the job queue
-- create separate entries per platform and PG version
CREATE TABLE "public"."commitfest_test_patch" (
    id                       BIGSERIAL               NOT NULL PRIMARY KEY,
    -- otherwise called "branch"
    pg_version               INTEGER                 NOT NULL
                                                     REFERENCES "public"."commitfest_test_pg_versions"(id),
    platform                 INTEGER                 NOT NULL
                                                     REFERENCES "public"."commitfest_test_platforms"(id),
    -- descriptive name, but not required
    name                     TEXT                    NOT NULL DEFAULT '',
    ts_added                 TIMESTAMPTZ             NOT NULL
                                                     DEFAULT NOW(),
    -- not started: ts_started IS NULL
    -- started: ts_started is timestamp, ts_finished IS NULL
    -- finished: ts_started is timestamp, ts_finished is timestamp
    ts_started               TIMESTAMPTZ             NULL,
    ts_finished              TIMESTAMPTZ             NULL,
    state                    TEXT                    NOT NULL
                                                     -- queued: still working on it
                                                     -- aborted: something happened which is buildfarm related
                                                     -- failed: patchset failed to compile or run tests
                                                     -- success: everything passed
                                                     CHECK(result IN ('queued', 'aborted', 'failed', 'success'))
                                                     DEFAULT 'queued',
    -- the tool will update this column to the revision used during the test
    -- especially useful so that the website does not have to specify a revision while inserting the job
    git_revision             TEXT                    NOT NULL DEFAULT ''
);



-- the "commitfest_patch" table holds a reference to every patchset
-- a set of patches can be one or multiple entries in this table, all linking back to "commitfest_test_patch"
-- a patch can be a mail message-id (then all patches in the email are handled together), or a link to a pull request
-- a pull request must be a link to the GitHub PR
CREATE TABLE "public"."commitfest_patch" (
    id                       BIGSERIAL               NOT NULL PRIMARY KEY,
    patch                    BIGINT                  NOT NULL
                                                     REFERENCES "public"."commitfest_test_patch"(id),
    -- real identifier for the patch
    -- this can be the message-id for an email in the archive
    -- then all patches in this email are tested together
    -- it can also just a link to a single patch
    --
    -- if multiple patches from different emails are to be tested,
    -- provide one entry in this table per direct link to the patch
    patch_location           TEXT                    NOT NULL,
    patch_type               INTEGER                 NOT NULL
                                                     REFERENCES "public"."commitfest_patch_type"(id),
    repo_url                 TEXT                    NOT NULL DEFAULT ''
);



-- overall results for every test
-- use an extra table to keep "commitfest_test_patch" small
CREATE TABLE "public"."commitfest_test_results" (
    id                       BIGSERIAL               NOT NULL PRIMARY KEY,
    test_id                  BIGINT                  NOT NULL
                                                     REFERENCES "public"."commitfest_test_patch"(id),
    repository               TEXT                    NOT NULL,
    -- same as "commitfest_test_patch".git_revision
    revision                 TEXT                    NOT NULL,
    branch                   TEXT                    NOT NULL,
    -- was this run on "head" at the time of the test
    is_head                  BOOLEAN                 NOT NULL,
    -- time when the test was started
    start_time               TIMESTAMPTZ             NOT NULL,
    -- time when the test was finished
    end_time                 TIMESTAMPTZ             NOT NULL,
    -- did configure run (or did it break before)
    run_configure            BOOLEAN                 NOT NULL,
    run_make                 BOOLEAN                 NOT NULL,
    run_install              BOOLEAN                 NOT NULL,
    run_tests                BOOLEAN                 NOT NULL,
    time_git_update          REAL                    NOT NULL,
    time_configure           REAL                    NOT NULL,
    time_make                REAL                    NOT NULL,
    time_install             REAL                    NOT NULL,
    time_tests               REAL                    NOT NULL,
    result_git_update        INTEGER,
    result_patch             INTEGER,
    result_configure         INTEGER,
    result_make              INTEGER,
    result_install           INTEGER,
    result_tests             INTEGER,
    -- only known if install passed
    pg_version               TEXT,
    pg_version_num           TEXT,
    pg_version_str           TEXT
);



-- extra data for every test
-- use an extra table to keep "commitfest_test_results" reasonable small
-- this table will contain all the output from the different stages
-- this table might contain sensitive information
CREATE TABLE "public"."commitfest_test_data" (
    id                       BIGSERIAL               NOT NULL PRIMARY KEY,
    test_id                  BIGINT                  NOT NULL
                                                     REFERENCES "public"."commitfest_test_results"(id)
                                                     ON DELETE CASCADE,
    patches                  TEXT                    NOT NULL DEFAULT '',
    errorstr                 TEXT                    NOT NULL DEFAULT '',
    stage_git_update         TEXT                    NOT NULL DEFAULT '',
    stage_patch              TEXT                    NOT NULL DEFAULT '',
    stage_configure          TEXT                    NOT NULL DEFAULT '',
    stage_make               TEXT                    NOT NULL DEFAULT '',
    stage_install            TEXT                    NOT NULL DEFAULT '',
    stage_tests              TEXT                    NOT NULL DEFAULT ''
);







-- queue the test with a descriptive name for every active version on every active platform
-- INSERT INTO "public"."commitfest_test_patch"
--             (name, pg_version, platform)
--             SELECT 'Patch 1',
--                    v.id, p.id
--                FROM "public"."commitfest_test_pg_versions" v,
--                     "public"."commitfest_test_platforms" p
--              WHERE v.active = true
--                AND p.active = true;


-- WITH tp AS (
--   SELECT id
--     FROM "public"."commitfest_test_patch"
--    WHERE name = 'Patch 1'
-- )
-- INSERT INTO "public"."commitfest_patch"
--             (patch, patch_location, patch_type)
--      SELECT tp.id,
--             'https://www.postgresql.org/path/to/patch.diff',
--             (SELECT pt.id FROM "public"."commitfest_patch_type" pt WHERE pt.name = 'patch')
--        FROM tp;
