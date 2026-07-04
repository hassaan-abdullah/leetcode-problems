"""
This code was entirely wrtten by using Claude Code (Fable-5) and ChatGPT 5.4-mini. It is 
designed to be run from the command line, and it will load a solution file and run it 
against a set of test cases defined in a JSON file.

This single solver can run all the three programming languages. 

Supported solution styles:
1. Python module-level function named `twoSum(nums, target)`.
2. Python class named `Solution` with a method `twoSum(self, nums, target)`.
3. C function named `twoSum(int* nums, int numsSize, int target, int* returnSize)`.
4. C++ class named `Solution` with a method
   `vector<int> twoSum(vector<int>& nums, int target)`.
5. C++ module-level free function named
   `vector<int> twoSum(vector<int>& nums, int target)`.
"""

import importlib.util
import inspect
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

FUNCTION_NAME = "twoSum"
ROOT_DIR = Path(__file__).resolve().parent
TEST_CASES_FILE = ROOT_DIR / "test-cases.json"


def is_valid_pair(result, expected):
    """Treat [i, j] and [j, i] as the same answer."""
    return len(result) == 2 and len(expected) == 2 and sorted(result) == sorted(expected)


def load_python_solution(path):
    """Import a Python solution file and return a callable twoSum(nums, target)."""
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    cls = getattr(module, "Solution", None)
    if cls is not None and hasattr(cls, FUNCTION_NAME):
        return getattr(cls(), FUNCTION_NAME)

    func = getattr(module, FUNCTION_NAME, None)
    if func is not None:
        params = list(inspect.signature(func).parameters)
        if params and params[0] == "self":
            return lambda nums, target: func(None, nums, target)
        return func

    sys.exit(f"\nError: no '{FUNCTION_NAME}' function found in {path.name}")


def render_int_array(name, values, mutable=True):
    qualifier = "" if mutable else "static const "
    body = ", ".join(str(int(v)) for v in values)
    return f"{qualifier}int {name}[] = {{{body}}};"


def render_test_cases_for_native(test_cases):
    lines = []
    for i, case in enumerate(test_cases):
        lines.append(render_int_array(f"nums_{i}", case["nums"]))
        lines.append(render_int_array(f"expected_{i}", case["expected"], mutable=False))
    lines.append("typedef struct {")
    lines.append("    int *nums;")
    lines.append("    int numsSize;")
    lines.append("    int target;")
    lines.append("    const int *expected;")
    lines.append("} TestCase;")
    lines.append("")
    lines.append("static TestCase cases[] = {")
    for i, case in enumerate(test_cases):
        lines.append(
            f"    {{nums_{i}, {len(case['nums'])}, {int(case['target'])}, expected_{i}}},"
        )
    lines.append("};")
    return "\n".join(lines)


def resolve_compiler(candidates):
    for candidate in candidates:
        compiler = shutil.which(candidate)
        if compiler:
            return compiler
    return None


def build_native_harness(solution_path, test_cases, language):
    suffix = solution_path.suffix.lower()
    is_cpp = language == "cpp"
    solution_copy_name = f"solution{suffix}"
    runner_name = "runner.cpp" if is_cpp else "runner.c"
    binary_name = "runner.exe" if os.name == "nt" else "runner"

    if is_cpp:
        compiler = resolve_compiler(["g++", "clang++"])
        compile_args = [compiler, "-std=c++17", "-O2", runner_name, "-o", binary_name]
    else:
        compiler = resolve_compiler(["gcc", "clang"])
        compile_args = [compiler, "-std=c11", "-O2", runner_name, "-o", binary_name]

    if not compiler:
        sys.exit(
            f"\nError: no suitable {'C++' if is_cpp else 'C'} compiler was found on PATH."
        )

    with tempfile.TemporaryDirectory(prefix="two_sum_") as temp_dir:
        temp_dir = Path(temp_dir)
        copied_solution = temp_dir / solution_copy_name
        shutil.copy2(solution_path, copied_solution)

        cases_blob = render_test_cases_for_native(test_cases)

        if is_cpp:
            def build_cpp_runner(call_style):
                call_expr = "Solution solver;\n        vector<int> result = solver.twoSum(nums, cases[i].target);" if call_style == "class" else "vector<int> result = twoSum(nums, cases[i].target);"
                return f"""#include <algorithm>
#include <array>
#include <iostream>
#include <vector>
using namespace std;
#include "{solution_copy_name}"

{cases_blob}

static bool same_pair(const vector<int>& result, const int expected[2]) {{
    return result.size() == 2 &&
           ((result[0] == expected[0] && result[1] == expected[1]) ||
            (result[0] == expected[1] && result[1] == expected[0]));
}}

int main() {{
    const int total = static_cast<int>(sizeof(cases) / sizeof(cases[0]));
    int passed = 0;

    cout << "\\nTesting {solution_path.name} against " << total << " cases\\n\\n";

    for (int i = 0; i < total; ++i) {{
        vector<int> nums(cases[i].nums, cases[i].nums + cases[i].numsSize);
        {call_expr}
        bool ok = same_pair(result, cases[i].expected);
        if (ok) {{
            ++passed;
        }}
        cout << "Case " << (i + 1) << " / " << total << " --- "
             << (ok ? "PASS" : "FAIL");
        if (!ok) {{
            cout << "  (expected [" << cases[i].expected[0] << ", "
                 << cases[i].expected[1] << "], got [";
            for (size_t j = 0; j < result.size(); ++j) {{
                if (j) cout << ", ";
                cout << result[j];
            }}
            cout << "])";
        }}
        cout << '\\n';
    }}

    cout << "\\nOut of " << total << " cases, "
         << (total ? (passed * 100 / total) : 0) << "% of the cases passed.\\n";
    return 0;
}}
"""

            class_runner = build_cpp_runner("class")
            function_runner = build_cpp_runner("function")

            def compile_and_run(runner_source):
                runner_path = temp_dir / runner_name
                runner_path.write_text(runner_source, encoding="utf-8")
                compile_proc = subprocess.run(
                    compile_args,
                    cwd=temp_dir,
                    capture_output=True,
                    text=True,
                )
                if compile_proc.returncode != 0:
                    return False, (
                        compile_proc.stderr.strip()
                        or compile_proc.stdout.strip()
                        or "unknown compiler error"
                    )

                run_proc = subprocess.run(
                    [str(temp_dir / binary_name)],
                    cwd=temp_dir,
                    capture_output=True,
                    text=True,
                )
                if run_proc.stdout:
                    sys.stdout.write(run_proc.stdout)
                if run_proc.stderr:
                    sys.stderr.write(run_proc.stderr)
                if run_proc.returncode != 0:
                    sys.exit(run_proc.returncode)
                return True, ""

            ok, class_error = compile_and_run(class_runner)
            if not ok:
                ok, function_error = compile_and_run(function_runner)
                if not ok:
                    sys.exit(
                        f"\nError: failed to compile {solution_path.name} as either a C++ class or a C++ free function\n"
                        f"[class attempt]\n{class_error}\n\n[free-function attempt]\n{function_error}"
                    )
            return

        else:
            runner_source = f"""#include <stdio.h>
#include <stdlib.h>
#include "{solution_copy_name}"

{cases_blob}

static int same_pair(const int *result, int returnSize, const int expected[2]) {{
    return returnSize == 2 &&
           ((result[0] == expected[0] && result[1] == expected[1]) ||
            (result[0] == expected[1] && result[1] == expected[0]));
}}

int main(void) {{
    const int total = (int)(sizeof(cases) / sizeof(cases[0]));
    int passed = 0;

    printf("\\nTesting {solution_path.name} against %d cases\\n\\n", total);

    for (int i = 0; i < total; ++i) {{
        int returnSize = 0;
        int *result = twoSum(cases[i].nums, cases[i].numsSize, cases[i].target, &returnSize);
        int ok = same_pair(result, returnSize, cases[i].expected);
        if (ok) {{
            ++passed;
        }}
        printf("Case %d / %d --- %s", i + 1, total, ok ? "PASS" : "FAIL");
        if (!ok) {{
            printf("  (expected [%d, %d], got [", cases[i].expected[0], cases[i].expected[1]);
            for (int j = 0; j < returnSize; ++j) {{
                if (j) {{
                    printf(", ");
                }}
                printf("%d", result[j]);
            }}
            printf("])");
        }}
        printf("\\n");
        free(result);
    }}

    printf("\\nOut of %d cases, %d%% of the cases passed.\\n",
           total, total ? (passed * 100 / total) : 0);
    return 0;
}}
"""

            runner_path = temp_dir / runner_name
            runner_path.write_text(runner_source, encoding="utf-8")

            compile_proc = subprocess.run(
                compile_args,
                cwd=temp_dir,
                capture_output=True,
                text=True,
            )
            if compile_proc.returncode != 0:
                message = compile_proc.stderr.strip() or compile_proc.stdout.strip() or "unknown compiler error"
                sys.exit(f"\nError: failed to compile {solution_path.name}\n{message}")

            run_proc = subprocess.run(
                [str(temp_dir / binary_name)],
                cwd=temp_dir,
                capture_output=True,
                text=True,
            )
            if run_proc.stdout:
                sys.stdout.write(run_proc.stdout)
            if run_proc.stderr:
                sys.stderr.write(run_proc.stderr)
            if run_proc.returncode != 0:
                sys.exit(run_proc.returncode)


def run_python_solution(solution_path, test_cases):
    solve = load_python_solution(solution_path)
    total = len(test_cases)
    passed = 0

    print(f"\nTesting {solution_path.name} against {total} cases\n")

    for i, case in enumerate(test_cases, start=1):
        nums, target, expected = case["nums"], case["target"], case["expected"]
        try:
            result = solve(list(nums), target)
            ok = is_valid_pair(result, expected)
            detail = "" if ok else f"  (expected {expected}, got {result})"
        except Exception as e:
            ok = False
            detail = f"  (error: {e})"

        if ok:
            passed += 1
        print(f"Case {i} / {total} --- {'PASS' if ok else 'FAIL'}{detail}")

    percentage = passed / total * 100 if total else 0
    print(f"\nOut of {total} cases, {percentage:.0f}% of the cases passed.")


def main():
    if len(sys.argv) != 2:
        sys.exit(f"\nUsage: python {Path(sys.argv[0]).name} <solution-file.py|.c|.cpp>")

    solution_path = Path(sys.argv[1])
    if not solution_path.is_file():
        sys.exit(f"Error: file not found: {solution_path}")

    with open(TEST_CASES_FILE, encoding="utf-8-sig") as f:
        test_cases = json.load(f)

    suffix = solution_path.suffix.lower()
    if suffix == ".py":
        run_python_solution(solution_path, test_cases)
    elif suffix == ".c":
        build_native_harness(solution_path, test_cases, "c")
    elif suffix in {".cpp", ".cc", ".cxx", ".c++"}:
        build_native_harness(solution_path, test_cases, "cpp")
    else:
        sys.exit(f"\nError: unsupported solution file type: {solution_path.suffix}")


if __name__ == "__main__":
    main()
