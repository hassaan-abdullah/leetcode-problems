"""
This code was entirely wrtten by using Claude Code (Fable-5) and ChatGPT 5.4-mini. It is
designed to be run from the command line, and it will load a solution file and run it
against a set of test cases defined in a JSON file.

This single solver can run all the three programming languages.

Each test case's "l1" / "l2" / "expected" arrays store a number's digits in the same
order LeetCode uses for this problem: index 0 is the least significant digit, so the
array is exactly the node-by-node value sequence of the singly linked list.

Solution files are expected to assume `ListNode` already exists (matching LeetCode's
own starter code) rather than defining it themselves; this harness provides it.

Supported solution styles:
1. Python module-level function named `addTwoNumbers(l1, l2)`.
2. Python class named `Solution` with a method `addTwoNumbers(self, l1, l2)`.
3. C function named `struct ListNode* addTwoNumbers(struct ListNode* l1, struct ListNode* l2)`.
4. C++ class named `Solution` with a method
   `ListNode* addTwoNumbers(ListNode* l1, ListNode* l2)`.
5. C++ module-level free function named
   `ListNode* addTwoNumbers(ListNode* l1, ListNode* l2)`.
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
from typing import Optional

FUNCTION_NAME = "addTwoNumbers"
ROOT_DIR = Path(__file__).resolve().parent
TEST_CASES_FILE = ROOT_DIR / "test-cases.json"


class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next


def build_linked_list(values):
    """Build a ListNode chain from digits (index 0 = least significant)."""
    head = ListNode(values[0])
    current = head
    for value in values[1:]:
        current.next = ListNode(value)
        current = current.next
    return head


def linked_list_to_values(head):
    values = []
    current = head
    while current is not None:
        values.append(current.val)
        current = current.next
    return values


def load_python_solution(path):
    """Import a Python solution file and return a callable addTwoNumbers(l1, l2)."""
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    module.ListNode = ListNode
    module.Optional = Optional
    spec.loader.exec_module(module)

    cls = getattr(module, "Solution", None)
    if cls is not None and hasattr(cls, FUNCTION_NAME):
        return getattr(cls(), FUNCTION_NAME)

    func = getattr(module, FUNCTION_NAME, None)
    if func is not None:
        params = list(inspect.signature(func).parameters)
        if params and params[0] == "self":
            return lambda l1, l2: func(None, l1, l2)
        return func

    sys.exit(f"\nError: no '{FUNCTION_NAME}' function found in {path.name}")


def render_int_array(name, values, mutable=True):
    qualifier = "" if mutable else "static const "
    body = ", ".join(str(int(v)) for v in values)
    return f"{qualifier}int {name}[] = {{{body}}};"


def render_test_cases_for_native(test_cases):
    lines = []
    for i, case in enumerate(test_cases):
        lines.append(render_int_array(f"l1_{i}", case["l1"], mutable=False))
        lines.append(render_int_array(f"l2_{i}", case["l2"], mutable=False))
        lines.append(render_int_array(f"expected_{i}", case["expected"], mutable=False))
    lines.append("typedef struct {")
    lines.append("    const int *l1;")
    lines.append("    int l1Size;")
    lines.append("    const int *l2;")
    lines.append("    int l2Size;")
    lines.append("    const int *expected;")
    lines.append("    int expectedSize;")
    lines.append("} TestCase;")
    lines.append("")
    lines.append("static TestCase cases[] = {")
    for i, case in enumerate(test_cases):
        lines.append(
            f"    {{l1_{i}, {len(case['l1'])}, l2_{i}, {len(case['l2'])}, "
            f"expected_{i}, {len(case['expected'])}}},"
        )
    lines.append("};")
    return "\n".join(lines)


def resolve_compiler(candidates):
    for candidate in candidates:
        compiler = shutil.which(candidate)
        if compiler:
            return compiler
    return None


LIST_NODE_STRUCT_C = """struct ListNode {
    int val;
    struct ListNode *next;
};
"""

LIST_NODE_STRUCT_CPP = """struct ListNode {
    int val;
    ListNode *next;
    ListNode() : val(0), next(nullptr) {}
    ListNode(int x) : val(x), next(nullptr) {}
    ListNode(int x, ListNode *next) : val(x), next(next) {}
};
"""


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

    with tempfile.TemporaryDirectory(prefix="add_two_numbers_") as temp_dir:
        temp_dir = Path(temp_dir)
        copied_solution = temp_dir / solution_copy_name
        shutil.copy2(solution_path, copied_solution)

        cases_blob = render_test_cases_for_native(test_cases)

        if is_cpp:
            def build_cpp_runner(call_style):
                call_expr = (
                    "Solution solver;\n        ListNode *result = solver.addTwoNumbers(l1, l2);"
                    if call_style == "class"
                    else "ListNode *result = addTwoNumbers(l1, l2);"
                )
                return f"""#include <iostream>
#include <vector>
using namespace std;

{LIST_NODE_STRUCT_CPP}
#include "{solution_copy_name}"

{cases_blob}

static ListNode* build_list(const int *values, int size) {{
    ListNode *head = new ListNode(values[0]);
    ListNode *current = head;
    for (int i = 1; i < size; ++i) {{
        current->next = new ListNode(values[i]);
        current = current->next;
    }}
    return head;
}}

static vector<int> to_vector(ListNode *head) {{
    vector<int> values;
    for (ListNode *cur = head; cur != nullptr; cur = cur->next) {{
        values.push_back(cur->val);
    }}
    return values;
}}

int main() {{
    const int total = static_cast<int>(sizeof(cases) / sizeof(cases[0]));
    int passed = 0;

    cout << "\\nTesting {solution_path.name} against " << total << " cases\\n\\n";

    for (int i = 0; i < total; ++i) {{
        ListNode *l1 = build_list(cases[i].l1, cases[i].l1Size);
        ListNode *l2 = build_list(cases[i].l2, cases[i].l2Size);
        {call_expr}
        vector<int> resultValues = to_vector(result);
        vector<int> expectedValues(cases[i].expected, cases[i].expected + cases[i].expectedSize);
        bool ok = resultValues == expectedValues;
        if (ok) {{
            ++passed;
        }}
        cout << "Case " << (i + 1) << " / " << total << " --- "
             << (ok ? "PASS" : "FAIL");
        if (!ok) {{
            cout << "  (expected [";
            for (size_t j = 0; j < expectedValues.size(); ++j) {{
                if (j) cout << ", ";
                cout << expectedValues[j];
            }}
            cout << "], got [";
            for (size_t j = 0; j < resultValues.size(); ++j) {{
                if (j) cout << ", ";
                cout << resultValues[j];
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

{LIST_NODE_STRUCT_C}
#include "{solution_copy_name}"

{cases_blob}

static struct ListNode* build_list(const int *values, int size) {{
    struct ListNode *head = malloc(sizeof(struct ListNode));
    head->val = values[0];
    head->next = NULL;
    struct ListNode *current = head;
    for (int i = 1; i < size; ++i) {{
        current->next = malloc(sizeof(struct ListNode));
        current->next->val = values[i];
        current->next->next = NULL;
        current = current->next;
    }}
    return head;
}}

static void free_list(struct ListNode *head) {{
    while (head != NULL) {{
        struct ListNode *next = head->next;
        free(head);
        head = next;
    }}
}}

int main(void) {{
    const int total = (int)(sizeof(cases) / sizeof(cases[0]));
    int passed = 0;

    printf("\\nTesting {solution_path.name} against %d cases\\n\\n", total);

    for (int i = 0; i < total; ++i) {{
        struct ListNode *l1 = build_list(cases[i].l1, cases[i].l1Size);
        struct ListNode *l2 = build_list(cases[i].l2, cases[i].l2Size);
        struct ListNode *result = addTwoNumbers(l1, l2);

        int ok = 1;
        int resultSize = 0;
        struct ListNode *cur = result;
        for (int j = 0; j < cases[i].expectedSize; ++j) {{
            if (cur == NULL || cur->val != cases[i].expected[j]) {{
                ok = 0;
                break;
            }}
            cur = cur->next;
            ++resultSize;
        }}
        if (ok && cur != NULL) {{
            ok = 0;
        }}

        if (ok) {{
            ++passed;
        }}
        printf("Case %d / %d --- %s", i + 1, total, ok ? "PASS" : "FAIL");
        if (!ok) {{
            printf("  (expected [");
            for (int j = 0; j < cases[i].expectedSize; ++j) {{
                if (j) printf(", ");
                printf("%d", cases[i].expected[j]);
            }}
            printf("], got [");
            for (struct ListNode *p = result; p != NULL; p = p->next) {{
                if (p != result) printf(", ");
                printf("%d", p->val);
            }}
            printf("])");
        }}
        printf("\\n");
        free_list(result);
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
        expected = case["expected"]
        try:
            l1 = build_linked_list(case["l1"])
            l2 = build_linked_list(case["l2"])
            result = linked_list_to_values(solve(l1, l2))
            ok = result == expected
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
