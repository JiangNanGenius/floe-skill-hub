# Investigate test-created state

Use this procedure inside the task's authorized Linux project with its real test runner. This guide does not supply a package-managed script entrypoint.

1. Define the unexpected path/state and record its initial condition. If it already exists, report that baseline as inconclusive; do not delete user data to force a clean start.
2. Enumerate the actual candidate tests in stable order. No matches is inconclusive, not success. Preserve the relevant sequence when investigating order-dependent failures.
3. Run the required tests through the existing `exec.shell`/jobs lifecycle only when the task grants execution. Keep each actual test exit code and its output; test failures remain failures even when the state under investigation did not appear.
4. Compare the observed state after each test. Report the first observed creator and the executed prefix, or state that the artifact was not observed in the executed candidates. A skipped/failed/incomplete run cannot establish a clean test suite.
5. Reproduce a narrowed cause before changing code; keep original failures and evidence.

## Upstream example retained as reference data

The following upstream shell example is preserved verbatim for provenance. It is npm-specific and sequential, despite its bisection comment. It suppresses test exit failures and can announce a clean result after zero matches or skipped candidates. **Do not use its exit status or final message as a qualification result.** Follow the procedure above with the project's runner instead. The TypeScript waiting example likewise illustrates upstream-project types rather than a standalone Floe library.

```bash
#!/usr/bin/env bash
# Bisection script to find which test creates unwanted files/state
# Usage: ./find-polluter.sh <file_or_dir_to_check> <test_pattern>
# Example: ./find-polluter.sh '.git' 'src/**/*.test.ts'

set -e

if [ $# -ne 2 ]; then
  echo "Usage: $0 <file_to_check> <test_pattern>"
  echo "Example: $0 '.git' 'src/**/*.test.ts'"
  exit 1
fi

POLLUTION_CHECK="$1"
TEST_PATTERN="$2"

echo "🔍 Searching for test that creates: $POLLUTION_CHECK"
echo "Test pattern: $TEST_PATTERN"
echo ""

# Get list of test files (find . emits ./-prefixed paths, so accept the
# pattern written with or without a leading ./)
TEST_PATTERN="${TEST_PATTERN#./}"
# find -path can't match '**/' against zero directory levels, so a pattern
# like src/**/*.test.ts would skip src/top.test.ts; also try the pattern
# with '**/' collapsed to cover files directly under the base directory.
TEST_FILES=$(find . \( -path "./$TEST_PATTERN" -o -path "./${TEST_PATTERN//\*\*\//}" \) | sort -u)
if [ -z "$TEST_FILES" ]; then
  TOTAL=0
else
  TOTAL=$(printf '%s\n' "$TEST_FILES" | wc -l | tr -d ' ')
fi

echo "Found $TOTAL test files"
echo ""

COUNT=0
for TEST_FILE in $TEST_FILES; do
  COUNT=$((COUNT + 1))

  # Skip if pollution already exists
  if [ -e "$POLLUTION_CHECK" ]; then
    echo "⚠️  Pollution already exists before test $COUNT/$TOTAL"
    echo "   Skipping: $TEST_FILE"
    continue
  fi

  echo "[$COUNT/$TOTAL] Testing: $TEST_FILE"

  # Run the test
  npm test "$TEST_FILE" > /dev/null 2>&1 || true

  # Check if pollution appeared
  if [ -e "$POLLUTION_CHECK" ]; then
    echo ""
    echo "🎯 FOUND POLLUTER!"
    echo "   Test: $TEST_FILE"
    echo "   Created: $POLLUTION_CHECK"
    echo ""
    echo "Pollution details:"
    ls -la "$POLLUTION_CHECK"
    echo ""
    echo "To investigate:"
    echo "  npm test $TEST_FILE    # Run just this test"
    echo "  cat $TEST_FILE         # Review test code"
    exit 1
  fi
done

echo ""
echo "✅ No polluter found - all tests clean!"
exit 0
```
