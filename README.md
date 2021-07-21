# Autotest: Automated integration testing for Android and Chrome OS Devices

Autotest is a framework for fully automated testing. It was originally designed
to test the Linux kernel, and expanded by the Chrome OS team to validate
complete system images of Chrome OS and Android.

Autotest is composed of a number of modules that will help you to do stand alone
tests or setup a fully automated test grid, depending on what you are up to.
A non extensive list of functionality is:


## Run some tauto tests

TODO: formalize/finish this.

Currently, Tauto only has 1 test to verify basic test-harness stability. This
test is a client side test, dummy_Pass. There are no server side tests (yet).

To work in Tauto, the only requirement is a reasonably up-to-date chroot, and a
working dut (test build) on a network your chroot can ssh with (lab network).

To run a test:
```bash
(inside)
cd ~/trunk/src/platform/tauto/
export tauto_dir=$(pwd)
cd site_utils
ssh-agent python3 test_that.py <DUT IP> dummy_Pass --autotest_dir=${tauto_dir} --py_version=3
```

*Note:* There is a TODO to clean this up to a cleaner cmd, but for now it should work.


If this works, you should see something like this:
```bash
---------------------------------------------------------------------------
/tmp/test_that_results_ib6w8qq6/results-1-dummy_Pass            [  PASSED  ]
/tmp/test_that_results_ib6w8qq6/results-1-dummy_Pass/dummy_Pass [  PASSED  ]
---------------------------------------------------------------------------
Total PASS: 2/2 (100%)

```

*Note2:* For some TBD reason, this test is a little slower than it should be,
but after the first run, all subsiquent should be <20 seconds or so.

## Write some tauto tests

TODO

## Grabbing the latest source

TODO

## Hacking and submitting patches

See the coding style guide for guidance on submitting patches.

[Coding Style](docs/coding-style.md)

## Pre-upload hook dependencies

TODO

## Checking in code

Right now its not expected that all the Tauto unittest's work (this note will
be removed when they do). Thus, running those prior to checkin is not
expected. However, the `dummy_Pass` test **must** work in python 3 prior to
a checkin. Please do not check in without running this test. It only takes
~10-20 seconds, and saves lots of headache of a harness breaking, as there is
no CQ-coverage ATM.
Additionally, as there no CQ coverage, once you get an OWNER +2, just submit.