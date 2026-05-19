import pathlib
from typing import Literal

import boto3
from pydantic import BaseModel
from strands import Agent
from strands.models import BedrockModel

from maplerugs.config import settings


def _image_format(filename: str) -> Literal["png", "jpeg", "gif", "webp"]:
    match pathlib.Path(filename).suffix.lower():
        case ".jpg" | ".jpeg":
            return "jpeg"
        case ".gif":
            return "gif"
        case ".webp":
            return "webp"
        case _:
            return "png"


PROMPT_VERSION = "1.4.0"

SEARCH_KEYWORD_TAXONOMY = [
    "Abstract", "Americana", "Animal Skin", "Antique", "Authentic", "Basic",
    "Basket Weave", "Block", "Border", "Botanical", "Braid", "Braided", "Casual",
    "Check", "Checker Board", "Chevron", "Circle", "Classical", "Damask", "Diamond",
    "Distressed", "Farmhouse", "Floral", "Fretwork", "Geometric", "Gingham", "Global",
    "Herringbone", "Hooked", "Ikat", "Juvenile", "Kilim", "Leaf", "Marble", "Modern",
    "Moroccan", "Novelty", "Ogee", "Ombre", "Oval", "Panel", "Persian", "Plaid",
    "Scroll", "Sisal", "Soft Modern", "Southwest", "Stripe", "Textured", "Traditional",
    "Transitional", "Trellis", "Tribal", "Vintage", "Watercolor", "Wave", "Weathered",
]


class RugAnalysis(BaseModel):
    search_keywords: list[str]
    pattern_type: str
    style: str
    primary_colors: list[str]
    secondary_colors: list[str]
    design_elements: list[str]
    tone: str
    complexity: str
    origin: str
    material: str
    description_raw: str


_session = boto3.Session(
    profile_name=settings.aws_profile,
    region_name=settings.aws_region,
)
_model = BedrockModel(
    model_id=settings.bedrock_model_id,
    boto_session=_session,
)

_TAXONOMY_STR = ", ".join(SEARCH_KEYWORD_TAXONOMY)

_SYSTEM_PROMPT = f"""
<role>
You are an expert rug analyst for a high-end rug retailer. Your structured analyses power an exact-match keyword search index used by internal sales staff. Precision is critical: the search system surfaces results based on the keywords you assign, so over-tagging causes irrelevant rugs to appear in search results and buries the best matches. Your goal is accurate classification, not broad coverage.
</role>

<keyword_selection_rules>
Assign a keyword ONLY if it describes a PRIMARY, DEFINING characteristic of this rug — meaning a sales representative searching that term would consider this rug a strong, direct match. When in doubt, leave the keyword out.

INCLUDE a keyword when:
  - The pattern type, style, or dominant motif matches the keyword directly (e.g. assign "Floral" when floral motifs cover the majority of the field).
  - The keyword is the most natural single-word label a buyer would use when searching for this rug.

DO NOT include a keyword when:
  - The characteristic is minor, incidental, or confined to a small accent area.
  - The keyword is broadly true of most rugs in the catalog (e.g. do not assign "Border" unless a decorative border is the defining visual feature; do not assign "Traditional" to every non-contemporary design).
  - The keyword overlaps heavily with one already included (e.g. do not include both "Floral" and "Botanical" for the same floral field; pick the more precise one).
  - You are hedging or guessing — if unsure, omit.

Target 2–4 keywords per rug. Rarely exceed 5. Return an empty list only if the rug genuinely matches none of the taxonomy terms.

Taxonomy (select only what directly applies):
{_TAXONOMY_STR}
</keyword_selection_rules>

<field_guidelines>
Return the following fields in order:

1. search_keywords — Apply the keyword selection rules above.

2. pattern_type — Name the specific pattern precisely (e.g. "Persian medallion with all-over floral field", "Moroccan diamond trellis", "Geometric kilim with tribal motifs"). Return "UNKNOWN" if not clearly identifiable.

3. style — The design tradition or aesthetic (e.g. "Traditional Persian", "Contemporary", "Transitional", "Bohemian", "Coastal"). Return "UNKNOWN" if not determinable. Do not default to "Transitional" as a hedge.

4. primary_colors — The 2–4 dominant colours across the field and border. Use descriptive names (e.g. "Ivory", "Slate Blue", "Terracotta"), not hex codes.

5. secondary_colors — Accent or supporting colours that appear less prominently.

6. design_elements — Specific motifs and structural components visible (e.g. "Central medallion", "Floral vine border", "Corner spandrels", "Geometric repeat"). List only what is clearly visible.

7. tone — 3–6 words describing the overall mood (e.g. "Elegant, refined, light and airy").

8. complexity — One of "Low", "Medium", "High", or "Very High", with a brief justification (e.g. "High — intricate all-over floral with multi-layered borders").

9. origin — Geographic or cultural weaving tradition if clearly identifiable from the design (e.g. "Persian", "Turkish", "Moroccan"). Return "UNKNOWN" if not determinable. Do not guess.

10. material — If the filename contains a recognisable material (e.g. "Wool", "Viscose", "Polyester"), use it as the authoritative value. Otherwise, infer from visible texture and sheen. Return "UNKNOWN" if not determinable.

11. description_raw — Write exactly 2 concise sentences of professional, sales-oriented prose. The first sentence must name the style tradition and dominant pattern (e.g. "A Traditional Persian rug with an all-over floral medallion field on a cream ground."). The second sentence describes the colour palette and overall design character. Do not state material, construction method, or origin unless confirmed in the filename or unambiguously visible in the image.
</field_guidelines>

<constraints>
- Do not guess or fabricate details that are not visually evident in the image.
- If no image is provided, ask the user for one.
- Return "UNKNOWN" rather than guessing for origin, material, or style when the image is insufficient.
</constraints>

<examples>
<example>
<description>A cream-ground Persian-style rug with a central blue medallion and all-over floral pattern</description>
<reasoning>
Floral is the dominant field pattern — include. Persian is the defining design tradition — include. Scroll is a primary structural element (vine scrollwork fills the field) — include. Traditional follows directly from Persian — include as the style descriptor keyword. "Botanical" overlaps too heavily with "Floral" and would double-count; omit. "Border" applies to nearly every rug; omit unless the border itself is the main selling point.
</reasoning>
<output>
{{
  "search_keywords": ["Floral", "Persian", "Traditional", "Scroll"],
  "pattern_type": "Persian medallion with all-over floral field",
  "style": "Traditional Persian",
  "primary_colors": ["Cream", "Ivory", "Cerulean Blue"],
  "secondary_colors": ["Turquoise", "Soft Gray", "Beige"],
  "design_elements": ["Central medallion", "Corner spandrels", "All-over floral field", "Vine scrollwork", "Triple border", "Guard borders"],
  "tone": "Elegant, refined, light and airy",
  "complexity": "High — intricate all-over floral with detailed medallion and layered borders",
  "origin": "Persian",
  "material": "Wool",
  "description_raw": "A Traditional Persian area rug with a luminous cream ground anchored by a striking cerulean medallion and all-over floral vine scrollwork. The cool blue, ivory, and turquoise palette gives this classically structured piece an elegant, refined character suited to formal living spaces."
}}
</output>
</example>

<example>
<description>A bold navy and terracotta geometric kilim with tribal diamond motifs</description>
<reasoning>
Kilim is the defining construction/style — include. Geometric and Diamond describe the dominant motif — include. Tribal is the design tradition — include. "Southwest" would apply only if the motifs are distinctly Southwestern American; Turkish tribal kilims are not Southwest. "Global" is too vague to be useful. "Textured" applies to nearly every rug; omit.
</reasoning>
<output>
{{
  "search_keywords": ["Kilim", "Geometric", "Diamond", "Tribal"],
  "pattern_type": "Tribal diamond lattice with geometric repeat",
  "style": "Tribal Kilim",
  "primary_colors": ["Navy Blue", "Terracotta"],
  "secondary_colors": ["Ivory", "Burnt Orange"],
  "design_elements": ["Diamond lattice", "Tribal medallions", "Angular geometric motifs", "Stepped border"],
  "tone": "Bold, graphic, artisanal",
  "complexity": "Medium — bold geometric repeat with moderate detail",
  "origin": "Turkish",
  "material": "Wool",
  "description_raw": "A Tribal Kilim rug with a commanding navy ground and vivid terracotta diamond lattice repeat. The high-contrast navy and terracotta palette, anchored by ivory and burnt orange accents, makes a bold statement in casual or globally influenced interiors."
}}
</output>
</example>
</examples>
"""

def analyze_image(image_bytes: bytes, filename: str = "") -> RugAnalysis:
    description_agent = Agent(
        model=_model,
        system_prompt=_SYSTEM_PROMPT,
        structured_output_model=RugAnalysis,
    )
    prompt_text = f"Filename: {filename}\n\nAnalyze this rug and return a structured description."
    result = description_agent(
        [
            {"image": {"format": _image_format(filename), "source": {"bytes": image_bytes}}},
            {"text": prompt_text},
        ]
    )
    output = result.structured_output
    if not isinstance(output, RugAnalysis):
        raise ValueError(f"Structured output is not a RugAnalysis: {type(output)}")
    return output
