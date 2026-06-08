from __future__ import annotations

import datetime as _dt
import json
import re
import subprocess
from collections.abc import Mapping
from typing import Any


SOURCE_TYPE = "user_screenshot_baseline"
SOURCE = "Serenity method radar / user screenshot baseline"
PACKET_KEY = "command_center_serenity_method_radar_packet"
ALLOWED_GITHUB_PROBE_FIELDS = {
    "http_status",
    "probe_status",
    "github_stars",
    "github_forks",
    "pushed_at",
    "html_url",
    "error_message_safe",
}
REPO_SLUG_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9._-]+$")

DECISION_USAGE_POLICY = {
    "display_only": True,
    "enters_chokepoint_score": False,
    "enters_strategy_action": False,
    "enters_next_session_projection": False,
    "enters_deepseek_prompt": False,
    "note": "仅用于 Serenity 方法来源可复核性说明，不作为交易信号。",
}

SERENITY_SCREENSHOT_BASELINE_REPOS = [
    {
        "rank": 1,
        "repo": "muxuuu/serenity-skill",
        "screenshot_feature": "核心方法论 + 最系统化",
        "source_type": SOURCE_TYPE,
    },
    {
        "rank": 2,
        "repo": "lanfuli/aleabito-serenity-skills",
        "screenshot_feature": "推文档案库 + 注意力雷达",
        "source_type": SOURCE_TYPE,
    },
    {
        "rank": 3,
        "repo": "haskaomni/serenity",
        "screenshot_feature": "Alpha 假设 + 本地数据库",
        "source_type": SOURCE_TYPE,
    },
    {
        "rank": 4,
        "repo": "W-Y-P/Serenity-aleabitoreddit-skill",
        "screenshot_feature": "完整框架 + 财务翻译最深",
        "source_type": SOURCE_TYPE,
    },
    {
        "rank": 5,
        "repo": "ZadAnthony/serenity-skill",
        "screenshot_feature": "中文 Claude 版 + 防幻觉最强",
        "source_type": SOURCE_TYPE,
    },
    {
        "rank": 6,
        "repo": "fadewalk/serenity-stock-choke",
        "screenshot_feature": "A 股卡脖子 + 政策适配最佳",
        "source_type": SOURCE_TYPE,
    },
    {
        "rank": 7,
        "repo": "leslieyeo/serenity-reply",
        "screenshot_feature": "深度资料 + 心智模型蒸馏",
        "source_type": SOURCE_TYPE,
    },
    {
        "rank": 8,
        "repo": "zongmin-yu/serenity-skills",
        "screenshot_feature": "半导体供应链 + 垂直领域",
        "source_type": SOURCE_TYPE,
    },
    {
        "rank": 9,
        "repo": "yan-labs/serenity-aleabitoreddit",
        "screenshot_feature": "推文档案 + 战绩校准 + skills.sh 一键安装",
        "source_type": SOURCE_TYPE,
    },
    {
        "rank": 10,
        "repo": "xvhaoran778-cyber/Serenity.SKILL",
        "screenshot_feature": "跨市场卡点 + 贝叶斯更新 + 评分量表",
        "source_type": SOURCE_TYPE,
    },
]

HALLUCINATION_DEFENSE_EVOLUTION = [
    {
        "generation": "Gen 1",
        "representative_repo": "leslieyeo",
        "mechanism": "标注来源可信度",
        "effect": "基础透明",
        "source_type": SOURCE_TYPE,
    },
    {
        "generation": "Gen 2",
        "representative_repo": "muxuuu / W-Y-P",
        "mechanism": "证据分级 + 一手源优先",
        "effect": "减少编造",
        "source_type": SOURCE_TYPE,
    },
    {
        "generation": "Gen 3",
        "representative_repo": "ZadAnthony",
        "mechanism": "独立复核 + 取数纪律 + 精度降级",
        "effect": "极强防幻觉",
        "source_type": SOURCE_TYPE,
    },
    {
        "generation": "Gen 4",
        "representative_repo": "fadewalk",
        "mechanism": "A 股特有信号交叉验证",
        "effect": "本土化防骗",
        "source_type": SOURCE_TYPE,
    },
]

SERENITY_METHOD_SUMMARIES = [
    {
        "key": "chinese_implementation_breakthrough",
        "label": "中文实现突破",
        "representative_repo": "ZadAnthony/serenity-skill",
        "points": [
            "中文表达规范",
            "禁止造词",
            "教学跟踪",
            "反确认偏误内置",
        ],
        "source_type": SOURCE_TYPE,
    },
    {
        "key": "data_driven_limitations",
        "label": "数据驱动的局限",
        "representative_repos": [
            "yan-labs/serenity-aleabitoreddit",
            "lanfuli/aleabito-serenity-skills",
            "haskaomni/serenity",
        ],
        "points": [
            "基于真实历史数据，避免过拟合",
            "注意幸存者偏差和单账号脆弱性",
            "适合作为候选发生器，不是预言机",
        ],
        "source_type": SOURCE_TYPE,
    },
    {
        "key": "cross_market_bayesian_framework",
        "label": "跨市场贝叶斯框架",
        "representative_repo": "xvhaoran778-cyber/Serenity.SKILL",
        "points": [
            "15 维评分量表",
            "交易线索标签",
            "多市场投影源",
        ],
        "source_type": SOURCE_TYPE,
    },
]

RADAR_SOURCE_NOTES = [
    "本地基线来自用户本次上传截图；不是实时 GitHub 校验结果。",
    "截图特色不是 GitHub stars，截图里的方法评价不是官方评价。",
    "GitHub stars 只代表公开关注度，不代表方法质量、投资有效性或交易胜率。",
    "本模块不调用 DeepSeek，不进入交易评分、策略动作或次日操作图谱。",
]


def _copy_json(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _to_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _now_iso(now: Any = None) -> str:
    if isinstance(now, _dt.datetime):
        return now.isoformat(timespec="seconds")
    if isinstance(now, _dt.date):
        return _dt.datetime.combine(now, _dt.time.min).isoformat(timespec="seconds")
    if isinstance(now, str) and now.strip():
        return now.strip()
    return _dt.datetime.now().isoformat(timespec="seconds")


def _repo_names(repos: Any = None) -> list[str]:
    if repos is None:
        return [item["repo"] for item in SERENITY_SCREENSHOT_BASELINE_REPOS]
    if isinstance(repos, Mapping):
        values = repos.keys()
    else:
        values = repos if isinstance(repos, (list, tuple, set)) else []
    result = []
    for value in values:
        repo = _to_text(value)
        if repo and repo not in result:
            result.append(repo)
    return result


def _valid_repo_slug(repo: str) -> bool:
    return bool(REPO_SLUG_PATTERN.fullmatch(_to_text(repo)))


def _safe_github_probe_item(value: Any) -> dict:
    payload = dict(value) if isinstance(value, Mapping) else {}
    return {key: payload.get(key) for key in ALLOWED_GITHUB_PROBE_FIELDS if key in payload}


def _normalize_github_probe(github_probe: Any = None) -> dict:
    if not isinstance(github_probe, Mapping):
        return {}
    normalized = {}
    for repo, payload in github_probe.items():
        repo_name = _to_text(repo)
        if repo_name and _valid_repo_slug(repo_name):
            normalized[repo_name] = _safe_github_probe_item(payload)
    return normalized


def _github_probe_for_repo(repo: str, timeout_seconds: int = 8) -> dict:
    repo = _to_text(repo)
    if not _valid_repo_slug(repo):
        return {"http_status": None, "probe_status": "invalid_repo", "error_message_safe": "GitHub 仓库 slug 格式不合法。"}
    url = f"https://api.github.com/repos/{repo}"
    timeout = max(1, int(timeout_seconds or 8))
    try:
        result = subprocess.run(
            [
                "curl",
                "-L",
                "-sS",
                "--max-time",
                str(timeout),
                "-H",
                "Accept: application/vnd.github+json",
                "-w",
                "\n%{http_code}",
                url,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout + 2,
        )
    except FileNotFoundError:
        return {"http_status": None, "probe_status": "curl_missing", "error_message_safe": "curl 不可用，无法手动校验 GitHub。"}
    except subprocess.TimeoutExpired:
        return {"http_status": None, "probe_status": "timeout", "error_message_safe": "GitHub 校验超时。"}
    except Exception as exc:
        return {"http_status": None, "probe_status": "error", "error_message_safe": f"GitHub 校验失败：{type(exc).__name__}"}

    stdout = result.stdout or ""
    body, _, status_text = stdout.rpartition("\n")
    try:
        http_status = int(status_text.strip())
    except Exception:
        http_status = None

    if result.returncode != 0:
        message = (result.stderr or "").strip() or "curl 返回非零状态。"
        return {"http_status": http_status, "probe_status": "curl_error", "error_message_safe": message[:160]}
    if http_status != 200:
        return {"http_status": http_status, "probe_status": "http_error", "error_message_safe": f"GitHub API 返回 {http_status or '未知状态'}。"}

    try:
        data = json.loads(body or "{}")
    except Exception:
        return {"http_status": http_status, "probe_status": "parse_error", "error_message_safe": "GitHub API 返回内容无法解析。"}

    return {
        "http_status": http_status,
        "probe_status": "success",
        "github_stars": data.get("stargazers_count"),
        "github_forks": data.get("forks_count"),
        "pushed_at": data.get("pushed_at"),
        "html_url": data.get("html_url"),
    }


def probe_github_repositories(repos: Any = None, timeout_seconds: int = 8) -> dict:
    return {repo: _github_probe_for_repo(repo, timeout_seconds=timeout_seconds) for repo in _repo_names(repos)}


def build_serenity_method_radar_packet(github_probe: Any = None, now: Any = None) -> dict:
    normalized_probe = _normalize_github_probe(github_probe)
    repositories = _copy_json(SERENITY_SCREENSHOT_BASELINE_REPOS)
    for item in repositories:
        repo = item.get("repo")
        item["github_probe"] = normalized_probe.get(repo, {})

    return {
        "packet_key": PACKET_KEY,
        "title": "Serenity 方法雷达",
        "status": "ready",
        "summary": "本地截图基线已加载；GitHub 当前状态仅在手动校验后显示，且不覆盖截图方法评价。",
        "repositories": repositories,
        "hallucination_defense_evolution": _copy_json(HALLUCINATION_DEFENSE_EVOLUTION),
        "method_summaries": _copy_json(SERENITY_METHOD_SUMMARIES),
        "github_probe": normalized_probe,
        "github_probe_policy": {
            "default_network": False,
            "manual_button_only": True,
            "allowed_fields": sorted(ALLOWED_GITHUB_PROBE_FIELDS),
            "does_not_override_screenshot_baseline": True,
            "note": "GitHub stars 只代表公开关注度，不代表方法质量、投资有效性或交易胜率。",
        },
        "decision_usage_policy": dict(DECISION_USAGE_POLICY),
        "source_notes": list(RADAR_SOURCE_NOTES),
        "source": SOURCE,
        "source_type": SOURCE_TYPE,
        "deepseek_called": False,
        "updated_at": _now_iso(now),
    }
