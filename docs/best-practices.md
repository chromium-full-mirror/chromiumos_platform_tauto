# Autotest Best Practices
When the Chrome OS team started using autotest, we tried our best to figure out
how to fit our code and our tests into the upstream style with little guidance
and poor documentation.  This went poorly.  With the benefit of hindsight,
we’re going to lay out some best-practices that we’d like to enforce going
forward.  In many cases, there is legacy code that contradicts this style; we
should go through and refactor that code to fit these guidelines as time
allows.

## Upstream Documentation

There is a sizeable volume of general Autotest documentation available on
github:
https://github.com/autotest/autotest/wiki

## Coding style

Basically PEP-8.  See [docs/coding-style.md](coding-style.md)

## Where should my code live?

| Type of Code              | Relative Path           |
|---------------------------|-------------------------|
| client-side tests         | client/site_tests/      |
| server-side tests         | server/site_tests       |
| common library code       | client/common_lib/cros/ |
| server-only library code  | server/cros             |
