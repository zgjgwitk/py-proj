import json
from collections import defaultdict


def optimize_type_value_query(original_query: dict) -> dict:
    """
    优化 ES 查询中 type+typeValue 的 should 条件。

    原始查询将每个 (type, typeValue) 组合展开为独立的 bool.must 条件，
    优化后按 type 分组，typeValue 使用 terms 查询，大幅减少查询条件数量。

    Args:
        original_query: 原始 ES 查询 dict

    Returns:
        优化后的 ES 查询 dict（深拷贝，不修改原始对象）
    """
    query = json.loads(json.dumps(original_query))  # 深拷贝

    filter_list = query.get("query", {}).get("bool", {}).get("filter", [])
    if not filter_list:
        return query

    # 找到包含 should 的 filter 条件（第二个 bool 块）
    should_filter_index = None
    for i, f in enumerate(filter_list):
        if "bool" in f and "should" in f["bool"]:
            should_filter_index = i
            break

    if should_filter_index is None:
        return query

    should_conditions = filter_list[should_filter_index]["bool"]["should"]

    # 按 type 分组收集 typeValue
    # 格式: { "CoupExpireWarn1": set(typeValue列表), ... }
    type_to_values: dict[str, set] = defaultdict(set)
    # 不符合 type+typeValue 模式的条件保留原样
    other_conditions = []

    for cond in should_conditions:
        if not isinstance(cond, dict):
            other_conditions.append(cond)
            continue

        bool_must = cond.get("bool", {}).get("must", [])
        if len(bool_must) != 2:
            other_conditions.append(cond)
            continue

        type_val = None
        type_value_val = None

        for item in bool_must:
            term = item.get("term", {})
            if "type" in term:
                type_val = term["type"].get("value") if isinstance(term["type"], dict) else term["type"]
            elif "typeValue" in term:
                type_value_val = term["typeValue"].get("value") if isinstance(term["typeValue"], dict) else term["typeValue"]

        if type_val is not None and type_value_val is not None:
            type_to_values[type_val].add(type_value_val)
        else:
            other_conditions.append(cond)

    if not type_to_values:
        return query

    # 构建优化后的 should 条件
    optimized_should = list(other_conditions)
    for type_name, type_values in sorted(type_to_values.items()):
        optimized_should.append({
            "bool": {
                "must": [
                    {"term": {"type": {"value": type_name}}},
                    {"terms": {"typeValue": sorted(type_values)}}
                ]
            }
        })

    filter_list[should_filter_index] = {"bool": {"should": optimized_should}}

    return query


INPUT_FILE = r"D:\Github\py-proj\py-es\优化TypeAndValueStat方法\input.txt"
OUTPUT_FILE = r"D:\Github\py-proj\py-es\优化TypeAndValueStat方法\output.txt"


def main():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        original_query = json.load(f)

    # 统计优化前 should 条件数量
    before_count = 0
    for item in original_query.get("query", {}).get("bool", {}).get("filter", []):
        if "bool" in item and "should" in item["bool"]:
            before_count = len(item["bool"]["should"])
            break

    optimized_query = optimize_type_value_query(original_query)

    # 统计优化后 should 条件数量
    after_count = 0
    for item in optimized_query.get("query", {}).get("bool", {}).get("filter", []):
        if "bool" in item and "should" in item["bool"]:
            after_count = len(item["bool"]["should"])
            break

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(optimized_query, f, ensure_ascii=False, indent=2)

    print(f"优化前 should 条件数: {before_count}")
    print(f"优化后 should 条件数: {after_count}")
    if before_count > 0:
        print(f"减少比例: {(1 - after_count / before_count) * 100:.1f}%")
    print(f"已输出到: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
