#!/usr/bin/env python3
"""Keyboard-first SKIP configuration UI."""

from __future__ import annotations

import argparse
import curses
import datetime as dt
import json
import sys
from copy import deepcopy
from curses.textpad import Textbox
from pathlib import Path
from typing import Any, Callable

if not __package__:
    import intent_context
    from skip_setup import DEFAULT_CORE_RULES, RuleConfigurationError, RulePaths, SetupService
else:
    from scripts import intent_context
    from scripts.skip_setup import DEFAULT_CORE_RULES, RuleConfigurationError, RulePaths, SetupService


KEY_ENTER = {10, 13, curses.KEY_ENTER}


def menu_move(index: int, key: int, size: int) -> int:
    if key == curses.KEY_UP:
        return (index - 1) % size
    if key == curses.KEY_DOWN:
        return (index + 1) % size
    return index


def toggled_disabled(disabled: list[str], rule_id: str) -> list[str]:
    values = set(disabled)
    if rule_id in values:
        values.remove(rule_id)
    else:
        values.add(rule_id)
    return sorted(values)


def verbatim_project_rule(
    rule_id: str,
    text: str,
    *,
    status: str = "active",
    changed_at: str | None = None,
) -> dict[str, Any]:
    return {
        "id": rule_id,
        "rule": text,
        "scope": {"kind": "project"},
        "status": status,
        "authority": {"changed_at": changed_at or dt.date.today().isoformat()},
    }


class SkipTui:
    def __init__(self, screen: curses.window, service: SetupService) -> None:
        self.screen = screen
        self.service = service
        self.current = service.load()
        self.proposed = deepcopy(self.current)
        self.message = ""

    def draw_lines(self, title: str, lines: list[str], selected: int | None = None) -> None:
        self.screen.erase()
        height, width = self.screen.getmaxyx()
        self.screen.addnstr(1, 2, title, max(1, width - 4), curses.A_BOLD)
        for offset, line in enumerate(lines, start=3):
            if offset >= height - 2:
                break
            attr = curses.A_REVERSE if selected == offset - 3 else curses.A_NORMAL
            self.screen.addnstr(offset, 2, line, max(1, width - 4), attr)
        if self.message:
            self.screen.addnstr(height - 1, 2, self.message, max(1, width - 4), curses.A_DIM)
        self.screen.refresh()

    def confirm(self, title: str, detail: str) -> bool:
        index = 1
        while True:
            self.draw_lines(title, [detail, "", "취소", "적용"], index + 2)
            key = self.screen.getch()
            if key in (curses.KEY_LEFT, curses.KEY_UP):
                index = 0
            elif key in (curses.KEY_RIGHT, curses.KEY_DOWN):
                index = 1
            elif key in KEY_ENTER:
                return bool(index)
            elif key == 27:
                return False

    def edit_text(self, title: str, initial: str = "") -> str | None:
        self.screen.erase()
        height, width = self.screen.getmaxyx()
        self.screen.addnstr(1, 2, title, max(1, width - 4), curses.A_BOLD)
        self.screen.addnstr(2, 2, "Ctrl-G: 완료  Esc: 취소", max(1, width - 4), curses.A_DIM)
        window = curses.newwin(max(3, height - 5), max(8, width - 4), 4, 2)
        window.addstr(0, 0, initial)
        textbox = Textbox(window, insert_mode=True)

        def validate(key: int) -> int:
            return 7 if key == 27 else key

        result = textbox.edit(validate).rstrip()
        return None if not result and not initial else result

    def core_rules(self) -> None:
        core, project = self.proposed
        ids = list(DEFAULT_CORE_RULES)
        index = 0
        while True:
            disabled = set(core["disabled_default_rule_ids"])
            lines = [
                f"[{' ' if rule_id in disabled else 'x'}] {rule_id} {DEFAULT_CORE_RULES[rule_id]}"
                for rule_id in ids
            ]
            self.message = "↑/↓ 이동  Space 선택  Enter 검토  Esc 돌아가기"
            self.draw_lines("SKIP 기본 규칙 설정", lines, index)
            key = self.screen.getch()
            index = menu_move(index, key, len(ids))
            if key == ord(" "):
                core["disabled_default_rule_ids"] = toggled_disabled(
                    core["disabled_default_rule_ids"], ids[index]
                )
            elif key in KEY_ENTER:
                enabled = len(ids) - len(core["disabled_default_rule_ids"])
                if self.confirm("변경 확인", f"활성 {enabled}개 / 비활성 {len(ids) - enabled}개"):
                    self.service.apply(self.current, (core, project))
                    self.current = deepcopy((core, project))
                    self.message = "기본 규칙 설정을 적용했습니다."
                    return
            elif key == 27:
                self.proposed = deepcopy(self.current)
                return

    def prompt_id(self, initial: str = "") -> str | None:
        value = self.edit_text("규칙 ID (letters, numbers, dot, underscore, hyphen)", initial)
        if value is None:
            return None
        return value.strip()

    def project_rules(self) -> None:
        core, project = self.proposed
        index = 0
        while True:
            rules = project["rules"]
            lines = ["+ 새 규칙 작성"] + [
                f"[{'x' if rule['status'] == 'active' else ' '}] {rule['id']}  {str(rule['rule']).splitlines()[0]}"
                for rule in rules
            ] + ["저장하고 돌아가기"]
            self.message = "Enter 선택  Space 활성/비활성  Delete 삭제  Esc 취소"
            self.draw_lines("이 프로젝트 전용 규칙", lines, index)
            key = self.screen.getch()
            index = menu_move(index, key, len(lines))
            if key in KEY_ENTER:
                if index == len(lines) - 1:
                    if (core, project) == self.current or self.confirm(
                        "변경 확인", f"프로젝트 규칙 {len(rules)}개를 저장합니다."
                    ):
                        self.service.apply(self.current, (core, project))
                        self.current = deepcopy((core, project))
                        return
                    continue
                existing = None if index == 0 else rules[index - 1]
                rule_id = self.prompt_id(str(existing["id"]) if existing else "")
                if not rule_id:
                    continue
                text = self.edit_text("규칙 원문 작성", str(existing["rule"]) if existing else "")
                if text is None:
                    continue
                value = verbatim_project_rule(
                    rule_id,
                    text,
                    status=str(existing.get("status", "active")) if existing else "active",
                )
                if existing:
                    rules[index - 1] = value
                else:
                    rules.append(value)
                    index = len(rules)
                try:
                    self.service.validate(core, project)
                except RuleConfigurationError as exc:
                    self.message = str(exc)
                    self.proposed = deepcopy(self.current)
                    core, project = self.proposed
                    index = 0
            elif key == ord(" ") and 0 < index <= len(rules):
                rule = rules[index - 1]
                rule["status"] = "inactive" if rule["status"] == "active" else "active"
                rule["authority"]["changed_at"] = dt.date.today().isoformat()
            elif key in (curses.KEY_DC, 127) and 0 < index <= len(rules):
                del rules[index - 1]
                index = min(index, len(rules))
            elif key == 27:
                self.proposed = deepcopy(self.current)
                return

    def run(self) -> None:
        curses.curs_set(0)
        index = 0
        options = ["SKIP 기본 규칙 설정", "이 프로젝트 전용 규칙 작성", "종료"]
        while True:
            self.message = "↑/↓ 이동  Enter 선택"
            self.draw_lines("SKIP 규칙", options, index)
            key = self.screen.getch()
            index = menu_move(index, key, len(options))
            if key in KEY_ENTER:
                if index == 0:
                    self.core_rules()
                elif index == 1:
                    self.project_rules()
                else:
                    return
            elif key in (27, ord("q")):
                return


def build_service(args: argparse.Namespace) -> SetupService:
    resolved = intent_context.resolve_project(args)
    core_path = intent_context.resolve_beneath(resolved.root, Path("config/core-rules.yaml"))
    project_path = intent_context.resolve_beneath(
        resolved.root, Path("projects") / resolved.project_id / "project-rules.yaml"
    )
    return SetupService(RulePaths(core_path, project_path), resolved.project_id, intent_context.runtime_id)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Configure SKIP rules with a keyboard-first interface.")
    intent_context.add_identity_arguments(result)
    result.add_argument("--allow", nargs="?", const="", metavar="REQUEST_ID")
    result.add_argument("--goal")
    result.add_argument("--command-file")
    result.add_argument("--authority-kind", choices=["user_turn", "native_user_action", "interactive_cli"])
    result.add_argument("--host")
    result.add_argument("text", nargs="*", help="natural-language request for a provider adapter")
    return result


def main(wrapper: Callable[[Callable[[curses.window], None]], None] = curses.wrapper) -> int:
    args = parser().parse_args()
    if args.allow is not None:
        if not args.goal or not args.command_file:
            print(json.dumps({"status": "error", "error_code": "NO_PENDING_TARGET",
                              "error": "--goal and --command-file are required when no host adapter retains the pending request"}, ensure_ascii=False), file=sys.stderr)
            return 2
        command = intent_context.command_object(args.command_file)
        runtime = intent_context.decision_runtime_for(args)
        preview = runtime.preview(command)
        requested = args.allow or preview["request_id"]
        authority_kind = args.authority_kind
        if authority_kind is None:
            if not sys.stdin.isatty() or not sys.stdout.isatty():
                print(json.dumps({"status": "error", "error_code": "INVALID_AUTHORITY",
                                  "error": "non-interactive allow requires a verified host authority envelope"}, ensure_ascii=False), file=sys.stderr)
                return 2
            print(json.dumps(preview, ensure_ascii=False, indent=2))
            answer = input("이 변경을 승인합니까? [y/N] ").strip().casefold()
            if answer not in {"y", "yes"}:
                return 3
            authority_kind = "interactive_cli"
        try:
            result = runtime.allow(command, {"schema": "authority-envelope/v1",
                                              "kind": authority_kind, "request_id": requested,
                                              "host": args.host})
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        except Exception as exc:
            print(json.dumps({"status": "error", "error_code": getattr(exc, "error_code", "internal_tool_error"),
                              "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
            return 2
    if args.text:
        print(
            json.dumps(
                {"schema": "skip.invoke/v1", "text": " ".join(args.text)},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print("SKIP interactive setup requires a TTY.", file=sys.stderr)
        return 2
    try:
        service = build_service(args)
        wrapper(lambda screen: SkipTui(screen, service).run())
        return 0
    except (intent_context.SelectionError, RuleConfigurationError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
