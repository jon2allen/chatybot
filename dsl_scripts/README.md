# dsl_scripts

Working ChatDSL utility scripts - finders, reporters, and maintenance
tasks you run against your own sessions and data. Not part of the
documentation cookbook; these are meant to be executed as-is.

Run any script with:

    /script dsl_scripts/<name>.chatdsl

## Scripts

- `find_test_session.chatdsl` - find every session saved with a test
  model alias, extract the newest non-empty one's first exchange, and
  report whole-session sizes for the first 10 matches.
- `find_test_delete.chatdsl` - find every session saved with a test
  model alias and delete them, gated by an interactive Y/N confirmation
  (safe default: aborts unless confirmed).

## Not to be confused with

- `doc/cookbook/` - curated, documented recipes (the cookbook copies of
  these scripts live there too).
- `dsl_test/` - test fixtures and regression scripts, not utilities.
