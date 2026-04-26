from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from .util import slugify

PROJECT_CATEGORY_THRESHOLD = 0.45
MIN_EVIDENCE = 3


def generate_projects(store, min_evidence: int = MIN_EVIDENCE) -> dict[str, Any]:
    """Generate project ideas from clusters with high-signal categories."""
    now = datetime.now(timezone.utc).isoformat()
    projects_created = 0
    evidence_added = 0

    clusters = store.get_clusters()
    high_signal_categories = {
        "ai-agents", "product-ideas", "tools", "coding",
        "infra", "workflows", "business", "design",
    }

    for cluster in clusters:
        cluster_id = int(cluster["id"])
        members = store.get_cluster_members(cluster_id)
        if len(members) < min_evidence:
            continue

        # Analyze cluster composition
        category_counts: Counter = Counter()
        entity_counts: Counter = Counter()
        link_domains: Counter = Counter()
        top_texts: list[str] = []

        for member in members:
            # Classifications
            classifs = store.get_bookmark_classifications(member["id"])
            for c in classifs:
                if c["is_primary"]:
                    category_counts[c["category_slug"]] += 1

            # Entities
            entities = store.get_bookmark_entities(member["id"])
            for e in entities:
                entity_counts[e["name"]] += 1

            # Links
            links = store.get_bookmark_links(member["id"])
            for link in links:
                if link["domain"]:
                    link_domains[link["domain"]] += 1

            # Text sample
            text = member["tweet_text"] or member["raw_text"] or ""
            if text:
                top_texts.append(text[:200])

        # Check if cluster has high-signal category
        top_cat, top_cat_count = category_counts.most_common(1)[0]
        if top_cat not in high_signal_categories:
            continue
        if top_cat_count < min_evidence:
            continue

        # Generate project idea
        top_entities = [e for e, _ in entity_counts.most_common(5)]
        top_domains = [d for d, _ in link_domains.most_common(3)]
        cluster_label = cluster["label"] or top_cat.replace("-", " ").title()
        project_title = _generate_title(top_cat, top_entities, cluster_label)
        project_slug = slugify(project_title)
        one_liner = _generate_one_liner(top_cat, top_entities, top_domains, len(members))
        problem = _extract_problem(top_texts, top_cat)
        audience = _extract_audience(top_cat)
        why_now = _extract_why_now(top_cat, top_entities)
        impl_notes = _generate_impl_notes(top_entities, top_domains, top_cat)

        confidence = min(0.9, 0.3 + (top_cat_count / len(members)) * 0.4)

        # Check if project already exists
        existing = store.conn.execute(
            "SELECT id FROM project_ideas WHERE slug = ?", (project_slug,)
        ).fetchone()

        project_id: int
        if existing:
            project_id = int(existing["id"])
            store.conn.execute(
                """UPDATE project_ideas SET
                   title=?, one_liner=?, problem=?, audience=?,
                   why_now=?, implementation_notes=?, confidence=?,
                   updated_at=?
                   WHERE id=?""",
                (project_title, one_liner, problem, audience, why_now,
                 impl_notes, confidence, now, project_id),
            )
        else:
            store.conn.execute(
                """INSERT INTO project_ideas
                   (slug, title, one_liner, problem, audience, why_now,
                    implementation_notes, source_cluster_id, confidence,
                    status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (project_slug, project_title, one_liner, problem, audience,
                 why_now, impl_notes, cluster_id, confidence, "candidate", now, now),
            )
            store.conn.commit()
            project_id = int(
                store.conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            )

        # Add evidence bookmarks
        for member in members[:min_evidence * 2]:
            existing_source = store.conn.execute(
                """SELECT 1 FROM project_sources
                   WHERE project_id = ? AND bookmark_id = ?""",
                (project_id, member["id"]),
            ).fetchone()
            if not existing_source:
                store.conn.execute(
                    """INSERT INTO project_sources(project_id, bookmark_id, role)
                       VALUES (?, ?, ?)""",
                    (project_id, member["id"], "evidence"),
                )
                evidence_added += 1

        projects_created += 1

    store.conn.commit()
    return {"projects_created": projects_created, "evidence_added": evidence_added}


def _generate_title(category: str, entities: list[str], fallback: str) -> str:
    """Generate a project title from cluster data."""
    if entities:
        # Capitalize entities
        capitalized = [e.title() if len(e) > 2 else e.upper() for e in entities[:3]]
        if len(capitalized) == 1:
            return f"{capitalized[0]} Builder"
        return f"{capitalized[0]} x {capitalized[1]}"
    return fallback


def _generate_one_liner(category: str, entities: list[str], domains: list[str], count: int) -> str:
    """Generate a one-liner summary."""
    entity_part = " + ".join(entities[:2]) if entities else "this space"
    domain_part = f" (across {domains[0]})" if domains else ""
    return f"Build something with {entity_part}{domain_part} — found in {count} bookmarks."


def _extract_problem(texts: list[str], category: str) -> str:
    """Extract the problem/opportunity from bookmark texts."""
    problem_indicators = ["pain", "hard", "difficult", "slow", "annoying", "broken", "missing", "need", "want", "wish"]
    found = []
    for text in texts[:5]:
        text_lower = text.lower()
        for indicator in problem_indicators:
            if indicator in text_lower:
                found.append(indicator)
    if found:
        counter = Counter(found)
        top = counter.most_common(1)[0][0]
        return f"The {category.replace('-', ' ')} space lacks good solutions for: {top} problems."
    return f"Opportunity to improve tooling in the {category.replace('-', ' ')} area."


def _extract_audience(category: str) -> str:
    """Extract target audience from category."""
    audiences = {
        "ai-agents": "Developers building autonomous agents and AI workflows",
        "coding": "Software engineers and developers",
        "product-ideas": "Indie hackers and builders",
        "tools": "Developers and power users",
        "infra": "DevOps engineers and platform teams",
        "workflows": "Operations teams and productivity-focused individuals",
        "business": "Founders and business development professionals",
        "design": "Designers and frontend developers",
    }
    return audiences.get(category, "Builders and developers interested in this space")


def _extract_why_now(category: str, entities: list[str]) -> str:
    """Extract why this project is relevant now."""
    now_parts = []
    if entities:
        now_parts.append(f"{entities[0]} is gaining traction")
    now_parts.append("Bookmark count shows sustained interest")
    return ". ".join(now_parts) + "."


def _generate_impl_notes(entities: list[str], domains: list[str], category: str) -> str:
    """Generate implementation notes."""
    parts = []
    if entities:
        parts.append(f"Key technologies: {', '.join(entities[:3])}")
    if domains:
        parts.append(f"Reference domains: {', '.join(domains[:2])}")
    parts.append(f"Start with a minimal viable feature in the {category.replace('-', ' ')} space")
    return "\n".join(parts)
