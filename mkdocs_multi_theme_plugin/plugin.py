from mkdocs.plugins import BasePlugin
from mkdocs.config import base, config_options as c
from mkdocs import theme

class _PageConfig(base.Config):
    title = c.Type(str)
    config = c.SubConfig(base.BaseConfigOption[theme.Theme])

class MultiThemePluginConfig(base.Config):
    custom_pages = c.ListOfItems(c.SubConfig(_PageConfig, default=[]))

class MultiThemePlugin(BasePlugin[MultiThemePluginConfig]):
    def on_page_content(self, html, **kwargs) -> str:
        """Modify page content by prepending `title` config value."""
        return f"{self.config.title} {html}"