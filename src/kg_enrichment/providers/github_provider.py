"""GitHub provider — organization, repository, and contributor intelligence.

Fetches org info, repositories, languages, contributors, dependencies.
Works with or without a GitHub token (rate-limited without).
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from kg_enrichment.core.graph import KnowledgeGraph
from kg_enrichment.core.models import Entity, EnrichmentTask, ProviderResult, Relationship
from kg_enrichment.providers.base import BaseProvider

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


class GitHubProvider(BaseProvider):
    name = "github"
    description = "GitHub organization, repository, and contributor intelligence"
    supported_entity_types = ["organization", "person", "software", "repository"]
    requires_api_key = False  # Works without, but rate-limited
    rate_limit = 1.0

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "KGEnrichment/0.1",
        }
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    async def can_enrich(self, entity: Entity) -> bool:
        if entity.entity_type in ("repository",):
            return True
        if entity.entity_type in ("organization", "person", "software"):
            return True
        gh = entity.attributes.get("github_org") or entity.attributes.get("github_url")
        return bool(gh)

    async def enrich(self, entity: Entity, graph: KnowledgeGraph) -> ProviderResult:
        result = ProviderResult(provider_name=self.name)

        github_org = (
            entity.attributes.get("github_org")
            or entity.attributes.get("github_url", "").rstrip("/").split("/")[-1]
        )

        if entity.entity_type == "repository":
            return await self._enrich_repo(entity, result)

        if not github_org:
            # Try searching GitHub for the entity name
            github_org = entity.name.lower().replace(" ", "").replace(",", "").replace(".", "")

        return await self._enrich_org(github_org, entity, result)

    async def _enrich_org(
        self, org_name: str, entity: Entity, result: ProviderResult
    ) -> ProviderResult:
        """Fetch everything about a GitHub organization."""
        async with httpx.AsyncClient(
            timeout=30.0, headers=self._headers()
        ) as client:
            # Org profile
            try:
                resp = await client.get(f"{GITHUB_API}/orgs/{org_name}")
                if resp.status_code == 200:
                    org_data = resp.json()
                    entity.attributes["github"] = {
                        "login": org_data.get("login"),
                        "description": org_data.get("description"),
                        "blog": org_data.get("blog"),
                        "location": org_data.get("location"),
                        "public_repos": org_data.get("public_repos"),
                        "public_gists": org_data.get("public_gists"),
                        "followers": org_data.get("followers"),
                        "created_at": org_data.get("created_at"),
                    }
                    entity.add_source("github")
                    result.raw_data.append({"type": "org_profile", "data": org_data})

                    # Blog → domain entity
                    blog = org_data.get("blog")
                    if blog:
                        from urllib.parse import urlparse
                        domain = urlparse(
                            blog if "://" in blog else f"https://{blog}"
                        ).netloc
                        if domain:
                            domain_entity = Entity(
                                entity_type="domain",
                                name=domain,
                                attributes={"url": blog, "source": "github_org_blog"},
                                sources=["github"],
                            )
                            result.suggested_entities.append(domain_entity)
                            result.suggested_relationships.append(Relationship(
                                rel_type="owns_domain",
                                source_entity_id=entity.id,
                                target_entity_id=domain_entity.id,
                                sources=["github"],
                            ))
            except Exception as e:
                logger.warning(f"GitHub org fetch failed for {org_name}: {e}")
                result.errors.append(f"GitHub org error: {e}")

            # Repositories
            try:
                resp = await client.get(
                    f"{GITHUB_API}/orgs/{org_name}/repos",
                    params={"sort": "pushed", "per_page": 30},
                )
                if resp.status_code == 200:
                    repos = resp.json()
                    for repo in repos:
                        repo_entity = Entity(
                            entity_type="repository",
                            name=repo.get("full_name", repo.get("name", "")),
                            attributes={
                                "description": repo.get("description", ""),
                                "language": repo.get("language", ""),
                                "stars": repo.get("stargazers_count", 0),
                                "forks": repo.get("forks_count", 0),
                                "open_issues": repo.get("open_issues_count", 0),
                                "created_at": repo.get("created_at", ""),
                                "updated_at": repo.get("updated_at", ""),
                                "topics": repo.get("topics", []),
                                "license": (repo.get("license") or {}).get("spdx_id", ""),
                                "url": repo.get("html_url", ""),
                            },
                            sources=["github"],
                        )
                        result.suggested_entities.append(repo_entity)
                        result.suggested_relationships.append(Relationship(
                            rel_type="owns_repo",
                            source_entity_id=entity.id,
                            target_entity_id=repo_entity.id,
                            sources=["github"],
                        ))
                    result.raw_data.append({
                        "type": "repos", "count": len(repos),
                    })
            except Exception as e:
                logger.warning(f"GitHub repos fetch failed for {org_name}: {e}")

            # Members (public)
            try:
                resp = await client.get(
                    f"{GITHUB_API}/orgs/{org_name}/members",
                    params={"per_page": 50},
                )
                if resp.status_code == 200:
                    members = resp.json()
                    for member in members:
                        person_entity = Entity(
                            entity_type="person",
                            name=member.get("login", ""),
                            attributes={
                                "github_username": member.get("login", ""),
                                "github_url": member.get("html_url", ""),
                                "avatar": member.get("avatar_url", ""),
                            },
                            sources=["github"],
                        )
                        result.suggested_entities.append(person_entity)
                        result.suggested_relationships.append(Relationship(
                            rel_type="member_of",
                            source_entity_id=person_entity.id,
                            target_entity_id=entity.id,
                            sources=["github"],
                        ))
                    result.raw_data.append({
                        "type": "members", "count": len(members),
                    })
            except Exception as e:
                logger.warning(f"GitHub members fetch failed for {org_name}: {e}")

        result.metadata = {"github_org": org_name}
        return result

    async def _enrich_repo(
        self, entity: Entity, result: ProviderResult
    ) -> ProviderResult:
        """Fetch everything about a specific repository."""
        repo_name = entity.name
        if "/" not in repo_name:
            return result

        async with httpx.AsyncClient(
            timeout=30.0, headers=self._headers()
        ) as client:
            # Repo details
            try:
                resp = await client.get(f"{GITHUB_API}/repos/{repo_name}")
                if resp.status_code == 200:
                    repo_data = resp.json()
                    entity.attributes.update({
                        "description": repo_data.get("description", ""),
                        "language": repo_data.get("language", ""),
                        "stars": repo_data.get("stargazers_count", 0),
                        "forks": repo_data.get("forks_count", 0),
                        "topics": repo_data.get("topics", []),
                    })
                    entity.add_source("github")
                    result.raw_data.append({"type": "repo_detail", "data": repo_data})
            except Exception as e:
                result.errors.append(f"Repo detail error: {e}")

            # Contributors
            try:
                resp = await client.get(
                    f"{GITHUB_API}/repos/{repo_name}/contributors",
                    params={"per_page": 30},
                )
                if resp.status_code == 200:
                    contributors = resp.json()
                    for contrib in contributors:
                        person_entity = Entity(
                            entity_type="person",
                            name=contrib.get("login", ""),
                            attributes={
                                "github_username": contrib.get("login", ""),
                                "contributions": contrib.get("contributions", 0),
                            },
                            sources=["github"],
                        )
                        result.suggested_entities.append(person_entity)
                        result.suggested_relationships.append(Relationship(
                            rel_type="contributes_to",
                            source_entity_id=person_entity.id,
                            target_entity_id=entity.id,
                            attributes={
                                "contributions": contrib.get("contributions", 0),
                            },
                            sources=["github"],
                        ))
            except Exception as e:
                result.errors.append(f"Contributors error: {e}")

            # Languages
            try:
                resp = await client.get(f"{GITHUB_API}/repos/{repo_name}/languages")
                if resp.status_code == 200:
                    entity.attributes["languages"] = resp.json()
            except Exception:
                pass

        result.metadata = {"repo": repo_name}
        return result
