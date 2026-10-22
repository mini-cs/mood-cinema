"""디자인 토큰 (스펙 9.1). 컴포넌트는 색·간격을 여기 상수로만 쓴다."""

BG = "#0E0F13"
SURFACE = "#1A1C23"
TEXT = "#EDEDED"
MUTED = "#9AA0A6"
ACCENT = "#E8A33D"
REASON_BG = "rgba(232, 163, 61, 0.08)"
HEADER_BG = "rgba(14, 15, 19, 0.75)"

HERO_GRADIENT = (
    "linear-gradient(90deg, rgba(14,15,19,0.95) 0%, rgba(14,15,19,0.70) 40%, rgba(14,15,19,0) 75%), "
    "linear-gradient(0deg, #0E0F13 0%, rgba(14,15,19,0) 30%)"
)

FONT_FAMILY = 'Pretendard, "Apple SD Gothic Neo", "Noto Sans KR", sans-serif'

SECTION_GAP = "48px"
# Reflex 반응형 리스트: [기본, 30em~, 48em(768px)~]
PAGE_PADDING_X = ["16px", "16px", "48px"]
CARD_WIDTH = ["120px", "120px", "160px"]

POSTER_RATIO = "2 / 3"
POSTER_RADIUS = "8px"

ONE_LINE = {"white_space": "nowrap", "overflow": "hidden", "text_overflow": "ellipsis"}
THREE_LINES = {"display": "-webkit-box", "-webkit-line-clamp": "3", "-webkit-box-orient": "vertical", "overflow": "hidden"}

CARD_HOVER = {
    "transition": "transform 0.15s ease, box-shadow 0.15s ease",
    "border_radius": POSTER_RADIUS,
    "_hover": {"transform": "scale(1.04)", "box_shadow": f"0 0 0 2px {ACCENT}"},
}
