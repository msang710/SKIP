import type { PluginAttachmentItem } from "@getpaseo/plugin/server";

type ParsedInvocation = {
  help: boolean;
  project?: string;
  now: boolean;
  date?: string;
  updated?: string;
  goal?: string;
  artifacts?: string[];
  focusDecisions: boolean;
  decisions?: string[];
  verify: boolean;
  compare: boolean;
  includeUndated: boolean;
};

type Preset = {
  item: PluginAttachmentItem;
  keywords: string[];
};

const SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const DECISION = /^[A-Za-z][A-Za-z0-9_-]*$/;
const ARTIFACTS = new Set([
  "impact",
  "prd",
  "user-stories",
  "system-design",
  "tasks",
]);

function invocationItem(
  id: string,
  identifier: string,
  title: string,
  subtitle: string,
  invocation: string,
): PluginAttachmentItem {
  return {
    id,
    identifier,
    title,
    subtitle,
    url: `https://local.skip.invalid/invocations/${encodeURIComponent(id)}`,
    text: [
      "Use this exact SKIP invocation as the controlling request:",
      "",
      invocation,
      "",
      "Honor its fail-closed context selection and do not widen the selected record scope implicitly.",
    ].join("\n"),
    resourceType: "SKIP invocation",
  };
}

function errorItem(message: string): PluginAttachmentItem {
  return {
    id: "invalid-query",
    identifier: "입력 오류",
    title: "검색 조건을 확인하세요",
    subtitle: message,
    url: "https://local.skip.invalid/errors/invalid-query",
    text: `SKIP validation error: ${message}\nDo not run a SKIP invocation from this attachment. Ask the user to correct the options.`,
    resourceType: "SKIP validation error",
  };
}

const HELP_PRESET: Preset = {
  item: invocationItem(
    "help",
    "도움말",
    "호출 옵션 도움말",
    "사용 가능한 옵션과 조합 예시 보기",
    "$skip --help",
  ),
  keywords: ["help options usage"],
};

const PRESETS: Preset[] = [
  {
    item: invocationItem(
      "now",
      "현재",
      "현재 구현 상태",
      "저장된 NOW 기록만 읽기",
      "$skip --now",
    ),
    keywords: ["now", "current implementation state"],
  },
  {
    item: invocationItem(
      "now-verify",
      "재검증",
      "현재 상태와 코드 재검증",
      "NOW를 읽고 관련 소스 확인",
      "$skip --now --verify",
    ),
    keywords: ["now verify", "verify code"],
  },
  {
    item: invocationItem(
      "now-decisions",
      "결정",
      "현재 제품 결정",
      "코드에 반영된 제품 동작 확인",
      "$skip --now --focus decisions",
    ),
    keywords: ["current product decisions", "decisions"],
  },
  {
    item: invocationItem(
      "history-date",
      "날짜",
      "날짜별 이전 기록",
      "예: date:260825 · goal과 artifacts 선택 가능",
      "$skip --date 2026-08-25",
    ),
    keywords: ["historical documents by date", "history date goal artifacts"],
  },
  {
    item: invocationItem(
      "compare",
      "비교",
      "현재와 이전 기록 비교",
      "예: compare date:260825 · goal 선택 가능",
      "$skip --now --compare --date 2026-08-25",
    ),
    keywords: ["compare now with date", "compare date goal"],
  },
  HELP_PRESET,
];

function normalizeDate(value: string): string {
  const expanded = /^\d{6}$/.test(value)
    ? `20${value.slice(0, 2)}-${value.slice(2, 4)}-${value.slice(4, 6)}`
    : value;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(expanded)) {
    throw new Error(`잘못된 날짜 형식: ${value}`);
  }
  const [year, month, day] = expanded.split("-").map(Number);
  const parsed = new Date(Date.UTC(year, month - 1, day));
  if (
    parsed.getUTCFullYear() !== year ||
    parsed.getUTCMonth() !== month - 1 ||
    parsed.getUTCDate() !== day
  ) {
    throw new Error(`존재하지 않는 날짜: ${value}`);
  }
  return expanded;
}

function list(value: string, label: string): string[] {
  const values = value.split(",").map((entry) => entry.trim()).filter(Boolean);
  if (values.length === 0) throw new Error(`${label} 값이 필요합니다`);
  return values;
}

function parseQuery(query: string): ParsedInvocation | null {
  const tokens = query.trim().split(/\s+/).filter(Boolean);
  if (tokens.length === 0) return null;

  const result: ParsedInvocation = {
    help: false,
    now: false,
    focusDecisions: false,
    verify: false,
    compare: false,
    includeUndated: false,
  };
  if (tokens.some((token) => token.toLowerCase() === "help" || token === "--help")) {
    result.help = true;
    return result;
  }
  let recognized = 0;
  let hasPlainSearchWord = false;

  for (const raw of tokens) {
    const token = raw.toLowerCase();
    if (token === "now") {
      result.now = true;
    } else if (token === "verify") {
      result.verify = true;
    } else if (token === "compare") {
      result.compare = true;
    } else if (token === "decisions") {
      result.focusDecisions = true;
    } else if (token === "include-undated") {
      result.includeUndated = true;
    } else if (/^\d{6}$/.test(token)) {
      result.date = normalizeDate(token);
    } else if (token.includes(":")) {
      const separator = token.indexOf(":");
      const key = token.slice(0, separator);
      const value = raw.slice(separator + 1);
      if (!value) throw new Error(`${key} 값이 필요합니다`);
      switch (key) {
        case "project":
          if (!SLUG.test(value)) throw new Error(`잘못된 프로젝트 ID: ${value}`);
          result.project = value;
          break;
        case "date":
          result.date = normalizeDate(value);
          break;
        case "updated":
          result.updated = normalizeDate(value);
          break;
        case "goal":
          if (!SLUG.test(value)) throw new Error(`잘못된 목표 이름: ${value}`);
          result.goal = value;
          break;
        case "artifacts": {
          const artifacts = list(value, "artifacts").map((entry) => entry.replaceAll("_", "-"));
          const invalid = artifacts.find((entry) => !ARTIFACTS.has(entry));
          if (invalid) throw new Error(`지원하지 않는 산출물: ${invalid}`);
          result.artifacts = artifacts;
          break;
        }
        case "focus":
          if (value !== "decisions") throw new Error(`지원하지 않는 focus 값: ${value}`);
          result.focusDecisions = true;
          break;
        case "decision": {
          const decisions = list(value, "decision");
          const invalid = decisions.find((entry) => !DECISION.test(entry));
          if (invalid) throw new Error(`잘못된 결정 ID: ${invalid}`);
          result.decisions = decisions;
          break;
        }
        default:
          throw new Error(`알 수 없는 옵션: ${key}`);
      }
    } else {
      hasPlainSearchWord = true;
      continue;
    }
    recognized += 1;
  }

  if (recognized === 0 || hasPlainSearchWord) return null;
  if (result.now && (result.date || result.updated) && !result.compare) {
    throw new Error("NOW와 날짜 조건을 함께 사용하려면 compare가 필요합니다");
  }
  if (result.compare && !(result.now && (result.date || result.updated))) {
    throw new Error("compare에는 now와 날짜 조건이 모두 필요합니다");
  }
  return result;
}

function buildInvocation(parsed: ParsedInvocation): string {
  if (parsed.help) return "$skip --help";
  const parts = ["$skip"];
  if (parsed.project) parts.push("--project", parsed.project);
  if (parsed.now) parts.push("--now");
  if (parsed.compare) parts.push("--compare");
  if (parsed.date) parts.push("--date", parsed.date);
  if (parsed.updated) parts.push("--updated", parsed.updated);
  if (parsed.goal) parts.push("--goal", parsed.goal);
  if (parsed.artifacts) parts.push("--artifacts", parsed.artifacts.join(","));
  if (parsed.focusDecisions) parts.push("--focus", "decisions");
  if (parsed.decisions) parts.push("--decision", parsed.decisions.join(","));
  if (parsed.verify) parts.push("--verify");
  if (parsed.includeUndated) parts.push("--include-undated");
  return parts.join(" ");
}

export function searchIntent(query: string): { items: PluginAttachmentItem[] } {
  const trimmed = query.trim();
  if (!trimmed) return { items: PRESETS.map(({ item }) => item) };

  try {
    const parsed = parseQuery(trimmed);
    if (!parsed) {
      const words = trimmed.toLowerCase().split(/\s+/);
      return {
        items: PRESETS.filter(({ item, keywords }) => {
          const searchable = [item.identifier, item.title, item.subtitle ?? "", ...keywords]
            .join(" ")
            .toLowerCase();
          return words.every((word) => searchable.includes(word));
        }).map(({ item }) => item),
      };
    }
    if (parsed.help) return { items: [HELP_PRESET.item] };
    const invocation = buildInvocation(parsed);
    return {
      items: [
        invocationItem(
          "custom",
          "사용자 지정",
          "입력한 조건으로 호출",
          "선택하면 생성된 호출문을 에이전트에 전달합니다",
          invocation,
        ),
      ],
    };
  } catch (error) {
    return { items: [errorItem(error instanceof Error ? error.message : "잘못된 검색 조건")] };
  }
}
