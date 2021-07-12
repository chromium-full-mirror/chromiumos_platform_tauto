## Introduction

`test_that` is the supported mechanism to run autotests against Chrome OS
devices at your desk.  `test_that` replaces an older script, `run_remote_tests`.

Features for testing a local device:
  - CTRL+C kills `test_that` and all its autoserv children. Orphaned processes
    are no longer left behind.
  - Tests that require binary autotest dependencies will just work, because
    test_that always runs from the sysroot location.
  - Running emerge after python-only test changes is no longer necessary.
    test_that uses autotest_quickmerge to copy your python changes to the
    sysroot.
  - Tests are generally specified to `test_that` by the NAME field of their
    control file. Matching tests by filename is supported using f:[file
    pattern]

In addition to running tests against local device, `test_that` can be used to
launch jobs in the ChromeOS Hardware Lab (or against a local Autotest instance
or a Moblab). This feature is only supported for infrastructure-produced builds
that were uploaded to google storage.

### Example uses (inside the chroot)

TODO update

### Running jobs against a local Autotest setup or MobLab

`test_that` allows you to run jobs against a local Autotest setup or a
MobLab instance. This usage is similar to running tests in the lab. The argument
--web allows you to specify the web address of the Autotest instance you want to
run tests within.

For instance:
```
$ test_that -b lumpy -i lumpy-paladin/R38-6009.0.0-rc4 --web 100.96.51.136 :lab:
dummy_Pass
```

This will kick off the dummy_Pass test on a lumpy device on the Autotest
instance located at 100.96.51.136
