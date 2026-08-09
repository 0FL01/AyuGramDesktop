#!/usr/bin/env python3

import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[2]
PATH = ROOT / "Telegram/codegen/codegen/lang/subsets.cpp"

T = "\t"

edits = [
    (
        "constexpr auto kCacheVersion = quint32(1);",
        "constexpr auto kCacheVersion = quint32(2);",
    ),
    (
        f"{T}for (auto i = qsizetype(0); i + 4 < size; ++i) {{\n"
        f"{T}{T}if (data[i] != 'l'\n"
        f"{T}{T}{T}|| data[i + 1] != 'n'\n"
        f"{T}{T}{T}|| data[i + 2] != 'g'\n"
        f"{T}{T}{T}|| data[i + 3] != '_'\n"
        f"{T}{T}{T}|| (i > 0 && IsIdentifierChar(data[i - 1]))) {{",
        f"{T}for (auto i = qsizetype(0); i + 4 < size; ++i) {{\n"
        f"{T}{T}const auto languageKeyPrefix = (\n"
        f"{T}{T}{T}(data[i] == 'l'\n"
        f"{T}{T}{T}{T}&& data[i + 1] == 'n'\n"
        f"{T}{T}{T}{T}&& data[i + 2] == 'g'\n"
        f"{T}{T}{T}{T}&& data[i + 3] == '_')\n"
        f"{T}{T}{T}|| (data[i] == 'a'\n"
        f"{T}{T}{T}{T}&& data[i + 1] == 'y'\n"
        f"{T}{T}{T}{T}&& data[i + 2] == 'u'\n"
        f"{T}{T}{T}{T}&& data[i + 3] == '_'));\n"
        f"{T}{T}if (!languageKeyPrefix\n"
        f"{T}{T}{T}|| (i > 0 && IsIdentifierChar(data[i - 1]))) {{",
    ),
]


def main():
    if not PATH.exists():
        print(f"::error::missing file: {PATH.relative_to(ROOT)}", file=sys.stderr)
        return 1

    text = PATH.read_text(encoding="utf-8")
    for old, new in edits:
        if new in text:
            continue
        if old not in text:
            print(f"::error::target not found in {PATH.relative_to(ROOT)}", file=sys.stderr)
            return 1
        text = text.replace(old, new, 1)

    PATH.write_text(text, encoding="utf-8")
    print("AyuGram language subset fix applied successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
