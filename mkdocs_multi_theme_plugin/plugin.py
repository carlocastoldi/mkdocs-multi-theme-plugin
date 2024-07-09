import fnmatch
import jinja2
import os
import mkdocs.utils

from mkdocs.config import base, config_options as c
from mkdocs.plugins import BasePlugin, get_plugin_logger
from mkdocs.structure.files import File, Files
from mkdocs.structure.pages import Page
from mkdocs.theme import Theme

PLUGIN_NAME = "multi-theme" # same as defined in pyproject.toml

log = get_plugin_logger(__name__)

class _AdditionalTheme(base.Config):
    pages = c.ListOfItems(c.Type(str), default=[])
    theme = c.Theme()

class MultiThemePluginConfig(base.Config):
    additional_themes = c.ListOfItems(c.SubConfig(_AdditionalTheme), default={})

class MultiThemePlugin(BasePlugin[MultiThemePluginConfig]):
    global_theme: Theme

    def on_files(self, files: Files, config: base.Config):
        def filter(path: str, theme):
            # '.*' filters dot files/dirs at root level whereas '*/.*' filters nested levels
            patterns = ['.*', '*/.*', '*.py', '*.pyc', '*.html', '*readme*', 'mkdocs_theme.yml']
            # Exclude translation files
            patterns.append("locales/*")
            patterns.extend(f'*{x}' for x in mkdocs.utils.markdown_extensions)
            patterns.extend(theme.static_templates)
            for pattern in patterns:
                if fnmatch.fnmatch(path.lower(), pattern):
                    return False
            return True

        self.global_theme = config.theme
        for additional_themes in self.config.additional_themes:
            theme = additional_themes.theme
            path_names = jinja2.FileSystemLoader(theme.dirs).list_templates()
            path_names = [path for path in path_names if filter(path, theme)]

            for path in path_names:
                if files.get_file_from_path(path) is None:
                    for dir in theme.dirs:
                        # Find the first theme dir which contains path
                        if os.path.isfile(os.path.join(dir, path)):
                            # dst = os.path.join(config.site_dir, theme.name)
                            dst = config.site_dir
                            files.append(File(path, dir, dst, config.use_directory_urls))
                            break
        return files

    def on_page_context(self, context: dict, page: Page, config, nav, **kwargs) -> str:
        for additional_theme in self.config.additional_themes:
            if page.file.src_uri in [page for page in additional_theme.pages]:
                config.theme = additional_theme.theme
                context["config"] = config
                return context
        return context

    def on_post_page(self, output: str, page: Page, config: base.Config) -> str:
        # if on_files() moves the file to a different destination, we should change
        # the references of the theme to point to the new location
        config.theme = self.global_theme # revert back to config's original theme
        return output