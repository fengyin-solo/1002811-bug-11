"""内存数据仓库：给每个业务模块准备一份可筛选、可流转的示例数据。

真实项目里这里会换成数据库访问层；当前实现只依赖标准库，保证克隆下来就能起。
"""
from __future__ import annotations

import re
from typing import Any

from app.seed import SEED_ROWS


def parse_area(value: Any) -> float | None:
    """把「1200.5」「1,200.5 ㎡」这类面积写法解析成数值；无法识别时返回 None。"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = re.sub(r"[,\s平方米㎡m²]", "", str(value))
        if not text:
            return None
        try:
            number = float(text)
        except ValueError:
            return None
    return number if number >= 0 else None


class Store:
    def __init__(self) -> None:
        self._tables: dict[str, list[dict[str, Any]]] = {
            name: [dict(row) for row in rows] for name, rows in SEED_ROWS.items()
        }

    def module_names(self) -> list[str]:
        return sorted(self._tables)

    def rows(self, module: str) -> list[dict[str, Any]]:
        return self._tables.setdefault(module, [])

    def find(self, module: str, entry_id: int) -> dict[str, Any] | None:
        for row in self.rows(module):
            if int(row.get("id", 0)) == entry_id:
                return row
        return None

    def overview(self) -> dict[str, object]:
        modules: list[dict[str, object]] = []
        for name in self.module_names():
            rows = self.rows(name)
            modules.append({
                "name": name,
                "created": len(rows),
                "pending": sum(1 for row in rows if row.get("pending")),
                "abnormal": sum(1 for row in rows if row.get("abnormal")),
            })
        # 在管面积随接管明细实时重算：仅统计「已接管」绿地
        managed_area = round(
            sum(
                area
                for row in self.rows("plot")
                if row.get("status") == "已接管"
                for area in [parse_area(row.get("面积"))]
                if area is not None
            ),
            2,
        )
        cards = [
            {"label": "业务模块", "value": len(modules)},
            {"label": "今日新增", "value": sum(int(item["created"]) for item in modules)},
            {"label": "待处理", "value": sum(int(item["pending"]) for item in modules)},
            {"label": "异常量", "value": sum(int(item["abnormal"]) for item in modules)},
            {"label": "在管面积(㎡)", "value": managed_area},
        ]
        return {"cards": cards, "modules": modules}


store = Store()
