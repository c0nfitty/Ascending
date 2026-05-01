import re
from datetime import UTC, datetime

from pydantic import BaseModel

from maplerugs.agents.description_agent import PROMPT_VERSION, RugAnalysis, analyze_image
from maplerugs.config import settings

_DIMENSIONS_RE = re.compile(r"-(\d+)x(\d+)-", re.IGNORECASE)


class SourceConfig(BaseModel):
    rug_id: str
    s3_image_key: str
    processed_at: str
    model_version: str
    prompt_version: str


class CatalogMetadata(BaseModel):
    style: str | None = None
    year: str | None = None
    color_name: str | None = None
    customer_style_names: list[str] = []


class RugRecord(BaseModel):
    source_config: SourceConfig
    width: str
    height: str
    analysis: RugAnalysis
    catalog_metadata: CatalogMetadata | None = None
    combined_text: str


def _parse_dimensions(filename: str) -> tuple[str, str] | None:
    m = _DIMENSIONS_RE.search(filename)
    return (m.group(1), m.group(2)) if m else None


def _make_combined_text(analysis: RugAnalysis, catalog: CatalogMetadata | None = None) -> str:
    fields = [
        analysis.description_raw,
        f"Analysis Style: {analysis.style}.",
        f"Pattern: {analysis.pattern_type}.",
        f"Primary colors: {', '.join(analysis.primary_colors)}.",
        f"Secondary colors: {', '.join(analysis.secondary_colors)}.",
        f"Design elements: {', '.join(analysis.design_elements)}.",
        f"Tone: {analysis.tone}.",
        f"Complexity: {analysis.complexity}.",
        f"Origin: {analysis.origin}.",
        f"Material: {analysis.material}.",
    ]
    if catalog and catalog.style:
        fields.append(f"Catalog Style: {catalog.style}.")
    if catalog and catalog.year:
        fields.append(f"Year: {catalog.year}.")
    if catalog and catalog.color_name:
        fields.append(f"Color: {catalog.color_name}.")
    if catalog and catalog.customer_style_names:
        fields.append(f"Also known as: {', '.join(catalog.customer_style_names)}.")
    return " ".join(f for f in fields if "UNKNOWN" not in f and "NOT APPLICABLE" not in f)


def process_image(
    image_bytes: bytes,
    filename: str = "",
    rug_id: str | None = None,
    s3_image_key: str | None = None,
    catalog_metadata: CatalogMetadata | None = None,
) -> RugRecord:
    analysis = analyze_image(image_bytes, filename)
    dims = _parse_dimensions(filename)
    source_config = SourceConfig(
        rug_id=rug_id or "",
        s3_image_key=s3_image_key or "",
        processed_at=datetime.now(UTC).isoformat(),
        model_version=settings.bedrock_model_id,
        prompt_version=PROMPT_VERSION,
    )
    return RugRecord(
        source_config=source_config,
        width=dims[0] if dims else "UNKNOWN",
        height=dims[1] if dims else "UNKNOWN",
        analysis=analysis,
        catalog_metadata=catalog_metadata,
        combined_text=_make_combined_text(analysis, catalog_metadata),
    )
