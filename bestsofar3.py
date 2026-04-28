import flet as ft
import requests as rq
import boto3
import logging
import botocore
import botocore.exceptions
import random
import re
from time import sleep
from botocore.config import Config
from urllib.parse import urlparse

ALLOWED_BUCKETS = {"maples-2026-rug-dataset"}

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif")
SOURCE_PAREN_RE = re.compile(r"^\s*[-•]\s*(.+?)\s*\(source:\s*([A-Za-z0-9]{4})\)\s*$", re.IGNORECASE)
FILE_ID_LINE_RE = re.compile(r"^\s*[-•]\s*File\s*ID\s*:\s*([A-Za-z0-9]{4})\s*$", re.IGNORECASE)
ID_ONLY_BULLET_RE = re.compile(r"^\s*[-•]\s*([A-Za-z0-9]{4})\s*$")
IMAGE_WITH_ID_RE = re.compile(r"^\s*[-•]\s*Image\s+with\s+ID\s+([A-Za-z0-9]{4})\s*:\s*(.+)$", re.IGNORECASE)
PAREN_ID_RE = re.compile(r"^(.*)\(([A-Za-z0-9]{4})\)\s*$")

FALLBACK_DESC = "Rug image matching the query; description unavailable from search results."

def extract_desc_id_pairs(raw_text: str) -> list[tuple[str, str]]:
    pairs = []
    for raw in raw_text.splitlines():
        ln = raw.strip()
        if not ln:
            continue

        # "- Image with ID Ab12: Description..."
        m = IMAGE_WITH_ID_RE.match(ln)
        if m:
            pairs.append((m.group(2).strip(), m.group(1)))
            continue

        # "- Description ... (source: Ab12)"
        m = SOURCE_PAREN_RE.match(ln)
        if m:
            pairs.append((m.group(1).strip(), m.group(2)))
            continue

        # "- File ID: Ab12"
        
        m = FILE_ID_LINE_RE.match(ln)
        if m:
            pairs.append((FALLBACK_DESC, m.group(1)))
            continue

        # "- Ab12"
        m = ID_ONLY_BULLET_RE.match(ln)
        if m:
            pairs.append((FALLBACK_DESC, m.group(1)))
            continue

        # "Description ... (Ab12)" (works for numbered too)
        m = PAREN_ID_RE.match(ln)
        if m and m.group(2):
            desc = m.group(1).strip(" -•\t")
            if not desc:
                desc = FALLBACK_DESC
            pairs.append((desc, m.group(2)))
            continue

    return pairs



def parse_s3_uri(uri: str) -> tuple[str, str] | None:
    """
    Convert s3://bucket/key into (bucket, key)
    """
    parsed = urlparse(uri)
    if parsed.scheme != "s3":
        return None
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    return bucket, key


def presign_s3_uri(uri: str, expires_in: int = 3600) -> str | None:
    parsed = parse_s3_uri(uri)
    if not parsed:
        return None

    bucket, key = parsed
    

    # Only presign image files
    if not key.lower().endswith(IMAGE_EXTENSIONS):
        return None

    try:
        return s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires_in,
        )
    except botocore.exceptions.ClientError as e:
        logger.error(f"Failed to presign {uri}: {e}")
        return None

# ---- S3 config ----
BUCKET_NAME = "maples-2026-rug-dataset"
REGION = "us-east-1"
s3_client = boto3.client("s3", region_name=REGION)

# Map agent image IDs (like vynf) to S3 object KEYS (recommended),
# not full URLs.
IMAGE_ID_TO_S3_KEY = {
    "xeYB": "4028-FC36099+30x46+(1).png",
    # "vynf": "some/key.png",
}

# Agent image IDs come in parentheses, e.g. (vynf)
IMAGE_ID_RE = re.compile(r"\(([A-Za-z0-9]{4})\)")  # assumes 4-char IDs, like your examples


def strip_ids_from_text(text: str) -> str:
    # remove (vynf) and %[KIZC]% if it ever appears
    return re.sub(r"\([A-Za-z0-9]{3,12}\)|%\[[A-Za-z0-9]{3,12}\]%", "", text).strip()

bedrock_config = Config(
    region_name=REGION,
    connect_timeout=10,
    read_timeout=180,  # try 180–300 for agents
    retries={"max_attempts": 8, "mode": "adaptive"},
)

client = boto3.client("bedrock-agent-runtime", config=bedrock_config)
logger = logging.getLogger(__name__)

class Message:
    def __init__(
        self,
        user_name: str,
        text: str,
        message_type: str,
        items: list[tuple[str, str]] | None = None,  # [(id, url, or none), ...]
    ):
        self.user_name = user_name
        self.text = text
        self.message_type = message_type
        self.items = items or []
        

def extract_image_ids(text: str) -> list[str]:
    # finds ["vynf", "gr84", ...]
    return IMAGE_ID_RE.findall(text)


def image_id_to_presigned_url(image_id: str, expires_in: int = 3600) -> str | None:
    key = IMAGE_ID_TO_S3_KEY.get(image_id)
    if not key:
        return None

    try:
        return s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET_NAME, "Key": key},
            ExpiresIn=expires_in,
        )
    except botocore.exceptions.ClientError as e:
        logger.error(f"Failed to presign {BUCKET_NAME}/{key}: {e}")
        return None

class ChatMessage(ft.Row):
    def __init__(self, message: Message):
        super().__init__()
        self.vertical_alignment = ft.CrossAxisAlignment.START
        
        controls = [ft.Text(message.user_name, weight="bold")]

    # Optional: show header text (e.g., "Here is a list of images...")
        if message.text:
            controls.append(ft.Text(message.text, selectable=True, no_wrap=False))

        # Then show each description followed by its link
        for desc, url in message.items:
            controls.append(ft.Text(desc, selectable=True, no_wrap=False))
            if url:
                controls.append(
                    ft.Image(
                        src=url,
                        width=300,          # adjust to taste
                        fit=ft.ImageFit.CONTAIN,
                        border_radius=10,
                    )
                )
                
                controls.append(
                    ft.TextButton(
                        "Open full image",
                        on_click=lambda e, u=url: e.page.launch_url(u),
                    )
                )

        self.controls = [
            ft.CircleAvatar(
                content=ft.Text(self.get_initials(message.user_name)),
                color=ft.Colors.WHITE,
                bgcolor=self.get_avatar_color(message.user_name),
            ),
            ft.Column(controls, tight=True, spacing=5, expand=True),
        ]

    @staticmethod
    def invoke_agent(agent_id, agent_alias_id, session_id, prompt):
        completion_text = ""      # ✅ MUST exist before the loop
        s3_uris = []              # ✅ collect citation S3 URIs

        try:
            response = client.invoke_agent(
                agentId=agent_id,
                agentAliasId=agent_alias_id,
                sessionId=session_id,
                inputText=prompt,
                enableTrace=True,
                promptCreationConfigurations={
                    "excludePreviousThinkingSteps": True,
                    "previousConversationTurnsToInclude": 0,
                },
            )

            for event in response.get("completion", []):
                # 1) Text + citations
                if "chunk" in event:
                    chunk = event["chunk"]
                    completion_text += chunk["bytes"].decode("utf-8", errors="ignore")

                    attribution = chunk.get("attribution", {})
                    for citation in attribution.get("citations", []):
                        for ref in citation.get("retrievedReferences", []):
                            loc = ref.get("location", {})
                            if loc.get("type") == "S3":
                                uri = loc.get("s3Location", {}).get("uri")
                                if uri:
                                    s3_uris.append(uri)

                # 2) Optional: scan trace for s3://...
                if "trace" in event:
                    trace_str = str(event["trace"])
                    for match in re.findall(r"s3://[^\s'\"<>]+", trace_str):
                        if match.lower().endswith(IMAGE_EXTENSIONS):
                            s3_uris.append(match)

            # de-dupe, preserve order
            #s3_uris = list(dict.fromkeys(s3_uris))

            return completion_text.strip(), s3_uris

        except botocore.exceptions.ClientError as e:
            logger.error(f"Couldn't invoke agent: {e}")
            raise

    
    # keep your get_initials/get_avatar_color below...
    def get_initials(self, user_name: str):
        if user_name:
            return user_name[:1].capitalize()
        else:
            return "Nova"  # or any default value you prefer

    def get_avatar_color(self, user_name: str):
        colors_lookup = [
            ft.Colors.AMBER,
            ft.Colors.BLUE,
            ft.Colors.BROWN,
            ft.Colors.CYAN,
            ft.Colors.GREEN,
            ft.Colors.INDIGO,
            ft.Colors.LIME,
            ft.Colors.ORANGE,
            ft.Colors.PINK,
            ft.Colors.PURPLE,
            ft.Colors.RED,
            ft.Colors.TEAL,
            ft.Colors.YELLOW,
        ]
        return colors_lookup[hash(user_name) % len(colors_lookup)]

def main(page: ft.Page):
    page.horizontal_alignment = ft.CrossAxisAlignment.STRETCH
    page.title = "AWS Nova"
    
    def join_chat_click(e):
        if not join_user_name.value:
            join_user_name.error_text = "Name cannot be blank!"
            join_user_name.update()
        else:
            page.session.set("user_name", join_user_name.value)
            welcome_dlg.open = False
            new_message.prefix = ft.Text(f"{join_user_name.value}: ")
            page.pubsub.send_all(
                Message(
                    user_name=join_user_name.value,
                    text=f"{join_user_name.value} has joined the chat.",
                    message_type="login_message",
                )
            )
            page.pubsub.send_all(
                Message(
                    user_name="Nova",
                    text=f"Nova has joined the chat.",
                    message_type="login_message",
                )
            )
            page.update()

    def send_message_click(e):
        # Ignore empty sends
            if not new_message.value:
                return

        # Send user's message to chat
            page.pubsub.send_all(
                Message(
                page.session.get("user_name"),
                new_message.value,
                message_type="chat_message",
                )
            )

            qq = str(new_message.value)
            new_message.value = ""
            new_message.focus()
            page.update()

            # Show spinner
            pr = ft.ProgressRing(width=16, height=16, stroke_width=2)
            progress_row = ft.Row([pr], alignment=ft.MainAxisAlignment.CENTER)
            chat.controls.append(progress_row)
            page.update()

            try:
                # Call agent
                tst, s3_uris = ChatMessage.invoke_agent("BGAW0PPHIF", "FEX9BZ2ZUF", "asdv34345", qq)

                raw_text = (tst or "").replace("\n\n", "").strip()

                # 1) Extract (description, id) pairs from model output
                desc_id_pairs = extract_desc_id_pairs(raw_text)
                
                # ✅ DEBUG PRINTS: put them right here
                print("QUERY:", qq)
                print("RAW_TEXT (first 400):", raw_text[:400])
                print("S3_URIS COUNT:", len(s3_uris or []))
                print("S3_URIS SAMPLE:", (s3_uris or [])[:5])
                print("DESC_ID_PAIRS COUNT:", len(desc_id_pairs))
                
                # ✅ De-dupe S3 URIs to avoid repeats
                s3_uris = list(dict.fromkeys(s3_uris or []))

                # ✅ Build items ONLY from S3 URIs (deterministic)
                items = []
                for uri in (s3_uris or []):
                    url = presign_s3_uri(uri)
                    if not url:
                        continue

                    parsed = parse_s3_uri(uri)
                    if parsed:
                        bucket, key = parsed
                        head = s3_client.head_object(Bucket=bucket, Key=key)
                        meta = head.get("Metadata", {}) or {}
                        print("META FOR", key, "=>", meta)

                        desc = meta.get("description") or key.split("/")[-1]
                    # desc = key.split("/")[-1]  # filename fallback (swap to metadata later)
                    else:
                        desc = "Image"

                    items.append((desc, url))

                # If no citations -> no images
                if not items:
                    page.pubsub.send_all(
                        Message(
                            "Nova",
                            f"No image citations were returned for: {qq}",
                            message_type="system_message",
                            items=[],
                        )
                    )
                    return

                # 4) Header text (keep it simple)
                header_text = "Images:"
                clean_text = strip_ids_from_text(raw_text)

                # If the model gave a "The following files..." header line, keep it
                # (grab non-bullet lines)
                header_lines = []
                for ln in clean_text.splitlines():
                    ln = ln.strip()
                    if not ln:
                        continue
                    if ln.startswith("-") or re.match(r"^\d+\.", ln) or ln.lower().startswith("images:") or ln.lower().startswith("answer:"):
                        continue
                    header_lines.append(ln)

                if header_lines:
                    header_text = "\n".join(header_lines).strip()

                # Publish Nova response
                page.pubsub.send_all(
                    Message(
                        "Nova",
                        header_text,
                        message_type="system_message",
                        items=items,
                    )
                )

            except Exception as ex:
                page.pubsub.send_all(
                    Message(
                        "Nova",
                        f"Error calling agent: {ex}",
                        message_type="system_message",
                        items=[],
                    )
                )

            finally:
                # ALWAYS remove spinner
                if progress_row in chat.controls:
                    chat.controls.remove(progress_row)
                page.update()

            
    def on_message(message: Message):
        if message.message_type == "chat_message":
            m = ChatMessage(message)
        elif message.message_type == "system_message":
            m = ChatMessage(message)
        elif message.message_type == "login_message":
            m = ft.Text(message.text, italic=True, color=ft.Colors.BLUE_100, size=12)
        chat.controls.append(m)
        page.update()

    page.pubsub.subscribe(on_message)

    # A dialog asking for a user display name
    join_user_name = ft.TextField(
        label="Enter your name to join the chat",
        autofocus=True,
        on_submit=join_chat_click,
    )
    welcome_dlg = ft.AlertDialog(
        open=True,
        modal=True,
        title=ft.Text("Welcome!"),
        content=ft.Column([join_user_name], width=300, height=70, tight=True),
        actions=[ft.ElevatedButton(text="Join chat", on_click=join_chat_click)],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    page.overlay.append(welcome_dlg)

    # Chat messages
    chat = ft.ListView(
        expand=True,
        spacing=10,
        auto_scroll=True,
    )

    # A new message entry form
    new_message = ft.TextField(
        hint_text="Write a message...",
        autofocus=True,
        shift_enter=True,
        min_lines=1,
        max_lines=5,
        filled=True,
        expand=True,
        on_submit=send_message_click,
    )
    add_item = ft.TextField(
        hint_text="Add new item...",
        autofocus=False,)

    # Add everything to the page
    page.add(
        ft.Container(
            content=chat,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=5,
            padding=10,
            expand=True,
        ),
        ft.Row(
            [
                new_message,
                ft.IconButton(
                    icon=ft.Icons.SEND_ROUNDED,
                    tooltip="Send message",
                    on_click=send_message_click,
                ),
            ]
            
            
        ),
    )


ft.app(target=main)