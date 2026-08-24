"""Editorial policy for the recruiter-facing repository catalog."""

from __future__ import annotations

from typing import Any


CATEGORY_METADATA = {
    "Developer Tooling": "Tools for agents, code quality, review, evidence, and controlled automation.",
    "Product Systems": "End-to-end products that turn domain workflows into usable software systems.",
    "Creative and Consumer": "Experiments and products for media, publishing, and visual interaction.",
    "Research and Education": "Applied research, data science, and continuing academic work.",
}

SUBCATEGORY_METADATA = {
    "Agent-enabled": "Infrastructure and contracts that make agent workflows bounded, inspectable, and reusable.",
    "Quality and Review": "Developer-facing checks and review surfaces that make software quality easier to act on.",
    "Change and Evidence": "Tools that explain changes, preserve evidence, and reduce integration uncertainty.",
    "Automation and Control": "Guarded automation and local control planes with explicit human boundaries.",
    "AI and Knowledge": "Products for structured knowledge, applied AI, and decision support.",
    "Sports and Analytics": "Sports products and analytical systems spanning training, scouting, and modeling.",
    "Work and Operations": "Operational software for teams, professionals, and repeatable business workflows.",
    "Music and Media": "Consumer experiences for music, taste, and media discovery.",
    "Publishing": "Editorial and portfolio systems for presenting authored work.",
    "Visual Experiences": "Image-first interfaces and visual creation tools.",
    "Data Science": "Research pipelines and inspectable analytical applications.",
    "Academic Projects": "Coursework and school projects that continue as active product explorations.",
    "Writing": "Systems for research-grounded and claim-safe writing.",
}


def _include(category: str, subcategory: str, *, rank: int | None = None, **extra: Any) -> dict[str, Any]:
    return {"readme_disposition": "include", "category": category, "subcategory": subcategory, "featured_rank": rank, **extra}


def _exclude(reason: str) -> dict[str, Any]:
    return {"readme_disposition": "exclude", "exclusion_reason": reason}


POLICY: dict[str, dict[str, Any]] = {
    "pronto": _include("Developer Tooling", "Automation and Control", rank=1, display_name="Pronto"),
    "AIOS": _include("Developer Tooling", "Agent-enabled", rank=1),
    "skills-library": _exclude("Generated archive; the maintained agent workbench is represented separately."),
    "CLFE": _include("Product Systems", "Sports and Analytics"),
    "RTE Transferable Signals": _include("Research and Education", "Data Science", display_name="RTE Transferable Signals"),
    "cap-fit-builder": _include("Product Systems", "Sports and Analytics", display_name="Cap Fit Builder"),
    "signal-lab": _include("Research and Education", "Data Science", display_name="Signal Lab"),
    "womens-stats": _include("Product Systems", "Sports and Analytics", display_name="Women's Stats"),
    "BIP-Console": _exclude("Archived and superseded by maintained portfolio systems."),
    "Bballedu": _include("Product Systems", "Sports and Analytics", rank=1, display_name="Court Vision"),
    "BidCamp": _include("Product Systems", "Work and Operations", rank=1),
    "Book": _include("Creative and Consumer", "Publishing", rank=2),
    "Crimclock": _include("Product Systems", "Work and Operations", rank=2, display_name="CrimClock", summary="Legal-time intelligence for procedural deadlines, sentencing, parole eligibility, custody impact, and case timelines.", summary_source="project-compass+owner-policy"),
    "Dsci-proj": _include("Research and Education", "Data Science", rank=1, display_name="Issue Resolution Risk"),
    "Fantasy": _include("Product Systems", "Sports and Analytics", rank=2),
    "LaxDS": _include("Research and Education", "Data Science"),
    "Terrace": _include("Developer Tooling", "Agent-enabled", display_name="Terrace"),
    "agent-eval-contract": _include("Developer Tooling", "Agent-enabled", display_name="Agent Eval Contract"),
    "agent-eval-runtime": _include("Developer Tooling", "Agent-enabled", display_name="Agent Eval Runtime"),
    "agent-router": _include("Developer Tooling", "Agent-enabled", rank=2, display_name="Agent Router"),
    "ai-context-runtime": _include("Developer Tooling", "Agent-enabled", display_name="AI Context Runtime"),
    "ai-workflow-leverage": _include("Developer Tooling", "Agent-enabled", display_name="AI Workflow Leverage"),
    "attentiond": _include("Developer Tooling", "Automation and Control", display_name="Attentiond"),
    "automation-flight-recorder": _include("Developer Tooling", "Automation and Control", display_name="Automation Flight Recorder"),
    "behavior-coverage-atlas": _include("Developer Tooling", "Quality and Review", display_name="Behavior Coverage Atlas"),
    "browser-control": _include("Developer Tooling", "Automation and Control", display_name="Browser Control"),
    "career-ops": _include("Product Systems", "Work and Operations", display_name="Career Ops"),
    "change-integration-simulator": _include("Developer Tooling", "Change and Evidence", display_name="Change Integration Simulator"),
    "change-radius": _include("Developer Tooling", "Change and Evidence", display_name="Change Radius"),
    "ci-incident-router": _include("Developer Tooling", "Automation and Control", display_name="CI Incident Router"),
    "claude-config": _exclude("Personal compatibility configuration rather than a standalone portfolio project."),
    "codex": _exclude("Provider-confirmed fork without a distinct portfolio claim."),
    "context-compiler-contract": _include("Developer Tooling", "Agent-enabled", display_name="Context Compiler Contract"),
    "contract-watch": _include("Developer Tooling", "Change and Evidence", display_name="Contract Watch"),
    "daily-front-page": _exclude("Personal information surface with no safe recruiter-facing projection."),
    "debug-trail": _include("Developer Tooling", "Change and Evidence", display_name="Debug Trail"),
    "deletion-proof-workbench": _include("Developer Tooling", "Change and Evidence", display_name="Deletion Proof Workbench"),
    "dispatches-from-cyberspace": _include("Creative and Consumer", "Publishing", display_name="Dispatches from Cyberspace"),
    "dotfiles": _exclude("Personal workstation infrastructure."),
    "editors-desk-newsletter": {
        "readme_disposition": "defer",
        "review_reason": "Private repository with no approved recruiter-facing projection.",
    },
    "eslint-plugin-anti-slop": _include("Developer Tooling", "Quality and Review", display_name="ESLint Anti-Slop"),
    "evidence-replay": _include("Developer Tooling", "Change and Evidence", display_name="Evidence Replay"),
    "failure-capsule": _include("Developer Tooling", "Change and Evidence", display_name="Failure Capsule"),
    "fleet-radar": {"readme_disposition": "defer", "review_reason": "Project identity evidence is missing."},
    "gmail-mcp-bridge": _exclude("Personal account infrastructure with no safe public projection."),
    "jakye-skill-family": _include("Developer Tooling", "Agent-enabled", display_name="Jakye Skill Family"),
    "jakyeamos-agent-skills": _include("Developer Tooling", "Agent-enabled", rank=3, display_name="Portable Agentic Workbench"),
    "jakyeamos-agentic-setup-private": _exclude("Private host and overlay infrastructure."),
    "jakyeamos-profile": _exclude("The profile catalog itself; including it would be self-referential."),
    "mac-control": _include("Developer Tooling", "Automation and Control", rank=2, display_name="Mac Control"),
    "marketing-autoresearch": _include("Research and Education", "Data Science", display_name="Marketing Autoresearch"),
    "paperwhite-web": {"readme_disposition": "defer", "review_reason": "No configured remote."},
    "participant-dedup": _include("Product Systems", "Work and Operations", display_name="Participant Dedup"),
    "pattern-atlas": _include("Developer Tooling", "Change and Evidence", rank=2, display_name="Pattern Atlas"),
    "pixel-art-workbench": _include("Creative and Consumer", "Visual Experiences", rank=1, display_name="Pixel Art Workbench"),
    "playlist-appender": {"readme_disposition": "defer", "review_reason": "No configured remote."},
    "portfolio": _include("Creative and Consumer", "Publishing", rank=1, display_name="Front Office Amos"),
    "pre-cr-suite-lsp": _include("Developer Tooling", "Quality and Review", display_name="Pre-CR Suite"),
    "quality-lens": _include("Developer Tooling", "Quality and Review", rank=2, display_name="Quality Lens"),
    "quality-runner": _include("Developer Tooling", "Quality and Review", rank=1, display_name="Quality Runner"),
    "quality-setup": _include("Developer Tooling", "Quality and Review", display_name="Quality Setup"),
    "readiness-inspector": _include("Developer Tooling", "Quality and Review", display_name="Readiness Inspector"),
    "relay": _exclude("Personal control-plane infrastructure."),
    "remediation-canvas": _include("Developer Tooling", "Quality and Review", display_name="Remediation Canvas"),
    "remodelvision": _include("Research and Education", "Academic Projects", rank=2, display_name="RemodelVision", summary="Continuing school project that turns a room photo and renovation brief into a visual concept and indicative cost estimate.", summary_source="project-compass+owner-policy"),
    "research-domain-writing": _include("Research and Education", "Writing", rank=1, display_name="Research Domain Writing"),
    "review-attention-map": _include("Developer Tooling", "Quality and Review", display_name="Review Attention Map"),
    "review-sandbox": _include("Developer Tooling", "Quality and Review", display_name="Review Sandbox"),
    "rule-lab": _include("Developer Tooling", "Quality and Review", display_name="Rule Lab"),
    "soundscape-app": _include("Creative and Consumer", "Music and Media", rank=2, display_name="Soundscape", summary="Music-taste platform for capturing reactions, comparing trusted perspectives, discovering music, and revisiting how taste changes over time.", summary_source="project-compass"),
    "surface-flow": _include(
        "Creative and Consumer",
        "Visual Experiences",
        display_name="Surface Flow",
        summary="Semantic article layout across perspective-mapped illustrated surfaces.",
        summary_source="project-compass+github",
    ),
    "steward": _include("Developer Tooling", "Change and Evidence", rank=3, display_name="Steward"),
    "structural-diff": _include("Developer Tooling", "Change and Evidence", rank=1, display_name="Structural Diff"),
    "tenure": _include("Product Systems", "AI and Knowledge", rank=1, display_name="Tenure", summary="Knowledge operating system that turns specialist expertise into permissioned guidance and surfaces process gaps and staleness.", summary_source="project-compass+owner-policy"),
    "test-intent-registry": _include("Developer Tooling", "Quality and Review", display_name="Test Intent Registry"),
    "tmcp": _include("Developer Tooling", "Agent-enabled", display_name="TMCP"),
    "workflow-gateboard": _include("Developer Tooling", "Quality and Review", display_name="Workflow Gateboard"),
    "LIS": _include("Product Systems", "Sports and Analytics", rank=3, display_name="LIS", summary="Python analytics package for NBA game-control scoring with live-data ingestion, cached rescoring, confidence tiers, and player-level diagnostics.", summary_source="github-readme"),
}


PUBLIC_RELEASES: dict[str, dict[str, str]] = {
    "quality-runner": {"release": "PyPI `v0.6.0`", "public_url": "https://github.com/jakyeamos/quality-runner/tree/v0.6.0"},
    "eslint-plugin-anti-slop": {"release": "npm `v0.5.0`", "public_url": "https://github.com/jakyeamos/eslint-plugin-anti-slop/releases/tag/v0.5.0"},
    "pre-cr-suite-lsp": {"release": "npm `@pre-cr/* v0.1.0`", "public_url": "https://github.com/jakyeamos/pre-cr-suite/tree/v0.1.0"},
    "agent-eval-contract": {"release": "PyPI `v0.2.0`; repo tag `v0.3.0`", "public_url": "https://github.com/jakyeamos/agent-eval-contract"},
    "research-domain-writing": {"release": "PyPI `v0.1.0`; repo tag `v0.2.2`", "public_url": "https://github.com/jakyeamos/research-domain-writing"},
    "tmcp": {"release": "GitHub release `v0.5.8`", "public_url": "https://github.com/jakyeamos/tmcp/releases/tag/v0.5.8"},
    "Terrace": {"release": "npm `v0.1.1`", "public_url": "https://github.com/jakyeamos/Terrace"},
}
