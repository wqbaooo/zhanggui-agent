#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""高德地图 Web 服务工具。

用于开店 Agent 的商圈/竞品/聚客点分析。只做事实采集和统计，
不直接做开店结论。
"""

from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
from urllib.request import urlopen


PROJECT_ROOT = Path(__file__).resolve().parent


def load_env_file(path: Path = PROJECT_ROOT / ".env"):
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file()


@dataclass
class Poi:
    name: str
    type: str
    address: str
    location: str
    distance: Optional[int] = None
    tel: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)


class AmapTool:
    base_url = "https://restapi.amap.com/v3"

    # 高德 POI typecode 可继续扩展；先用关键词 + 泛类组合，避免过早复杂化。
    anchor_keywords = ["小区", "社区", "学校", "大学", "写字楼", "办公楼", "医院", "地铁站", "公交站", "菜市场", "商场", "超市"]
    competitor_keywords = {
        "早餐": ["早餐", "包子", "豆浆", "粥", "馄饨", "面馆", "粉面"],
        "小吃": ["小吃", "炸串", "卤味", "麻辣烫", "煎饼", "烧饼", "包子"],
        "粉面": ["面馆", "米粉", "粉面", "拉面", "重庆小面"],
        "饮品": ["奶茶", "咖啡", "饮品", "茶饮"],
        "快餐": ["快餐", "简餐", "盖饭", "黄焖鸡", "便当"],
    }

    def __init__(self, key: Optional[str] = None):
        self.key = key or os.getenv("AMAP_WEBSERVICE_KEY")
        if not self.key:
            raise ValueError("缺少 AMAP_WEBSERVICE_KEY，请在 .env 中配置高德 Web 服务 API key。")
        self.request_interval = float(os.getenv("AMAP_REQUEST_INTERVAL", "0.35"))
        self._last_request_at = 0.0

    def geocode(self, address: str, city: Optional[str] = None) -> Dict[str, Any]:
        data = self._get("/geocode/geo", {"address": address, "city": city or ""})
        geocodes = data.get("geocodes", [])
        if not geocodes:
            raise ValueError(f"高德未找到地址：{address}")
        best = geocodes[0]
        return {
            "formatted_address": best.get("formatted_address", ""),
            "province": best.get("province", ""),
            "city": best.get("city", ""),
            "district": best.get("district", ""),
            "location": best.get("location", ""),
            "level": best.get("level", ""),
            "raw": best,
        }

    def search_around(self, location: str, keywords: str, radius: int = 1000, offset: int = 25, page: int = 1) -> List[Poi]:
        data = self._get(
            "/place/around",
            {
                "location": location,
                "keywords": keywords,
                "radius": radius,
                "offset": offset,
                "page": page,
                "extensions": "base",
                "sortrule": "distance",
            },
        )
        center = parse_location(location)
        pois = [self._parse_poi(item) for item in data.get("pois", [])]
        if center:
            for poi in pois:
                if poi.distance is None:
                    poi_location = parse_location(poi.location)
                    if poi_location:
                        poi.distance = int(haversine_m(center[0], center[1], poi_location[0], poi_location[1]))
        return pois

    def analyze_site(self, address: str, category: str = "早餐", city: Optional[str] = None, radius: int = 1000) -> Dict[str, Any]:
        geo = self.geocode(address, city)
        location = geo["location"]
        competitor_keywords = self.competitor_keywords.get(category, [category])

        competitors: List[Poi] = []
        for keyword in competitor_keywords[:5]:
            competitors.extend(self.search_around(location, keyword, radius=radius))

        anchors: Dict[str, List[Poi]] = {}
        for keyword in self.anchor_keywords[:10]:
            pois = self.search_around(location, keyword, radius=radius)
            if pois:
                anchors[keyword] = pois[:8]

        competitors = self._dedupe(competitors)
        return {
            "address": address,
            "category": category,
            "radius": radius,
            "geocode": geo,
            "competitors": {
                "count": len(competitors),
                "items": [self._poi_dict(poi) for poi in competitors[:30]],
                "keywords": competitor_keywords,
            },
            "anchors": {
                keyword: {
                    "count": len(items),
                    "items": [self._poi_dict(poi) for poi in items[:8]],
                }
                for keyword, items in anchors.items()
            },
            "signals": self._signals(competitors, anchors),
        }

    def search_by_region(self, keywords: str, city: str, region: str = "", offset: int = 25) -> Dict[str, Any]:
        """区域关键词搜索：在整个城市或区县范围内搜索指定品类POI。
        
        适用场景：用户没有具体地址，想知道"红谷滩有多少早餐店"。
        
        Args:
            keywords: 搜索关键词（如 '早餐|包子|面馆'）
            city: 城市名（如 '南昌'）
            region: 区县名（可选，如 '红谷滩区'）
            offset: 每页返回数量
        """
        params = {
            "keywords": keywords,
            "city": city,
            "offset": offset,
            "extensions": "base",
        }
        if region:
            params["city"] = region  # 高德text搜索支持区县级city参数
        
        data = self._get("/place/text", params)
        pois = [self._parse_poi(item) for item in data.get("pois", [])]
        count = int(data.get("count", 0))
        
        return {
            "keywords": keywords,
            "city": city,
            "region": region or city,
            "total_count": count,
            "returned": len(pois),
            "pois": [self._poi_dict(poi) for poi in pois],
            "type_distribution": self._type_distribution(pois),
        }

    def analyze_town(self, city: str, county: str, town: str = "", category: str = "早餐") -> Dict[str, Any]:
        """乡镇级商圈分析：细化到县/乡镇级别的POI密度和竞争格局。
        
        Args:
            city: 城市名
            county: 区/县名（如 '渝水区'）
            town: 乡镇/街道名（可选，如 '城北街道'）
            category: 餐饮品类
        """
        area_name = f"{city}{county}" + (f"{town}" if town else "")
        keywords_list = self.competitor_keywords.get(category, [category])
        
        # 1. 搜索同品类竞品
        all_competitors = []
        for kw in keywords_list[:4]:
            result = self.search_by_region(kw, city, county)
            all_competitors.extend(result["pois"])
        
        all_competitors = self._dedupe_poi_dicts(all_competitors)
        
        # 2. 搜索关键锚点（学校/小区/写字楼/菜市场）
        anchor_results = {}
        for anchor_kw in ["学校", "小区", "写字楼", "菜市场", "公交站"][:5]:
            result = self.search_by_region(anchor_kw, city, county)
            anchor_results[anchor_kw] = {
                "count": result["total_count"],
                "top3": result["pois"][:3],
            }
        
        # 3. 竞争强度评估
        total_competitors = len(all_competitors)
        anchor_score = sum(r["count"] for r in anchor_results.values())
        
        density_level = "低"
        if total_competitors > 30:
            density_level = "高"
        elif total_competitors > 10:
            density_level = "中"
        
        return {
            "area": area_name,
            "city": city,
            "county": county,
            "town": town or "未指定",
            "category": category,
            "competitors": {
                "total_found": total_competitors,
                "density_level": density_level,
                "top_pois": all_competitors[:15],
                "keywords_used": keywords_list,
            },
            "anchors": anchor_results,
            "signals": {
                "anchor_total": anchor_score,
                "competition_intensity": density_level,
                "suitable_for_category": self._suitability_assess(total_competitors, anchor_results, density_level),
            },
        }

    def get_district_info(self, keywords: str, subdistrict: int = 1) -> Dict[str, Any]:
        """获取行政区划信息（边界、下级行政区列表）。
        
        Args:
            keywords: 行政区划关键词（如 '红谷滩区'）
            subdistrict: 是否返回下级行政区（1=是）
        """
        data = self._get("/config/district", {
            "keywords": keywords,
            "subdistrict": subdistrict,
            "extensions": "base",
        })
        districts = data.get("districts", [])
        if not districts:
            return {"error": f"未找到行政区划: {keywords}"}
        
        d = districts[0]
        return {
            "name": d.get("name", ""),
            "level": d.get("level", ""),
            "citycode": d.get("citycode", ""),
            "adcode": d.get("adcode", ""),
            "center": d.get("center", ""),
            "sub_districts": [
                {"name": sd.get("name", ""), "level": sd.get("level", ""),
                 "center": sd.get("center", ""), "adcode": sd.get("adcode", "")}
                for sd in d.get("districts", [])
            ] if subdistrict else [],
        }

    # ============ 私有辅助方法 ============

    def _type_distribution(self, pois: List[Poi]) -> Dict[str, int]:
        """统计 POI 类型分布。"""
        dist = {}
        for poi in pois:
            t = poi.type.split(";")[0] if poi.type else "未知"
            dist[t] = dist.get(t, 0) + 1
        return dict(sorted(dist.items(), key=lambda x: x[1], reverse=True)[:10])

    def _dedupe_poi_dicts(self, pois: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """对POI字典列表去重。"""
        seen = set()
        result = []
        for poi in pois:
            key = (poi.get("name"), poi.get("location"))
            if key in seen:
                continue
            seen.add(key)
            result.append(poi)
        return result

    def _suitability_assess(self, competitor_count: int, anchors: Dict[str, Any], density: str) -> str:
        """简单评估品类适配度。"""
        has_school = anchors.get("学校", {}).get("count", 0) > 0
        has_residential = anchors.get("小区", {}).get("count", 0) > 0
        has_office = anchors.get("写字楼", {}).get("count", 0) > 0
        
        if has_school and has_residential:
            return "区域有学校和小区，适合早餐/小吃类。建议关注上学/上班高峰客流。"
        if has_office and density != "高":
            return "写字楼集中且竞争不激烈，适合快餐/简餐类。建议调查午间客流。"
        if competitor_count < 5:
            return "竞品极少——可能是蓝海市场，也可能是需求不足。建议实地验证人流。"
        return "区域竞争适中，可进一步分析具体铺位。"

    def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        params = {k: v for k, v in params.items() if v is not None}
        params["key"] = self.key
        url = f"{self.base_url}{path}?{urlencode(params)}"
        for attempt in range(4):
            self._rate_limit()
            with urlopen(url, timeout=15) as response:
                data = json.loads(response.read().decode("utf-8"))
            if data.get("status") == "1":
                return data
            if data.get("infocode") == "10021":
                time.sleep(1.0 + attempt)
                continue
            raise RuntimeError(f"高德 API 调用失败：{data.get('info')} ({data.get('infocode')})")
        raise RuntimeError("高德 API 调用失败：连续触发 QPS 限制，请稍后重试或调大 AMAP_REQUEST_INTERVAL。")

    def _rate_limit(self):
        elapsed = time.time() - self._last_request_at
        if elapsed < self.request_interval:
            time.sleep(self.request_interval - elapsed)
        self._last_request_at = time.time()

    def _parse_poi(self, item: Dict[str, Any]) -> Poi:
        distance = item.get("distance")
        try:
            distance_int = int(distance) if distance not in {"", None, []} else None
        except Exception:
            distance_int = None
        return Poi(
            name=item.get("name", ""),
            type=item.get("type", ""),
            address=item.get("address", "") if isinstance(item.get("address", ""), str) else "",
            location=item.get("location", ""),
            distance=distance_int,
            tel=item.get("tel", "") if isinstance(item.get("tel", ""), str) else "",
            raw=item,
        )

    def _dedupe(self, pois: List[Poi]) -> List[Poi]:
        seen = set()
        result = []
        for poi in pois:
            key = (poi.name, poi.location)
            if key in seen:
                continue
            seen.add(key)
            result.append(poi)
        return sorted(result, key=lambda poi: poi.distance if poi.distance is not None else 999999)

    def _poi_dict(self, poi: Poi) -> Dict[str, Any]:
        return {
            "name": poi.name,
            "type": poi.type,
            "address": poi.address,
            "location": poi.location,
            "distance": poi.distance,
        }

    def _signals(self, competitors: List[Poi], anchors: Dict[str, List[Poi]]) -> Dict[str, Any]:
        near_competitors = [poi for poi in competitors if poi.distance is not None and poi.distance <= 500]
        anchor_counts = {keyword: len(items) for keyword, items in anchors.items()}
        return {
            "competitors_within_500m": len(near_competitors),
            "competitors_within_radius": len(competitors),
            "anchor_counts": anchor_counts,
            "has_subway_signal": bool(anchors.get("地铁站")),
            "has_residential_signal": bool(anchors.get("小区") or anchors.get("社区")),
            "has_office_signal": bool(anchors.get("写字楼") or anchors.get("办公楼")),
            "has_school_signal": bool(anchors.get("学校") or anchors.get("大学")),
            "notes": [
                "地图 POI 只能说明周边业态和潜在线索，不能替代实地蹲点。",
                "高德返回的 POI 不包含真实客流和门店经营流水，需要结合现场观察和平台数据。",
            ],
        }


def parse_location(location: str) -> Optional[tuple[float, float]]:
    try:
        lon, lat = location.split(",", 1)
        return float(lon), float(lat)
    except Exception:
        return None


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    radius = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))
