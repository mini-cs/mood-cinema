import reflex as rx

config = rx.Config(
    app_name="mood_cinema",
    # 0.10에서는 Radix 테마를 플러그인으로 명시한다 (App(theme=...)과 암묵적 활성화는 deprecated). 쓰지 않는 사이트맵은 끈다
    plugins=[rx.plugins.RadixThemesPlugin(theme=rx.theme(appearance="dark", accent_color="amber", radius="large"))],
    disable_plugins=[rx.plugins.SitemapPlugin],
)
