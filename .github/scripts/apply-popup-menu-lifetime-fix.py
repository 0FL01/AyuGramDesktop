#!/usr/bin/env python3
#
# Popup menu lifetime fix: gsl::not_null<T*> constructed from a null
# pointer in Wayland submenu positioning + handleTriggered null deref
# + contextless QAction::changed connects.
#
# Root causes (tdesktop #30645 class — ptr_ != nullptr / pointers:110):
#
#   A) PopupMenu::prepareGeometryFor Wayland branch constructs
#      not_null<ItemBase*> from findSelectedAction() which returns
#      nullable ItemBase*. When the parent menu's selection is cleared
#      between action activation and submenu positioning (e.g. via
#      childHiding -> setChildShownAction(nullptr) -> activateWindow
#      -> focus event -> clearMouseSelection), findSelectedAction()
#      returns nullptr -> not_null(null) -> Expects -> SIGSEGV.
#
#   B) PopupMenu::handleTriggered / DropdownMenu::handleTriggered call
#      data.action->trigger() without null guard. popupSubmenuFromAction
#      guards for null internally (returns false), but handleTriggered
#      falls through to data.action->trigger() on the false path.
#
#   C) menu_action.cpp / menu_toggle.cpp connect QAction::changed without
#      a context object. If QAction outlives the Action/Toggle widget,
      # the lambda runs on a destroyed this. Currently latent (destruction
#      order deletes Action before QAction), but a foot-gun.
#
# Fail-closed: if an exact target string is missing (upstream drifted) the
# script errors out so the build fails loudly rather than shipping an
# unpatched binary. If a site is already patched (new text present) it is
# skipped, so re-running or an upstream fix is handled gracefully.

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]

T = "\t"

patches = [
    {
        "file": "Telegram/lib_ui/ui/widgets/popup_menu.cpp",
        "edits": [
            # --- Fix A: Wayland not_null(findSelectedAction()) ---
            (
                "if (_parent) {\n"
                f"{T}{T}{T}// we must have an action to position the submenu around\n"
                f"{T}{T}{T}const auto action = not_null(\n"
                f"{T}{T}{T}{T}_parent->menu()->findSelectedAction());\n"
                f"{T}{T}{T}native->setParentControlGeometry(\n"
                f"{T}{T}{T}{T}QRect(\n"
                f"{T}{T}{T}{T}{T}action->mapTo(action->window(), QPoint()),\n"
                f"{T}{T}{T}{T}{T}action->size()) + _st.scrollPadding);\n"
                f"{T}{T}}} else if (padding.top()) {{",
                "if (_parent) {\n"
                f"{T}{T}{T}const auto action = _parent->menu()->findSelectedAction();\n"
                f"{T}{T}{T}if (!action) {{\n"
                f"{T}{T}{T}{T}return false;\n"
                f"{T}{T}{T}}}\n"
                f"{T}{T}{T}native->setParentControlGeometry(\n"
                f"{T}{T}{T}{T}QRect(\n"
                f"{T}{T}{T}{T}{T}action->mapTo(action->window(), QPoint()),\n"
                f"{T}{T}{T}{T}{T}action->size()) + _st.scrollPadding);\n"
                f"{T}{T}}} else if (padding.top()) {{",
                "if (_parent) {\n"
                f"{T}{T}{T}// we must have an action to position the submenu around\n"
                f"{T}{T}{T}Assert(parentActionWidget != nullptr);\n"
                f"{T}{T}{T}native->setParentControlGeometry(\n"
                f"{T}{T}{T}{T}QRect(\n"
                f"{T}{T}{T}{T}{T}parentActionWidget->mapTo(\n"
                f"{T}{T}{T}{T}{T}{T}parentActionWidget->window(),\n"
                f"{T}{T}{T}{T}{T}{T}QPoint()),\n"
                f"{T}{T}{T}{T}{T}parentActionWidget->size())\n"
                f"{T}{T}{T}{T}+ _st.scrollPadding);\n"
                f"{T}{T}}} else if (padding.top()) {{",
            ),
            # --- Fix B: handleTriggered null guard ---
            (
                "void PopupMenu::handleTriggered(const Menu::CallbackData &data) {\n"
                f"{T}if (!popupSubmenuFromAction(data)) {{\n"
                f"{T}{T}_triggering = true;\n",
                "void PopupMenu::handleTriggered(const Menu::CallbackData &data) {\n"
                f"{T}if (!data.action) {{\n"
                f"{T}{T}return;\n"
                f"{T}}}\n"
                f"{T}if (!popupSubmenuFromAction(data)) {{\n"
                f"{T}{T}_triggering = true;\n",
            ),
        ],
    },
    {
        "file": "Telegram/lib_ui/ui/widgets/dropdown_menu.cpp",
        "edits": [
            # --- Fix B: DropdownMenu handleTriggered null guard ---
            (
                "void DropdownMenu::handleTriggered(const Menu::CallbackData &data) {\n"
                f"{T}if (!popupSubmenuFromAction(data)) {{\n"
                f"{T}{T}if (!data.preventClose) {{\n",
                "void DropdownMenu::handleTriggered(const Menu::CallbackData &data) {\n"
                f"{T}if (!data.action) {{\n"
                f"{T}{T}return;\n"
                f"{T}}}\n"
                f"{T}if (!popupSubmenuFromAction(data)) {{\n"
                f"{T}{T}if (!data.preventClose) {{\n",
            ),
        ],
    },
    {
        "file": "Telegram/lib_ui/ui/widgets/menu/menu_action.cpp",
        "edits": [
            # --- Fix C: add context to QAction::changed connect ---
            (
                "connect(_action, &QAction::changed, [=] { processAction(); });",
                "connect(_action, &QAction::changed, this, [=] { processAction(); });",
            ),
        ],
    },
    {
        "file": "Telegram/lib_ui/ui/widgets/menu/menu_toggle.cpp",
        "edits": [
            # --- Fix C: add context to QAction::changed connect ---
            (
                "connect(action(), &QAction::changed, [=] { processAction(); });",
                "connect(action(), &QAction::changed, this, [=] { processAction(); });",
            ),
        ],
    },
]


def main():
    failed = False
    for patch in patches:
        path = ROOT / patch["file"]
        if not path.exists():
            print(f"::error::missing file: {patch['file']}", file=sys.stderr)
            failed = True
            continue
        text = path.read_text(encoding="utf-8")
        changed = False
        for old, new, *equivalents in patch["edits"]:
            if any(candidate in text for candidate in (new, *equivalents)):
                print(f"skip (already patched): {patch['file']} :: {old.splitlines()[0][:60]}")
                continue
            if old not in text:
                print(
                    f"::error::target not found in {patch['file']} :: {old.splitlines()[0][:70]}",
                    file=sys.stderr,
                )
                failed = True
                continue
            text = text.replace(old, new, 1)
            changed = True
            print(f"patched: {patch['file']} :: {old.splitlines()[0][:60]}")
        if changed:
            path.write_text(text, encoding="utf-8")
    if failed:
        print("::error::popup menu lifetime fix did not fully apply; see errors above.", file=sys.stderr)
        return 1
    print("popup menu lifetime fix applied successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
