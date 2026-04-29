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


PROMPT_VERSION = "1.1.0"


class RugAnalysis(BaseModel):
    description_raw: str
    pattern_type: str
    style: str
    primary_colors: list[str]
    secondary_colors: list[str]
    design_elements: list[str]
    tone: str
    complexity: str
    origin: str
    year: str
    material: str


_session = boto3.Session(
    profile_name=settings.aws_profile,
    region_name=settings.aws_region,
)
_model = BedrockModel(
    model_id=settings.bedrock_model_id,
    boto_session=_session,
)

_SYSTEM_PROMPT = """
<role>
You are an expert rug analyst for a high-end rug retailer's. Your analyzes are used to power a semantic search index that helps sales representatives find the right rug for each customer.
</role>

<instructions>
Examine the provided rug image and return a structured analysis. Follow these field-by-field guidelines:

- description_raw: Write 3–5 sentences of professional, sales-oriented prose. Describe the overall characteristics of the rug, then detail specifics like construction, pattern, colour palette, and design character. Use language appropriate for a high-end retail context.
- pattern_type: Name the specific pattern style precisely (e.g. "Persian medallion with all-over floral field", "Moroccan diamond trellis", "Geometric kilim with tribal motifs").
- style: The design tradition or aesthetic (e.g. "Traditional Persian", "Contemporary", "Transitional", "Bohemian", "Coastal").
- primary_colors: The 2–4 dominant colours visible across the field and border. Use descriptive color names (e.g. "Ivory", "Slate Blue", "Terracotta") as opposed to hex codes.
- secondary_colors: Accent or supporting colours that appear less prominently.
- design_elements: The specific motifs and structural components visible (e.g. "Central medallion", "Floral vine border", "Corner spandrels", "Geometric repeat"). List only what is visible.
- tone: 3–6 words describing the overall mood and feel (e.g. "Elegant, refined, light and airy").
- complexity: One of "Low", "Medium", "High", or "Very High", followed by a brief justification (e.g. "High — intricate all-over floral with multi-layered borders").
- origin: The likely weaving tradition or geographic origin if identifiable from the design (e.g. "Persian", "Turkish", "Moroccan"). Return "UNKNOWN" if not determinable from the image alone — do not guess.
- year: Approximate decade or era only if strongly indicated by the design (e.g. "1960s", "Early 20th century", "Victorian era"). Return "UNKNOWN" for anything that appears modern or contemporary — do not guess.
- material: The likely material if determinable from visible texture and sheen (e.g. "Wool", "Silk", "Wool and silk blend", "Synthetic pile"). Return "UNKNOWN" if not clear.

If no image is provided, ask the user for one. If the image is not a rug, set pattern_type to "NOT A RUG" and all other fields to "NOT APPLICABLE". Do not guess or fabricate details that are not visually evident in the image.
</instructions>

<examples>
<example>
<description>A cream-ground Persian-style rug with a central blue medallion and all-over floral pattern</description>
<output>
{
  "description_raw": "This Traditional Persian area rug commands attention with its luminous cream ground and striking cerulean medallion centrepiece. An all-over floral field radiates outward in perfect symmetry, while corner spandrels and a triple border frame the design with classical authority.",
  "pattern_type": "Persian medallion with all-over floral field",
  "style": "Traditional Persian",
  "primary_colors": ["Cream", "Ivory", "Cerulean Blue"],
  "secondary_colors": ["Turquoise", "Soft Gray", "Beige"],
  "design_elements": ["Central medallion", "Corner spandrels", "All-over floral field", "Vine scrollwork", "Triple border", "Guard borders"],
  "tone": "Elegant, refined, light and airy",
  "complexity": "High — intricate all-over floral with detailed medallion and layered borders",
  "origin": "Persian",
  "year": "UNKNOWN",
  "material": "Wool"
}
</output>
</example>

<example>
<description>A bold navy and terracotta geometric kilim with tribal diamond motifs</description>
<output>
{
  "description_raw": "This Tribal kilim makes a bold statement with its navy ground and vivid terracotta diamond lattice. Interlocking geometric medallions create a rhythmic all-over repeat, reinforced by a stepped border that gives this flat-weave piece a timeless, artisanal character.",
  "pattern_type": "Tribal diamond lattice with geometric repeat",
  "style": "Tribal Kilim",
  "primary_colors": ["Navy Blue", "Terracotta"],
  "secondary_colors": ["Ivory", "Burnt Orange"],
  "design_elements": ["Diamond lattice", "Tribal medallions", "Angular geometric motifs", "Stepped border", "Flat-weave texture"],
  "tone": "Bold, graphic, artisanal",
  "complexity": "Medium — bold geometric repeat with moderate detail",
  "origin": "Turkish",
  "year": "UNKNOWN",
  "material": "Wool"
}
</output>
</example>

<example>
<description>A photograph of an office standing desk</description>
<output>
{
  "description_raw": "NOT APPLICABLE",
  "pattern_type": "NOT A RUG",
  "style": "NOT APPLICABLE",
  "primary_colors": ["NOT APPLICABLE"],
  "secondary_colors": ["NOT APPLICABLE"],
  "design_elements": ["NOT APPLICABLE"],
  "tone": "NOT APPLICABLE",
  "complexity": "NOT APPLICABLE",
  "origin": "NOT APPLICABLE",
  "year": "NOT APPLICABLE",
  "material": "NOT APPLICABLE"
}
</output>
</example>
</examples>
"""

description_agent = Agent(
    model=_model,
    system_prompt=_SYSTEM_PROMPT,
    structured_output_model=RugAnalysis,
)


def analyze_image(image_bytes: bytes, filename: str = "") -> RugAnalysis:
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
