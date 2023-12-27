# write class that extends MardownRenderer from mistune library

import copy
import re
import urwid
from textwrap import indent

from mistune.renderers.markdown import MarkdownRenderer
from lookatme.utils import pile_or_listbox_add
from lookatme.tutorial import tutor

class MDRenderer(MarkdownRenderer):
    pass

class TuiRenderer(object):
    """A renderer to re-format Markdown text."""
    NAME = 'tuirenderer'

    def __init__(self):
        self.__methods = {}

    def register(self, name: str, method):
        """Register a render method for the named token. For example::

            def render_wiki(renderer, key, title):
                return f'<a href="/wiki/{key}">{title}</a>'

            renderer.register('wiki', render_wiki)
        """
        # bind self into renderer method
        self.__methods[name] = lambda *arg, **kwargs: method(self, *arg, **kwargs)

    def _get_method(self, name):
        try:
            return object.__getattribute__(self, name)
        except AttributeError:
            method = self.__methods.get(name)
            if not method:
                raise AttributeError('No renderer "{!r}"'.format(name))
            return method

    def _propagate_meta(self, item1, item2):
        """Copy the metadata from item1 to item2"""
        meta = getattr(item1, "meta", {})
        existing_meta = getattr(item2, "meta", {})
        new_meta = copy.deepcopy(meta)
        new_meta.update(existing_meta)
        setattr(item2, "meta", new_meta)

    def render_token(self, token, state):
        func = self._get_method(token['type'])
        return func(token, state)

    def iter_tokens(self, tokens, state):
        for tok in tokens:
            yield self.render_token(tok, state)

    @tutor(
        "general",
        "markdown supported features",
        r"""
        Lookatme supports most markdown features.

        |                         Supported | Not (yet) Supported |
        |----------------------------------:|---------------------|
        |                            Tables | Footnotes           |
        |                          Headings | *Images             |
        |                        Paragraphs | Inline HTML         |
        |                      Block quotes |                     |
        |                     Ordered lists |                     |
        |                   Unordered lists |                     |
        | Code blocks & syntax highlighting |                     |
        |                 Inline code spans |                     |
        |                   Double emphasis |                     |
        |                   Single Emphasis |                     |
        |                     Strikethrough |                     |
        |                             Links |                     |

        \*Images may be supported through extensions
        """,
        order=4,
    )
    def render_tokens(self, tokens, state):
        tmp_listbox = urwid.ListBox([])
        stack = [tmp_listbox]
        renderer = TuiRenderer()
        for token in tokens:
            self._log.debug(f"{'  '*len(stack)}Rendering token {token}")

            last_stack = stack[-1]
            last_stack_len = len(stack)

            res = renderer(token, stack[-1], stack, self.loop)
            if len(stack) > last_stack_len:
                self._propagate_meta(last_stack, stack[-1])
            if res is None:
                continue
            pile_or_listbox_add(last_stack, res)

        return tmp_listbox.body

    def __call__(self, tokens):
        out = self.render_tokens(tokens)
        # special handle for line breaks
        # out += '\n\n'.join(self.render_referrences(state)) + '\n'
        return out

    # def render_referrences(self):
    #     ref_links = state.env['ref_links']
    #     for key in ref_links:
    #         attrs = ref_links[key]
    #         text = '[' + attrs['label'] + ']: ' + attrs['url']
    #         title = attrs.get('title')
    #         if title:
    #             text += ' "' + title + '"'
    #         yield text

    def render_children(self, token):
        children = token['children']
        return self.render_tokens(children)

    def text(self, token) -> str:
        return token['raw']

    def emphasis(self, token) -> str:
        return '*' + self.render_children(token) + '*'

    def strong(self, token) -> str:
        return '**' + self.render_children(token) + '**'

    def link(self, token) -> str:
        label = token.get('label')
        text = self.render_children(token)
        out = '[' + text + ']'
        if label:
            return out + '[' + label + ']'

        attrs = token['attrs']
        url = attrs['url']
        title = attrs.get('title')
        if text == url and not title:
            return '<' + text + '>'
        elif 'mailto:' + text == url and not title:
            return '<' + text + '>'

        out += '('
        if '(' in url or ')' in url:
            out += '<' + url + '>'
        else:
            out += url
        if title:
            out += ' "' + title + '"'
        return out + ')'

    def image(self, token) -> str:
        return '!' + self.link(token)

    def codespan(self, token) -> str:
        return '`' + token['raw'] + '`'

    def linebreak(self, token) -> str:
        return '  \n'

    def softbreak(self, token) -> str:
        return '\n'

    def blank_line(self, token) -> str:
        return ''

    def inline_html(self, token) -> str:
        return token['raw']

    def paragraph(self, token) -> str:
        text = self.render_children(token)
        return text + '\n\n'

    def heading(self, token) -> str:
        level = token['attrs']['level']
        marker = '#' * level
        text = self.render_children(token)
        return marker + ' ' + text + '\n\n'

    def thematic_break(self, token) -> str:
        return '***\n\n'

    def block_text(self, token) -> str:
        return self.render_children(token) + '\n'

    def block_code(self, token) -> str:
        attrs = token.get('attrs', {})
        info = attrs.get('info', '')
        code = token['raw']
        if code and code[-1] != '\n':
            code += '\n'

        marker = token.get('marker')
        if not marker:
            marker = _get_fenced_marker(code)
        return marker + info + '\n' + code + marker + '\n\n'

    def block_quote(self, token) -> str:
        text = indent(self.render_children(token), '> ')
        return text + '\n\n'

    def block_html(self, token) -> str:
        return token['raw'] + '\n\n'

    def block_error(self, token) -> str:
        return ''

    # def list(self, token) -> str:
    #     return render_list(self, token)
    

fenced_re = re.compile(r'^[`~]+', re.M)


def _get_fenced_marker(code):
    found = fenced_re.findall(code)
    if not found:
        return '```'

    ticks = []  # `
    waves = []  # ~
    for s in found:
        if s[0] == '`':
            ticks.append(len(s))
        else:
            waves.append(len(s))

    if not ticks:
        return '```'

    if not waves:
        return '~~~'
    return '`' * (max(ticks) + 1)
