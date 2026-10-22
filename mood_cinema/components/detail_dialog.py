import reflex as rx

from mood_cinema import styles
from mood_cinema.components.recommend import reason_box
from mood_cinema.state import DetailState

DETAIL_GRADIENT = "linear-gradient(0deg, #0E0F13 0%, rgba(14,15,19,0.6) 50%, rgba(14,15,19,0.1) 100%)"


def _backdrop(view) -> rx.Component:
    # 위쪽 배경 이미지 + 아래로 어두워지는 그라데이션. 배경이 없으면 면 색만
    return rx.box(
        height=["160px", "160px", "300px"],
        width="100%",
        background_color=styles.SURFACE,
        background_image=rx.cond(
            view.backdrop_url != "",
            DETAIL_GRADIENT + ", url(" + view.backdrop_url + ")",
            DETAIL_GRADIENT,
        ),
        background_size="cover",
        background_position="center top",
    )


def _poster(view) -> rx.Component:
    return rx.cond(
        view.poster_url != "",
        rx.image(
            src=view.poster_url,
            alt=view.title,
            width=["96px", "96px", "160px"],
            aspect_ratio=styles.POSTER_RATIO,
            object_fit="cover",
            border_radius=styles.POSTER_RADIUS,
            box_shadow="0 8px 24px rgba(0,0,0,0.6)",
            flex_shrink="0",
        ),
    )


def _content(view) -> rx.Component:
    return rx.box(
        _backdrop(view),
        rx.vstack(
            # 포스터를 배경 위로 끌어올려 겹친다
            rx.hstack(
                _poster(view),
                rx.vstack(
                    rx.dialog.title(view.title, size="7", margin="0", color=styles.TEXT),
                    rx.cond(view.original_title != "", rx.text(view.original_title, size="2", color=styles.MUTED)),
                    rx.text(view.meta, size="2", color=styles.MUTED),
                    spacing="1",
                    align="start",
                ),
                align="end",
                spacing="4",
                margin_top=["-56px", "-56px", "-96px"],
                width="100%",
            ),
            rx.cond(view.reason != "", reason_box(view.reason)),
            rx.dialog.description(view.overview, size="2", color=styles.TEXT, style={"line_height": "1.7"}),
            rx.cond(
                view.trailer_embed_url != "",
                rx.box(
                    rx.el.iframe(
                        src=view.trailer_embed_url,
                        title="예고편",
                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture",
                        allow_full_screen=True,
                        style={"width": "100%", "height": "100%", "border": "0"},
                    ),
                    width="100%",
                    aspect_ratio="16 / 9",
                    border_radius=styles.POSTER_RADIUS,
                    overflow="hidden",
                ),
            ),
            spacing="4",
            padding=["16px", "16px", "28px"],
            padding_top="0",
            width="100%",
        ),
        position="relative",
        z_index="1",
    )


def _loading() -> rx.Component:
    return rx.vstack(
        rx.skeleton(rx.box(height="240px", width="100%"), loading=True, width="100%"),
        rx.skeleton(rx.text("제목을 불러오는 중"), loading=True),
        rx.skeleton(rx.box(height="80px", width="100%"), loading=True, width="100%"),
        rx.dialog.title("불러오는 중", style={"position": "absolute", "width": "1px", "height": "1px", "overflow": "hidden", "clip": "rect(0 0 0 0)"}),
        spacing="4",
        padding="28px",
        width="100%",
    )


def _error() -> rx.Component:
    return rx.box(
        rx.dialog.title("작품 상세", size="5"),
        rx.callout(DetailState.error, icon="triangle_alert", color_scheme="red", margin_top="12px"),
        padding="28px",
    )


def detail_dialog() -> rx.Component:
    """페이지에 한 번만 둔다. 카드·히어로가 DetailState.open_detail로 연다."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.cond(
                DetailState.loading,
                _loading(),
                rx.cond(DetailState.error != "", _error(), _content(DetailState.view)),
            ),
            rx.box(
                rx.dialog.close(
                    rx.icon_button(rx.icon("x"), variant="soft", color_scheme="gray", radius="full", aria_label="닫기"),
                ),
                position="absolute",
                top="12px",
                right="12px",
                z_index="2",
            ),
            max_width="860px",
            width="calc(100vw - 32px)",
            padding="0",
            overflow="hidden",
            background_color=styles.BG,
            position="relative",
        ),
        open=DetailState.open,
        on_open_change=DetailState.set_open,
    )
