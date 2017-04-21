# Database for PostgreSQL Commitfest Test Tool

## Tables


### commitfest_patch_type

Contains a list of possible patch types:

* message-id: a Message-ID in the PostgreSQL archive (list only the Message-ID, not the full path)
* patch: a link to a patch (complete URL required)
* pull request: a link to a GitHub Pull Request


### commitfest_test_pg_versions

Lists all known PostgreSQL versions, along with a flag if the version is to be tested. Versions which are no lonmger supported by the community can be easily deactivated here.


### commitfest_test_platforms

Lists all known OS platforms, along with a flag if the platform is to be tested. The test tool has yet another set of configuration options which specify the supported platform(s) for an installation. It is possible that an active platform has no running test tool which can run queued jobs for this platform.


### commitfest_test_patch

One entry per PostgreSQL version and platform, and per test run, and per patch. Multiple tests for the same patch just re-queue the patch in this table.

If a queued test is currently worked on, the _working_on_ flag is set to _TRUE_.

If a queued test is finished (no matter the result), the _finished_ flag is set to _TRUE_.

The _result_ column holds the last status for this specific job.

Overall test status for a patch should be determined by the last available result (finished is true) for any given combination of PostgreSQL version and supported platform.


### commitfest_patch

The actual patch information goes into this table. Every test in _commitfest_test_patch_ can have multiple entries in _commitfest_patch_, and they should be applied in order (ORDER BY id DESC).


### commitfest_test_results

Holds overall test results for a queued test.


### commitfest_test_data

Holds detailed information about a specific test.

_commitfest_test_results_ and _commitfest_test_data_ hold data about the same test, but _commitfest_test_data_ can grow quite big.
