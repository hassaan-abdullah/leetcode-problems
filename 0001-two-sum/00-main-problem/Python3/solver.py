"""
Claude Code was used to write this solver script in its entirety. It is designed to be 
run from the command line, and it will load a solution file and run it against a set of 
test cases defined in a JSON file.

This script is similar to what LeetCode uses, so it supports two styles of solution files:
1. A module-level function named `twoSum(nums, target)`.
2. A class named `Solution` with a method `twoSum(self, nums, target)`.
"""

import importlib.util
import inspect
import json
import sys
from pathlib import Path

FUNCTION_NAME = "twoSum"
TEST_CASES_FILE = Path(__file__).parent / "test-cases.json"


def load_solution(path):
    """Import the solution file and return a callable twoSum(nums, target)."""
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Case 1: function defined inside a Solution class (LeetCode style)
    cls = getattr(module, "Solution", None)
    if cls is not None and hasattr(cls, FUNCTION_NAME):
        return getattr(cls(), FUNCTION_NAME)

    # Case 2: module-level function (with or without a leading `self` param)
    func = getattr(module, FUNCTION_NAME, None)
    if func is not None:
        params = list(inspect.signature(func).parameters)
        if params and params[0] == "self":
            return lambda nums, target: func(None, nums, target)
        return func

    sys.exit(f"\nError: no '{FUNCTION_NAME}' function found in {path.name}")


def main():
    if len(sys.argv) != 2:
        sys.exit(f"\nUsage: python {Path(sys.argv[0]).name} <solution-file.py>")

    solution_path = Path(sys.argv[1])
    if not solution_path.is_file():
        sys.exit(f"Error: file not found: {solution_path}")

    # Use utf-8-sig so JSON files saved with a BOM on Windows still load cleanly.
    with open(TEST_CASES_FILE, encoding="utf-8-sig") as f:
        test_cases = json.load(f)

    solve = load_solution(solution_path)
    total = len(test_cases)
    passed = 0

    print(f"\nTesting {solution_path.name} against {total} cases\n")

    for i, case in enumerate(test_cases, start=1):
        nums, target, expected = case["nums"], case["target"], case["expected"]
        try:
            result = solve(list(nums), target)
            ok = sorted(result) == sorted(expected)
            detail = "" if ok else f"  (expected {expected}, got {result})"
        except Exception as e:
            ok = False
            detail = f"  (error: {e})"

        if ok:
            passed += 1
        print(f"Case {i} / {total} --- {'PASS' if ok else 'FAIL'}{detail}")

    percentage = passed / total * 100 if total else 0
    print(f"\nOut of {total} cases, {percentage:.0f}% of the cases passed.")


if __name__ == "__main__":
    main()
