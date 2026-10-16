"""
Central management plane for multi-site deployments.

Tracks provisioned sites, their model versions and health, and exposes
idempotent register/update operations plus aggregate reporting. This is the
control-plane counterpart to the per-site data/sync plane: onboarding a site or
bumping a model version is a single idempotent call keyed by ``site_id``.
"""

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class SiteRecord:
    site_id: str
    name: str = ""
    model_version: str = ""
    endpoint: str = ""
    active: bool = True
    last_seen: str = ""

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


class SiteRegistry:
    def __init__(self) -> None:
        self._sites: Dict[str, SiteRecord] = {}

    def register(
        self,
        site_id: str,
        name: str = "",
        model_version: str = "",
        endpoint: str = "",
        active: bool = True,
    ) -> SiteRecord:
        """Create or update a site; idempotent on ``site_id``."""
        existing = self._sites.get(site_id)
        record = SiteRecord(
            site_id=site_id,
            name=name or (existing.name if existing else ""),
            model_version=model_version or (existing.model_version if existing else ""),
            endpoint=endpoint or (existing.endpoint if existing else ""),
            active=active,
            last_seen=existing.last_seen if existing else "",
        )
        self._sites[site_id] = record
        return record

    def get(self, site_id: str) -> Optional[SiteRecord]:
        return self._sites.get(site_id)

    def deactivate(self, site_id: str) -> bool:
        if site_id not in self._sites:
            return False
        self._sites[site_id].active = False
        return True

    def activate(self, site_id: str) -> bool:
        if site_id not in self._sites:
            return False
        self._sites[site_id].active = True
        return True

    def heartbeat(self, site_id: str, timestamp: Optional[str] = None) -> bool:
        if site_id not in self._sites:
            return False
        self._sites[site_id].last_seen = timestamp or datetime.utcnow().isoformat()
        return True

    def update_model_version(self, site_id: str, version: str) -> bool:
        if site_id not in self._sites:
            return False
        self._sites[site_id].model_version = version
        return True

    def list_sites(self, active_only: bool = False) -> List[SiteRecord]:
        sites = self._sites.values()
        if active_only:
            sites = (site for site in sites if site.active)
        return sorted(sites, key=lambda site: site.site_id)

    def aggregate(self) -> Dict[str, object]:
        sites = list(self._sites.values())
        by_version: Dict[str, int] = {}
        for site in sites:
            key = site.model_version or "unknown"
            by_version[key] = by_version.get(key, 0) + 1
        return {
            "total": len(sites),
            "active": sum(1 for site in sites if site.active),
            "inactive": sum(1 for site in sites if not site.active),
            "by_model_version": by_version,
        }

    def __len__(self) -> int:
        return len(self._sites)

    def __contains__(self, site_id: str) -> bool:
        return site_id in self._sites
