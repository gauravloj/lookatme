# write class that extends MardownRenderer from mistune library

import copy
import re
import urwid
from textwrap import indent

import lookatme.render.pygments as pygments_render
import lookatme.config as config
import lookatme.utils as utils
from lookatme.utils import pile_or_listbox_add
from lookatme.contrib import contrib_first
from lookatme.tutorial import tutor
from lookatme.widgets.clickable_text import ClickableText, LinkIndicatorSpec

def _get_widget_text(textwidget):
    if isinstance(textwidget, ClickableText):
        return textwidget.attrib, textwidget.text
    return textwidget

class TuiRenderer(object):
    """A renderer to re-format Markdown text."""
    NAME = 'tuirenderer'

    def __init__(self, loop):
        self.__methods = {}
        self.loop = loop
        self._log = config.get_log().getChild("RENDER")
        self.localized_state = dict()


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

    def render_token(self, token, stack):
        func = self._get_method(token['type'])
        return func(token, stack)

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
    def render_tokens(self, tokens):
        tmp_listbox = urwid.ListBox([])
        stack = [tmp_listbox]
        for token in tokens:
            self._log.debug(f"{'  '*len(stack)}Rendering token {token}")

            last_stack = stack[-1]
            last_stack_len = len(stack)

            res = self.render_token(token, stack)
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

    def render_children(self, token, stack):
        children = token['children']
        return self.render_tokens(children)
    
    @tutor(
        "markdown",
        "tables",
        r"""
        Rows in tables are defined by separating columns with `|` characters. The
        header row is the first row defined and is separated by hypens (`---`).

        Alignment within a column can be set by adding a colon, `:`, to the left,
        right, or both ends of a header's separator.

        <TUTOR:EXAMPLE>
        | left align | centered | right align |
        |------------|:--------:|------------:|
        | 1          |     a    |           A |
        | 11         |    aa    |          AA |
        | 111        |    aaa   |         AAA |
        | 1111       |   aaaaa  |        AAAA |
        </TUTOR:EXAMPLE>

        ## Style

        Tables can be styled with slide metadata. This is the default style:

        <TUTOR:STYLE>table</TUTOR:STYLE>
        """,
    )
    @contrib_first
    def table(self, token, stack):
        """Renders a table using the :any:`Table` widget.

        See :any:`lookatme.tui.SlideRenderer.do_render` for argument and return
        value descriptions.

        The table widget makes use of the styles below:

        .. code-block:: yaml

            table:
            column_spacing: 3
            header_divider: "─"

        :returns: A list of urwid Widgets or a single urwid Widget
        """
        return [ClickableText("rendered table")]

    def render_table_bak(self, text):
        return '<table>\n' + text + '</table>\n'


    def render_table_head(renderer, text):
        return '<thead>\n<tr>\n' + text + '</tr>\n</thead>\n'


    def render_table_body(renderer, text):
        return '<tbody>\n' + text + '</tbody>\n'


    def render_table_row(renderer, text):
        return '<tr>\n' + text + '</tr>\n'


    def render_table_cell(renderer, text, align=None, head=False):
        if head:
            tag = 'th'
        else:
            tag = 'td'

        html = '  <' + tag
        if align:
            html += ' style="text-align:' + align + '"'

        return html + '>' + text + '</' + tag + '>\n'


    def text(self, token, stack) -> str:
        text = token['raw']

        headingstyle = self.localized_state.get("headings", {}).get("style", None)
        if headingstyle is not None:
            text = utils.styled_text(text, headingstyle)

        return [ClickableText(text)]

    def _add_effect(self, token, stack, addeffect):
        oldstyle = self.localized_state.get("oldstyle", {
            'fg': '',
            'bg': '',
        })
        oldfg = oldstyle['fg']
        oldbg = oldstyle['bg']
        if len(oldfg) > 0:
            oldfg += f',{addeffect}'
        else:
            oldfg = f'default,{addeffect}'
        if len(oldbg) == 0:
            oldbg = f'default'

        self.localized_state["oldstyle"] = {
            'fg': oldfg,
            'bg': oldbg,
        }
        text = self.render_children(token, stack)
        self.localized_state["oldstyle"] = oldstyle
        attrspec, _ = utils.styled_text(text, addeffect, oldstyle)
        return [ClickableText((attrspec, text[0].text))]
    
    def emphasis(self, token, stack) -> str:
        return self._add_effect(token, stack, 'italics')
    
    def strong(self, token, stack) -> str:
        return self._add_effect(token, stack, "underline")

    @tutor(
        "markdown",
        "strikethrough",
        r"""
        <TUTOR:EXAMPLE>
        I lost my ~~mind~~ keyboard and couldn't type anymore.
        </TUTOR:EXAMPLE>
        """
    )
    @contrib_first
    def strikethrough(self, token, stack):
        """Renders strikethrough text (``~~text~~``)

        :returns: list of `urwid Text markup <http://urwid.org/manual/displayattributes.html#text-markup>`_
            tuples.
        """
        return self._add_effect(token, stack, "strikethrough")
    
    @tutor(
        "markdown",
        "links",
        r"""
        Links are inline elements in markdown and have the form `[text](link)`

        <TUTOR:EXAMPLE>
        [lookatme on GitHub](https://github.com/d0c-s4vage/lookatme)
        </TUTOR:EXAMPLE>

        ## Style

        Links can be styled with slide metadata. This is the default style:

        <TUTOR:STYLE>link</TUTOR:STYLE>
        """
    )
    @contrib_first
    # def link(link_uri, title, link_text):
    def link(self, token, stack):
        """Renders a link. This function does a few special things to make the
        clickable links happen. All text in lookatme is rendered using the
        :any:`ClickableText` class. The ``ClickableText`` class looks for
        ``urwid.AttrSpec`` instances that are actually ``LinkIndicatorSpec`` instances
        within the Text markup. If an AttrSpec is an instance of ``LinkIndicator``
        spec in the Text markup, ClickableText knows to handle clicks on that
        section of the text as a link.

        :returns: list of `urwid Text markup <http://urwid.org/manual/displayattributes.html#text-markup>`_
            tuples.
        """
        raw_link_text = []
        for x in token['children']:
            raw_link_text.append(x['raw'])
        raw_link_text = "".join(raw_link_text)

        label = token.get('label')
        spec, text = utils.styled_text(
            [raw_link_text], utils.spec_from_style(config.get_style()["link"]))
        toreturn = [ClickableText((spec, text))]
        if label:
            spec, text = utils.styled_text(
                [label], utils.spec_from_style(config.get_style()["link"]))
            return toreturn + [ClickableText([(spec, text)])]

        attrs = token['attrs']
        link_uri = attrs['url']
        # title = attrs.get('title')
        
        spec = LinkIndicatorSpec(raw_link_text, link_uri, spec)
        return [ClickableText((spec, text))]


    def render_image(self, token) -> str:
        return '!' + self.link(token)

    def codespan(self, token, stack) -> str:
        text = pygments_render.render_text(" " + token['raw'] + " ", plain=True)
        return [ClickableText(text)]

    def linebreak(self, token, stack) -> str:
        return [urwid.Divider()]

    def softbreak(self, token, stack) -> str:
        return [urwid.Divider()]

    def blank_line(self, token, stack) -> str:
        return [urwid.Divider(), urwid.Divider()]

    def render_inline_html(self, token, stack) -> str:
        return [token['raw']]

    def paragraph(self, token, stack) -> str:
        text = self.render_children(token, stack)
        return [urwid.Divider()] + text + [urwid.Divider()]



    @tutor(
        "markdown",
        "headings",
        r"""
        Headings are specified by prefixing text with `#` characters:

        <TUTOR:EXAMPLE>
        ## Heading Level 2
        ### Heading Level 3
        #### Heading Level 4
        ##### Heading Level 5
        </TUTOR:EXAMPLE>

        ## Style

        Headings can be styled with slide metadata. This is the default style:

        <TUTOR:STYLE>headings</TUTOR:STYLE>
        """,
    )
    @contrib_first
    def heading(self, token, stack) -> str:
        """Render markdown headings, using the defined styles for the styling and
        prefix/suffix.

        See :any:`lookatme.tui.SlideRenderer.do_render` for argument and return
        value descriptions.

        Below are the default stylings for headings:

        .. code-block:: yaml

            headings:
            '1':
                bg: default
                fg: '#9fc,bold'
                prefix: "██ "
                suffix: ""
            '2':
                bg: default
                fg: '#1cc,bold'
                prefix: "▓▓▓ "
                suffix: ""
            '3':
                bg: default
                fg: '#29c,bold'
                prefix: "▒▒▒▒ "
                suffix: ""
            '4':
                bg: default
                fg: '#66a,bold'
                prefix: "░░░░░ "
                suffix: ""
            default:
                bg: default
                fg: '#579,bold'
                prefix: "░░░░░ "
                suffix: ""

        :returns: A list of urwid Widgets or a single urwid Widget
        """
        headings = config.get_style()["headings"]
        level = token['attrs']['level']
        style = config.get_style()["headings"].get(str(level), headings["default"])

        prefix = utils.styled_text(style["prefix"], style)
        suffix = utils.styled_text(style["suffix"], style)

        self.localized_state["headings"] = {
            'style': style,
        }

        rendered = self.render_children(token, stack)
        
        self.localized_state["headings"] = dict()

        raw_text = list(map(_get_widget_text, rendered))

        return [
            urwid.Divider(),
            ClickableText(
                # [prefix] + utils.styled_text(rendered, style) + [suffix]),  # type: ignore
                [prefix] + raw_text + [suffix]),  # type: ignore
            urwid.Divider(),
        ]
    
    @contrib_first
    def thematic_break(self, token, stack):
        """Render a newline

        See :any:`lookatme.tui.SlideRenderer.do_render` for argument and return
        value descriptions.
        """
        hrule_conf = config.get_style()["hrule"]
        div = urwid.Divider(hrule_conf['char'], top=1, bottom=1)
        return [urwid.Pile([urwid.AttrMap(div, utils.spec_from_style(hrule_conf['style']))])]

    def render_block_text(self, token, stack) -> str:
        return self.render_children(token, stack) + '\n'

    def block_code(self, token, stack) -> str:
        """Renders a code block using the Pygments library.

        See :any:`lookatme.tui.SlideRenderer.do_render` for additional argument and
        return value descriptions.
        """
        attrs = token.get('attrs', {})
        lang = attrs.get('info', 'text')
        code = token['raw']
        res = pygments_render.render_text(code, lang=lang)

        return [
            urwid.Divider(),
            res,
            urwid.Divider()
        ]

    def block_quote(self, token, stack) -> str:
        # text = indent(self.render_children(token, stack), '> ')
        # return text + '\n\n'
        """Begins rendering of a block quote. Pushes a new ``urwid.Pile()`` to the
        stack that is indented, has styling applied, and has the quote markers
        on the left.

        This function makes use of the styles:

        .. code-block:: yaml

            quote:
            top_corner: "┌"
            bottom_corner: "└"
            side: "╎"
            style:
                bg: default
                fg: italics,#aaa

        See :any:`lookatme.tui.SlideRenderer.do_render` for additional argument and
        return value descriptions.
        """
        pile = urwid.Pile([])

        styles = config.get_style()["quote"]

        quote_side = styles["side"]
        quote_top_corner = styles["top_corner"]
        quote_bottom_corner = styles["bottom_corner"]
        quote_style = styles["style"]

        res = self.render_children(token, stack)

        pile_or_listbox_add(pile, res)

        toreturn = [
            urwid.Divider(),
            urwid.LineBox(
                urwid.AttrMap(
                    urwid.Padding(pile, left=2),
                    utils.spec_from_style(quote_style),
                ),
                lline=quote_side, rline="",
                tline=" ", trcorner="", tlcorner=quote_top_corner,
                bline=" ", brcorner="", blcorner=quote_bottom_corner,
            ),
            urwid.Divider(),
        ]

        return toreturn        

    def render_block_html(self, token, stack) -> str:
        return token['raw'] + '\n\n'

    def render_block_error(self, token, stack) -> str:
        return ''
        


    # def list(self, token) -> str:
    #     return render_list(self, token)
    