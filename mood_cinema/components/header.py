import reflex as rx

from mood_cinema import styles


def header() -> rx.Component:
    return rx.hstack(
        rx.link(rx.heading("🎬 Mood Cinema", size="5", color=styles.TEXT), href="/", underline="none"),
        rx.spacer(),
        rx.link("AI 추천", href="#recommend", color=styles.TEXT, underline="none", size="2"),
        rx.link("트렌딩", href="#trending", color=styles.TEXT, underline="none", size="2"),
        position="sticky",
        top="0",
        z_index="10",
        width="100%",
        align="center",
        spacing="5",
        padding_x=styles.PAGE_PADDING_X,
        padding_y="14px",
        background_color=styles.HEADER_BG,
        style={"backdrop_filter": "blur(12px)", "-webkit-backdrop-filter": "blur(12px)"},
        border_bottom="1px solid rgba(255,255,255,0.06)",
    )
