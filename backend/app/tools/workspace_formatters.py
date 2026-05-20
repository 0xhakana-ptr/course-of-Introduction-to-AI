from collections.abc import Mapping

from .workspace_utils import normalize_optional_text


def format_workspace_entry(entry: Mapping[str, object]) -> str:
    kind = str(entry.get("kind") or "file").strip() or "file"
    path = str(entry.get("path") or "").strip()
    return f"- [{kind}] {path}"


def format_workspace_listing_summary(listing: Mapping[str, object]) -> str:
    lines = [
        f"Workspace listing for `{listing['path']}`:",
    ]
    items = listing.get("items")
    if isinstance(items, list) and items:
        lines.extend(
            format_workspace_entry(entry)
            for entry in items
            if isinstance(entry, Mapping)
        )
    else:
        lines.append("- <empty>")

    if bool(listing.get("truncated")):
        lines.append(
            f"... (showing first {len(items) if isinstance(items, list) else 0} of {listing['total']} entries)"
        )
    return "\n".join(lines)


def format_workspace_test_summary(result: Mapping[str, object]) -> str:
    lines = ["Workspace pytest result:"]

    target_paths = result.get("target_paths")
    if isinstance(target_paths, list) and target_paths:
        lines.append(f"targets: {', '.join(str(path) for path in target_paths)}")

    summary = normalize_optional_text(result.get("summary"))
    if summary is not None:
        lines.append(summary)

    stdout_preview = normalize_optional_text(result.get("stdout_preview"))
    if stdout_preview is not None:
        lines.append(f"stdout preview:\n{stdout_preview}")

    stderr_preview = normalize_optional_text(result.get("stderr_preview"))
    if stderr_preview is not None:
        lines.append(f"stderr preview:\n{stderr_preview}")

    return "\n\n".join(lines)


def format_workspace_entry_for_user(entry: Mapping[str, object]) -> str:
    kind = str(entry.get("kind") or "file").strip()
    kind_label = "目录" if kind == "dir" else "文件"
    path = str(entry.get("path") or "").strip() or "<unknown>"
    return f"- {kind_label}: {path}"


def format_file_preview_for_user(data: Mapping[str, object]) -> str:
    path = str(data.get("path") or "").strip() or "目标文件"
    content = str(data.get("content") or "")
    lines = [f"我读到了 `{path}` 的内容。"]

    if not content:
        lines.append("")
        lines.append("这个文件目前没有可显示的文本内容。")
        return "\n".join(lines)

    lines.append("")
    lines.append("内容预览:")
    lines.append(content)
    if bool(data.get("truncated")):
        lines.append("")
        lines.append("内容比较长，我这里只显示了前半部分。")
    return "\n".join(lines)


def format_listing_for_user(data: Mapping[str, object]) -> str:
    path = str(data.get("path") or ".").strip() or "."
    if data.get("exists") is False:
        return (
            f"没有找到 workspace 路径 `{path}`。\n\n"
            "请检查文件名和目录层级，或先让我列出上一级目录。"
        )

    total = int(data.get("total") or 0)
    items = data.get("items")
    lines = [f"我列出了 `{path}` 下的内容，共找到 {total} 项。"]

    if isinstance(items, list) and items:
        lines.append("")
        lines.extend(
            format_workspace_entry_for_user(entry)
            for entry in items
            if isinstance(entry, Mapping)
        )
    else:
        lines.append("")
        lines.append("这个目录目前是空的。")

    if bool(data.get("truncated")):
        shown = len(items) if isinstance(items, list) else 0
        lines.append("")
        lines.append(f"内容较多，这里先显示前 {shown} 项。")
    return "\n".join(lines)


def format_test_result_for_user(data: Mapping[str, object]) -> str:
    ok = bool(data.get("ok"))
    target_paths = data.get("target_paths")
    targets = (
        ", ".join(str(path) for path in target_paths)
        if isinstance(target_paths, list) and target_paths
        else "默认测试目录"
    )
    summary = normalize_optional_text(data.get("summary"))
    stdout_preview = normalize_optional_text(data.get("stdout_preview"))
    stderr_preview = normalize_optional_text(data.get("stderr_preview"))

    lines = [
        "我运行完测试了。",
        "",
        f"目标: {targets}",
        f"结果: {'通过' if ok else '未通过'}",
    ]

    if summary is not None:
        lines.extend(["", summary])

    if stderr_preview is not None:
        lines.extend(["", "错误输出预览:", stderr_preview])
    elif stdout_preview is not None and not ok:
        lines.extend(["", "输出预览:", stdout_preview])

    return "\n".join(lines)


def format_workspace_operation_summary(data: Mapping[str, object]) -> str:
    operation = str(data.get("operation") or "operation").strip()
    kind = "目录" if str(data.get("kind") or "") == "dir" else "文件"
    if operation == "move":
        return (
            f"已移动/重命名{kind}。\n\n"
            f"source_path: {data.get('source_path')}\n"
            f"target_path: {data.get('target_path')}"
        )
    if operation == "copy":
        return (
            f"已复制{kind}。\n\n"
            f"source_path: {data.get('source_path')}\n"
            f"target_path: {data.get('target_path')}"
        )
    if operation == "delete":
        return f"已删除{kind}。\n\npath: {data.get('path')}"
    return f"已完成文件操作。\n\noperation: {operation}"


def format_file_operation_for_user(data: Mapping[str, object]) -> str:
    operation = str(data.get("operation") or "operation").strip()
    kind = "目录" if str(data.get("kind") or "") == "dir" else "文件"
    if operation == "move":
        return (
            f"已移动/重命名{kind}。\n\n"
            f"原路径: `{data.get('source_path')}`\n"
            f"新路径: `{data.get('target_path')}`"
        )
    if operation == "copy":
        return (
            f"已复制{kind}。\n\n"
            f"原路径: `{data.get('source_path')}`\n"
            f"新路径: `{data.get('target_path')}`"
        )
    if operation == "delete":
        return f"已删除{kind}: `{data.get('path')}`"
    return format_workspace_operation_summary(data)


def format_workspace_search_summary(data: Mapping[str, object]) -> str:
    query = str(data.get("query") or "").strip()
    path = str(data.get("path") or ".").strip() or "."
    count = int(data.get("match_count") or 0)
    return f"Workspace search `{query}` in `{path}` matched {count} line(s)."


def format_search_result_for_user(data: Mapping[str, object]) -> str:
    query = str(data.get("query") or "").strip()
    path = str(data.get("path") or ".").strip() or "."
    count = int(data.get("match_count") or 0)
    lines = [f"我在 `{path}` 中搜索了 `{query}`，找到 {count} 条匹配。"]
    matches = data.get("matches")
    if isinstance(matches, list) and matches:
        lines.append("")
        for match in matches:
            if not isinstance(match, Mapping):
                continue
            lines.append(
                f"- `{match.get('path')}`:{match.get('line_number')} {match.get('preview')}"
            )
    if bool(data.get("truncated")):
        lines.append("")
        lines.append("匹配结果较多，这里只显示前几条。")
    return "\n".join(lines)


def format_workspace_write_summary(data: Mapping[str, object]) -> str:
    if str(data.get("target_location") or "").strip() == "desktop":
        action = "覆盖" if bool(data.get("overwritten")) else "导出"
        lines = [
            f"已按配置{action}文本文件到桌面导出目录。",
            "",
            f"path: {data.get('path')}",
            f"chars_written: {data.get('chars_written')}",
        ]
        if bool(data.get("truncated")):
            lines.append("注意: 内容超过长度限制，已裁剪后写入。")
        return "\n".join(lines)

    action = "覆盖" if bool(data.get("overwritten")) else "创建"
    lines = [
        f"已在 workspace 中{action}文本文件。",
        "",
        f"path: {data.get('path')}",
        f"chars_written: {data.get('chars_written')}",
    ]
    if bool(data.get("truncated")):
        lines.append("注意: 内容超过长度限制，已裁剪后写入。")
    return "\n".join(lines)
