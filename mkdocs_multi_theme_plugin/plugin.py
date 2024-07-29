import fnmatch
import jinja2
import os
import mkdocs.commands
import mkdocs.commands.build
import mkdocs.utils

from mkdocs.config import base, config_options as c, defaults
from mkdocs.plugins import BasePlugin, CombinedEvent, get_plugin_logger, event_priority
from mkdocs.structure.files import File, Files
from mkdocs.structure.nav import Navigation
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
    envs: dict[str,jinja2.Environment]
    global_theme: Theme
    nav: Navigation

    @event_priority(100)
    def _on_config_pre_plugins(self, config: defaults.MkDocsConfig) -> defaults.MkDocsConfig | None:
        self.envs = {additional_theme.theme.name: additional_theme.theme.get_env() for additional_theme in self.config.additional_themes}
        self.global_theme = config.theme
        if "mkdocstrings" in config.plugins:
            config.theme.name = "material" # requires the plugins using this property to fallback to a default theme
        return config

    @event_priority(-100)
    def _on_config_post_plugins(self, config: defaults.MkDocsConfig) -> defaults.MkDocsConfig | None:
        if "mkdocstrings" in config.plugins:
            config.theme.name = self.global_theme.name
        return config

    on_config = CombinedEvent(_on_config_pre_plugins, _on_config_post_plugins)

    def on_nav(self, nav: Navigation, config: defaults.MkDocsConfig, files: Files):
        self.nav = nav
        return self.nav

    def on_env(self, env: jinja2.Environment, config: defaults.MkDocsConfig, files: Files):
        # builds the static files for each of the additional theme.
        # if some resulting files are colliding, the global theme has the precedence

        log.debug("Copying static assets.")

        for additional_theme in self.config.additional_themes:
            for template in additional_theme.theme.static_templates:
                mkdocs.commands.build._build_theme_template(template, env, files, config, self.nav)
        return env

    def on_files(self, files: Files, config: defaults.MkDocsConfig):
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

    def on_page_context(self, context: dict, page: Page, config: defaults.MkDocsConfig, nav: Navigation, **kwargs) -> str:
        for additional_theme in self.config.additional_themes:
            if page.file.src_uri in [page for page in additional_theme.pages]:
                config.theme = additional_theme.theme
                context["config"] = config
                return context
        return context

    def on_page_template(self, template: jinja2.Template, template_file: str, page: Page, config: defaults.MkDocsConfig, nav: Navigation) -> jinja2.Template:
        for additional_theme in self.config.additional_themes:
            if page.file.src_uri in [page for page in additional_theme.pages]:
                return self.envs[additional_theme.theme.name].get_template(template_file)

    def on_post_page(self, output: str, page: Page, config: defaults.MkDocsConfig) -> str:
        # if on_files() moves the file to a different destination, we should change
        # the references of the theme to point to the new location
        config.theme = self.global_theme # revert back to config's original theme
        return output
