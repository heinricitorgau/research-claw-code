from __future__ import annotations

import shutil

from local_ai.checkers.check_c_answer import check_c_answer


def test_c_answer_checker_detects_missing_main() -> None:
    result = check_c_answer("```c\n#include <stdio.h>\nvoid hello(void) {}\n```")
    assert not result["ok"]
    assert "Missing int main" in result["issues"]


def test_c_answer_checker_detects_compile_failure_if_compiler_exists() -> None:
    if not any(shutil.which(name) for name in ("gcc", "clang", "cc")):
        return
    answer = """```c
#include <stdio.h>
int main(void) {
    printf("hi")
    return 0;
}
```
測試輸出：
hi
"""
    result = check_c_answer(answer)
    assert not result["ok"]
    assert "C code does not compile" in result["issues"]
